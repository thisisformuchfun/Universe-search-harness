import io
import contextlib
import json
import os
import tempfile
import types
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
import capture_serial_v9 as capture
import native_transport_sedr5_v5 as transport
from test_transport_deferred_v2 import DeferredEvidenceTest

class IndexTests(unittest.TestCase):
    def test_exact_unique_child(self):
        self.assertTrue(capture.exact_child(b'<html><a href="20150108/">date</a></html>', '20150108/'))
        self.assertFalse(capture.exact_child(b'<a href="20150108/">x</a><a href="20150108/">y</a>', '20150108/'))
    def test_base_and_duplicate_href_are_rejected(self):
        self.assertFalse(capture.exact_child(b'<base href="https://bad.invalid/"><a href="20150108/">x</a>', '20150108/'))
        self.assertFalse(capture.exact_child(b'<a href="20150108/" href="https://bad.invalid/">x</a>', '20150108/'))
    def test_lookalikes_rejected(self):
        for html in (b'<a href="../20150108/">x</a>', b'<a href="20150108/%2e%2e/">x</a>',
                     b'<a href="https://bad.invalid/20150108/">x</a>'):
            self.assertFalse(capture.exact_child(html, '20150108/'))
    def test_invalid_utf8_or_nul_fails(self):
        for raw in (b'\xff<a href="20150108/">x</a>', b'\x00<a href="20150108/">x</a>'):
            with self.assertRaises((ValueError, UnicodeDecodeError)):
                capture.exact_child(raw, '20150108/')
    def test_transport_failure_never_admits(self):
        self.assertEqual(capture.decide('root', {'status':'FAILED_VISIBLE'}, b'<a href="20150108/">x</a>', '20150108/'), 'STOP_TRANSPORT')
    def test_product_magic_is_explicitly_not_identity(self):
        result = capture.decide('product', {'status':'HTTP_COMPLETE_UNPARSED'}, b'SIMPLE  =', None)
        self.assertEqual(result, 'PASS_TRANSPORT_PREFIX_ONLY')
        self.assertNotIn('IDENTITY', result)
    def test_fixed_scope_and_caps(self):
        self.assertEqual(sum(stage[2] for stage in capture.STAGES), 5500000)
        self.assertTrue(all(stage[1].startswith('https://casdc.china-vo.org/') for stage in capture.STAGES))

class TimingTests(unittest.TestCase):
    def test_early_wake_stops(self):
        with patch.object(capture.time, 'perf_counter_ns', side_effect=[0, 0]), patch.object(capture.time, 'sleep'):
            with self.assertRaises(TimeoutError):
                capture.wait_for_next(0, 20_000_000_000)
    def test_deadline_stops_before_sleep(self):
        with patch.object(capture.time, 'perf_counter_ns', return_value=0), patch.object(capture.time, 'sleep') as sleep:
            with self.assertRaises(TimeoutError):
                capture.wait_for_next(0, 5_000_000_000)
            sleep.assert_not_called()

