import csv,hashlib,io,socket,subprocess,types,unittest
from unittest.mock import patch
import schema_v1 as s
import target_v1 as t

def digest(data): return hashlib.sha256(data).hexdigest()
def make_csv(header):
    row={k:'' for k in s.FIELDS}; row.update(s.CONTROL_KEY); row['filename']=s.CONTROL
    out=io.StringIO(newline=''); w=csv.writer(out,lineterminator='\r\n')
    w.writerow(header); w.writerow([row[k] for k in s.FIELDS]); return out.getvalue().encode()

class ControlPrerequisiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net=patch.object(socket,'socket',side_effect=AssertionError('network forbidden in tests'))
        cls.child=patch.object(subprocess,'Popen',side_effect=AssertionError('child forbidden in tests'))
        cls.net.start(); cls.child.start()
    @classmethod
    def tearDownClass(cls): cls.child.stop(); cls.net.stop()

    def setUp(self):
        self.raw=make_csv(s.PREFIXED); self.sample=make_csv(s.FIELDS); self.headers=b'private-test-header'
        self.cb=b'body '+s.CONTROL.encode(); self.tb=b'body '+s.TARGET.encode()
        self.patchers=[patch.object(t,'CONTROL_RAW',digest(self.raw)),patch.object(t,'SAMPLE_RAW',digest(self.sample)),
                       patch.object(t,'CONTROL_BODY',digest(self.cb)),patch.object(t,'TARGET_BODY',digest(self.tb))]
        for p in self.patchers: p.start(); self.addCleanup(p.stop)
        ident={'pid':123,'identity_status':'OWNED_HANDLE_CREATION_TIME_OBSERVED'}
        self.record={'status':'HTTP_COMPLETE_UNPARSED','http_status':200,'ssl_verify_result':0,'num_redirects':0,
                     'effective_url':t.URL,'returncode':0,'cleanup_status':'EXIT_CONFIRMED','limit_failure':None,
                     'body_overage_bytes':0,'header_overage_bytes':0,'native_stdout_overage_bytes':0,
                     'native_stderr_overage_bytes':0,'owned_pid':123,'raw_sha256':digest(self.raw),
                     'headers_sha256':digest(self.headers)}
        self.request={'request':{'name':'control','method':'POST','url':t.URL,'manifest_sha256':t.PRIOR_MANIFEST,
                                 'payload_sha256':t.CONTROL_BODY}}
        self.result={'status':'STOP_EXCEPTION','request_files':['control.request.json'],'lease_released':True,
                     'owned_process_exit_confirmed':True,'last_owned_process':ident}
        self.owned={'owned_process':ident}
        self.lib=types.SimpleNamespace(valid_http_headers=lambda raw,code,size:True)
    def check(self):
        return t.check_control(self.record,self.request,self.result,self.owned,self.raw,self.headers,
                               self.sample,self.cb,self.tb,self.lib)
    def test_positive_prerequisites(self):
        summary=self.check(); self.assertEqual(summary['control_rows'],1); self.assertNotIn('private-test-header',str(summary))
    def test_transport_or_cleanup_failure_stops(self):
        self.record['ssl_verify_result']=1
        with self.assertRaises(ValueError): self.check()
    def test_process_identity_mismatch_stops(self):
        self.record['owned_pid']=456
        with self.assertRaises(ValueError): self.check()
    def test_target_request_in_prior_run_stops(self):
        self.result['request_files'].append('target.request.json')
        with self.assertRaises(ValueError): self.check()
    def test_changed_body_stops(self):
        self.tb+=b'extra'
        with self.assertRaises(ValueError): self.check()

if __name__=='__main__': unittest.main()
