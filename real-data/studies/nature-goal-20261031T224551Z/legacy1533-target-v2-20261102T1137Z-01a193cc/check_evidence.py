"""Read-only integrity and descriptive weight summary for the preserved field."""
import hashlib,json
from pathlib import Path
D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=json.loads((D/'capture/RESULT.json').read_text(encoding='utf-8'))
finish=json.loads((D/'capture/FINISH.json').read_text(encoding='utf-8'))
inv=json.loads((D/'TARGET_FITS_INVENTORY.json').read_text(encoding='utf-8'))
weights=json.loads((D/'LOCAL_WEIGHT_COUNTS.json').read_text(encoding='utf-8'))
raw_sha=sha(D/'capture/legacy_target.raw')
assert raw_sha==result['body_sha256']==inv['input_sha256']==weights['input_sha256']
assert finish['terminal_sha256']==sha(D/'capture/RESULT.json') and finish['lease_released']
print(json.dumps({'sha256':raw_sha,'http_status':result['http_status'],
 'fits_hdus':len(inv['hdus']), 'z_windows':[{k:r[k] for k in ('point','weight_zero_pixels','window_pixels')}
 for r in weights['rows'] if r['band']=='z'], 'interpretation':'descriptive only; no new orbit or BH'}))
