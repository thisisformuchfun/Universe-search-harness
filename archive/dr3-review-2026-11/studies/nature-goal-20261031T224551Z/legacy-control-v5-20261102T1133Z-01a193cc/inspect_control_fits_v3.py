"""Descriptive FITS control inspection; no target data and no orbit inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, warnings
import numpy as np
import astropy
from astropy.io import fits
from astropy.wcs import WCS

D=Path(__file__).resolve().parent
raw=D/'capture'/'legacy_control.raw'
finish=json.loads((D/'capture'/'FINISH.json').read_text(encoding='utf-8'))
transport=json.loads((D/'capture'/'RESULT.json').read_text(encoding='utf-8'))
if not finish.get('lease_released') or not finish.get('owned_process_exit_confirmed') or transport.get('status') != 'HTTP_COMPLETE_FITS_UNVALIDATED':
    raise RuntimeError('incomplete acquisition or ownership record')
hash_now=hashlib.sha256(raw.read_bytes()).hexdigest()
if hash_now != transport.get('body_sha256'): raise RuntimeError('input hash mismatch')
rows=[]
with warnings.catch_warnings(record=True) as seen:
    warnings.simplefilter('always')
    with fits.open(raw,mode='readonly',memmap=False,checksum=True,lazy_load_hdus=False) as hdus:
        hdus.verify('exception')
        for i,h in enumerate(hdus):
            head=h.header
            d=h.data
            row={'index':i,'extname':head.get('EXTNAME'),'class':type(h).__name__,
                 'shape':list(d.shape) if d is not None else None,
                 'dtype':str(d.dtype) if d is not None else None,
                 'bunit':head.get('BUNIT'),'band':head.get('BAND'),'image_type':head.get('IMAGETYP'),
                 'brick':head.get('BRICK'),'survey':head.get('SURVEY'),'version':head.get('VERSION'),
                 'checksum_present':'CHECKSUM' in head,
                 'datasum_present':'DATASUM' in head}
            if d is not None and d.ndim==2 and np.issubdtype(d.dtype,np.number):
                finite=np.isfinite(d)
                row['finite_fraction']=float(finite.mean())
                row['nonzero_fraction']=float(np.count_nonzero(d[finite])/finite.sum()) if finite.any() else None
                row['min']=float(d[finite].min()) if finite.any() else None
                row['max']=float(d[finite].max()) if finite.any() else None
                try:
                    w=WCS(head,naxis=2)
                    row['wcs_celestial']=bool(w.has_celestial)
                    row['ctype']=list(w.wcs.ctype)
                    if w.has_celestial:
                        x0,y0=w.world_to_pixel_values(154.7709,46.4537)
                        x,y=float(x0),float(y0)
                        row['control_pixel_xy']=[float(x),float(y)]
                        row['control_inside']=bool(-0.5<=x<d.shape[1]-0.5 and -0.5<=y<d.shape[0]-0.5)
                        if row['control_inside']:
                            xi,yi=int(round(x)),int(round(y))
                            xi=max(0,min(d.shape[1]-1,xi)); yi=max(0,min(d.shape[0]-1,yi))
                            row['control_pixel_value']=float(d[yi,xi]) if np.isfinite(d[yi,xi]) else None
                except Exception as exc:
                    row['wcs_error_type']=type(exc).__name__
            rows.append(row)
    warning_types=[type(w.message).__name__ for w in seen]
result={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':hash_now,
        'astropy':astropy.__version__,'numpy':np.__version__,'fits_verify_exception_passed':True,
        'warning_types':warning_types,'hdus':rows,
        'interpretation':'descriptive only; pass/fail and scientific scope need independent review'}
with (D/'CONTROL_FITS_INVENTORY_V3.json').open('x',encoding='utf-8') as f:
    json.dump(result,f,indent=2,allow_nan=False); f.write('\n')
print(json.dumps(result,indent=2,allow_nan=False))
