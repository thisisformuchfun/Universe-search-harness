"""Validate control-mask WCS with bounded tile sections; not a held-field test."""
from pathlib import Path
import hashlib,json
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
D=Path(__file__).resolve().parent
control=D.parent/'legacy-control-v5-20261102T1133Z-01a193cc'
raw=D/'capture/mask_control.raw'; inv=json.loads((D/'MASK_HEADER_INVENTORY.json').read_text(encoding='utf-8'))
sha=hashlib.sha256(raw.read_bytes()).hexdigest()
if sha!=inv['sha256'] or not inv['fits_verify_exception_passed'] or inv['warning_types']:
    raise ValueError('physical header inventory mismatch')
h=inv['hdus'][1]['fields']
if (h.get('ZCMPTYPE')!='HCOMPRESS_1' or h.get('ZBITPIX')!=16 or h.get('ZNAXIS1')!=3600
    or h.get('ZNAXIS2')!=3600 or h.get('ZTILE1')!=100 or h.get('ZTILE2')!=100
    or h.get('EXTNAME')!='MASKBITS' or h.get('BRICK')!='1548p465'):
    raise ValueError('unexpected compressed optical mask geometry')
def flags(v):
    n=int(v)&0xffff
    names=('SATUR_G','SATUR_R','SATUR_Z','ALLMASK_G','ALLMASK_R','ALLMASK_Z')
    return {name:bool(n & (1<<bit)) for name,bit in zip(names,range(2,8))}
assert all(flags(1<<bit)[name] for name,bit in zip(('SATUR_G','SATUR_R','SATUR_Z','ALLMASK_G','ALLMASK_R','ALLMASK_Z'),range(2,8)))
assert not any(flags(0).values())
with fits.open(control/'capture/legacy_control.raw',mode='readonly',memmap=False) as images, \
     fits.open(raw,mode='readonly',memmap=True,lazy_load_hdus=False) as masks:
    image=[i for i in images if i.header.get('BAND')=='g' and i.header.get('IMAGETYP')=='image' and i.header.get('BRICK')=='1548p465']
    if len(image)!=1: raise ValueError('control image not unique')
    image=image[0]; optical=masks[1]
    if type(optical).__name__!='CompImageHDU': raise ValueError('not compressed image')
    wcut=WCS(image.header,naxis=2); wmask=WCS(optical.header,naxis=2)
    if not wcut.has_celestial or not wmask.has_celestial:raise ValueError('missing celestial WCS')
    checks=[]
    for x,y in [(64.0,64.0),(15.0,15.0),(112.0,15.0),(15.0,112.0),(112.0,112.0)]:
        ra,dec=wcut.pixel_to_world_values(x,y); mx,my=wmask.world_to_pixel_values(ra,dec)
        mx,my=float(mx),float(my)
        dx=mx-(x+image.header['BRICK_X0']);dy=my-(y+image.header['BRICK_Y0'])
        checks.append({'cutout_xy':[x,y],'mask_xy':[mx,my],'offset_residual_pixels':[float(dx),float(dy)]})
    x,y=wmask.world_to_pixel_values(154.7709,46.4537); x,y=float(x),float(y); xx,yy=int(round(x)),int(round(y))
    if not (2<=xx<3598 and 2<=yy<3598):raise ValueError('control not inside mask')
    section=np.asarray(optical.section[yy-2:yy+3,xx-2:xx+3])
    if section.shape!=(5,5) or not np.issubdtype(section.dtype,np.integer):raise ValueError('invalid optical mask section')
    center=int(section[2,2])&0xffff
    output={'input_sha256':sha,'control_image_sha256':hashlib.sha256((control/'capture/legacy_control.raw').read_bytes()).hexdigest(),
       'mask_shape':[3600,3600],'tile_shape':[100,100],'sample_xy':[xx,yy],
       'control_section_values':[[int(v)&0xffff for v in row] for row in section],
       'center_bit_flags':flags(center),'wcs_registration_checks':checks,
       'max_abs_registration_residual_pixels':max(abs(v) for c in checks for v in c['offset_residual_pixels']),
       'synthetic_bit_decoding_passed':True,
       'interpretation':'format and alignment control only; no held-field mask or orbit'}
with (D/'MASK_CONTROL_INSPECTION.json').open('x',encoding='utf-8') as f:json.dump(output,f,indent=2,allow_nan=False);f.write('\n')
print(json.dumps(output,indent=2))
