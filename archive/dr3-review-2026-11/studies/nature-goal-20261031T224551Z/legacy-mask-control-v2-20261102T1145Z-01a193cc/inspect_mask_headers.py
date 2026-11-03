"""Inspect compressed FITS headers only; no tile decompression."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,warnings
from astropy.io import fits
D=Path(__file__).resolve().parent; raw=D/'capture/mask_control.raw'
r=json.loads((D/'capture/RESULT.json').read_text(encoding='utf-8'))
f=json.loads((D/'capture/FINISH.json').read_text(encoding='utf-8'))
sha=hashlib.sha256(raw.read_bytes()).hexdigest()
if sha!=r['body_sha256'] or not f['lease_released'] or not f['owned_process_exit_confirmed']:
    raise ValueError('transport proof mismatch')
keys=['XTENSION','BITPIX','NAXIS','NAXIS1','NAXIS2','ZIMAGE','ZCMPTYPE','ZBITPIX','ZNAXIS','ZNAXIS1','ZNAXIS2','ZTILE1','ZTILE2','ZQUANTIZ','BZERO','BSCALE','CHECKSUM','DATASUM','EXTNAME','BRICK','SURVEY','VERSION']
rows=[]
with warnings.catch_warnings(record=True) as seen:
 warnings.simplefilter('always')
 with fits.open(raw,mode='readonly',memmap=True,disable_image_compression=True,checksum=True,lazy_load_hdus=False) as hdus:
    hdus.verify('exception')
    for i,h in enumerate(hdus):
      rows.append({'index':i,'class':type(h).__name__,'fields':{k:h.header.get(k) for k in keys if k in h.header}})
 warnings_seen=[type(w.message).__name__ for w in seen]
obj={'created_utc':datetime.now(timezone.utc).isoformat(),'sha256':sha,'mode':'physical headers, compression disabled',
     'fits_verify_exception_passed':True,'warning_types':warnings_seen,'hdus':rows}
with (D/'MASK_HEADER_INVENTORY.json').open('x',encoding='utf-8') as stream:json.dump(obj,stream,indent=2);stream.write('\n')
print(json.dumps(obj,indent=2))