class CleanupTests(unittest.TestCase):
    def test_unconfirmed_process_is_not_called_terminated(self):
        class StillRunning:
            def poll(self): return None
            def kill(self): pass
            def wait(self, timeout): raise subprocess.TimeoutExpired('fake', timeout)
        rec = {'owned_process_kill_issued':False}
        transport.cleanup_owned(StillRunning(), rec)
        self.assertEqual(rec['cleanup_status'], 'EXIT_UNCONFIRMED')
        self.assertTrue(rec['owned_process_kill_issued'])
        self.assertEqual(rec['cleanup_error_type'], 'TimeoutExpired')
    def test_exited_and_not_started_are_distinct(self):
        class Done:
            def poll(self): return 0
        a = {}; b = {}
        transport.cleanup_owned(Done(), a); transport.cleanup_owned(None, b)
        self.assertEqual(a['cleanup_status'], 'EXIT_CONFIRMED')
        self.assertEqual(b['cleanup_status'], 'NOT_STARTED')
    def test_hash_reads_bounded_blocks(self):
        class Stream:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size):
                self.assertion(size)
                return b''
            def assertion(self, size):
                if size != 65536: raise AssertionError('unbounded read')
        class PathStub:
            def open(self, mode): return Stream()
        self.assertEqual(transport.sha(PathStub()), 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855')

class HeaderTests(unittest.TestCase):
    def test_complete_status_and_proxy_block(self):
        self.assertTrue(capture.valid_http_headers(b'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n', 200))
        self.assertTrue(capture.valid_http_headers(b'HTTP/1.1 200 Connection established\r\n\r\nHTTP/2 200\r\ncontent-type: text/html\r\n\r\n', 200))
        self.assertTrue(capture.valid_http_headers(b'HTTP/1.1 200 OK\r\nX: \x80\r\nContent-Length: 3\r\n\r\n', 200, 3))
        self.assertFalse(capture.valid_http_headers(b'HTTP/1.1 200 OK\r\nContent-Length: 4\r\n\r\n', 200, 3))
    def test_missing_malformed_or_mismatched_rejected(self):
        for b in (b'', b'HTTP/1.1 200 OK\r\n', b'HTTP/1.1 403 Forbidden\r\n\r\n',
                  b'junk\r\n\r\n', b'HTTP/1.1 200 OK\r\nno-colon\r\n\r\n',
                  b'HTTP/1.1 200 OK\r\nX: \x01\r\n\r\n', b'HTTP/1.1 200 \x7f\r\n\r\n',
                  b'HTTP/1.1 200 OK\r\nContent-Length: 1\r\nContent-Length: 1\r\n\r\n'):
            self.assertFalse(capture.valid_http_headers(b, 200))

class OwnershipTests(unittest.TestCase):
    def test_pid_is_in_memory_before_persistence_failure(self):
        owner = {'pid':None, 'identity':None}
        with patch.object(capture, 'process_identity', return_value={'pid':97531, 'creation_filetime_100ns':'123'}), patch.object(capture, 'save', side_effect=OSError('synthetic')):
            with self.assertRaises(OSError):
                capture.bind_owned_pid(Path('unused'), 'token', Path('unused'), 'root', types.SimpleNamespace(pid=97531, _handle=None), owner)
        self.assertEqual(owner['pid'], 97531)
        self.assertEqual(owner['identity']['creation_filetime_100ns'], '123')
    def test_current_process_identity_never_authorizes_pid_only_action(self):
        identity = capture.process_identity(types.SimpleNamespace(pid=os.getpid(), _handle=-1))
        self.assertEqual(identity['pid'], os.getpid())
        self.assertIn(identity['identity_status'], ('OWNED_HANDLE_CREATION_TIME_OBSERVED','UNAVAILABLE'))
        self.assertIn('Never kill', identity['instruction'])
        if identity['creation_filetime_100ns'] is not None:
            self.assertTrue(identity['creation_filetime_100ns'].isdigit())
    def test_exception_after_spawn_retains_lease_and_current_identity(self):
        parent = Path(__file__).resolve().parent
        sandbox = Path(tempfile.mkdtemp(prefix='synthetic-lifecycle-', dir=parent))
        self.assertEqual(sandbox.resolve().parent, parent.resolve())
        lease = sandbox/'coordination'/'sedr5-acquisition.lock'
        lease.parent.mkdir()
        def fake_fetch(out, request, name, deadline, owner_callback=None):
            capture.save(out/(name+'.request.json'), {'synthetic':True})
            owner_callback(types.SimpleNamespace(pid=97531, _handle=None))
            raise OSError('synthetic terminal-record failure')
        fake_transport = types.SimpleNamespace(REQUEST_URLS={}, LIMITS={}, fetch=fake_fetch)
        fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module:None))
        fake_identity = {'pid':97531, 'creation_filetime_100ns':'123', 'identity_status':'SYNTHETIC'}
        with patch.object(capture, 'D', sandbox), patch.object(capture, 'LOCK', lease), \
             patch.object(capture, 'validate_inputs', return_value=({'protocol_sha256':'synthetic'}, {}, 'synthetic')), \
             patch.object(capture, 'process_identity', return_value=fake_identity), \
             patch.object(capture.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
             patch.object(capture.importlib.util, 'module_from_spec', return_value=fake_transport), \
             contextlib.redirect_stdout(io.StringIO()):
            result = capture.execute('a'*64)
        self.assertEqual(result, 1)
        self.assertTrue(lease.exists())
        saved = json.loads(lease.read_text(encoding='utf8'))
        self.assertEqual(saved['last_owned_process'], fake_identity)
        self.assertEqual(saved['cleanup_status'], 'EXIT_UNCONFIRMED')
        outcome = json.loads((sandbox/'capture-v9'/'RESULTS.json').read_text(encoding='utf8'))
        self.assertFalse(outcome['lease_released'])
        self.assertEqual(outcome['lifecycle'][0]['request_file_state'], 'INVALID')
        self.assertTrue(outcome['lifecycle'][0]['process_started'])
        self.assertIsNone(outcome['lifecycle'][0]['http_transport_complete'])
        # Sandbox is intentionally retained for inspection; no real process was started.

    def test_interruption_during_identity_preserves_known_pid(self):
        parent = Path(__file__).resolve().parent
        sandbox = Path(tempfile.mkdtemp(prefix='synthetic-identity-', dir=parent))
        self.assertEqual(sandbox.resolve().parent, parent.resolve())
        lease = sandbox/'coordination'/'sedr5-acquisition.lock'
        lease.parent.mkdir()
        def fake_fetch(out, request, name, deadline, owner_callback=None):
            capture.save(out/(name+'.request.json'), {'synthetic':True})
            owner_callback(types.SimpleNamespace(pid=97531, _handle=None))
        fake_transport = types.SimpleNamespace(REQUEST_URLS={}, LIMITS={}, fetch=fake_fetch)
        fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module:None))
        with patch.object(capture, 'D', sandbox), patch.object(capture, 'LOCK', lease), \
             patch.object(capture, 'validate_inputs', return_value=({'protocol_sha256':'synthetic'}, {}, 'synthetic')), \
             patch.object(capture, 'process_identity', side_effect=KeyboardInterrupt), \
             patch.object(capture.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
             patch.object(capture.importlib.util, 'module_from_spec', return_value=fake_transport), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                capture.execute('a'*64)
        saved = json.loads(lease.read_text(encoding='utf8'))
        self.assertEqual(saved['last_owned_pid'], 97531)
        self.assertIsNone(saved['last_owned_process'])
        outcome = json.loads((sandbox/'capture-v9'/'RESULTS.json').read_text(encoding='utf8'))
        self.assertEqual(outcome['last_owned_pid'], 97531)
        self.assertFalse(outcome['lease_released'])
        self.assertTrue(outcome['lifecycle'][0]['process_started'])
        # Synthetic sandbox retained; no real process or network request occurred.

    def test_partial_metadata_does_not_prevent_final_handoff(self):
        parent = Path(__file__).resolve().parent
        sandbox = Path(tempfile.mkdtemp(prefix='synthetic-partial-', dir=parent))
        self.assertEqual(sandbox.resolve().parent, parent.resolve())
        lease = sandbox/'coordination'/'sedr5-acquisition.lock'
        lease.parent.mkdir()
        def fake_fetch(out, request, name, deadline, owner_callback=None):
            (out/(name+'.request.json')).write_text('{', encoding='utf8')
            owner_callback(types.SimpleNamespace(pid=97531, _handle=None))
            (out/(name+'.json')).write_text('{"status":', encoding='utf8')
            raise OSError('synthetic partial native record')
        fake_transport = types.SimpleNamespace(REQUEST_URLS={}, LIMITS={}, fetch=fake_fetch)
        fake_spec = types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda module:None))
        identity = {'pid':97531, 'creation_filetime_100ns':'123', 'identity_status':'SYNTHETIC'}
        with patch.object(capture, 'D', sandbox), patch.object(capture, 'LOCK', lease), \
             patch.object(capture, 'validate_inputs', return_value=({'protocol_sha256':'synthetic'}, {}, 'synthetic')), \
             patch.object(capture, 'process_identity', return_value=identity), \
             patch.object(capture.importlib.util, 'spec_from_file_location', return_value=fake_spec), \
             patch.object(capture.importlib.util, 'module_from_spec', return_value=fake_transport), \
             contextlib.redirect_stdout(io.StringIO()):
            result = capture.execute('a'*64)
        self.assertEqual(result, 1)
        outcome = json.loads((sandbox/'capture-v9'/'RESULTS.json').read_text(encoding='utf8'))
        self.assertFalse(outcome['lease_released'])
        self.assertEqual(outcome['last_owned_pid'], 97531)
        self.assertEqual(outcome['lifecycle'][0]['request_file_state'], 'INVALID')
        self.assertEqual(outcome['lifecycle'][0]['native_file_state'], 'INVALID')
        self.assertTrue(outcome['lifecycle'][0]['process_started'])
        self.assertIsNone(outcome['lifecycle'][0]['http_transport_complete'])
        # Synthetic sandbox retained; no real process or network request occurred.

if __name__ == '__main__': unittest.main()