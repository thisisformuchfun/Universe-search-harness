"""Compare numeric and frame-aware control WCS; no held-field mask data."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame
D=Path(__file__).resolve().parent
raw=D/'capture/mask_control.raw'; image=D.parent/'legacy-control-v5-20261102T1133Z-01a193cc/capture/legacy_control.raw'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
header=json.loads((D/'MASK_HEADER_INVENTORY.json').read_text(encoding='utf-8'))
if h(raw)!=header['sha256']:raise ValueError('mask input mismatch')
with fits.open(image,memmap=False) as a, fits.open(raw,memmap=True,lazy_load_hdus=False) as b:
 cut=[x for x in a if x.header.get('BAND')=='g' and x.header.get('IMAGETYP')=='image' and x.header.get('BRICK')=='1548p465']
 if len(cut)!=1:raise ValueError('control cutout ambiguity')
 cut=cut[0]; mask=b[1]; cw=WCS(cut.header,naxis=2); mw=WCS(mask.header,naxis=2)
 cf=wcs_to_celestial_frame(cw); mf=wcs_to_celestial_frame(mw)
 samples=[]
 for x,y in [(64.0,64.0),(15.0,15.0),(112.0,15.0),(15.0,112.0),(112.0,112.0)]:
    world=cw.pixel_to_world(x,y)
    numeric=mw.world_to_pixel_values(world.icrs.ra.deg,world.icrs.dec.deg)
    aware=mw.world_to_pixel(world)
    numeric=[float(v) for v in numeric]; aware=[float(v) for v in aware]
    samples.append({'cutout_xy':[x,y],'mask_numeric_xy':numeric,'mask_frame_aware_xy':aware,
      'numeric_vs_frame_aware_offset_pixels':[aware[i]-numeric[i] for i in (0,1)]})
obj={'created_utc':datetime.now(timezone.utc).isoformat(),'mask_sha256':h(raw),'image_sha256':h(image),
     'cutout_radesys_card':cut.header.get('RADESYS'),'cutout_equinox_card':cut.header.get('EQUINOX'),
     'mask_radesys_card':mask.header.get('RADESYS'),'mask_equinox_card':mask.header.get('EQUINOX'),
     'astropy_cutout_frame':str(cf),'astropy_mask_frame':str(mf),'samples':samples,
     'interpretation':'numeric grid agreement does not resolve frame convention or absolute astrometry'}
with (D/'MASK_FRAME_COMPARISON.json').open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps(obj,indent=2))
