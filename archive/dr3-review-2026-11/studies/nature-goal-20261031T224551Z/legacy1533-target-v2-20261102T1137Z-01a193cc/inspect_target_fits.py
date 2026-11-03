"""Inventory the acquired Legacy field. No detection or orbit inference."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, warnings
import numpy as np
import astropy
from astropy.io import fits
from astropy.wcs import WCS

D=Path(__file__).resolve().parent
raw=D/'capture'/'legacy_target.raw'
finish=json.loads((D/'capture'/'FINISH.json').read_text(encoding='utf-8'))
transport=json.loads((D/'capture'/'RESULT.json').read_text(encoding='utf-8'))
if not finish.get('lease_released') or not finish.get('owned_process_exit_confirmed') or transport.get('status')!='HTTP_COMPLETE_FITS_UNVALIDATED':
    raise RuntimeError('incomplete acquisition or ownership record')
if finish.get('terminal_sha256')!=hashlib.sha256((D/'capture'/'RESULT.json').read_bytes()).hexdigest():
    raise RuntimeError('terminal result hash mismatch')
hash_now=hashlib.sha256(raw.read_bytes()).hexdigest()
if hash_now!=transport.get('body_sha256'): raise RuntimeError('body hash mismatch')
points={'gaia_2016_unpropagated':[185.71462554756414,40.88393733581962],
        'ps1_one_detection_mean':[185.71518099,40.88389641],
        'gaia_neighbor_2016_unpropagated':[185.7131520967809,40.88946022434856]}
rows=[]
with warnings.catch_warnings(record=True) as seen:
    warnings.simplefilter('always')
    with fits.open(raw,mode='readonly',memmap=False,checksum=True,lazy_load_hdus=False) as hdus:
        hdus.verify('exception')
        for i,h in enumerate(hdus):
            head=h.header; data=h.data
            row={'index':i,'class':type(h).__name__,'shape':list(data.shape) if data is not None else None,
                 'dtype':str(data.dtype) if data is not None else None,
                 'survey':head.get('SURVEY'),'version':head.get('VERSION'),
                 'band':head.get('BAND'),'image_type':head.get('IMAGETYP'),'brick':head.get('BRICK'),
                 'bunit':head.get('BUNIT'),'radesys_card':head.get('RADESYS'),
                 'equinox_card':head.get('EQUINOX'),'checksum_present':'CHECKSUM' in head,
                 'datasum_present':'DATASUM' in head}
            if data is not None and data.ndim==2 and np.issubdtype(data.dtype,np.number):
                finite=np.isfinite(data); row['finite_fraction']=float(finite.mean())
                row['min']=float(data[finite].min()) if finite.any() else None
                row['max']=float(data[finite].max()) if finite.any() else None
                try:
                    w=WCS(head,naxis=2); row['wcs_celestial']=bool(w.has_celestial)
                    row['ctype']=list(w.wcs.ctype); row['astropy_default_radesys']=w.wcs.radesys
                    row['locations']={}
                    if w.has_celestial:
                        for name,(ra,dec) in points.items():
                            x0,y0=w.world_to_pixel_values(ra,dec); x,y=float(x0),float(y0)
                            inside=bool(np.isfinite(x) and np.isfinite(y) and -0.5<=x<data.shape[1]-0.5 and -0.5<=y<data.shape[0]-0.5)
                            info={'pixel_xy':[x,y],'inside':inside}
                            if inside:
                                xi=max(0,min(data.shape[1]-1,int(round(x))))
                                yi=max(0,min(data.shape[0]-1,int(round(y))))
                                value=data[yi,xi]; info['nearest_pixel_finite']=bool(np.isfinite(value))
                                info['nearest_pixel_value']=float(value) if np.isfinite(value) else None
                            row['locations'][name]=info
                except Exception as exc:
                    row['wcs_error_type']=type(exc).__name__
            rows.append(row)
    warning_types=[type(w.message).__name__ for w in seen]
output={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':hash_now,
        'astropy':astropy.__version__,'numpy':np.__version__,'fits_verify_exception_passed':True,
        'warning_types':warning_types,'points':points,'hdus':rows,
        'interpretation':'coverage inventory only; no detection, flux-limit or orbit inference'}
with (D/'TARGET_FITS_INVENTORY.json').open('x',encoding='utf-8') as f:
    json.dump(output,f,indent=2,allow_nan=False); f.write('\n')
print(json.dumps(output,indent=2,allow_nan=False))
