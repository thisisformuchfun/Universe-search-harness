"""One target-only request after validating the immutable successful control."""
from datetime import datetime,timedelta,timezone
from pathlib import Path
import hashlib,importlib.util,json,os,re,subprocess,sys,time,uuid
import schema_v1 as schema

D=Path(__file__).resolve().parent
T=D.parent
S=D.parents[2]
C=S.parent/'coordination'
LOCK=C/'sedr5-acquisition.lock'
PRIOR=T/'sedr5-exact-query-20261102T0912Z-01a193cc'
SAMPLE=T/'sedr5-catalogue-sample-20261102T085730Z-01a193cc/capture-v1/sample.raw'
LIB=T/'held1533-sedr5-20261102T081926Z-01a193cc/capture_serial_v9.py'
CONTROL_OUT=PRIOR/'capture-v1'
URL='https://nadc.china-vo.org/data/data/general/sedr5/sexprv/build.csvs'
PRIOR_MANIFEST='6fefd5df5810567921011256e37c69c7aa18198d26847575447dc2b9adbe7add'
CONTROL_BODY='06add9fe268e26af96d5ec1c6cd4b62a2bab32c169039851aaff3353d22e0adc'
TARGET_BODY='4f6e5a30cb9eded0d5a32f6ee45912ca718d8ba8385a179b076869cc4b0017c5'
CONTROL_RAW='c87ea085110605f3ecd2023caa3ea321a4ad3c580a431df0f460ad2368f25759'
SAMPLE_RAW='445105154437335a95353a37aecbe93609d89a48bdee3b99fbcb54be33de8513'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    return h.hexdigest()
def save(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(obj,f,indent=2,allow_nan=False); f.write('\n'); f.flush(); os.fsync(f.fileno())
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module); return module

def check_control(record,request,result,owned,raw,headers,sample,control_body,target_body,lib):
    req=request.get('request',{})
    if (record.get('status')!='HTTP_COMPLETE_UNPARSED' or record.get('http_status')!=200
        or record.get('ssl_verify_result')!=0 or record.get('num_redirects')!=0
        or record.get('effective_url')!=URL or record.get('returncode')!=0
        or record.get('cleanup_status')!='EXIT_CONFIRMED' or record.get('limit_failure') is not None
        or any(record.get(k)!=0 for k in ('body_overage_bytes','header_overage_bytes','native_stdout_overage_bytes','native_stderr_overage_bytes'))
        or result.get('status')!='STOP_EXCEPTION' or result.get('request_files')!=['control.request.json']
        or result.get('lease_released') is not True or result.get('owned_process_exit_confirmed') is not True
        or req.get('name')!='control' or req.get('method')!='POST' or req.get('url')!=URL
        or req.get('manifest_sha256')!=PRIOR_MANIFEST or req.get('payload_sha256')!=CONTROL_BODY):
        raise ValueError('control transport or request prerequisite failed')
    identity=owned.get('owned_process',{})
    if (not identity or identity!=result.get('last_owned_process') or identity.get('pid')!=record.get('owned_pid')
        or identity.get('identity_status')!='OWNED_HANDLE_CREATION_TIME_OBSERVED'):
        raise ValueError('control process prerequisite failed')
    if (hashlib.sha256(raw).hexdigest()!=CONTROL_RAW or record.get('raw_sha256')!=CONTROL_RAW
        or hashlib.sha256(headers).hexdigest()!=record.get('headers_sha256')
        or not lib.valid_http_headers(headers,200,len(raw))
        or hashlib.sha256(sample).hexdigest()!=SAMPLE_RAW
        or hashlib.sha256(control_body).hexdigest()!=CONTROL_BODY
        or hashlib.sha256(target_body).hexdigest()!=TARGET_BODY):
        raise ValueError('control evidence hash or headers failed')
    if control_body.replace(schema.CONTROL.encode(),b'<fixed-filename>') != target_body.replace(schema.TARGET.encode(),b'<fixed-filename>'):
        raise ValueError('target body differs beyond filename')
    sample_kind,sample_rows=schema.parse_csv(sample)
    control_kind,control_rows=schema.parse_csv(raw)
    chosen=[r for r in sample_rows if r['filename']==schema.CONTROL]
    if (sample_kind!='SAMPLE_UNPREFIXED' or control_kind!='QUERY_PREFIXED'
        or not schema.control_passes(chosen) or not schema.control_passes(control_rows)):
        raise ValueError('corrected known-positive control failed')
    return {'sample_schema':sample_kind,'control_schema':control_kind,'control_rows':len(control_rows),
            'same_filename_and_sample_tuple':True,'target_identity_validated':False}

