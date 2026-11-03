"""Non-production, paired monotonic array orientation; no RV inference."""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json,os,re,sys,time
import numpy as np
from astropy.io import fits
import astropy

D=Path(__file__).resolve().parent
T=D.parent
PRODUCT=T/'held1533-sedr5-20261102T081926Z-01a193cc/capture-v9/product.raw'
PRIOR=T/'sedr5-pixel-feasibility-v2-20261102T0928Z-01a193cc/RESULTS.json'
PRODUCT_SHA='7a33d6a4ff8594c33b43181309bc5ad4e0739e6245943e06ba099172d04742de'
PRIOR_SHA='ce14934e290c8e1212f515f53158ab21d8ba8ce5bab9e38ff2c26187b53d2548'
FIELDS=('LOGLAM','FLUX','INVVAR','PIXELMASK','SKYFLUX','FLUXCORR')
LABELS=[('82124924','b'),('82124952','b'),('82124981','b'),
        ('82124924','r'),('82124952','r'),('82124981','r')]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for x in iter(lambda:f.read(65536),b''): h.update(x)
    return h.hexdigest()

def orient(fields):
    if set(fields)!=set(FIELDS): raise ValueError('unexpected fields')
    if any(np.ma.isMaskedArray(x) for x in fields.values()): raise ValueError('masked arrays unsupported')
    arrays={name:np.asarray(fields[name]) for name in FIELDS}
    if any(a.ndim!=1 for a in arrays.values()) or len({a.shape for a in arrays.values()})!=1:
        raise ValueError('unaligned pixel dimensions')
    if any(a.dtype.kind not in 'fiu' for a in arrays.values()) or arrays['PIXELMASK'].dtype.kind not in 'iu':
        raise ValueError('unsupported pixel dtype')
    wave=arrays['LOGLAM']
    if wave.size<2 or not np.isfinite(wave).all(): raise ValueError('invalid wavelength array')
    ascending=bool(np.all(wave[1:]>wave[:-1]))
    descending=bool(np.all(wave[1:]<wave[:-1]))
    if not (ascending or descending): raise ValueError('wavelength not strictly monotonic')
    oriented={name:(a[::-1] if descending else a).copy() for name,a in arrays.items()}
    return oriented,descending

def validate(expected):
    manifest=D/'MANIFEST.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest)!=expected: raise ValueError('manifest mismatch')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    paths={'script_sha256':Path(__file__),'protocol_sha256':D/'PROTOCOL.md','test_sha256':D/'test_orientation_v1.py',
           'test_result_sha256':D/'TEST_RESULT.json','product_sha256':PRODUCT,'prior_result_sha256':PRIOR}
    if any(sha(path)!=m[key] for key,path in paths.items()) or m['product_sha256']!=PRODUCT_SHA or m['prior_result_sha256']!=PRIOR_SHA:
        raise ValueError('input hash mismatch')
    test=json.loads((D/'TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode')!=0 or test.get('tests_expected')!=8
        or sha(D/'TEST_STDOUT.raw')!=test.get('stdout_sha256') or sha(D/'TEST_STDERR.raw')!=test.get('stderr_sha256')):
        raise ValueError('offline tests not established')
    return m

def main(expected):
    validate(expected); start=time.perf_counter_ns(); began=datetime.now(timezone.utc).isoformat()
    with fits.open(PRODUCT,memmap=False) as hdus:
        if len(hdus)<2 or type(hdus[1]).__name__!='BinTableHDU' or len(hdus[1].data)!=1:
            raise ValueError('unexpected FITS structure')
        data=hdus[1].data
        def txt(x): return x.decode('ascii').strip() if isinstance(x,bytes) else str(x).strip()
        mjm,arms=data['MJM'][0],data['COLOR'][0]
        if (np.ma.isMaskedArray(mjm) or np.ma.isMaskedArray(arms) or len(mjm)!=6 or len(arms)!=6
            or [(txt(m),txt(a)) for m,a in zip(mjm,arms)]!=LABELS): raise ValueError('unexpected labels')
        columns={name:data[name][0] for name in FIELDS}
        if any(np.ma.isMaskedArray(a) or a.shape!=(6,4136) for a in columns.values()):
            raise ValueError('unsupported array shape or mask')
        frames=[]
        for i,(minute,arm) in enumerate(LABELS):
            original={name:columns[name][i] for name in FIELDS}
            ordered,reversed_order=orient(original)
            roundtrip={name:(ordered[name][::-1] if reversed_order else ordered[name]).tobytes()==original[name].tobytes()
                       and ordered[name].dtype==original[name].dtype for name in FIELDS}
            if not all(roundtrip.values()): raise ValueError('byte roundtrip mismatch')
            frames.append({'mjm':minute,'arm':arm,'input_orientation':'descending' if reversed_order else 'ascending',
                           'first_loglam':float(original['LOGLAM'][0]),'last_loglam':float(original['LOGLAM'][-1]),
                           'all_fields_roundtrip_byte_equal':True})
    result={'started_utc':began,'finished_utc':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,'manifest_sha256':expected,
            'product_sha256':PRODUCT_SHA,'prior_result_sha256':PRIOR_SHA,'numpy_version':np.__version__,
            'astropy_version':astropy.__version__,'scope':'paired orientation prototype only; no RV or calibration inference',
            'holdout_evaluated':False,'frames':frames}
    encoded=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    with (D/'RESULTS.json').open('xb') as f: f.write(encoded); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'status':'PAIRED_ROUNDTRIP_COMPLETE','frames':len(frames),'result_sha256':sha(D/'RESULTS.json')}))

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: orientation_v1.py MANIFEST_SHA256')
    main(sys.argv[1])
