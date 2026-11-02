"""Bounded SEDR5 availability capture for one pre-existing held source.

Availability/transport only: never interprets RVs, follows returned links,
validates FITS identity, changes a science criterion, or evaluates a holdout.
"""
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import time
import uuid

D = Path(__file__).resolve().parent
S = D.parents[2]
C = S.parent / 'coordination'
LOCK = C / 'sedr5-acquisition.lock'
PROTOCOL = D / 'PROTOCOL_V5.json'
MANIFEST = D / 'CAPTURE_MANIFEST_V9.json'
TRANSPORT = D / 'native_transport_sedr5_v5.py'
SOURCE = D.parent / 'spectral-error-original-fits/evidence/294101037.raw'
BASE = 'https://casdc.china-vo.org/lamost/vac/sedr5/fits/'
PLATE = 'HD122456N425117B01'
FILENAME = '20150108_HD122456N425117B01_01_037.fit'
STAGES = (
    ('root', BASE, 500000, '20150108/'),
    ('day', BASE + '20150108/', 500000, PLATE + '/'),
    ('plan', BASE + '20150108/' + PLATE + '/', 500000, FILENAME),
    ('product', BASE + '20150108/' + PLATE + '/' + FILENAME, 4000000, None),
)
CURL = r'C:/Windows/System32/curl.exe'

class IndexLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.ambiguous = False
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'base':
            self.ambiguous = True
        if tag == 'a':
            hrefs = [v for k, v in attrs if k.lower() == 'href']
            if len(hrefs) > 1 or any(v is None for v in hrefs):
                self.ambiguous = True
            self.links.extend(hrefs)
    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

def exact_child(raw, expected):
    if len(raw) > 500000 or b'\x00' in raw:
        raise ValueError('unsupported index')
    parser = IndexLinks()
    parser.feed(raw.decode('utf-8', errors='strict'))
    parser.close()
    return not parser.ambiguous and parser.links.count(expected) == 1

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(65536), b''):
            h.update(block)
    return h.hexdigest()

def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())

def wait_for_next(last_finish, deadline):
    gap = 1_000_000_000
    reserve = 8_000_000_000
    now = time.perf_counter_ns()
    delay = max(0, last_finish + gap - now)
    if now + delay + reserve >= deadline:
        raise TimeoutError('insufficient batch time for spacing')
    if delay:
        time.sleep(delay / 1e9)
    now = time.perf_counter_ns()
    if now < last_finish + gap or now + reserve >= deadline:
        raise TimeoutError('spacing or deadline not satisfied')

