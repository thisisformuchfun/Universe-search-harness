"""Read-only verification of the target mask and descriptive bit counts."""
from pathlib import Path
import hashlib,json
D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
raw=D/'capture/mask_target.raw'; result=json.loads((D/'capture/RESULT.json').read_text(encoding='utf8'))
finish=json.loads((D/'capture/FINISH.json').read_text(encoding='utf8'))
windows=json.loads((D/'TARGET_MASK_WINDOWS.json').read_text(encoding='utf8'))
assert sha(raw)==result['body_sha256']==windows['mask_sha256']
assert finish['terminal_sha256']==sha(D/'capture/RESULT.json') and finish['lease_released']
print(json.dumps({'mask_sha256':sha(raw),'http_status':result['http_status'],
 'points':[{'name':r['point'],'count':r['union']['pixel_count'],
            'satur_r':r['union']['counts_by_bit']['SATUR_R'],
            'satur_z':r['union']['counts_by_bit']['SATUR_Z'],
            'allmask_z':r['union']['counts_by_bit']['ALLMASK_Z']} for r in windows['rows']],
 'interpretation':'provider flags in sampled regions; no orbit or black-hole inference'}))