def validate(expected):
    manifest=D/'MANIFEST.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest)!=expected: raise ValueError('manifest mismatch')
    m=json.loads(manifest.read_text(encoding='utf-8'))
    paths={'script_sha256':Path(__file__),'schema_sha256':D/'schema_v1.py','protocol_sha256':D/'PROTOCOL.md',
           'transport_sha256':D/'native_transport_post_v1.py','library_sha256':LIB,'test_sha256':D/'test_schema_v1.py',
           'test_control_sha256':D/'test_control_v1.py',
           'test_result_sha256':D/'TEST_RESULT.json','target_body_sha256':D/'target.body',
           'sample_sha256':SAMPLE,'prior_manifest_sha256':PRIOR/'MANIFEST.json',
           'control_body_sha256':PRIOR/'control.body','prior_target_body_sha256':PRIOR/'target.body',
           'control_raw_sha256':CONTROL_OUT/'control.raw','control_headers_sha256':CONTROL_OUT/'control.headers',
           'control_record_sha256':CONTROL_OUT/'control.json','control_request_sha256':CONTROL_OUT/'control.request.json',
           'control_owned_sha256':CONTROL_OUT/'control.owned.json','prior_results_sha256':CONTROL_OUT/'RESULTS.json'}
    if any(sha(path)!=m[key] for key,path in paths.items()): raise ValueError('pinned evidence mismatch')
    if (m['prior_manifest_sha256']!=PRIOR_MANIFEST or m['control_body_sha256']!=CONTROL_BODY
        or m['target_body_sha256']!=TARGET_BODY or m['prior_target_body_sha256']!=TARGET_BODY
        or m['control_raw_sha256']!=CONTROL_RAW or m['sample_sha256']!=SAMPLE_RAW
        or m['library_sha256']!='3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5'):
        raise ValueError('unexpected pinned evidence')
    test=json.loads((D/'TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode')!=0 or test.get('tests_expected')!=12
        or sha(D/'TEST_STDOUT.raw')!=test.get('stdout_sha256') or sha(D/'TEST_STDERR.raw')!=test.get('stderr_sha256')):
        raise ValueError('offline tests not established')
    lib=load('capture_helpers',LIB)
    record=json.loads((CONTROL_OUT/'control.json').read_text(encoding='utf-8'))
    request=json.loads((CONTROL_OUT/'control.request.json').read_text(encoding='utf-8'))
    result=json.loads((CONTROL_OUT/'RESULTS.json').read_text(encoding='utf-8'))
    owned=json.loads((CONTROL_OUT/'control.owned.json').read_text(encoding='utf-8'))
    if record.get('request_sha256')!=m['control_request_sha256'] or list(CONTROL_OUT.glob('target.*')):
        raise ValueError('prior request provenance mismatch')
    control=check_control(record,request,result,owned,(CONTROL_OUT/'control.raw').read_bytes(),
                          (CONTROL_OUT/'control.headers').read_bytes(),SAMPLE.read_bytes(),
                          (PRIOR/'control.body').read_bytes(),(D/'target.body').read_bytes(),lib)
    version=subprocess.run(['C:/Windows/System32/curl.exe','--disable','--version'],stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE,timeout=5,check=True).stdout.decode('ascii').splitlines()[0]
    match=re.match(r'^curl (\d+)\.(\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups()))<(8,4,0): raise ValueError('curl streaming body cap unavailable')
    return m,lib,control,version

def main(expected):
    m,lib,control,version=validate(expected)
    tr=load('post_transport',D/'native_transport_post_v1.py')
    tr.PAYLOADS={'target':(D/'target.body',m['target_body_sha256'])}
    tr.LIMITS.update(body_bytes=schema.CAP,header_bytes=65536,stdout_bytes=4096,stderr_bytes=262144,
                     curl_seconds=45,process_seconds=48,poll_seconds=0.02,owned_process_cleanup_seconds=2)
    out=D/'capture-v1'; out.mkdir(exist_ok=False)
    save(out/'CLAIM.json',{'started_utc':datetime.now(timezone.utc).isoformat(),'manifest_sha256':expected,
                           'curl_version':version,'previous_control':control})
    token=str(uuid.uuid4()); now=datetime.now(timezone.utc)
    try:
        save(LOCK,{'session':'astra-20261031T2113Z-01a193cc','owner_token':token,'directory':str(D),
                   'purpose':'SEDR5 existing-fibre target after saved control','adapter_pid':os.getpid(),
                   'acquired_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=3)).isoformat()})
    except FileExistsError:
        save(out/'RESULTS.json',{'status':'STOP_EXISTING_LEASE','requests_started':0}); return 1
    owner={'pid':None,'identity':None}; cleanup_confirmed=True; status='STOP_NOT_STARTED'; summary={}; interrupted=None
    try:
        deadline=time.perf_counter_ns()+55_000_000_000
        request={'name':'target','method':'POST','url':URL,'payload_sha256':m['target_body_sha256'],
                 'manifest_sha256':expected,'protocol_sha256':m['protocol_sha256'],
                 'scope':'public catalogue identity strings only; no RV analysis'}
        def on_spawn(proc): lib.bind_owned_pid(LOCK,token,out,'target',proc,owner)
        cleanup_confirmed=False
        record=tr.fetch(out,request,'target',deadline,owner_callback=on_spawn)
        cleanup_confirmed=record.get('cleanup_status') in ('NOT_STARTED','EXIT_CONFIRMED')
        if not cleanup_confirmed: status='STOP_OWNED_PROCESS_EXIT_UNCONFIRMED'
        else:
            raw,headers=out/'target.raw',out/'target.headers'
            valid=(record.get('status')=='HTTP_COMPLETE_UNPARSED' and record.get('http_status')==200
                   and record.get('ssl_verify_result')==0 and record.get('num_redirects')==0
                   and record.get('effective_url')==URL and record.get('returncode')==0
                   and raw.is_file() and raw.stat().st_size<=schema.CAP and headers.is_file()
                   and headers.stat().st_size<=65536 and sha(raw)==record.get('raw_sha256')
                   and sha(headers)==record.get('headers_sha256'))
            if not valid or not lib.valid_http_headers(headers.read_bytes(),200,raw.stat().st_size):
                status='STOP_TRANSPORT_OR_HEADERS'
            else:
                kind,rows=schema.parse_csv(raw.read_bytes())
                if kind!='QUERY_PREFIXED': status='STOP_UNEXPECTED_TARGET_SCHEMA'
                else:
                    summary=schema.identity_summary(rows)
                    status=('TARGET_FILENAME_ROWS_IDENTITY_UNVALIDATED' if summary['all_exact_filename']
                            else 'TARGET_EMPTY_OR_FOREIGN_UNRESOLVED')
    except BaseException as exc:
        status='STOP_EXCEPTION'; summary={'error_type':type(exc).__name__}; interrupted=exc
    finally:
        current=json.loads(LOCK.read_text(encoding='utf-8')) if LOCK.exists() else {}
        if current.get('owner_token')==token and cleanup_confirmed: LOCK.unlink()
        elif current.get('owner_token')==token:
            current.update({'cleanup_status':'EXIT_UNCONFIRMED','last_owned_pid':owner['pid'],
                            'last_owned_process':owner['identity'],'instruction':'Do not overwrite lease or kill by PID alone.'})
            tmp=LOCK.with_name(LOCK.name+'.'+token+'.tmp'); save(tmp,current)
            if json.loads(LOCK.read_text(encoding='utf-8')).get('owner_token')!=token: raise RuntimeError('lease owner changed')
            os.replace(tmp,LOCK)
        result={'finished_utc':datetime.now(timezone.utc).isoformat(),'status':status,'manifest_sha256':expected,
                'previous_control':control,'summary':summary,'request_files':[p.name for p in sorted(out.glob('*.request.json'))],
                'owned_process_exit_confirmed':cleanup_confirmed,'last_owned_pid':owner['pid'],
                'last_owned_process':owner['identity'],'lease_released':not LOCK.exists(),
                'holdout_evaluated':False,'rv_analysis_performed':False,
                'native_headers_and_diagnostics':'local only; headers may contain session-bearing secrets'}
        save(out/'RESULTS.json',result)
    visible={k:v for k,v in summary.items() if k!='identity_rows'}
    print(json.dumps({'status':status,'summary':visible,'lease_released':result['lease_released']}),flush=True)
    if interrupted is not None and not isinstance(interrupted,Exception): raise interrupted
    return 0 if status=='TARGET_FILENAME_ROWS_IDENTITY_UNVALIDATED' else 1

if __name__=='__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: target_v1.py MANIFEST_SHA256')
    raise SystemExit(main(sys.argv[1]))
