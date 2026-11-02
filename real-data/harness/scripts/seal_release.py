"""Maintainer release step, NEVER called by the proposal loop. Review diffs first."""
import pathlib,json,hashlib
root=pathlib.Path(__file__).resolve().parents[1]
files=list((root/'harness2').rglob('*.py'))+list((root/'policy').glob('*.json'))
files.append(root/'data/pilot/SNAPSHOT_MANIFEST.json')
files=[p for p in files if p.name!='guard_manifest.json']
manifest={'scope':'These files cannot be changed by proposals. Hashes are audit checks, not an OS security boundary.',
'files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}}
(root/'policy/guard_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
