import importlib.util
import contextlib
import io
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

D = Path(__file__).resolve().parent
def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
q = load('query_under_test',D/'query_v2.py')

def row(**changes):
    r = {k:'' for k in q.FIELDS}
    r.update(q.CONTROL_KEY)
    r['filename'] = q.CONTROL
    r.update(changes)
    return r

def csv_data(rows, header=None):
    import csv,io
    s = io.StringIO(newline='')
    writer = csv.writer(s,lineterminator='\r\n')
    writer.writerow(q.FIELDS if header is None else header)
    writer.writerows(rows)
    return s.getvalue().encode()

class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.socket_guard = patch.object(socket,'socket',side_effect=AssertionError('network forbidden in tests'))
        cls.process_guard = patch.object(subprocess,'Popen',side_effect=AssertionError('child forbidden in tests'))
        cls.socket_guard.start()
        cls.process_guard.start()
    @classmethod
    def tearDownClass(cls):
        cls.process_guard.stop()
        cls.socket_guard.stop()

    def test_body_is_fixed_and_contains_no_file(self):
        a,b = q.multipart(q.CONTROL),q.multipart(q.TARGET)
        self.assertEqual(a.replace(q.CONTROL.encode(),b'<name>'),b.replace(q.TARGET.encode(),b'<name>'))
        self.assertEqual(a.count(b'name="showcol"'),29)
        self.assertIn(b'name="pos.posfile"; filename=""',a)
        self.assertNotIn(b'C:\\',a)
        with self.assertRaises(ValueError): q.multipart('unreviewed')

    def test_valid_and_empty_csv(self):
        r = row()
        self.assertEqual(q.parse_csv(csv_data([[r[k] for k in q.FIELDS]])),[r])
        self.assertEqual(q.parse_csv(csv_data([])),[])

    def test_bad_headers_and_width_stop(self):
        with self.assertRaises(ValueError): q.parse_csv(csv_data([],q.FIELDS[:-1]))
        with self.assertRaises(ValueError): q.parse_csv(csv_data([['short']]))
        with self.assertRaises(ValueError): q.parse_csv(b'not,csv\x00')

    def test_size_and_rows_are_bounded(self):
        with self.assertRaises(ValueError): q.parse_csv(b'x'*(q.CAP+1))
        r = row()
        with self.assertRaises(ValueError): q.parse_csv(csv_data([[r[k] for k in q.FIELDS]]*1001))

    def test_control_requires_unique_exact_sample_and_filename(self):
        r = row()
        self.assertTrue(q.control_passes([r,row(iexp='1')]))
        self.assertFalse(q.control_passes([]))
        self.assertFalse(q.control_passes([r,r]))
        self.assertFalse(q.control_passes([row(mjm='other')]))
        self.assertFalse(q.control_passes([r,row(filename='foreign')]))

    def test_target_summary_keeps_only_identity_fields(self):
        r = row(filename=q.TARGET,rv='never-print-this')
        summary = q.identity_summary([r])
        self.assertTrue(summary['all_exact_filename'])
        self.assertNotIn('rv',summary['identity_rows'][0])
        self.assertFalse(q.identity_summary([])['all_exact_filename'])
        self.assertFalse(q.identity_summary([row()])['all_exact_filename'])

    def test_transport_rejects_wrong_method_or_body_before_spawn(self):
        tr = load('transport_under_test',D/'native_transport_post_v2.py')
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)/'body'
            p.write_bytes(b'known')
            tr.PAYLOADS = {'control':(p,tr.sha(p))}
            for req in ({'url':tr.URL,'method':'GET','payload_sha256':tr.sha(p)},
                        {'url':tr.URL,'method':'POST','payload_sha256':'wrong'},
                        {'url':'https://example.invalid','method':'POST','payload_sha256':tr.sha(p)}):
                with self.assertRaises(ValueError): tr.fetch(Path(temp),req,'control',0)

    def run_lifecycle(self,mode):
        with tempfile.TemporaryDirectory(dir=D,prefix='lifecycle-test-') as temp:
            folder = Path(temp).resolve()
            self.assertEqual(folder.parent,D)
            lib = load('real_reviewed_helpers',q.LIB)
            events = []
            class Transport:
                LIMITS = {}
                PAYLOADS = {}
                @staticmethod
                def fetch(out,request,name,deadline,owner_callback=None):
                    events.append(name)
                    if name == 'target' and mode == 'before_target_spawn':
                        raise RuntimeError('simulated pre-spawn failure')
                    owner_callback(types.SimpleNamespace(pid=111 if name=='control' else 222))
                    r = row(iexp='wrong') if mode=='bad_control' else row()
                    raw = out/(name+'.raw')
                    headers = out/(name+'.headers')
                    raw.write_bytes(csv_data([[r[k] for k in q.FIELDS]]))
                    headers.write_bytes(b'fake headers')
                    return {'cleanup_status':'EXIT_CONFIRMED','status':'HTTP_COMPLETE_UNPARSED',
                            'http_status':200,'ssl_verify_result':0,'num_redirects':0,
                            'effective_url':q.URL,'returncode':0,'raw_sha256':q.sha(raw),
                            'headers_sha256':q.sha(headers)}
            def identity(proc):
                if proc.pid==222 and mode=='target_identity_interrupted':
                    raise KeyboardInterrupt('simulated interruption')
                return {'pid':proc.pid}
            def loader(name,path):
                return lib if name=='capture_helpers' else Transport
            manifest={'control_body_sha256':'a'*64,'target_body_sha256':'b'*64,'protocol_sha256':'c'*64}
            with patch.object(q,'D',folder), patch.object(q,'LOCK',folder/'lease'), \
                 patch.object(q,'validate',return_value=(manifest,'curl 8.22.0')), \
                 patch.object(q,'load',side_effect=loader), patch.object(lib,'process_identity',side_effect=identity), \
                 patch.object(lib,'valid_http_headers',return_value=True), patch.object(q.time,'sleep'), \
                 contextlib.redirect_stdout(io.StringIO()):
                if mode=='target_identity_interrupted':
                    with self.assertRaises(KeyboardInterrupt): q.main('f'*64)
                else:
                    self.assertEqual(q.main('f'*64),1)
                result = json.loads((folder/'capture-v1'/'RESULTS.json').read_text())
                lease = json.loads((folder/'lease').read_text()) if (folder/'lease').exists() else None
                return events,result,lease

    def test_target_prespawn_failure_does_not_reuse_control_identity(self):
        events,result,lease = self.run_lifecycle('before_target_spawn')
        self.assertEqual(events,['control','target'])
        self.assertIsNone(lease['last_owned_pid'])
        self.assertIsNone(lease['last_owned_process'])
        self.assertIsNone(result['last_owned_pid'])
        self.assertIsNone(result['last_owned_process'])

    def test_interrupted_target_identity_is_not_paired_with_control(self):
        events,result,lease = self.run_lifecycle('target_identity_interrupted')
        self.assertEqual(events,['control','target'])
        self.assertEqual(lease['last_owned_pid'],222)
        self.assertIsNone(lease['last_owned_process'])
        self.assertEqual(result['last_owned_pid'],222)
        self.assertIsNone(result['last_owned_process'])

    def test_failed_control_never_starts_target(self):
        events,result,lease = self.run_lifecycle('bad_control')
        self.assertEqual(events,['control'])
        self.assertEqual(result['status'],'STOP_CONTROL_UNVERIFIED')
        self.assertIsNone(lease)

if __name__ == '__main__': unittest.main()
