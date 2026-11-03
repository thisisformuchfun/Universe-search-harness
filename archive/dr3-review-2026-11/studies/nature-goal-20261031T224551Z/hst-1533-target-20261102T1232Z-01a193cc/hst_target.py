"""One HST held-source fixed-point metadata request, with shared-session coordination."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import types
import uuid

D = Path(__file__).resolve().parent
OLD = D.parent / 'held1533-sedr5-20261102T081926Z-01a193cc'
TRANSPORT = OLD / 'native_transport_sedr5_v5.py'
UTILS = OLD / 'capture_serial_v9.py'
C = D.parents[2].parent / 'coordination'
LOCK = C / 'hst1533-target-acquisition.lock'
MUTATION = C / 'mutation.lock'
COORD = C / 'astra-20261031T2113Z-01a193cc.json'
CUSTODY = C / 'HOLDOUT_CUSTODY.json'
CUSTODY_SHA = '155f5aa7f98726c62add15bd302b9f43ca4a216ed14850ecbf649c82a65d3c14'
MANIFEST = D / 'MANIFEST.json'
PRIOR = D.parent/'hst-fixed-point-control-tools/hst-fixed-point-20261101T0708Z-01a193cc'
CONTROL = D.parent/'hst-1533-control-v2-20261102T1233Z-01a193cc'
GAIA = D.parents[2]/'followups/held14-20261031T214650Z/evidence/gaia'
SESSION = 'astra-20261031T2113Z-01a193cc'
CONTROL_URL = 'https://mast.stsci.edu/vo-tap/api/v0.1/caom/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&MAXREC=20&QUERY=SELECT+TOP+20+objid%2Cobs_collection%2Cfacility_name%2Cinstrument_name%2Ctarget_name%2Cobs_id%2Cobs_publisher_did%2Cdataproduct_type%2Ccalib_level%2Cs_region%2Cs_ra%2Cs_dec%2Cs_fov%2Cs_resolution%2Cs_xel1%2Cs_xel2%2Ct_min%2Ct_max%2Ct_exptime%2Ct_resolution%2Ct_xel%2Cem_min%2Cem_max%2Cem_res_power%2Cem_xel%2Cpol_states%2Cpol_xel%2Co_ucd%2Caccess_url%2Caccess_format%2Caccess_estsize+FROM+ivoa.obscore+WHERE+obs_collection%3D%27HST%27+AND+dataproduct_type%3D%27image%27+AND+CONTAINS%28POINT%28%27ICRS%27%2C189.160987245742007%2C62.180980370585935%29%2Cs_region%29%3D1+ORDER+BY+objid'
URL = 'https://mast.stsci.edu/vo-tap/api/v0.1/caom/sync?REQUEST=doQuery&LANG=ADQL&FORMAT=votable&MAXREC=20&QUERY=SELECT+TOP+20+objid%2Cobs_collection%2Cfacility_name%2Cinstrument_name%2Ctarget_name%2Cobs_id%2Cobs_publisher_did%2Cdataproduct_type%2Ccalib_level%2Cs_region%2Cs_ra%2Cs_dec%2Cs_fov%2Cs_resolution%2Cs_xel1%2Cs_xel2%2Ct_min%2Ct_max%2Ct_exptime%2Ct_resolution%2Ct_xel%2Cem_min%2Cem_max%2Cem_res_power%2Cem_xel%2Cpol_states%2Cpol_xel%2Co_ucd%2Caccess_url%2Caccess_format%2Caccess_estsize+FROM+ivoa.obscore+WHERE+obs_collection%3D%27HST%27+AND+dataproduct_type%3D%27image%27+AND+CONTAINS%28POINT%28%27ICRS%27%2C185.71462554756414%2C40.88393733581962%29%2Cs_region%29%3D1+ORDER+BY+objid'
CURL = 'C:/Windows/System32/curl.exe'
LIMITS = {'body_bytes':1000000, 'header_bytes':65536, 'stdout_bytes':4096,
          'stderr_bytes':262144, 'curl_seconds':45, 'process_seconds':48,
          'poll_seconds':0.02, 'owned_process_cleanup_seconds':2}
STRIP = {'http_proxy','https_proxy','all_proxy','no_proxy','sslkeylogfile',
         'curl_ca_bundle','ssl_cert_file','ssl_cert_dir','curl_home','openssl_conf'}

def utc(): return datetime.now(timezone.utc).isoformat()

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()

def save(path, obj):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())

def assert_mutation(token):
    if json.loads(MUTATION.read_text(encoding='utf-8')).get('owner_token') != token:
        raise RuntimeError('mutation lease owner changed')

def atomic_json(path, obj, token, mutation_token):
    tmp = path.with_name(path.name+'.'+token+'.tmp')
    save(tmp,obj)
    assert_mutation(mutation_token)
    os.replace(tmp,path)

def module(name, path, source):
    # Execute only the exact reviewed local module bytes, never returned archive data.
    mod=types.ModuleType(name); mod.__file__=str(path)
    exec(compile(source,str(path),'exec'),mod.__dict__)
    return mod

def stripped_environment(env):
    return {k:v for k,v in env.items() if k.lower() not in STRIP}

def valid_native(rec, raw, header, util):
    return bool(rec.get('status') == 'HTTP_COMPLETE_UNPARSED'
        and rec.get('returncode') == 0 and rec.get('http_status') == 200
        and rec.get('ssl_verify_result') == 0 and rec.get('num_redirects') == 0
        and rec.get('effective_url') == URL and rec.get('cleanup_status') == 'EXIT_CONFIRMED'
        and raw.is_file() and raw.stat().st_size <= LIMITS['body_bytes']
        and header.is_file() and header.stat().st_size <= LIMITS['header_bytes']
        and sha(raw) == rec.get('raw_sha256') and sha(header) == rec.get('headers_sha256')
        and util.valid_http_headers(header.read_bytes(), 200, raw.stat().st_size))

def validate(manifest_sha):
    manifest_bytes=MANIFEST.read_bytes()
    if not re.fullmatch('[0-9a-f]{64}', manifest_sha) or hashlib.sha256(manifest_bytes).hexdigest() != manifest_sha:
        raise ValueError('manifest hash mismatch')
    m = json.loads(manifest_bytes.decode('utf-8'))
    required = {'script_sha256':D/'hst_target.py', 'protocol_sha256':D/'PROTOCOL.md',
                'test_sha256':D/'test_hst_target.py', 'query_sha256':D/'QUERY.adql', 'transport_sha256':TRANSPORT,
                'ownership_utils_sha256':UTILS, 'curl_sha256':Path(CURL),
                'prior_protocol_sha256':PRIOR/'PROTOCOL.json','prior_raw_sha256':PRIOR/'hst_fixed_point.raw',
                'prior_native_sha256':PRIOR/'hst_fixed_point.json','prior_result_sha256':PRIOR/'RESULTS.json',
                'prior_request_sha256':PRIOR/'hst_fixed_point.request.json',
                'prior_execution_review_sha256':D.parent/'execution-review/hst-fixed-point-20261101/POSTRUN_EXECUTION_REVIEW.json',
                'prior_duplicate_audit_sha256':D.parent/'execution-review/hst-fixed-point-20261101/DUPLICATE_RECORD_AUDIT.json',
                'prior_science_review_sha256':D.parent/'science/hst-fixed-point-control-20261101/POSTRUN_SCIENCE_REVIEW.json',
                'control_query_sha256':CONTROL/'QUERY.adql', 'control_manifest_sha256':CONTROL/'MANIFEST.json',
                'control_protocol_sha256':CONTROL/'PROTOCOL.md', 'control_request_sha256':CONTROL/'capture/hst_control.request.json',
                'control_native_sha256':CONTROL/'capture/hst_control.json',
                'control_raw_sha256':CONTROL/'capture/hst_control.raw', 'control_result_sha256':CONTROL/'capture/RESULT.json',
                'control_finish_sha256':CONTROL/'capture/FINISH.json',
                'control_science_review_sha256':CONTROL/'INDEPENDENT_SCIENCE_RESULT_REVIEW.json',
                'control_execution_review_sha256':CONTROL/'INDEPENDENT_EXECUTION_RESULT_REVIEW.json',
                'gaia_source_parsed_sha256':GAIA/'source_all14.parsed.json', 'gaia_source_raw_sha256':GAIA/'source_all14.raw'}
    frozen={}
    for key,path in required.items():
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest() != m.get(key): raise ValueError('pinned input mismatch: '+key)
        frozen[key]=data
    if m['transport_sha256'] != '0f6c1d71336306b5e0bb319f5ced7cfe0e059af891d6632d28f49e634c2c8f42':
        raise ValueError('unexpected native transport')
    if m['ownership_utils_sha256'] != '3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5':
        raise ValueError('unexpected ownership helpers')
    from urllib.parse import urlencode
    q=frozen['query_sha256'].decode('utf-8-sig').strip()
    expected_url='https://mast.stsci.edu/vo-tap/api/v0.1/caom/sync?'+urlencode([('REQUEST','doQuery'),('LANG','ADQL'),('FORMAT','votable'),('MAXREC','20'),('QUERY',q)])
    if URL != expected_url: raise ValueError('query and fixed URL differ')
    prior=json.loads(frozen['prior_protocol_sha256'].decode('utf8'))
    control_q=frozen['control_query_sha256'].decode('utf-8-sig').strip()
    if prior['requests'][0]['query']!=control_q or prior['requests'][0]['url']!=CONTROL_URL or b'109191367' not in frozen['prior_raw_sha256']:
        raise ValueError('prior HST control identity or query mismatch')
    validate_prior_chain(m, frozen, control_q)
    validate_target_chain(m, frozen, q, control_q)
    ver = subprocess.run([CURL,'--disable','--version'], capture_output=True, timeout=5, check=True).stdout.decode('ascii').splitlines()[0]
    match = re.match(r'^curl (\d+)\.(\d+)\.(\d+)', ver)
    if not match or tuple(map(int,match.groups())) < (8,4,0): raise ValueError('curl version too old')
    return m,ver,frozen

def validate_prior_chain(m, frozen, query):
    request=json.loads(frozen['prior_request_sha256'].decode('utf8'))
    native=json.loads(frozen['prior_native_sha256'].decode('utf8'))
    execution=json.loads(frozen['prior_execution_review_sha256'].decode('utf8'))
    science=json.loads(frozen['prior_science_review_sha256'].decode('utf8'))
    duplicate=json.loads(frozen['prior_duplicate_audit_sha256'].decode('utf8'))
    if (request['request']['url'] != CONTROL_URL or request['request']['query'] != query
        or native.get('request_sha256') != m['prior_request_sha256']
        or native.get('raw_sha256') != m['prior_raw_sha256']):
        raise ValueError('prior request/native chain mismatch')
    if execution.get('verdict') != 'ACCEPT_COMPLETE_CAPTURE_AND_KNOWN_ROW_SCALAR_CONTROL_WITH_COVERAGE_HOLD':
        raise ValueError('prior execution review not accepted')
    if science.get('verdict') != 'POPULATED_SCALAR_GEOMETRY_CONTROL_PASSES_V2_WITH_BOUNDED_UNKNOWN_ARCHIVE_COVERAGE':
        raise ValueError('prior science review not accepted')
    links={'protocol_sha256':'prior_protocol_sha256','raw_sha256':'prior_raw_sha256',
           'retrieval_sha256':'prior_native_sha256','result_sha256':'prior_result_sha256'}
    if any(review.get(a) != m[b] for review in (execution,science) for a,b in links.items()):
        raise ValueError('prior review evidence links mismatch')
    if (execution.get('request_sha256') != m['prior_request_sha256']
        or execution.get('duplicate_audit_sha256') != m['prior_duplicate_audit_sha256']
        or duplicate.get('raw_sha256') != m['prior_raw_sha256']
        or duplicate.get('rows') != 20 or duplicate.get('distinct_exact_objids') != 5):
        raise ValueError('prior duplicate audit or request link mismatch')

def validate_target_chain(m, frozen, query, control_query):
    from decimal import Decimal
    control_result=json.loads(frozen['control_result_sha256'].decode('utf8'))
    control_finish=json.loads(frozen['control_finish_sha256'].decode('utf8'))
    control_request=json.loads(frozen['control_request_sha256'].decode('utf8'))
    control_native=json.loads(frozen['control_native_sha256'].decode('utf8'))
    if (m['control_manifest_sha256'] != 'bec4540f44f17367faa3d85d6b2a6c8a30619151fcc950957df80c54a12a267d'
        or control_result.get('status') != 'HTTP_COMPLETE_VOTABLE_UNVALIDATED'
        or control_result.get('http_status') != 200 or control_result.get('body_sha256') != m['control_raw_sha256']
        or control_result.get('target_requested') is not False
        or control_finish.get('terminal_sha256') != m['control_result_sha256']
        or control_finish.get('lease_released') is not True
        or control_request.get('request',{}).get('url', control_request.get('url')) != CONTROL_URL
        or control_native.get('request_sha256') != m['control_request_sha256']
        or control_native.get('raw_sha256') != m['control_raw_sha256']
        or control_native.get('http_status') != 200):
        raise ValueError('fresh control chain mismatch')
    for key in ('control_science_review_sha256','control_execution_review_sha256'):
        review=json.loads(frozen[key].decode('utf8'))
        links=review.get('input_sha256') if key == 'control_science_review_sha256' else review.get('hashes')
        if (review.get('verdict') != 'PASS_BOUNDED_FIXED_POINT_CONTROL' or not isinstance(links,dict)
            or links.get('raw_sha256') != m['control_raw_sha256']
            or links.get('result_sha256') != m['control_result_sha256']
            or links.get('query_sha256') != m['control_query_sha256']
            or links.get('manifest_sha256') != m['control_manifest_sha256']
            or (key == 'control_science_review_sha256' and (links.get('protocol_sha256') != m['control_protocol_sha256'] or links.get('native_metadata_sha256') != m['control_native_sha256']))
            or (key == 'control_execution_review_sha256' and (links.get('request_sha256') != m['control_request_sha256'] or links.get('native_sha256') != m['control_native_sha256']))):
            raise ValueError('fresh control review mismatch')
    rows=json.loads(frozen['gaia_source_parsed_sha256'].decode('utf8'),parse_float=Decimal)
    matched=[r for r in rows if r.get('source_id')=='1533365584518328576']
    if (len(matched)!=1 or matched[0].get('ra')!=Decimal('185.71462554756414')
        or matched[0].get('dec')!=Decimal('40.88393733581962')
        or matched[0].get('ref_epoch')!=Decimal('2016.0')):
        raise ValueError('target Gaia ID, point or reference epoch mismatch')
    expected=control_query.replace('189.160987245742007,62.180980370585935',
                                   '185.71462554756414,40.88393733581962')
    if query != expected or b'1533365584518328576' not in frozen['gaia_source_raw_sha256']:
        raise ValueError('target query or Gaia raw identity mismatch')

@contextmanager
def mutation_lease():
    token=str(uuid.uuid4())
    save(MUTATION,{'owner_token':token,'session':SESSION,'pid':os.getpid(),'acquired_utc':utc()})
    try:
        yield token
    finally:
        if json.loads(MUTATION.read_text(encoding='utf-8')).get('owner_token') == token:
            MUTATION.unlink()

def claim(out,manifest_sha):
    token=str(uuid.uuid4()); now=datetime.now(timezone.utc)
    with mutation_lease() as mutation_token:
        if sha(CUSTODY) != CUSTODY_SHA: raise ValueError('holdout custody changed')
        state=json.loads(COORD.read_text(encoding='utf-8'))
        if (state.get('session') != SESSION or state.get('in_progress_directory') is not None
            or state.get('active_owned_scientific_processes') != []):
            raise ValueError('session coordination not idle')
        if any(p != MUTATION for p in C.glob('*.lock')):
            raise ValueError('another coordination/acquisition lease exists')
        lease={'session':SESSION,'owner_token':token,'directory':str(D),
               'purpose':'HST source 153336 fixed-point metadata only','adapter_pid':os.getpid(),
               'acquired_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=10)).isoformat(),
               'manifest_sha256':manifest_sha}
        assert_mutation(mutation_token)
        save(LOCK,lease)
        save(out/'COORDINATION_BEFORE.json',state)
        state.update({'task':'HST source 153336 fixed-point metadata only; no GPU', 'timestamp_utc':utc(),
                      'in_progress_directory':str(D), 'in_progress_capture_manifest_sha256':manifest_sha,
                      'active_owned_scientific_processes':[], 'gpu_allocation':'none'})
        atomic_json(COORD,state,token,mutation_token)
    return token

def finish(out,token,manifest_sha,safe_to_release,cleanup_status,ownership):
    # Durable terminal proof is required before any lease release.
    terminal=out/'RESULT.json'
    if not terminal.is_file(): raise RuntimeError('terminal result absent')
    terminal_sha=sha(terminal)
    with mutation_lease() as mutation_token:
        if sha(CUSTODY) != CUSTODY_SHA: raise ValueError('holdout custody changed before finish')
        if any(p not in (MUTATION,LOCK) for p in C.glob('*.lock')):
            raise ValueError('another lease appeared before finish')
        lease=json.loads(LOCK.read_text(encoding='utf-8'))
        state=json.loads(COORD.read_text(encoding='utf-8'))
        if (lease.get('owner_token') != token or state.get('session') != SESSION
            or state.get('in_progress_directory') != str(D)
            or state.get('active_owned_scientific_processes') != []
            or state.get('in_progress_capture_manifest_sha256') != manifest_sha):
            raise RuntimeError('lease or coordination owner changed')
        if not safe_to_release:
            lease.update({'cleanup_status':'EXIT_UNCONFIRMED', 'last_owned_pid':ownership['pid'],
                          'last_owned_process':ownership['identity'], 'terminal_sha256':terminal_sha,
                          'instruction':'Do not overwrite lease or kill by PID alone; verify creation identity.'})
            atomic_json(LOCK,lease,token,mutation_token)
            return {'lease_released':False,'safe_to_release':False,'cleanup_status':cleanup_status,
                    'owned_process_exit_confirmed':False,'terminal_sha256':terminal_sha}
        state.update({'task':'HST source 153336 metadata acquisition finished; isolated bookkeeping may remain',
                      'timestamp_utc':utc(),'in_progress_directory':None,
                      'in_progress_capture_manifest_sha256':None,
                      'active_owned_scientific_processes':[], 'gpu_allocation':'none'})
        atomic_json(COORD,state,token,mutation_token)
        if json.loads(LOCK.read_text(encoding='utf-8')).get('owner_token') != token:
            raise RuntimeError('lease owner changed during finish')
        assert_mutation(mutation_token)
        LOCK.unlink()
    return {'lease_released':True,'safe_to_release':True,'cleanup_status':cleanup_status,
            'owned_process_exit_confirmed':cleanup_status=='EXIT_CONFIRMED','terminal_sha256':terminal_sha}

def execute(manifest_sha):
    m,version,frozen=validate(manifest_sha)
    util=module('prior_capture_util',UTILS,frozen['ownership_utils_sha256'])
    tr=module('reviewed_native_transport',TRANSPORT,frozen['transport_sha256'])
    tr.sha=sha; tr.REQUEST_URLS={'hst_target':URL}; tr.LIMITS.update(LIMITS)
    out=D/'capture'; out.mkdir(exist_ok=False)
    save(out/'CLAIM.json',{'manifest_sha256':manifest_sha,'url':URL,'utc':utc(),
         'curl_version':version,'curl_sha256':m['curl_sha256'],
         'python_version':sys.version,'python_executable':sys.executable,
         'environment':'proxy and SSL override variables stripped by name',
         'scope':'one fixed held-source HST metadata query; no products'})
    token=None; safe_to_release=True; cleanup_status='NOT_STARTED'
    ownership={'pid':None,'identity':None}; interrupted=None
    fetch_invoked=False; rec=None
    result={'status':'STOP_NOT_STARTED','requests_attempted':0,'target_curl_start_observed':False,'holdout_evaluated':False}
    try:
        token=claim(out,manifest_sha)
        clean=stripped_environment(dict(os.environ)); os.environ.clear(); os.environ.update(clean)
        deadline=time.perf_counter_ns()+55_000_000_000
        req={'name':'hst_target','method':'GET','url':URL,'manifest_sha256':manifest_sha,
             'protocol_sha256':m['protocol_sha256'], 'response_policy':'no redirects or retries; HST target metadata transport only'}
        def owned(proc): util.bind_owned_pid(LOCK,token,out,'hst_target',proc,ownership)
        if sha(Path(CURL)) != m['curl_sha256']:
            raise ValueError('curl executable changed after preflight')
        safe_to_release=False; cleanup_status='EXIT_UNKNOWN'
        fetch_invoked=True
        rec=tr.fetch(out,req,'hst_target',deadline,owner_callback=owned)
        cleanup_status=rec.get('cleanup_status') if rec.get('cleanup_status') in ('NOT_STARTED','EXIT_CONFIRMED','EXIT_UNCONFIRMED') else 'EXIT_UNKNOWN'
        safe_to_release=cleanup_status in ('NOT_STARTED','EXIT_CONFIRMED')
        complete=safe_to_release and valid_native(rec,out/'hst_target.raw',out/'hst_target.headers',util)
        result.update({'status':'HTTP_COMPLETE_VOTABLE_UNVALIDATED' if complete else 'STOP_TRANSPORT',
             'http_status':rec.get('http_status'),'curl_exit':rec.get('returncode'),
             'tls_verify_result':rec.get('ssl_verify_result'),'redirect_count':rec.get('num_redirects'),
             'body_bytes':rec.get('raw_bytes'),'body_sha256':rec.get('raw_sha256'),
             'cleanup_status':rec.get('cleanup_status'), 'polling_overshoot_possible':True,
             'votable_schema_validation':False})
    except BaseException as exc:
        result.update({'status':'STOP_EXCEPTION','error_type':type(exc).__name__})
        if not isinstance(exc,Exception): interrupted=exc
    finally:
        native_pid=rec.get('owned_pid') if isinstance(rec,dict) else None
        if native_pid is None and (out/'hst_target.json').is_file():
            record_state, native_record = util.read_json_state(out/'hst_target.json')
            if record_state == 'VALID_JSON' and native_record.get('url') == URL:
                native_pid=native_record.get('owned_pid')
        if ownership['pid'] is None and type(native_pid) is int and native_pid > 0:
            ownership['pid']=native_pid
            ownership['identity']={'pid':native_pid,'identity_status':'NATIVE_RECORD_ONLY_UNVERIFIED'}
        observed_pid=ownership['pid']
        attempted=(1 if observed_pid is not None else
                   (0 if not fetch_invoked or (isinstance(rec,dict) and rec.get('cleanup_status')=='NOT_STARTED') else None))
        result.update({'target_curl_start_observed': True if observed_pid is not None else (False if attempted == 0 else None), 'fetch_invoked':fetch_invoked,'process_start_observed':observed_pid is not None,
                       'requests_attempted':attempted,
                       'request_record_present':(out/'hst_target.request.json').exists(),
                       'native_reported_pid':native_pid,
                       'finished_utc':utc(),'cleanup_status':cleanup_status,'safe_to_release':safe_to_release,
                       'owned_process_exit_confirmed':cleanup_status=='EXIT_CONFIRMED',
                       'last_owned_pid':ownership['pid'],'last_owned_process':ownership['identity'],
                       'lease_release_pending':token is not None})
        # If this exclusive, fsynced save fails, finish is never called and the lease remains.
        save(out/'RESULT.json',result)
        if token is not None:
            try:
                end=finish(out,token,manifest_sha,safe_to_release,cleanup_status,ownership)
            except Exception as exc:
                end={'lease_released':False,'safe_to_release':safe_to_release,'cleanup_status':cleanup_status,
                     'owned_process_exit_confirmed':cleanup_status=='EXIT_CONFIRMED',
                     'finish_error_type':type(exc).__name__}
        else:
            end={'lease_released':False,'safe_to_release':safe_to_release,'cleanup_status':cleanup_status,
                     'owned_process_exit_confirmed':cleanup_status=='EXIT_CONFIRMED',
                 'claim_not_completed':True}
        save(out/'FINISH.json',end)
    print(json.dumps({'status':result['status'],'requests_attempted':result['requests_attempted'],
                      'http_status':result.get('http_status'),'body_bytes':result.get('body_bytes'),
                      'safe_to_release':safe_to_release,'cleanup_status':cleanup_status,'lease_released':end['lease_released']}))
    if interrupted is not None: raise interrupted
    return 0 if result['status']=='HTTP_COMPLETE_VOTABLE_UNVALIDATED' and end['lease_released'] else 1

def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest-sha256',required=True)
    return execute(p.parse_args().manifest_sha256)

if __name__=='__main__': raise SystemExit(main())
