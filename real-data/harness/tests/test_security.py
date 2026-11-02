"""Independent boundary tests. Fabricated configurations are tests, not sky data."""
import hashlib
import json
import tempfile
import unittest
import os
import urllib.request
from pathlib import Path
from unittest.mock import patch,MagicMock
from harness2.core.components import HarnessBundle
from harness2.core.library import ContinualLibrary
from harness2.core.recursion import Harness2Engine
from harness2.core import guards
from harness2.providers.router import LLMConfig, UniversalModelRouter

BASE = dict(mass_function_weight=1, precision_weight=1, efficiency_weight=1)

class BoundaryTests(unittest.TestCase):
    def test_invalid_proposals(self):
        for value in [float('nan'), float('inf'), -1, True, '2', 5]:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                HarnessBundle.from_dict({**BASE, 'precision_weight': value})
        with self.assertRaises(ValueError):
            HarnessBundle.from_dict({**BASE, 'release_enabled': True})
        with self.assertRaises(ValueError):
            HarnessBundle.from_dict({key: 0 for key in BASE})

    def test_remote_and_credentialed_proposer_rejected(self):
        for url in ['http://evil.test/v1', 'https://127.0.0.1.evil.test/v1',
                    'http://user:pass@127.0.0.1/v1', 'http://127.0.0.1/v1?url=x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                UniversalModelRouter(LLMConfig('local', 'test-only', url))
        with self.assertRaises(ValueError):
            UniversalModelRouter(LLMConfig('remote', 'test-only'))

    def test_local_failure_does_not_fallback(self):
        router = UniversalModelRouter(LLMConfig('local', 'test-only'))
        with patch('urllib.request.OpenerDirector.open', side_effect=TimeoutError('test-only')):
            with self.assertRaises(TimeoutError):
                router.propose(HarnessBundle(), {'count': 0}, 0)

    def test_local_model_disables_environment_proxies(self):
        router=UniversalModelRouter(LLMConfig('local','test-only'))
        response=MagicMock()
        response.__enter__.return_value.read.return_value=json.dumps(
            {'choices':[{'message':{'content':json.dumps(BASE)}}]}).encode()
        original=urllib.request.build_opener
        with patch.dict(os.environ,{'HTTP_PROXY':'http://proxy.invalid:3128',
                                   'HTTPS_PROXY':'http://proxy.invalid:3128','NO_PROXY':''}):
            with patch('urllib.request.build_opener',wraps=original) as build:
                with patch('urllib.request.OpenerDirector.open',return_value=response):
                    self.assertEqual(router.propose(HarnessBundle(),{'count':0},0).to_dict(),BASE)
                handlers=build.call_args.args
                proxy=[h for h in handlers if isinstance(h,urllib.request.ProxyHandler)]
                self.assertEqual(len(proxy),1)
                self.assertEqual(proxy[0].proxies,{})

    def test_memory_policy_mismatch_and_injected_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'memory.json'
            library = ContinualLibrary(path)
            library.save(HarnessBundle(), 'old', {})
            with self.assertRaises(ValueError):
                library.load('new')
            data = json.loads(path.read_text())
            data['accepted_configuration']['release_enabled'] = True
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                library.load('old')

    def test_invalid_review_budgets(self):
        engine = Harness2Engine(None, None)
        for budget in [0, -1, 1001]:
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                engine.run_task([], budget=budget)

    def test_guard_rejects_changed_file_and_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'policy').mkdir()
            target = root/'protected.py'
            target.write_text('original')
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            (root/'policy/guard_manifest.json').write_text(json.dumps({'files': {'protected.py': digest}}))
            with patch.object(guards, 'ROOT', root):
                guards.verify_guard()
                target.write_text('modified')
                with self.assertRaises(RuntimeError):
                    guards.verify_guard()
                target.write_text('original')
                # Exercise the fail-closed symlink branch on every platform.
                with patch.object(Path,'is_symlink',return_value=True):
                    with self.assertRaises(RuntimeError):guards.verify_guard()

    def test_native_symlink_guard_when_os_permits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'policy').mkdir()
            sibling=root/'same_content.py';sibling.write_text('original')
            target=root/'protected.py'
            try:target.symlink_to(sibling)
            except OSError as exc:
                if getattr(exc,'winerror',None)==1314:
                    self.skipTest('Windows denied symlink creation (WinError 1314); guard branch tested separately')
                raise
            digest=hashlib.sha256(sibling.read_bytes()).hexdigest()
            (root/'policy/guard_manifest.json').write_text(json.dumps({'files':{'protected.py':digest}}))
            with patch.object(guards,'ROOT',root):
                with self.assertRaises(RuntimeError):guards.verify_guard()

if __name__ == '__main__':
    unittest.main()
