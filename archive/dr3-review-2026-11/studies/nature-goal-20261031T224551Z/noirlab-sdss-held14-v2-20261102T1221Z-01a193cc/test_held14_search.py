import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import time
import subprocess
import types
import unittest
from unittest import mock

P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('control_test',P/'held14_search.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class ControlTests(unittest.TestCase):
    def test_strips_proxy_and_ssl_overrides(self):
        self.assertEqual(m.stripped_environment({'HTTPS_PROXY':'secret','sslKEYLOGFILE':'private',
          'SSL_CERT_FILE':'private','SystemRoot':'kept'}),{'SystemRoot':'kept'})

    def test_native_checks_url_hash_status_tls_and_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); raw=d/'x.raw'; hdr=d/'x.headers'
            raw.write_bytes(b'abc'); hdr.write_bytes(b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\n\r\n')
            rec={'status':'HTTP_COMPLETE_UNPARSED','returncode':0,'http_status':200,
                 'ssl_verify_result':0,'num_redirects':0,'effective_url':m.URL,
                 'cleanup_status':'EXIT_CONFIRMED','raw_sha256':m.sha(raw),'headers_sha256':m.sha(hdr)}
            u=types.SimpleNamespace(valid_http_headers=lambda h,s,n:h.endswith(b'\r\n\r\n') and s==200 and n==3)
            self.assertTrue(m.valid_native(rec,raw,hdr,u))
            for key,val in [('effective_url','https://example.invalid/'),('http_status',503),
                            ('ssl_verify_result',1),('num_redirects',1),('raw_sha256','bad'),
                            ('cleanup_status','EXIT_UNCONFIRMED')]:
                self.assertFalse(m.valid_native({**rec,key:val},raw,hdr,u),key)
            hdr.write_bytes(b'broken'); self.assertFalse(m.valid_native(rec,raw,hdr,u))

    def setup_fake(self,mode,competing=False,fail_result_save=False):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        root=Path(temp.name); d=root/'study'; c=root/'coordination'; d.mkdir(); c.mkdir()
        lock=c/'legacy-control-acquisition.lock'; mutation=c/'mutation.lock'; coord=c/'session.json'; custody=c/'custody.json'
        fake_curl=root/'curl.exe'; fake_curl.write_bytes(b'fixture curl')
        custody.write_text('{"owner":"fixture"}',encoding='utf-8')
        coord.write_text(json.dumps({'session':m.SESSION,'in_progress_directory':None,
                                     'active_owned_scientific_processes':[]}),encoding='utf-8')
        if competing: (c/'other.lock').write_text('owned',encoding='utf-8')
        memory={'calls':0}
        def bind(_lock,_token,_out,_name,proc,ownership):
            ownership['pid']=proc.pid
            if mode=='bind_failure': raise RuntimeError('bind failed after PID')
            ownership['identity']={'pid':proc.pid,'identity_status':'SYNTHETIC'}
        util=types.SimpleNamespace(bind_owned_pid=bind,valid_http_headers=lambda h,s,n:True)
        def fetch(out,req,name,deadline,owner_callback):
            memory['calls']+=1; memory['url']=req['url']
            if mode=='custody_drift': custody.write_text('{"changed":true}',encoding='utf-8')
            if mode=='late_other_lock': (c/'late-other.lock').write_text('owned',encoding='utf-8')
            if mode=='before_callback': raise RuntimeError('before callback')
            if mode=='not_started': return {'status':'FAILED_VISIBLE','cleanup_status':'NOT_STARTED','owned_pid':None}
            owner_callback(types.SimpleNamespace(pid=4321))
            if mode=='after_callback': raise RuntimeError('after callback')
            raw=out/(name+'.raw'); hdr=out/(name+'.headers')
            raw.write_bytes(b'abc'); hdr.write_bytes(b'HTTP/1.1 200 OK\r\n\r\n')
            return {'status':'HTTP_COMPLETE_UNPARSED','returncode':0,'http_status':200,
              'ssl_verify_result':0,'num_redirects':0,'effective_url':m.URL,
              'cleanup_status':'EXIT_CONFIRMED' if mode in ('good','custody_drift','late_other_lock') else 'EXIT_UNCONFIRMED',
              'raw_bytes':3,'raw_sha256':m.sha(raw),'headers_sha256':m.sha(hdr),'owned_pid':4321}
        tr=types.SimpleNamespace(LIMITS={},REQUEST_URLS={},fetch=fetch,sha=None)
        def load(name,path,source):return util if name=='prior_capture_util' else tr
        real_save=m.save
        def save(path,obj):
            if fail_result_save and path.name=='RESULT.json': raise OSError('synthetic terminal save failure')
            return real_save(path,obj)
        patches=[mock.patch.object(m,'D',d),mock.patch.object(m,'C',c),mock.patch.object(m,'LOCK',lock),
                 mock.patch.object(m,'MUTATION',mutation),mock.patch.object(m,'COORD',coord),
                 mock.patch.object(m,'CUSTODY',custody),mock.patch.object(m,'CUSTODY_SHA',m.sha(custody)),
                 mock.patch.object(m,'CURL',str(fake_curl)),
                 mock.patch.object(m,'validate',return_value=({'protocol_sha256':'x','curl_sha256':m.sha(fake_curl)},'curl fixture',
                     {'ownership_utils_sha256':b'fixture','transport_sha256':b'fixture'})),
                 mock.patch.object(m,'module',side_effect=load),mock.patch.object(m,'save',side_effect=save)]
        stack=contextlib.ExitStack(); self.addCleanup(stack.close)
        for patch in patches: stack.enter_context(patch)
        stack.enter_context(mock.patch.dict(m.os.environ,{'HTTPS_PROXY':'private'},clear=False))
        output=stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        return d,c,lock,coord,memory,output

    def test_success_has_durable_terminal_before_release(self):
        d,c,lock,coord,mem,output=self.setup_fake('good')
        self.assertEqual(m.execute('f'*64),0)
        r=json.loads((d/'capture'/'RESULT.json').read_text()); end=json.loads((d/'capture'/'FINISH.json').read_text())
        self.assertEqual(r['requests_attempted'],1); self.assertTrue(r['target_curl_start_observed'])
        self.assertEqual(end['terminal_sha256'],m.sha(d/'capture'/'RESULT.json'))
        self.assertFalse(lock.exists()); self.assertTrue(end['lease_released']); self.assertEqual(mem['url'],m.URL)
        self.assertIsNone(json.loads(coord.read_text())['in_progress_directory']); self.assertNotIn('abc',output.getvalue())

    def test_unconfirmed_exit_retains_pid_and_lease(self):
        d,c,lock,coord,_,_=self.setup_fake('unconfirmed'); self.assertEqual(m.execute('f'*64),1)
        lease=json.loads(lock.read_text()); r=json.loads((d/'capture'/'RESULT.json').read_text())
        self.assertEqual(lease['last_owned_pid'],4321); self.assertEqual(r['last_owned_pid'],4321)
        self.assertFalse(r['owned_process_exit_confirmed']); self.assertIsNotNone(json.loads(coord.read_text())['in_progress_directory'])

    def test_exception_after_recording_pid_preserves_it(self):
        d,c,lock,coord,_,_=self.setup_fake('bind_failure'); self.assertEqual(m.execute('f'*64),1)
        self.assertEqual(json.loads(lock.read_text())['last_owned_pid'],4321)
        self.assertEqual(json.loads((d/'capture'/'RESULT.json').read_text())['requests_attempted'],1)

    def test_exception_before_callback_is_unknown_not_zero(self):
        d,c,lock,coord,_,_=self.setup_fake('before_callback'); self.assertEqual(m.execute('f'*64),1)
        r=json.loads((d/'capture'/'RESULT.json').read_text())
        self.assertTrue(r['fetch_invoked']); self.assertIsNone(r['requests_attempted']); self.assertTrue(lock.exists())

    def test_competing_lease_stops_before_fetch(self):
        d,c,lock,coord,mem,_=self.setup_fake('good',competing=True); self.assertEqual(m.execute('f'*64),1)
        r=json.loads((d/'capture'/'RESULT.json').read_text())
        self.assertEqual(mem['calls'],0); self.assertEqual(r['requests_attempted'],0); self.assertFalse(lock.exists())
        self.assertTrue((c/'other.lock').exists())

    def test_failed_terminal_save_retains_lease(self):
        d,c,lock,coord,mem,_=self.setup_fake('good',fail_result_save=True)
        with self.assertRaises(OSError): m.execute('f'*64)
        self.assertTrue(lock.exists()); self.assertIsNotNone(json.loads(coord.read_text())['in_progress_directory'])

    def test_custody_drift_retains_lease_after_durable_terminal(self):
        d,c,lock,coord,_,_=self.setup_fake('custody_drift'); self.assertEqual(m.execute('f'*64),1)
        self.assertTrue(lock.exists()); self.assertTrue((d/'capture'/'RESULT.json').is_file())
        self.assertEqual(json.loads((d/'capture'/'FINISH.json').read_text())['finish_error_type'],'ValueError')

    def test_other_lease_appearing_before_finish_retains_own_lease(self):
        d,c,lock,coord,_,_=self.setup_fake('late_other_lock'); self.assertEqual(m.execute('f'*64),1)
        self.assertTrue(lock.exists()); self.assertTrue((c/'late-other.lock').exists())
        self.assertIsNotNone(json.loads(coord.read_text())['in_progress_directory'])

    def test_mutation_owner_recheck_prevents_shared_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); mutation=root/'mutation.lock'; target=root/'shared.json'
            mutation.write_text(json.dumps({'owner_token':'other'})); target.write_text('old')
            with mock.patch.object(m,'MUTATION',mutation):
                with self.assertRaises(RuntimeError): m.atomic_json(target,{'new':True},'tmp','mine')
            self.assertEqual(target.read_text(),'old')
            self.assertEqual(json.loads(mutation.read_text())['owner_token'],'other')

    def test_native_not_started_is_safe_without_claiming_observed_exit(self):
        d,c,lock,coord,_,_=self.setup_fake('not_started'); self.assertEqual(m.execute('f'*64),1)
        r=json.loads((d/'capture'/'RESULT.json').read_text())
        end=json.loads((d/'capture'/'FINISH.json').read_text())
        self.assertFalse(lock.exists()); self.assertEqual(r['requests_attempted'],0)
        self.assertEqual(r['cleanup_status'],'NOT_STARTED'); self.assertTrue(r['safe_to_release'])
        self.assertFalse(r['owned_process_exit_confirmed']); self.assertFalse(end['owned_process_exit_confirmed'])

    def test_real_native_helper_cleans_owned_child_after_callback_failure(self):
        native=m.module('native_for_test',m.TRANSPORT,m.TRANSPORT.read_bytes())
        class FakeProc:
            pid=6789
            returncode=None
            def poll(self): return self.returncode
            def kill(self): self.returncode=-9
            def wait(self,timeout): return self.returncode
        proc=FakeProc(); url='https://example.invalid/fixture'
        def bad_owner(_proc): raise RuntimeError('synthetic callback failure')
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(native.REQUEST_URLS, {'fixture':url}, clear=True), \
                 mock.patch.object(native.subprocess,'Popen',return_value=proc):
                rec=native.fetch(Path(tmp),{'url':url,'method':'GET'},'fixture',
                                 time.perf_counter_ns()+10_000_000_000,owner_callback=bad_owner)
        self.assertEqual(rec['owned_pid'],6789); self.assertEqual(rec['cleanup_status'],'EXIT_CONFIRMED')
        self.assertEqual(proc.returncode,-9)

    def test_real_native_helper_defers_hash_if_exit_unconfirmed(self):
        native=m.module('native_for_test2',m.TRANSPORT,m.TRANSPORT.read_bytes())
        class StillRunning:
            pid=9876
            returncode=None
            def poll(self): return None
            def kill(self): pass
            def wait(self,timeout): raise subprocess.TimeoutExpired('fixture',timeout)
        url='https://example.invalid/fixture'
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            def fake_popen(command,stdout,stderr,shell):
                (out/'fixture.raw').write_bytes(b'xx'); return StillRunning()
            with mock.patch.dict(native.REQUEST_URLS, {'fixture':url}, clear=True), \
                 mock.patch.dict(native.LIMITS, {'body_bytes':1}, clear=False), \
                 mock.patch.object(native.subprocess,'Popen',side_effect=fake_popen):
                rec=native.fetch(out,{'url':url,'method':'GET'},'fixture',time.perf_counter_ns()+10_000_000_000)
        self.assertEqual(rec['cleanup_status'],'EXIT_UNCONFIRMED')
        self.assertEqual(rec['native_file_hashes'],'DEFERRED_UNTIL_EXIT_CONFIRMED')
        self.assertNotIn('raw_sha256',rec)

    def test_schema_prerequisite_rejects_changed_key_type(self):
        c=m.SCHEMA
        paths={'schema_inventory_sha256':c/'SCHEMA_INVENTORY_V3.json','schema_result_sha256':c/'capture/RESULT.json',
               'schema_finish_sha256':c/'capture/FINISH.json'}
        frozen={k:p.read_bytes() for k,p in paths.items()}
        inv0=json.loads(frozen['schema_inventory_sha256'])
        manifest={'schema_raw_sha256':m.sha(c/'capture/schema_probe.raw'),
                  **{'schema_'+k+'_sha256':inv0['evidence_pins'][k] for k in ('query','protocol','request','native')}}
        m.verify_schema_prerequisites(manifest,frozen)
        bad=dict(frozen); inv=json.loads(bad['schema_inventory_sha256'])
        row=next(r for r in inv['result']['rows'] if r['column_name']=='id2')
        row['datatype']='adql:DOUBLE';bad['schema_inventory_sha256']=json.dumps(inv).encode()
        with self.assertRaises(ValueError):m.verify_schema_prerequisites(manifest,bad)
        for key in ('query','protocol','request','native'):
            bad_manifest=dict(manifest);bad_manifest['schema_'+key+'_sha256']='0'*64
            with self.assertRaises(ValueError):m.verify_schema_prerequisites(bad_manifest,frozen)

    def test_missing_and_changed_schema_chain_files_stop_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); c=m.SCHEMA
            for n in ('held14_search.py','PROTOCOL.md','QUERY.adql','test_held14_search.py'):
                (d/n).write_bytes((P/n).read_bytes())
            paths={'script_sha256':d/'held14_search.py','protocol_sha256':d/'PROTOCOL.md',
                'test_sha256':d/'test_held14_search.py','query_sha256':d/'QUERY.adql',
                'transport_sha256':m.TRANSPORT,'ownership_utils_sha256':m.UTILS,'curl_sha256':Path(m.CURL),
                'schema_raw_sha256':c/'capture/schema_probe.raw','schema_inventory_sha256':c/'SCHEMA_INVENTORY_V3.json',
                'schema_result_sha256':c/'capture/RESULT.json','schema_finish_sha256':c/'capture/FINISH.json',
                'schema_science_sha256':c/'INDEPENDENT_SCIENCE_SCHEMA_REVIEW.md',
                'schema_execution_sha256':c/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md',
                'schema_parser_review_sha256':c/'INDEPENDENT_PARSER_REVIEW.md','schema_parser_sha256':c/'parse_schema_v3.py',
                'schema_parser_test_sha256':c/'test_parse_schema_v3.py','schema_query_sha256':c/'QUERY.adql',
                'schema_protocol_sha256':c/'PROTOCOL.md','schema_request_sha256':c/'capture/schema_probe.request.json',
                'schema_native_sha256':c/'capture/schema_probe.json'}
            a=m.POSITIVE
            paths.update({'positive_raw_sha256':a/'capture/spec_positive.raw','positive_query_sha256':a/'QUERY.adql',
                'positive_protocol_sha256':a/'PROTOCOL.md','positive_request_sha256':a/'capture/spec_positive.request.json',
                'positive_native_sha256':a/'capture/spec_positive.json','positive_result_sha256':a/'capture/RESULT.json',
                'positive_finish_sha256':a/'capture/FINISH.json','positive_inventory_sha256':a/'POSITIVE_CONTROL_V2.json',
                'positive_parser_sha256':a/'parse_positive_v2.py','positive_parser_test_sha256':a/'test_parse_positive_v2.py',
                'positive_science_sha256':a/'INDEPENDENT_SCIENCE_CONTROL_REVIEW.md',
                'positive_execution_sha256':a/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md',
                'positive_parser_review_sha256':a/'INDEPENDENT_PARSER_REVIEW.md'})
            e=m.EMPTY
            paths.update({'empty_raw_sha256':e/'capture/spec_empty.raw','empty_query_sha256':e/'QUERY.adql',
              'empty_protocol_sha256':e/'PROTOCOL.md','empty_request_sha256':e/'capture/spec_empty.request.json',
              'empty_native_sha256':e/'capture/spec_empty.json','empty_result_sha256':e/'capture/RESULT.json',
              'empty_finish_sha256':e/'capture/FINISH.json','empty_inventory_sha256':e/'EMPTY_CONTROL.json',
              'empty_parser_sha256':e/'parse_empty.py','empty_parser_test_sha256':e/'test_parse_empty.py',
              'empty_science_sha256':e/'INDEPENDENT_SCIENCE_CONTROL_REVIEW.md',
              'empty_execution_sha256':e/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md',
              'empty_parser_review_sha256':e/'INDEPENDENT_PARSER_REVIEW.md',
              'gaia_rows_sha256':m.GAIA,'held_objects_sha256':m.HELD})
            z=m.SHAPE
            paths.update({'shape_raw_sha256':z/'capture/shape_control.raw','shape_query_sha256':z/'QUERY.adql',
             'shape_protocol_sha256':z/'PROTOCOL.md','shape_request_sha256':z/'capture/shape_control.request.json',
             'shape_native_sha256':z/'capture/shape_control.json','shape_result_sha256':z/'capture/RESULT.json',
             'shape_finish_sha256':z/'capture/FINISH.json','shape_inventory_sha256':z/'SHAPE_CONTROL.json',
             'shape_parser_sha256':z/'parse_shape.py','shape_parser_test_sha256':z/'test_parse_shape_v2.py',
             'shape_science_sha256':z/'INDEPENDENT_SCIENCE_CONTROL_REVIEW.md',
             'shape_execution_sha256':z/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md',
             'shape_parser_review_sha256':z/'INDEPENDENT_PARSER_REVIEW.md'})
            manifest={k:m.sha(v) for k,v in paths.items()};mf=d/'MANIFEST.json';mf.write_text(json.dumps(manifest),encoding='utf8')
            expected=m.sha(mf); real_read=Path.read_bytes
            with mock.patch.object(m,'D',d),mock.patch.object(m,'MANIFEST',mf), \
                 mock.patch.object(m.subprocess,'run',return_value=types.SimpleNamespace(stdout=b'curl 8.22.0 fixture\n')):
                m.validate(expected)
                for key in ('schema_query_sha256','schema_protocol_sha256','schema_request_sha256','schema_native_sha256',
                            'positive_query_sha256','positive_protocol_sha256','positive_request_sha256','positive_native_sha256',
                            'empty_query_sha256','empty_protocol_sha256','empty_request_sha256','empty_native_sha256',
                            'shape_query_sha256','shape_protocol_sha256','shape_request_sha256','shape_native_sha256'):
                    target=paths[key]
                    for mode in ('missing','changed'):
                        def altered(path, target=target, mode=mode):
                            if path==target:
                                if mode=='missing':raise FileNotFoundError('fixture')
                                return real_read(path)+b'x'
                            return real_read(path)
                        with mock.patch.object(Path,'read_bytes',new=altered):
                            with self.assertRaises((FileNotFoundError,ValueError)):m.validate(expected)

    def test_positive_gate_requires_same_join_and_published_tuple(self):
        a=m.POSITIVE
        paths={'positive_inventory_sha256':a/'POSITIVE_CONTROL_V2.json','positive_result_sha256':a/'capture/RESULT.json',
               'positive_finish_sha256':a/'capture/FINISH.json','positive_query_sha256':a/'QUERY.adql'}
        frozen={k:p.read_bytes() for k,p in paths.items()}
        inv=json.loads(frozen['positive_inventory_sha256'])
        manifest={'positive_'+k+'_sha256':v for k,v in inv['evidence_pins'].items()}
        q=(m.EMPTY/'QUERY.adql').read_text(encoding='utf-8-sig').strip()
        m.verify_positive_prerequisites(manifest,frozen,q)
        with self.assertRaises(ValueError):m.verify_positive_prerequisites(manifest,frozen,q.replace(' AND x.id2=0',''))
        bad=dict(frozen); data=json.loads(bad['positive_inventory_sha256']); data['result']['records'][0]['fiberid']='221'
        bad['positive_inventory_sha256']=json.dumps(data).encode()
        with self.assertRaises(ValueError):m.verify_positive_prerequisites(manifest,bad,q)

    def test_held_query_requires_exact_14_and_valid_empty(self):
        e=m.EMPTY;a=m.POSITIVE
        paths={'empty_inventory_sha256':e/'EMPTY_CONTROL.json','empty_result_sha256':e/'capture/RESULT.json',
          'empty_finish_sha256':e/'capture/FINISH.json','gaia_rows_sha256':m.GAIA,'held_objects_sha256':m.HELD,
          'positive_query_sha256':a/'QUERY.adql'}
        frozen={k:p.read_bytes() for k,p in paths.items()}; inv=json.loads(frozen['empty_inventory_sha256'])
        manifest={'empty_'+k+'_sha256':v for k,v in inv['evidence_pins'].items() if k!='positive_raw'}
        manifest['positive_raw_sha256']=inv['evidence_pins']['positive_raw']
        q=(P/'QUERY.adql').read_text(encoding='utf-8-sig').strip()
        m.verify_held_prerequisites(manifest,frozen,q)
        with self.assertRaises(ValueError):m.verify_held_prerequisites(manifest,frozen,q.replace('TOP 201','TOP 200'))
        bad=dict(frozen); data=json.loads(bad['gaia_rows_sha256']);data[0]['source_id']=data[1]['source_id']
        bad['gaia_rows_sha256']=json.dumps(data).encode()
        with self.assertRaises(ValueError):m.verify_held_prerequisites(manifest,bad,q)
        bad=dict(frozen); data=json.loads(bad['empty_inventory_sha256']);data['result']['row_count']=1
        bad['empty_inventory_sha256']=json.dumps(data).encode()
        with self.assertRaises(ValueError):m.verify_held_prerequisites(manifest,bad,q)

    def test_shape_gate_binds_query_shape_and_published_tuple(self):
        z=m.SHAPE
        paths={'shape_inventory_sha256':z/'SHAPE_CONTROL.json','shape_result_sha256':z/'capture/RESULT.json',
               'shape_finish_sha256':z/'capture/FINISH.json','shape_query_sha256':z/'QUERY.adql'}
        frozen={k:p.read_bytes() for k,p in paths.items()};inv=json.loads(frozen['shape_inventory_sha256'])
        manifest={'shape_'+k+'_sha256':v for k,v in inv['evidence_pins'].items()}
        q=(P/'QUERY.adql').read_text(encoding='utf-8-sig').strip()
        m.verify_shape_prerequisites(manifest,frozen,q)
        with self.assertRaises(ValueError):m.verify_shape_prerequisites(manifest,frozen,q.replace('TOP 201','TOP 200'))
        bad=dict(frozen); data=json.loads(bad['shape_inventory_sha256']);data['result']['records'][0]['fiberid']='221'
        bad['shape_inventory_sha256']=json.dumps(data).encode()
        with self.assertRaises(ValueError):m.verify_shape_prerequisites(manifest,bad,q)

    def test_manifest_digest_checked_before_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'MANIFEST.json'; p.write_text('{}',encoding='utf-8')
            with mock.patch.object(m,'MANIFEST',p):
                with self.assertRaises(ValueError): m.validate('0'*64)

if __name__=='__main__': unittest.main(verbosity=2)