def validate_inputs(expected_manifest):
    if not re.fullmatch('[0-9a-f]{64}', expected_manifest) or sha(MANIFEST) != expected_manifest:
        raise ValueError('manifest hash mismatch')
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    expected_paths = {'capture_script_sha256': Path(__file__), 'protocol_sha256': PROTOCOL,
                      'transport_sha256': TRANSPORT, 'combined_source_sha256': SOURCE,
                      'test_sha256': D / 'test_capture_v9.py',
                      'deferred_test_sha256': D / 'test_transport_deferred_v2.py',
                      'test_result_sha256': D / 'TEST_V9_RESULT.json'}
    for key, path in expected_paths.items():
        if sha(path) != manifest[key]:
            raise ValueError('pinned input mismatch: ' + key)
    if manifest['transport_sha256'] != '0f6c1d71336306b5e0bb319f5ced7cfe0e059af891d6632d28f49e634c2c8f42':
        raise ValueError('unexpected transport')
    if manifest['combined_source_sha256'] != '2bfdfe2b133b1f5d9f880ae81be5002b48b7eb89cb8c45f538e048542cc32e06':
        raise ValueError('unexpected source')
    test = json.loads((D/'TEST_V9_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode') != 0 or test.get('tests_expected') != 20
            or sha(D/'TEST_V9_STDOUT.raw') != test.get('stdout_sha256')
            or sha(D/'TEST_V9_STDERR.raw') != test.get('stderr_sha256')):
        raise ValueError('saved offline test evidence mismatch')
    protocol = json.loads(PROTOCOL.read_text(encoding='utf-8'))
    if [(r['id'], r['url'], r['max_body_bytes']) for r in protocol['requests']] != [(a,b,c) for a,b,c,_ in STAGES]:
        raise ValueError('protocol request mismatch')
    if protocol['limits']['requests_max'] != 4 or protocol['limits']['sum_body_max_bytes'] != 5500000:
        raise ValueError('protocol limit mismatch')
    from astropy.io import fits
    with fits.open(SOURCE, mode='readonly', memmap=False) as hdus:
        header = hdus[0].header
        actual = {k:header.get(k) for k in ('OBSID','DATE-OBS','PLANID','SPID','FIBERID')}
    if actual != {'OBSID':294101037, 'DATE-OBS':'2015-01-08T21:25:00',
                  'PLANID':PLATE, 'SPID':1, 'FIBERID':37}:
        raise ValueError('combined source header mismatch')
    version = subprocess.run([CURL, '--disable', '--version'], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=5, check=True).stdout.decode('ascii').splitlines()[0]
    match = re.match(r'^curl (\d+)\.(\d+)\.(\d+)', version)
    if not match or tuple(map(int, match.groups())) < (8,4,0):
        raise ValueError('curl version lacks streaming max-filesize behavior')
    return manifest, actual, version

def valid_http_headers(raw, expected_status, body_bytes=None):
    if not raw or len(raw) > 65536 or not raw.endswith(b'\r\n\r\n'):
        return False
    blocks = raw[:-4].split(b'\r\n\r\n')
    last_code = None
    final_fields = {}
    for block in blocks:
        lines = block.split(b'\r\n')
        if any(any((byte < 32 and byte != 9) or byte == 127 for byte in line) for line in lines):
            return False
        match = re.fullmatch(rb'HTTP/(?:1\.0|1\.1|2|3) ([1-5][0-9]{2})(?:[ \t][^\r\n]*)?', lines[0])
        if not match:
            return False
        last_code = int(match.group(1))
        fields = {}
        for line in lines[1:]:
            if not re.fullmatch(rb"[!#$%&'*+.^_`|~0-9A-Za-z-]+:[^\r\n]*", line):
                return False
            key, value = line.split(b':', 1)
            fields.setdefault(key.lower(), []).append(value.strip())
        final_fields = fields
    lengths = final_fields.get(b'content-length', [])
    encodings = final_fields.get(b'transfer-encoding', [])
    if len(lengths) > 1 or len(encodings) > 1 or (lengths and encodings):
        return False
    if lengths and (not lengths[0].isdigit() or (body_bytes is not None and int(lengths[0]) != body_bytes)):
        return False
    return last_code == expected_status

def process_identity(proc):
    identity = {'pid':proc.pid, 'creation_filetime_100ns':None,
                'observed_utc':datetime.now(timezone.utc).isoformat(),
                'executable_expected':CURL, 'identity_status':'UNAVAILABLE',
                'instruction':'Never kill or claim ownership based on a stale PID alone.'}
    try:
        import ctypes
        from ctypes import wintypes
        handle = getattr(proc, '_handle', None)
        if handle is not None:
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)]*4
            kernel.GetProcessTimes.restype = wintypes.BOOL
            created, exited, kernel_time, user_time = [wintypes.FILETIME() for _ in range(4)]
            if kernel.GetProcessTimes(wintypes.HANDLE(int(handle)), ctypes.byref(created), ctypes.byref(exited),
                                      ctypes.byref(kernel_time), ctypes.byref(user_time)):
                identity['creation_filetime_100ns'] = str((created.dwHighDateTime << 32) | created.dwLowDateTime)
                identity['identity_status'] = 'OWNED_HANDLE_CREATION_TIME_OBSERVED'
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return identity

