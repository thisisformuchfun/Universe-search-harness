"""One held Gaia DR9 mask product, with shared-session coordination."""
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
LOCK = C / 'legacy-mask-target-acquisition.lock'
MUTATION = C / 'mutation.lock'
COORD = C / 'astra-20261031T2113Z-01a193cc.json'
CUSTODY = C / 'HOLDOUT_CUSTODY.json'
CUSTODY_SHA = '155f5aa7f98726c62add15bd302b9f43ca4a216ed14850ecbf649c82a65d3c14'
MANIFEST = D / 'MANIFEST.json'
CONTROL = D.parent / 'legacy-mask-control-v2-20261102T1145Z-01a193cc'
IMAGE_TARGET = D.parent / 'legacy1533-target-v2-20261102T1137Z-01a193cc'
GAIA_SOURCE = D.parents[2] / 'followups/held14-20261031T214650Z/evidence/gaia/source_all14.parsed.json'
SESSION = 'astra-20261031T2113Z-01a193cc'
URL = ('https://portal.nersc.gov/cfs/cosmo/data/legacysurvey/dr9/north/coadd/'
       '185/1857p410/legacysurvey-1857p410-maskbits.fits.fz')
CURL = 'C:/Windows/System32/curl.exe'
LIMITS = {'body_bytes':16777216, 'header_bytes':65536, 'stdout_bytes':4096,
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
    required = {'script_sha256':D/'mask_target.py','protocol_sha256':D/'PROTOCOL.md',
                'test_sha256':D/'test_mask_target.py','transport_sha256':TRANSPORT,
                'ownership_utils_sha256':UTILS,'curl_sha256':Path(CURL),'gaia_source_sha256':GAIA_SOURCE,
                'mask_control_raw_sha256':CONTROL/'capture/mask_control.raw',
                'mask_control_header_sha256':CONTROL/'MASK_HEADER_INVENTORY.json',
                'mask_control_inspection_sha256':CONTROL/'MASK_CONTROL_INSPECTION.json',
                'mask_control_frames_sha256':CONTROL/'MASK_FRAME_COMPARISON.json',
                'mask_control_result_sha256':CONTROL/'capture/RESULT.json',
                'mask_control_finish_sha256':CONTROL/'capture/FINISH.json',
                'mask_control_science_sha256':CONTROL/'INDEPENDENT_SCIENCE_CONTROL_REVIEW.md',
                'mask_control_execution_sha256':CONTROL/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md',
                'target_image_raw_sha256':IMAGE_TARGET/'capture/legacy_target.raw',
                'target_image_inventory_sha256':IMAGE_TARGET/'TARGET_FITS_INVENTORY.json',
                'target_image_result_sha256':IMAGE_TARGET/'capture/RESULT.json',
                'target_image_finish_sha256':IMAGE_TARGET/'capture/FINISH.json',
                'target_image_science_sha256':IMAGE_TARGET/'INDEPENDENT_SCIENCE_FITS_REVIEW.md',
                'target_image_execution_sha256':IMAGE_TARGET/'INDEPENDENT_EXECUTION_CAPTURE_REVIEW.md'}
    frozen={}
    for key,path in required.items():
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest() != m.get(key): raise ValueError('pinned input mismatch: '+key)
        frozen[key]=data
    if m['transport_sha256'] != '0f6c1d71336306b5e0bb319f5ced7cfe0e059af891d6632d28f49e634c2c8f42':
        raise ValueError('unexpected native transport')
    if m['ownership_utils_sha256'] != '3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5':
        raise ValueError('unexpected ownership helpers')
    verify_prerequisites(m,frozen)
    ver = subprocess.run([CURL,'--disable','--version'], capture_output=True, timeout=5, check=True).stdout.decode('ascii').splitlines()[0]
    match = re.match(r'^curl (\d+)\.(\d+)\.(\d+)', ver)
    if not match or tuple(map(int,match.groups())) < (8,4,0): raise ValueError('curl version too old')
    return m,ver,frozen

def verify_prerequisites(manifest,frozen):
    def parse(key): return json.loads(frozen[key].decode('utf-8'))
    source=parse('gaia_source_sha256')
    rows=[r for r in source if r.get('source_id')=='1533365584518328576']
    if len(rows)!=1 or rows[0].get('ra')!=185.71462554756414 or rows[0].get('dec')!=40.88393733581962:
        raise ValueError('Gaia exact identity mismatch')
    for prefix in ('mask_control','target_image'):
        result=parse(prefix+'_result_sha256'); finish=parse(prefix+'_finish_sha256')
        if (result.get('status')!='HTTP_COMPLETE_FITS_UNVALIDATED'
            or result.get('body_sha256')!=manifest[prefix+'_raw_sha256']
            or finish.get('terminal_sha256')!=hashlib.sha256(frozen[prefix+'_result_sha256']).hexdigest()
            or not finish.get('lease_released') or not finish.get('owned_process_exit_confirmed')):
            raise ValueError('prerequisite transport proof mismatch')
    head=parse('mask_control_header_sha256'); inspection=parse('mask_control_inspection_sha256')
    frames=parse('mask_control_frames_sha256'); image=parse('target_image_inventory_sha256')
    h=head['hdus'][1]['fields']
    if (head.get('sha256')!=manifest['mask_control_raw_sha256']
        or not head.get('fits_verify_exception_passed') or head.get('warning_types')
        or h.get('BRICK')!='1548p465' or h.get('EXTNAME')!='MASKBITS'
        or h.get('ZCMPTYPE')!='HCOMPRESS_1' or [h.get('ZNAXIS1'),h.get('ZNAXIS2')]!=[3600,3600]
        or [h.get('ZTILE1'),h.get('ZTILE2')]!=[100,100] or h.get('ZBITPIX')!=16
        or inspection.get('input_sha256')!=manifest['mask_control_raw_sha256']
        or not inspection.get('synthetic_bit_decoding_passed')
        or frames.get('mask_sha256')!=manifest['mask_control_raw_sha256']):
        raise ValueError('mask control format or frame evidence mismatch')
    if image.get('input_sha256')!=manifest['target_image_raw_sha256'] or not image.get('fits_verify_exception_passed'):
        raise ValueError('target image proof mismatch')
    for band in ('g','r','z'):
        entries=[x for x in image['hdus'] if x.get('brick')=='1857p410' and x.get('band')==band and x.get('image_type')=='image']
        if len(entries)!=1 or not all(entries[0]['locations'][p]['inside'] for p in
               ('gaia_2016_unpropagated','ps1_one_detection_mean','gaia_neighbor_2016_unpropagated')):
            raise ValueError('target image positions/brick not verified')

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
               'purpose':'Legacy DR9 held-field mask only','adapter_pid':os.getpid(),
               'acquired_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=10)).isoformat(),
               'manifest_sha256':manifest_sha}
        assert_mutation(mutation_token)
        save(LOCK,lease)
        save(out/'COORDINATION_BEFORE.json',state)
        state.update({'task':'Legacy held-field mask only; no GPU', 'timestamp_utc':utc(),
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
        state.update({'task':'Legacy held-field mask acquisition finished; isolated bookkeeping may remain',
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
    tr.sha=sha; tr.REQUEST_URLS={'mask_target':URL}; tr.LIMITS.update(LIMITS)
    out=D/'capture'; out.mkdir(exist_ok=False)
    save(out/'CLAIM.json',{'manifest_sha256':manifest_sha,'url':URL,'utc':utc(),
         'curl_version':version,'curl_sha256':m['curl_sha256'],
         'python_version':sys.version,'python_executable':sys.executable,
         'environment':'proxy and SSL override variables stripped by name',
         'scope':'one held Gaia mask product, no model or science decision'})
    token=None; safe_to_release=True; cleanup_status='NOT_STARTED'
    ownership={'pid':None,'identity':None}; interrupted=None
    fetch_invoked=False; rec=None
    result={'status':'STOP_NOT_STARTED','requests_attempted':0,'target_curl_start_observed':False,'holdout_evaluated':False}
    try:
        token=claim(out,manifest_sha)
        clean=stripped_environment(dict(os.environ)); os.environ.clear(); os.environ.update(clean)
        deadline=time.perf_counter_ns()+55_000_000_000
        req={'name':'mask_target','method':'GET','url':URL,'manifest_sha256':manifest_sha,
             'protocol_sha256':m['protocol_sha256'], 'response_policy':'no redirects or retries; held-mask transport only'}
        def owned(proc): util.bind_owned_pid(LOCK,token,out,'mask_target',proc,ownership)
        if sha(Path(CURL)) != m['curl_sha256']:
            raise ValueError('curl executable changed after preflight')
        safe_to_release=False; cleanup_status='EXIT_UNKNOWN'
        fetch_invoked=True
        rec=tr.fetch(out,req,'mask_target',deadline,owner_callback=owned)
        cleanup_status=rec.get('cleanup_status') if rec.get('cleanup_status') in ('NOT_STARTED','EXIT_CONFIRMED','EXIT_UNCONFIRMED') else 'EXIT_UNKNOWN'
        safe_to_release=cleanup_status in ('NOT_STARTED','EXIT_CONFIRMED')
        complete=safe_to_release and valid_native(rec,out/'mask_target.raw',out/'mask_target.headers',util)
        result.update({'status':'HTTP_COMPLETE_FITS_UNVALIDATED' if complete else 'STOP_TRANSPORT',
             'http_status':rec.get('http_status'),'curl_exit':rec.get('returncode'),
             'tls_verify_result':rec.get('ssl_verify_result'),'redirect_count':rec.get('num_redirects'),
             'body_bytes':rec.get('raw_bytes'),'body_sha256':rec.get('raw_sha256'),
             'cleanup_status':rec.get('cleanup_status'), 'polling_overshoot_possible':True,
             'fits_science_validation':False})
    except BaseException as exc:
        result.update({'status':'STOP_EXCEPTION','error_type':type(exc).__name__})
        if not isinstance(exc,Exception): interrupted=exc
    finally:
        native_pid=rec.get('owned_pid') if isinstance(rec,dict) else None
        if native_pid is None and (out/'mask_target.json').is_file():
            record_state, native_record = util.read_json_state(out/'mask_target.json')
            if record_state == 'VALID_JSON' and native_record.get('url') == URL:
                native_pid=native_record.get('owned_pid')
        if ownership['pid'] is None and type(native_pid) is int and native_pid > 0:
            ownership['pid']=native_pid
            ownership['identity']={'pid':native_pid,'identity_status':'NATIVE_RECORD_ONLY_UNVERIFIED'}
        observed_pid=ownership['pid']
        attempted=(1 if observed_pid is not None else
                   (0 if not fetch_invoked or (isinstance(rec,dict) and rec.get('cleanup_status')=='NOT_STARTED') else None))
        result.update({'target_curl_start_observed':(None if attempted is None else attempted==1),
                       'fetch_invoked':fetch_invoked,'process_start_observed':observed_pid is not None,
                       'requests_attempted':attempted,
                       'request_record_present':(out/'mask_target.request.json').exists(),
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
    return 0 if result['status']=='HTTP_COMPLETE_FITS_UNVALIDATED' and end['lease_released'] else 1

def main():
    p=argparse.ArgumentParser(); p.add_argument('--manifest-sha256',required=True)
    return execute(p.parse_args().manifest_sha256)

if __name__=='__main__': raise SystemExit(main())
