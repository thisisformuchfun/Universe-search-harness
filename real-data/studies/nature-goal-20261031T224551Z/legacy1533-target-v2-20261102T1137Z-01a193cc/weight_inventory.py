"""Reproducible 5x5 weight inventory at pre-existing sky positions; not a detection test."""
from pathlib import Path
import hashlib,json
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
D=Path(__file__).resolve().parent; raw=D/'capture'/'legacy_target.raw'
inv=json.loads((D/'TARGET_FITS_INVENTORY.json').read_text(encoding='utf-8'))
body_sha=hashlib.sha256(raw.read_bytes()).hexdigest()
if body_sha!=inv['input_sha256']: raise RuntimeError('FITS changed')
points=inv['points']; rows=[]
with fits.open(raw,mode='readonly',memmap=False) as hdus:
    for band in ('g','r','z'):
        def find(typ):
            matched=[h for h in hdus if h.header.get('BRICK')=='1857p410' and h.header.get('BAND')==band and h.header.get('IMAGETYP')==typ]
            if len(matched)!=1: raise ValueError('nonunique band/brick/type')
            return matched[0]
        img,weight=find('image'),find('invvar')
        if img.data.shape!=weight.data.shape: raise ValueError('image/weight shape mismatch')
        wi,ww=WCS(img.header,naxis=2),WCS(weight.header,naxis=2)
        for name,(ra,dec) in points.items():
            xi0,yi0=wi.world_to_pixel_values(ra,dec); xw0,yw0=ww.world_to_pixel_values(ra,dec)
            x,y,xw,yw=map(float,(xi0,yi0,xw0,yw0))
            if abs(x-xw)>1e-6 or abs(y-yw)>1e-6: raise ValueError('image/weight WCS mismatch')
            xx,yy=int(round(x)),int(round(y))
            if xx<2 or yy<2 or xx+2>=img.data.shape[1] or yy+2>=img.data.shape[0]: raise ValueError('window outside image')
            block=weight.data[yy-2:yy+3,xx-2:xx+3]; signal=img.data[yy-2:yy+3,xx-2:xx+3]
            if not np.isfinite(block).all() or not np.isfinite(signal).all(): raise ValueError('nonfinite window')
            rows.append({'band':band,'point':name,'center_xy':[xx,yy],'window_pixels':25,
                         'weight_zero_pixels':int(np.count_nonzero(block==0)),
                         'weight_positive_pixels':int(np.count_nonzero(block>0)),
                         'image_min':float(signal.min()),'image_max':float(signal.max())})
output={'input_sha256':body_sha,'brick':'1857p410','statistic':'descriptive 5x5 only',
        'rows':rows,'warning':'positive weight does not certify quality; zero-weight cause unknown'}
with (D/'LOCAL_WEIGHT_COUNTS.json').open('x',encoding='utf-8') as f:
    json.dump(output,f,indent=2,allow_nan=False); f.write('\n')
print(json.dumps(output,indent=2))
