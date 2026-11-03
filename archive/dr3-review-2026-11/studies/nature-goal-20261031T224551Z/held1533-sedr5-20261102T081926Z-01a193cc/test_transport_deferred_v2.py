from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch
import native_transport_sedr5_v5 as transport

class DeferredEvidenceTest(unittest.TestCase):
    def test_unconfirmed_exit_never_hashes_moving_outputs(self):
        parent = Path(__file__).resolve().parent
        sandbox = Path(tempfile.mkdtemp(prefix='synthetic-transport-', dir=parent))
        self.assertEqual(sandbox.resolve().parent, parent.resolve())
        class StillRunning:
            pid = 97531
            returncode = None
            def poll(self): return None
            def kill(self): pass
            def wait(self, timeout): raise subprocess.TimeoutExpired('fake', timeout)
        def fake_popen(command, stdout, stderr, shell):
            (sandbox/'root.raw').write_bytes(b'xx')
            return StillRunning()
        original_sha = transport.sha
        def checked_sha(path):
            if path.name in ('root.raw', 'root.headers', 'root.curl.stdout', 'root.curl.stderr'):
                raise AssertionError('unconfirmed native output was hashed')
            return original_sha(path)
        url = 'https://example.invalid/synthetic-only'
        seen=[]
        with patch.dict(transport.REQUEST_URLS, {'root':url}, clear=True), \
             patch.dict(transport.LIMITS, {'body_bytes':1}, clear=False), \
             patch.object(transport.subprocess, 'Popen', side_effect=fake_popen), \
             patch.object(transport, 'sha', side_effect=checked_sha):
            result = transport.fetch(sandbox, {'url':url,'method':'GET'}, 'root',
                                     time.perf_counter_ns()+10_000_000_000, owner_callback=seen.append)
        self.assertEqual([proc.pid for proc in seen], [97531])
        self.assertEqual(result['cleanup_status'], 'EXIT_UNCONFIRMED')
        self.assertEqual(result['native_file_hashes'], 'DEFERRED_UNTIL_EXIT_CONFIRMED')
        self.assertIsNone(result['body_overage_bytes'])
        self.assertNotIn('raw_sha256', result)
        self.assertTrue((sandbox/'root.request.json').exists())
        # The sandbox is intentionally retained; no network or real child process occurred.

if __name__ == '__main__': unittest.main()