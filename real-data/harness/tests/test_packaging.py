"""Packaging protocol fixtures; no private files or real science evaluation."""
import hashlib,importlib.util,json,tempfile,unittest,zipfile
from pathlib import Path

spec=importlib.util.spec_from_file_location('package_release',Path(__file__).resolve().parents[1]/'scripts/package_release.py')
packager=importlib.util.module_from_spec(spec);spec.loader.exec_module(packager)

class PackageTests(unittest.TestCase):
    def test_allowlist_excludes_caches_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'source';root.mkdir()
            files={'README.md':'test','harness2/example.py':'# test',
                   'data/pilot/rows.csv':'source_id\n1\n','data/astra-cache/private.xml':'not included',
                   'runs/private.json':'not included','.env':'not included','model.weights':'not included'}
            for name,body in files.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(body)
            (root/'data/pilot/SNAPSHOT_MANIFEST.json').write_text(json.dumps({'files':{'rows.csv':hashlib.sha256((root/'data/pilot/rows.csv').read_bytes()).hexdigest()}}))
            (root/'policy').mkdir();(root/'policy/guard_manifest.json').write_text(json.dumps({'files':{'harness2/example.py':'stale'}}))
            output=Path(d)/'reviewed.zip';result=packager.package(root,output)
            self.assertEqual(result['guard_state'],'UNSEALED_REVIEW_REQUIRED')
            original=output.read_bytes()
            with self.assertRaises(FileExistsError):packager.package(root,output)
            self.assertEqual(original,output.read_bytes())
            with zipfile.ZipFile(output) as z:
                names=z.namelist()
                self.assertIn('universe-real-harness/data/pilot/rows.csv',names)
                self.assertFalse(any('private' in name or '.env' in name or 'weights' in name for name in names))
            with self.assertRaisesRegex(ValueError,'baseline filename'):
                packager.package(root,Path(d)/'Universe_Search_Harness_Real_Data_v1.zip')
