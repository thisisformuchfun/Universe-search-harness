"""Identity and LOGLAM ordering of one public reference; no flux/RV analysis."""
from datetime import datetime,timezone
from decimal import Decimal,InvalidOperation
from pathlib import Path
import csv,hashlib,json,os,re,sys,time
import numpy as np
from astropy.io import fits
import astropy

D=Path(__file__).resolve().parent
T=D.parent
PRODUCT=D/'capture-v9/product.raw'
CAPTURE=D/'capture-v9/RESULTS.json'
SAMPLE=T/'sedr5-catalogue-sample-20261102T085730Z-01a193cc/capture-v1/sample.raw'
PRODUCT_SHA='0e1c7ac03810cd41ad1df477f0977d82e92ba1bad71e442912ca282b339fb439'
CAPTURE_SHA='f5e6881fbe18a3444f53464f1e053bc2f6e41c70c02e5b97142f15b92a7c4899'
SAMPLE_SHA='445105154437335a95353a37aecbe93609d89a48bdee3b99fbcb54be33de8513'
SPECID='20150309HD110643N151055B0215142'
FILENAME='20150309/HD110643N151055B02/20150309_HD110643N151055B02_15_142.fit'
FIELDS='specid obsdate planid spid fiberid iexp mjm sng sni subclass rv rverr rvpa teff logg feh minchi2 npix nabsline fratio fratio_b fratio_r obsid designation gid ra dec spec filename'.split()

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(65536),b''): h.update(x)
    return h.hexdigest()
def identify(h,row):
    try:
        hra,hdec=Decimal(str(h['RA'])),Decimal(str(h['DEC']))
        sra,sdec=Decimal(row['ra']),Decimal(row['dec'])
        if (not all(x.is_finite() for x in (hra,hdec,sra,sdec))
            or not (Decimal(0)<=hra<Decimal(360) and Decimal(-90)<=hdec<=Decimal(90))
            or not (Decimal(0)<=sra<Decimal(360) and Decimal(-90)<=sdec<=Decimal(90))):
            raise ValueError('nonfinite or out-of-range coordinates')
        if (h.get('PLANID')!=row['planid'] or type(h.get('SPID')) is not int
            or type(h.get('FIBERID')) is not int or h['SPID']!=int(row['spid'])
            or h['FIBERID']!=int(row['fiberid'])
            or hra!=sra or hdec!=sdec
            or ('OBSID' in h and (type(h['OBSID']) is not int or str(h['OBSID'])!=row['obsid']))):
            raise ValueError('reference header does not match sample')
    except (KeyError,InvalidOperation,TypeError,OverflowError) as exc:
        raise ValueError('missing or malformed reference identity') from exc
    return {'planid':h['PLANID'],'spid':h['SPID'],'fiberid':h['FIBERID'],
            'catalogue_ra':str(h['RA']),'catalogue_dec':str(h['DEC']),
            'header_obsid_present':'OBSID' in h,'independent_astrometry_established':False}
def sample_row(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f,strict=True)
        if reader.fieldnames!=FIELDS: raise ValueError('unexpected sample schema')
        rows=[r for r in reader if r.get('specid')==SPECID and r.get('iexp')=='0' and r.get('filename')==FILENAME]
    if len(rows)!=1: raise ValueError('sample row not unique')
    return rows[0]
def order_counts(w):
    if np.ma.isMaskedArray(w): raise ValueError('masked wavelength array unsupported')
    a=np.asarray(w)
    if a.ndim!=1 or a.size<2 or a.dtype.kind not in 'fiu': raise ValueError('invalid wavelength array')
    finite=np.isfinite(a); pairs=finite[:-1]&finite[1:]
    up=pairs&(a[1:]>a[:-1]); down=pairs&(a[1:]<a[:-1]); equal=pairs&(a[1:]==a[:-1])
    return {'pixels':int(a.size),'finite':int(finite.sum()),'finite_adjacent_pairs':int(pairs.sum()),
            'increasing_pairs':int(up.sum()),'decreasing_pairs':int(down.sum()),'equal_pairs':int(equal.sum())}
