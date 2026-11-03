"""Read-only verification of the fixed original-14 NOIRLab result."""
from pathlib import Path
import hashlib,json
D=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
raw=D/'capture/held14_search.raw';r=json.loads((D/'capture/RESULT.json').read_text(encoding='utf8'))
f=json.loads((D/'capture/FINISH.json').read_text(encoding='utf8'));x=json.loads((D/'HELD14_CROSSMATCH_ZERO.json').read_text(encoding='utf8'))
assert sha(raw)==r['body_sha256']==x['input_sha256']
assert f['terminal_sha256']==sha(D/'capture/RESULT.json') and f['lease_released']
assert x['result']['status']=='COMPLETE_ZERO_SELECTED_CROSSMATCH' and len(x['result']['queried_source_ids'])==14
print(json.dumps({'body_sha256':sha(raw),'http_status':r['http_status'],'source_count':14,
 'returned_rows':x['result']['row_count'],'scope':'NOIRLab DR17 clean-view 1.5-arcsec nearest-neighbor join only'}))