def bind_owned_pid(lock, token, out, name, proc, ownership):
    pid = proc.pid
    ownership['pid'] = pid
    if not isinstance(pid, int) or pid <= 0:
        raise ValueError('invalid owned PID')
    ownership['identity'] = process_identity(proc)
    save(out/(name+'.owned.json'), {'owned_process':ownership['identity'], 'owner_token':token,
                                  'recorded_utc':datetime.now(timezone.utc).isoformat()})
    current = json.loads(lock.read_text(encoding='utf-8'))
    if current.get('owner_token') != token:
        raise ValueError('lease owner changed')
    current['last_owned_process'] = ownership['identity']
    tmp = lock.with_name(lock.name+'.'+token+'.pid.tmp')
    save(tmp, current)
    if json.loads(lock.read_text(encoding='utf-8')).get('owner_token') != token:
        raise ValueError('lease owner changed')
    os.replace(tmp, lock)

def read_json_state(path):
    try:
        if not path.exists():
            return 'ABSENT', None
        if path.stat().st_size > 262144:
            return 'INVALID', None
        value = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            return 'INVALID', None
        return 'VALID_JSON', value
    except (OSError, UnicodeError, ValueError):
        return 'INVALID', None

def decide(stage, record, raw, expected):
    if record.get('status') != 'HTTP_COMPLETE_UNPARSED':
        return 'STOP_TRANSPORT'
    if expected is not None:
        return 'PASS_INDEX' if exact_child(raw, expected) else 'STOP_INDEX_UNVALIDATED'
    return 'PASS_TRANSPORT_PREFIX_ONLY' if raw.startswith(b'SIMPLE  =') else 'STOP_PRODUCT_PREFIX'

