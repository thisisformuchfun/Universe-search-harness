"""Accepted configurations affect the next run; no unvalidated prose-as-learning."""
from pathlib import Path
import json,os
from harness2.core.components import HarnessBundle

def atomic_json(path,payload):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(payload,indent=2,allow_nan=False)+'\n',encoding='utf8');os.replace(temp,path)

class ContinualLibrary:
    def __init__(self,path): self.path=Path(path)
    def load(self,guard_hash):
        if not self.path.exists(): return HarnessBundle()
        obj=json.loads(self.path.read_text())
        if obj.get('guard_hash')!=guard_hash: raise ValueError('Memory policy hash differs: do not reuse')
        return HarnessBundle.from_dict(obj['accepted_configuration'])
    def save(self,config,guard_hash,evidence):
        atomic_json(self.path,{'guard_hash':guard_hash,'accepted_configuration':config.to_dict(),
          'meaning':'A ranking utility lesson, NOT a detection or astrophysical claim','evidence':evidence})
