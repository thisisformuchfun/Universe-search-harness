"""Read bounded optical-mask windows under two WCS interpretations; no source inference."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
import numpy as np
from astropy.coordinates import SkyCoord
import astropy.units as u
from astropy.io import fits
from astropy.wcs import WCS
from astropy.wcs.utils import wcs_to_celestial_frame

D=Path(__file__).resolve().parent
IMAGE=D.parent/'legacy1533-target-v2-20261102T1137Z-01a193cc'
BIT_NAMES=('NPRIMARY','BRIGHT','SATUR_G','SATUR_R','SATUR_Z','ALLMASK_G','ALLMASK_R','ALLMASK_Z',
           'WISEM1','WISEM2','BAILOUT','MEDIUM','GALAXY','CLUSTER','SATUR_I','ALLMASK_I')
def decode(v):
    value=int(v)&0xffff
    return {name:bool(value&(1<<bit)) for bit,name in enumerate(BIT_NAMES)}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    raw=D/'capture/mask_target.raw'; inv=json.loads((D/'MASK_HEADER_INVENTORY.json').read_text(encoding='utf-8'))
    image_raw=IMAGE/'capture/legacy_target.raw'; image_inv=json.loads((IMAGE/'TARGET_FITS_INVENTORY.json').read_text(encoding='utf-8'))
    result=json.loads((D/'capture/RESULT.json').read_text(encoding='utf-8'))
    finish=json.loads((D/'capture/FINISH.json').read_text(encoding='utf-8'))
    if (sha(raw)!=inv['sha256'] or sha(raw)!=result['body_sha256'] or sha(image_raw)!=image_inv['input_sha256']
        or not inv['fits_verify_exception_passed'] or inv['warning_types'] or not finish['lease_released']
        or not finish['owned_process_exit_confirmed'] or finish['terminal_sha256']!=sha(D/'capture/RESULT.json')):
        raise ValueError('input or transport proof mismatch')
    h=inv['hdus'][1]['fields']
    if (h.get('ZCMPTYPE')!='HCOMPRESS_1' or h.get('ZBITPIX')!=16 or h.get('ZNAXIS1')!=3600
        or h.get('ZNAXIS2')!=3600 or h.get('ZTILE1')!=100 or h.get('ZTILE2')!=100
        or h.get('EXTNAME')!='MASKBITS' or h.get('BRICK')!='1857p410'):
        raise ValueError('unexpected target optical-mask geometry')
    rows=[]; checks=[]
    with fits.open(image_raw,mode='readonly',memmap=False) as imgs, fits.open(raw,mode='readonly',memmap=True,lazy_load_hdus=False) as masks:
        matches=[hdu for hdu in imgs if hdu.header.get('BRICK')=='1857p410' and hdu.header.get('BAND')=='g' and hdu.header.get('IMAGETYP')=='image']
        if len(matches)!=1 or type(masks[1]).__name__!='CompImageHDU':raise ValueError('ambiguous image or mask')
        img=matches[0]; mask=masks[1]; cw=WCS(img.header,naxis=2); mw=WCS(mask.header,naxis=2)
        if not cw.has_celestial or not mw.has_celestial:raise ValueError('missing celestial WCS')
        for x,y in [(96.,96.),(30.,30.),(160.,30.),(30.,160.),(160.,160.)]:
            ra,dec=cw.pixel_to_world_values(x,y); mx,my=mw.world_to_pixel_values(ra,dec)
            dx=float(mx)-(x+img.header['BRICK_X0']); dy=float(my)-(y+img.header['BRICK_Y0'])
            checks.append({'image_xy':[x,y],'numeric_grid_residual_pixels':[dx,dy]})
        max_res=max(abs(v) for c in checks for v in c['numeric_grid_residual_pixels'])
        if max_res>1e-4:raise ValueError('numeric grid does not match same brick')
        for name,(ra,dec) in image_inv['points'].items():
            numeric=mw.world_to_pixel_values(ra,dec)
            aware=mw.world_to_pixel(SkyCoord(ra=ra*u.deg,dec=dec*u.deg,frame='icrs'))
            mappings={'numeric':[float(v) for v in numeric],'frame_aware_icrs':[float(v) for v in aware]}
            sets={}
            for scenario,(x,y) in mappings.items():
                if not np.isfinite(x) or not np.isfinite(y):raise ValueError('nonfinite position')
                xx,yy=int(round(x)),int(round(y))
                if not(2<=xx<3598 and 2<=yy<3598):raise ValueError('window out of bounds')
                sets[scenario]={(xx+dx,yy+dy) for dy in range(-2,3) for dx in range(-2,3)}
            union=sets['numeric']|sets['frame_aware_icrs']
            minx,maxx=min(x for x,y in union),max(x for x,y in union)
            miny,maxy=min(y for x,y in union),max(y for x,y in union)
            if maxx-minx>8 or maxy-miny>8:raise ValueError('unexpected frame disagreement')
            section=np.asarray(mask.section[miny:maxy+1,minx:maxx+1])
            if not np.issubdtype(section.dtype,np.integer):raise ValueError('noninteger mask')
            values={(x,y):int(section[y-miny,x-minx])&0xffff for x,y in union}
            def summarise(coords):
                return {'pixel_count':len(coords),'counts_by_bit':{b:sum(decode(values[p])[b] for p in coords) for b in BIT_NAMES},
                        'unique_values':sorted(set(values[p] for p in coords))}
            rows.append({'point':name,'ra_dec': [ra,dec],'mapping_xy':mappings,
               'numeric':summarise(sets['numeric']),'frame_aware_icrs':summarise(sets['frame_aware_icrs']),
               'union':summarise(union),'union_pixels_xy':[[x,y] for x,y in sorted(union)]})
        frames={'image_header_radesys':img.header.get('RADESYS'),'image_header_equinox':img.header.get('EQUINOX'),
                'mask_header_radesys':mask.header.get('RADESYS'),'mask_header_equinox':mask.header.get('EQUINOX'),
                'astropy_image_frame':str(wcs_to_celestial_frame(cw)), 'astropy_mask_frame':str(wcs_to_celestial_frame(mw))}
        loaded=getattr(mask,'_data_loaded',None)
    out={'created_utc':datetime.now(timezone.utc).isoformat(),'mask_sha256':sha(raw),'image_sha256':sha(image_raw),
         'brick':'1857p410','frames':frames,'numeric_grid_checks':checks,'max_numeric_grid_residual_pixels':max_res,
         'full_optical_data_loaded':loaded,'rows':rows,
         'interpretation':'provider flags at sampled pixels only; frame union is not a position bound or orbit evidence'}
    with (D/'TARGET_MASK_WINDOWS.json').open('x',encoding='utf-8') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'mask_sha256':out['mask_sha256'],'frames':frames,'full_optical_data_loaded':loaded,
      'points':[{'point':r['point'],'mappings':r['mapping_xy'], 'union_count':r['union']['pixel_count'],
                 'satur_z':r['union']['counts_by_bit']['SATUR_Z'],'allmask_z':r['union']['counts_by_bit']['ALLMASK_Z'],
                 'values':r['union']['unique_values']} for r in rows]},indent=2))
if __name__=='__main__':main()
