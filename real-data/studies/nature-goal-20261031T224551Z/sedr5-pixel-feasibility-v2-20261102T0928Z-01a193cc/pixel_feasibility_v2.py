"""Descriptive statistics for one pinned public SEDR5 product; no RV fit."""
from datetime import datetime,timezone
from pathlib import Path
from fractions import Fraction
import hashlib,json,os,re,sys,time
import numpy as np
from astropy.io import fits
import astropy

D=Path(__file__).resolve().parent
T=D.parent
PRODUCT=T/'held1533-sedr5-20261102T081926Z-01a193cc/capture-v9/product.raw'
PRODUCT_SHA='7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de'
LABELS=[('82124924','b'),('82124952','b'),('82124981','b'),
        ('82124924','r'),('82124952','r'),('82124981','r')]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    return h.hexdigest()

def frame_metrics(flux,ivar,loglam,mask):
    if any(np.ma.isMaskedArray(x) for x in (flux,ivar,loglam,mask)):
        raise ValueError('masked arrays are unsupported')
    arrays=[np.asarray(x) for x in (flux,ivar,loglam,mask)]
    if any(a.ndim!=1 for a in arrays) or len({a.shape for a in arrays})!=1:
        raise ValueError('frame arrays have incompatible dimensions')
    f,v,w,m=arrays
    if any(a.dtype.kind not in 'fiu' for a in (f,v,w)) or m.dtype.kind not in 'iu':
        raise ValueError('unexpected array dtype')
    finite_f=np.isfinite(f); finite_v=np.isfinite(v); finite_w=np.isfinite(w)
    positive_v=finite_v & (v>0); zero_mask=m==0
    joint=finite_f & positive_v & finite_w & zero_mask
    with np.errstate(over='ignore',invalid='ignore'):
        proxy=f[joint].astype(np.float64)*np.sqrt(v[joint].astype(np.float64))
    proxy=proxy[np.isfinite(proxy)]
    adjacent=finite_w[:-1] & finite_w[1:]
    nonincreasing=adjacent & (w[1:]<=w[:-1])
    ordered=np.sort(proxy)
    if not ordered.size: median=None
    elif ordered.size%2: median=float(ordered[ordered.size//2])
    else:
        a=float(ordered[ordered.size//2-1]); b=float(ordered[ordered.size//2])
        median=float((Fraction.from_float(a)+Fraction.from_float(b))/2)
    return {'pixels':int(f.size),'finite_flux':int(finite_f.sum()),'finite_invvar':int(finite_v.sum()),
            'positive_invvar':int(positive_v.sum()),'finite_loglam':int(finite_w.sum()),
            'zero_pixelmask':int(zero_mask.sum()),'joint_numeric_count':int(joint.sum()),
            'finite_adjacent_loglam_pairs':int(adjacent.sum()),
            'nonincreasing_finite_loglam_pairs':int(nonincreasing.sum()),
            'finite_signed_proxy_count':int(proxy.size),
            'median_signed_flux_sqrt_invvar_proxy':median}

def labels(data):
    def txt(value):
        if isinstance(value,bytes): return value.decode('ascii').strip()
        return str(value).strip()
    mjm,color=data['MJM'][0],data['COLOR'][0]
    if np.ma.isMaskedArray(mjm) or np.ma.isMaskedArray(color) or len(mjm)!=len(LABELS) or len(color)!=len(LABELS):
        raise ValueError('unexpected label dimensions or mask')
    return [(txt(m),txt(c)) for m,c in zip(mjm,color)]

def validate(expected):
    manifest=D/'MANIFEST.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest)!=expected: raise ValueError('manifest mismatch')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    paths={'script_sha256':Path(__file__),'protocol_sha256':D/'PROTOCOL.md','test_sha256':D/'test_pixel_v2.py',
           'test_result_sha256':D/'TEST_RESULT.json','product_sha256':PRODUCT}
    if any(sha(path)!=m[k] for k,path in paths.items()) or m['product_sha256']!=PRODUCT_SHA:
        raise ValueError('input hash mismatch')
    test=json.loads((D/'TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode')!=0 or test.get('tests_expected')!=11
        or sha(D/'TEST_STDOUT.raw')!=test.get('stdout_sha256') or sha(D/'TEST_STDERR.raw')!=test.get('stderr_sha256')):
        raise ValueError('offline tests not established')
    return m

def main(expected):
    validate(expected); start=time.perf_counter_ns(); began=datetime.now(timezone.utc).isoformat()
    with fits.open(PRODUCT,memmap=False) as hdus:
        if len(hdus)<2 or type(hdus[1]).__name__!='BinTableHDU' or len(hdus[1].data)!=1:
            raise ValueError('unsupported FITS structure')
        data=hdus[1].data
        if labels(data)!=LABELS: raise ValueError('unexpected frame labels')
        columns={name:data[name][0] for name in ('FLUX','INVVAR','LOGLAM','PIXELMASK')}
        if any(np.ma.isMaskedArray(x) for x in columns.values()): raise ValueError('masked arrays are unsupported')
        if any(x.shape!=(6,4136) for x in columns.values()): raise ValueError('unexpected spectral dimensions')
        frames=[]
        for i,(mjm,arm) in enumerate(LABELS):
            frames.append({'mjm':mjm,'arm':arm,**frame_metrics(*(columns[n][i] for n in ('FLUX','INVVAR','LOGLAM','PIXELMASK')))})
    result={'started_utc':began,'finished_utc':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,'manifest_sha256':expected,
            'product_sha256':PRODUCT_SHA,'shape':[6,4136],'numpy_version':np.__version__,'astropy_version':astropy.__version__,
            'scope':'descriptive numerical availability; proxy unvalidated; no RV fit or source attribution',
            'holdout_evaluated':False,'frames':frames}
    output=D/'RESULTS.json'
    encoded=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode('utf-8')
    with output.open('xb') as f:
        f.write(encoded); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'status':'DESCRIPTIVE_ARRAY_CHECK_COMPLETE','frames':len(frames),'result_sha256':sha(output)}))

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: pixel_feasibility_v2.py MANIFEST_SHA256')
    main(sys.argv[1])