def frame_labels(mjm,arms,expected_minute):
    if np.ma.isMaskedArray(mjm) or np.ma.isMaskedArray(arms) or len(mjm)!=6 or len(arms)!=6:
        raise ValueError('unexpected label shape or mask')
    def txt(x): return x.decode('ascii').strip() if isinstance(x,bytes) else str(x).strip()
    labels=[(txt(m),txt(a)) for m,a in zip(mjm,arms)]
    if (any(not re.fullmatch(r'\d{8}',minute) or arm not in ('b','r') for minute,arm in labels)
        or len(set(labels))!=len(labels) or expected_minute not in [minute for minute,arm in labels]):
        raise ValueError('ambiguous frame labels or missing nominal minute')
    return labels
def validate(expected):
    manifest=D/'METADATA_MANIFEST_V2.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest)!=expected: raise ValueError('manifest mismatch')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    paths={'script_sha256':Path(__file__),'protocol_sha256':D/'METADATA_PROTOCOL_V2.md',
           'test_sha256':D/'test_reference_metadata_v2.py','test_result_sha256':D/'METADATA_V2_TEST_RESULT.json',
           'product_sha256':PRODUCT,'capture_sha256':CAPTURE,'sample_sha256':SAMPLE}
    if any(sha(p)!=m[k] for k,p in paths.items()) or m['product_sha256']!=PRODUCT_SHA or m['capture_sha256']!=CAPTURE_SHA or m['sample_sha256']!=SAMPLE_SHA:
        raise ValueError('pinned input mismatch')
    test=json.loads((D/'METADATA_V2_TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode')!=0 or test.get('tests_expected')!=11 or sha(D/'METADATA_V2_TEST_STDOUT.raw')!=test.get('stdout_sha256')
        or sha(D/'METADATA_V2_TEST_STDERR.raw')!=test.get('stderr_sha256')): raise ValueError('synthetic tests not established')
    capture=json.loads(CAPTURE.read_text(encoding='utf-8'))
    if (capture.get('status')!='PRODUCT_TRANSPORT_PREFIX_ONLY_IDENTITY_PENDING'
        or capture.get('request_files_present')!=3 or capture.get('lease_released') is not True
        or capture.get('owned_process_exit_confirmed') is not True): raise ValueError('capture state mismatch')
    return sample_row(SAMPLE)
def main(expected):
    row=validate(expected); start=time.perf_counter_ns(); began=datetime.now(timezone.utc).isoformat()
    with fits.open(PRODUCT,memmap=False) as hdus:
        if len(hdus)<2 or type(hdus[1]).__name__!='BinTableHDU' or len(hdus[1].data)!=1:
            raise ValueError('unexpected FITS structure')
        header=hdus[1].header; identity=identify(header,row); data=hdus[1].data
        mjm,arms,waves=data['MJM'][0],data['COLOR'][0],data['LOGLAM'][0]
        if np.ma.isMaskedArray(waves) or waves.shape!=(6,4136):
            raise ValueError('unexpected frame shape or masks')
        labels=frame_labels(mjm,arms,row['mjm'])
        frames=[{'mjm':minute,'arm':arm,**order_counts(waves[i])} for i,(minute,arm) in enumerate(labels)]
        dates={key:{'value':header.get(key),'comment':header.comments[key] if key in header else None}
               for key in ('DATE-OBS','DATE-BEG','DATE-END')}
    result={'started_utc':began,'finished_utc':datetime.now(timezone.utc).isoformat(),
            'elapsed_seconds':(time.perf_counter_ns()-start)/1e9,'manifest_sha256':expected,
            'product_sha256':PRODUCT_SHA,'sample_sha256':SAMPLE_SHA,'numpy_version':np.__version__,'astropy_version':astropy.__version__,
            'sample_identity':{k:row[k] for k in ('specid','obsdate','planid','spid','fiberid','iexp','mjm','obsid','ra','dec','filename')},
            'matched_fits_identity':identity,'date_header_strings':dates,'frames':frames,
            'scope':'one matched catalogue reference and LOGLAM ordering; no flux, RV, calibration or source-attribution inference',
            'holdout_evaluated':False}
    encoded=(json.dumps(result,indent=2,allow_nan=False)+'\n').encode()
    out=D/'metadata-v2'; out.mkdir(exist_ok=False)
    with (out/'RESULTS.json').open('xb') as f: f.write(encoded); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'status':'REFERENCE_IDENTITY_AND_ORDER_DESCRIBED','frames':len(frames),'result_sha256':sha(out/'RESULTS.json')}))
if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: reference_metadata_v2.py MANIFEST_SHA256')
    main(sys.argv[1])