def execute(expected_manifest):
    manifest, identity, curl_version = validate_inputs(expected_manifest)
    out = D / 'capture-v9'
    out.mkdir(exist_ok=False)
    save(out / 'CLAIM.json', {'started_utc':datetime.now(timezone.utc).isoformat(),
         'manifest_sha256':expected_manifest, 'protocol_sha256':manifest['protocol_sha256'],
         'identity':identity, 'curl_version':curl_version, 'scope':'availability only'})
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    lease = {'session':'astra-20261031T2113Z-01a193cc', 'owner_token':token,
             'directory':str(D), 'purpose':'SEDR5 bounded acquisition', 'adapter_pid':os.getpid(),
             'acquired_utc':now.isoformat(), 'expires_utc':(now+timedelta(minutes=10)).isoformat()}
    try:
        with LOCK.open('x', encoding='utf-8', newline='\n') as f:
            json.dump(lease, f); f.write('\n'); f.flush(); os.fsync(f.fileno())
    except FileExistsError:
        save(out/'RESULTS.json', {'status':'STOP_LIVE_OR_EXISTING_LEASE', 'requests_attempted':0})
        return 1
    results = []
    status = 'STOP_NOT_STARTED'
    last_finish = None
    cleanup_confirmed = True
    owned_pid = None
    ownership = {'pid':None, 'identity':None}
    interrupted = None
    current_stage = None
    try:
        spec = importlib.util.spec_from_file_location('fixed_transport', TRANSPORT)
        tr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tr)
        tr.sha = sha  # streamed hashing even if a monitored output overshoots
        tr.REQUEST_URLS = {name:url for name,url,_,_ in STAGES}
        tr.LIMITS.update(header_bytes=65536, stdout_bytes=4096, stderr_bytes=262144,
                         curl_seconds=45, process_seconds=48, poll_seconds=0.02,
                         owned_process_cleanup_seconds=2)
        deadline = time.perf_counter_ns() + 210_000_000_000
        status = 'COMPLETE_INDEXES_ONLY'
        for name, url, cap, expected_link in STAGES:
            if last_finish is not None:
                wait_for_next(last_finish, deadline)
            validate_inputs(expected_manifest)
            if time.perf_counter_ns() + 8_000_000_000 >= deadline:
                raise TimeoutError('batch deadline before request')
            tr.LIMITS['body_bytes'] = cap
            req = {'name':name, 'method':'GET', 'url':url, 'manifest_sha256':expected_manifest,
                   'protocol_sha256':manifest['protocol_sha256'], 'expected_link':expected_link,
                   'response_policy':'no redirects, no retries; native evidence local only'}
            cleanup_confirmed = False
            current_stage = name
            ownership['pid'] = None
            ownership['identity'] = None
            owned_pid = None
            def on_spawn(proc):
                bind_owned_pid(LOCK, token, out, name, proc, ownership)
            record = tr.fetch(out, req, name, deadline, owner_callback=on_spawn)
            owned_pid = ownership['pid']
            cleanup_confirmed = record.get('cleanup_status') in ('NOT_STARTED', 'EXIT_CONFIRMED')
            last_finish = time.perf_counter_ns()
            raw = out / (name + '.raw')
            if not cleanup_confirmed:
                status = 'STOP_OWNED_PROCESS_EXIT_UNCONFIRMED'
                results.append({'stage':name, 'decision':status, 'owned_pid':owned_pid,
                                'cleanup_status':record.get('cleanup_status')})
                break
            # A monitored overage is a terminal failure; never read it into memory.
            headers = out / (name + '.headers')
            valid_transport = (record.get('status') == 'HTTP_COMPLETE_UNPARSED'
                               and record.get('http_status') == 200
                               and record.get('ssl_verify_result') == 0
                               and record.get('num_redirects') == 0
                               and record.get('effective_url') == url
                               and record.get('returncode') == 0
                               and raw.is_file() and raw.stat().st_size <= cap
                               and headers.is_file() and headers.stat().st_size <= 65536
                               and sha(raw) == record.get('raw_sha256')
                               and sha(headers) == record.get('headers_sha256'))
            headers_verified = bool(valid_transport and valid_http_headers(headers.read_bytes(), 200, raw.stat().st_size))
            if not headers_verified:
                decision = 'STOP_TRANSPORT_OR_HEADERS'
            else:
                decision = decide(name, record, raw.read_bytes(), expected_link)
            result = {'stage':name, 'decision':decision, 'capture_record_sha256':sha(out/(name+'.json')),
                      'request_record_sha256':sha(out/(name+'.request.json')),
                      'body_sha256':record.get('raw_sha256'), 'body_bytes':record.get('raw_bytes'),
                      'http_status':record.get('http_status'), 'tls_verify_result':record.get('ssl_verify_result'),
                      'cleanup_status':record.get('cleanup_status'), 'owned_pid':owned_pid,
                      'http_headers_verified':headers_verified,
                      'polling_overshoot_possible':True}
            results.append(result)
            print(json.dumps(result), flush=True)
            if decision not in ('PASS_INDEX','PASS_TRANSPORT_PREFIX_ONLY'):
                status = decision
                break
            if name == 'product':
                status = 'PRODUCT_TRANSPORT_PREFIX_ONLY_IDENTITY_PENDING'
    except BaseException as exc:
        status = 'STOP_EXCEPTION'
        owned_pid = ownership['pid']
        results.append({'stage':'adapter','error_type':type(exc).__name__})
        interrupted = exc
    finally:
        current = json.loads(LOCK.read_text(encoding='utf-8')) if LOCK.exists() else {}
        if current.get('owner_token') == token and cleanup_confirmed:
            LOCK.unlink()
        elif current.get('owner_token') == token:
            current.update({'cleanup_status':'EXIT_UNCONFIRMED','last_owned_pid':owned_pid,
                            'last_owned_process':ownership['identity'],
                            'instruction':'Do not overwrite lease or kill by PID alone; verify process creation identity.'})
            tmp = LOCK.with_name(LOCK.name+'.'+token+'.tmp')
            save(tmp, current)
            if json.loads(LOCK.read_text(encoding='utf-8')).get('owner_token') != token:
                raise RuntimeError('lease owner changed')
            os.replace(tmp, LOCK)
        lifecycle = []
        for stage_name, stage_url, stage_cap, _ in STAGES:
            request_path = out/(stage_name+'.request.json')
            request_state, request_data = read_json_state(request_path)
            if request_state == 'VALID_JSON':
                req_data = request_data.get('request')
                seconds = request_data.get('effective_curl_seconds')
                command = request_data.get('command')
                expected_command = [CURL, '--disable', '--proto', '=https', '--connect-timeout', '15',
                    '--max-time', str(seconds), '--max-filesize', str(stage_cap), '--silent', '--show-error',
                    '--dump-header', str(out/(stage_name+'.headers')), '--output', str(out/(stage_name+'.raw')),
                    '--write-out', '%{http_code}\n%{ssl_verify_result}\n%{size_download}\n%{num_redirects}\n%{url_effective}\n',
                    '--url', stage_url]
                if (not isinstance(req_data, dict) or req_data.get('name') != stage_name
                        or req_data.get('method') != 'GET' or req_data.get('url') != stage_url
                        or req_data.get('manifest_sha256') != expected_manifest
                        or req_data.get('protocol_sha256') != manifest['protocol_sha256']
                        or type(seconds) is not int or not 1 <= seconds <= 45 or command != expected_command):
                    request_state = 'INVALID'
            owned_state, owned_data = read_json_state(out/(stage_name+'.owned.json'))
            if owned_state == 'VALID_JSON' and (owned_data.get('owner_token') != token
                    or not isinstance(owned_data.get('owned_process'), dict)
                    or not isinstance(owned_data['owned_process'].get('pid'), int)):
                owned_state = 'INVALID'
            native_state, native_data = read_json_state(out/(stage_name+'.json'))
            if native_state == 'VALID_JSON':
                if (request_state != 'VALID_JSON' or native_data.get('request_sha256') != sha(request_path)
                        or native_data.get('status') not in ('HTTP_COMPLETE_UNPARSED','FAILED_VISIBLE')):
                    native_state = 'INVALID'
            known_in_memory = stage_name == current_stage and ownership['pid'] is not None
            process_started = True if owned_state == 'VALID_JSON' or known_in_memory else (None if request_state != 'ABSENT' else False)
            http_complete = (native_data['status'] == 'HTTP_COMPLETE_UNPARSED') if native_state == 'VALID_JSON' else None
            lifecycle.append({'stage':stage_name, 'request_file_state':request_state,
                              'owned_file_state':owned_state, 'native_file_state':native_state,
                              'process_started':process_started, 'http_transport_complete':http_complete})
        result = {'finished_utc':datetime.now(timezone.utc).isoformat(), 'status':status,
                  'manifest_sha256':expected_manifest, 'records':results, 'lifecycle':lifecycle,
                  'request_files_present':sum(item['request_file_state'] != 'ABSENT' for item in lifecycle),
                  'requests_validly_recorded':sum(item['request_file_state'] == 'VALID_JSON' for item in lifecycle),
                  'not_prepared':[item['stage'] for item in lifecycle if item['request_file_state'] == 'ABSENT'],
                  'lease_released':not LOCK.exists(), 'owned_process_exit_confirmed':cleanup_confirmed,
                  'last_owned_pid':owned_pid, 'last_owned_process':ownership['identity'],
                  'product_identity_validated':False,
                  'new_orbit_or_holdout_evaluation':False,
                  'native_headers_and_diagnostics':'local evidence only; privacy review before any packaging'}
        save(out/'RESULTS.json', result)
    print(json.dumps({'status':status,'request_files_present':result['request_files_present'],
                      'lease_released':result['lease_released']}), flush=True)
    if interrupted is not None and not isinstance(interrupted, Exception):
        raise interrupted
    return 0 if status == 'PRODUCT_TRANSPORT_PREFIX_ONLY_IDENTITY_PENDING' else 1

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    return execute(args.manifest_sha256)

if __name__ == '__main__':
    raise SystemExit(main())