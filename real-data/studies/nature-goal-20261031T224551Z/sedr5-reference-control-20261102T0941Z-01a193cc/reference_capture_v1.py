"""Three fixed public SEDR5 reference GETs using the reviewed capture engine."""
from pathlib import Path
import csv,hashlib,importlib.util,io,json,re,subprocess,sys

D=Path(__file__).resolve().parent
T=D.parent
S=D.parents[2]
C=S.parent/'coordination'
PRIOR=T/'held1533-sedr5-20261102T081926Z-01a193cc'
LIB=PRIOR/'capture_serial_v9.py'
TRANSPORT=PRIOR/'native_transport_sedr5_v5.py'
ROOT=PRIOR/'capture-v9/root.raw'
ROOT_RECORD=PRIOR/'capture-v9/root.json'
SAMPLE=T/'sedr5-catalogue-sample-20261102T085730Z-01a193cc/capture-v1/sample.raw'
BASE='https://casdc.china-vo.org/lamost/vac/sedr5/fits/'
DAY='20150309'
PLATE='HD110643N151055B02'
FILENAME='20150309_HD110643N151055B02_15_142.fit'
REFERENCE=DAY+'/'+PLATE+'/'+FILENAME
SPECID='20150309HD110643N151055B0215142'
STAGES=(('day',BASE+DAY+'/',500000,PLATE+'/'),
        ('plan',BASE+DAY+'/'+PLATE+'/',500000,FILENAME),
        ('product',BASE+REFERENCE,4000000,None))
PINS={'library_sha256':'3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5',
      'transport_sha256':'0f6c1d71336306b5e0bb319f5ced7cfe0e059af891d6632d28f49e634c2c8f42',
      'root_sha256':'cf493675ced7a1332ee9105c7c6043ce6a8257f0093e1848390e13f2d5f89a83',
      'root_record_sha256':'0c09c2824cb39e6e90b9a353593c10de871e8929bb8820f9e52e52c07656a2c8',
      'sample_sha256':'445105154437335a95353a37aecbe93609d89a48bdee3b99fbcb54be33de8513'}
FIELDS='specid obsdate planid spid fiberid iexp mjm sng sni subclass rv rverr rvpa teff logg feh minchi2 npix nabsline fratio fratio_b fratio_r obsid designation gid ra dec spec filename'.split()

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(65536),b''): h.update(chunk)
    return h.hexdigest()
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod); return mod
def sample_identity(raw):
    if not raw or len(raw)>262144 or b'\x00' in raw: raise ValueError('bad sample bytes')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig',errors='strict'),newline=''),strict=True)
    if reader.fieldnames!=FIELDS: raise ValueError('unexpected sample schema')
    matches=[]
    for row in reader:
        if None in row or any(v is None for v in row.values()): raise ValueError('bad sample row')
        if all(row[k]==v for k,v in {'specid':SPECID,'obsdate':'2015-03-09','planid':PLATE,'spid':'15',
                                     'fiberid':'142','iexp':'0','mjm':'82211011','obsid':'331215142',
                                     'filename':REFERENCE}.items()):
            matches.append(row)
    if len(matches)!=1: raise ValueError('sample identity not unique')
    return {'specid':SPECID,'obsdate':'2015-03-09','planid':PLATE,'spid':'15','fiberid':'142',
            'iexp':'0','mjm':'82211011','obsid':'331215142','filename':REFERENCE}

def validate_inputs(expected):
    manifest=D/'MANIFEST.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest)!=expected: raise ValueError('manifest mismatch')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    paths={'script_sha256':Path(__file__),'protocol_sha256':D/'PROTOCOL.md','library_sha256':LIB,
           'transport_sha256':TRANSPORT,'root_sha256':ROOT,'root_record_sha256':ROOT_RECORD,'sample_sha256':SAMPLE,
           'test_sha256':D/'test_reference_v1.py','test_result_sha256':D/'TEST_RESULT.json'}
    if any(sha(path)!=m[k] for k,path in paths.items()) or any(m[k]!=v for k,v in PINS.items()):
        raise ValueError('pinned input mismatch')
    test=json.loads((D/'TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode')!=0 or test.get('tests_expected')!=8
        or sha(D/'TEST_STDOUT.raw')!=test.get('stdout_sha256') or sha(D/'TEST_STDERR.raw')!=test.get('stderr_sha256')):
        raise ValueError('offline tests not established')
    lib=load('reference_validation_helpers',LIB)
    r=json.loads(ROOT_RECORD.read_text(encoding='utf-8'))
    if (r.get('status')!='HTTP_COMPLETE_UNPARSED' or r.get('http_status')!=200 or r.get('ssl_verify_result')!=0
        or r.get('num_redirects')!=0 or r.get('effective_url')!=BASE or r.get('returncode')!=0
        or r.get('cleanup_status')!='EXIT_CONFIRMED' or r.get('raw_sha256')!=PINS['root_sha256']
        or not lib.exact_child(ROOT.read_bytes(),DAY+'/')):
        raise ValueError('saved root index not validated')
    identity=sample_identity(SAMPLE.read_bytes())
    version=subprocess.run(['C:/Windows/System32/curl.exe','--disable','--version'],stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,timeout=5,check=True).stdout.decode('ascii').splitlines()[0]
    match=re.match(r'^curl (\d+)\.(\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups()))<(8,4,0): raise ValueError('curl body cap unavailable')
    return m,identity,version

def main(expected):
    validate_inputs(expected)
    lib=load('reviewed_serial_reference_capture',LIB)
    lib.D=D
    lib.STAGES=STAGES
    lib.TRANSPORT=TRANSPORT
    lib.LOCK=C/'sedr5-acquisition.lock'
    lib.validate_inputs=validate_inputs
    return lib.execute(expected)

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: reference_capture_v1.py MANIFEST_SHA256')
    raise SystemExit(main(sys.argv[1]))
