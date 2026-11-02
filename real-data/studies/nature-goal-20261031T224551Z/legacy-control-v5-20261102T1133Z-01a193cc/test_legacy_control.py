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
spec=importlib.util.spec_from_file_location('control_test',P/'legacy_control.py')
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
        self.assertEqual(r['requests_attempted'],1); self.assertFalse(r['target_requested'])
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

    def test_manifest_digest_checked_before_use(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'MANIFEST.json'; p.write_text('{}',encoding='utf-8')
            with mock.patch.object(m,'MANIFEST',p):
                with self.assertRaises(ValueError): m.validate('0'*64)

if __name__=='__main__': unittest.main(verbosity=2)
