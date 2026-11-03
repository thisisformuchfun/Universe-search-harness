"""Reviewed, bounded SEDR5 sample-control and existing-fibre query."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
import uuid
import schema_v1 as wire

D = Path(__file__).resolve().parent
T = D.parent
S = D.parents[2]
C = S.parent / 'coordination'
PRIOR = T / 'held1533-sedr5-20261102T081926Z-01a193cc'
SAMPLE = T / 'sedr5-catalogue-sample-20261102T085730Z-01a193cc/capture-v1/sample.raw'
LIB = PRIOR / 'capture_serial_v9.py'
LOCK = C / 'sedr5-acquisition.lock'
URL = 'https://nadc.china-vo.org/data/data/general/sedr5/sexprv/build.csvs'
BOUNDARY = 'astra-sedr5-01a193cc-boundary'
CONTROL = '20150309/HD110643N151055B02/20150309_HD110643N151055B02_15_142.fit'
TARGET = '20150108/HD122456N425117B01/20150108_HD122456N425117B01_01_037.fit'
CONTROL_PRED = '20150309HD110643N151055B0215142'
TARGET_PRED = '20150108HD122456N425117B0101037'
CONTROL_KEY = {'specid':'20150309HD110643N151055B0215142', 'iexp':'0',
               'mjm':'82211011', 'obsid':'331215142'}
FIELDS = 'specid obsdate planid spid fiberid iexp mjm sng sni subclass rv rverr rvpa teff logg feh minchi2 npix nabsline fratio fratio_b fratio_r obsid designation gid ra dec spec filename'.split()
CHAR = {'specid','planid','mjm','subclass','designation','spec','filename'}
CAP = 524288


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def multipart(specid):
    if specid not in (CONTROL_PRED, TARGET_PRED):
        raise ValueError('identifier outside frozen study')
    items = [('pos.ramin',''),('pos.decmin',''),('pos.ramax',''),('pos.decmax',''),
             ('pos.cra','0.0'),('pos.cdec','0.0'),('pos.cradius','0.0'),
             ('pos.postextarea','#ra,dec,sep\r\n'),('pos.posfile',None),
             ('pos.defaultradius','2'),('pos.type','none'),('showcolcheck','')]
    for field in FIELDS:
        items.append(('showcol','sexprv.'+field))
        if field in CHAR:
            items.append(('sexprv.'+field+'.char', specid if field == 'specid' else ''))
        else:
            items.extend([('sexprv.'+field+'.min',''),('sexprv.'+field+'.max','')])
    data = bytearray()
    for name, value in items:
        data.extend(('--'+BOUNDARY+'\r\n').encode('ascii'))
        if value is None:
            data.extend(('Content-Disposition: form-data; name="'+name+'"; filename=""\r\n'
                         'Content-Type: application/octet-stream\r\n\r\n\r\n').encode('ascii'))
        else:
            data.extend(('Content-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode('ascii'))
    data.extend(('--'+BOUNDARY+'--\r\n').encode('ascii'))
    return bytes(data)


def parse_csv(raw):
    return wire.parse_csv(raw)[1]


def control_passes(rows):
    return (bool(rows) and all(row['filename'] == CONTROL and row['specid'] == CONTROL_PRED for row in rows)
            and sum(all(row[k] == v for k,v in CONTROL_KEY.items()) for row in rows) == 1)


def identity_summary(rows):
    keys = ('specid','obsdate','planid','spid','fiberid','iexp','mjm','obsid','gid','filename')
    return {'row_count':len(rows), 'all_exact_specid':bool(rows) and all(r['specid']==TARGET_PRED for r in rows),
            'identity_rows':[{k:r[k] for k in keys} for r in rows]}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(expected):
    manifest = D/'MANIFEST.json'
    if not re.fullmatch('[0-9a-f]{64}',expected) or sha(manifest) != expected:
        raise ValueError('manifest mismatch')
    m = json.loads(manifest.read_text(encoding='utf-8'))
    paths = {'script_sha256':Path(__file__), 'protocol_sha256':D/'PROTOCOL.md',
             'transport_sha256':D/'native_transport_post_v1.py', 'library_sha256':LIB,
             'schema_sha256':D/'schema_v1.py', 'test_sha256':D/'test_specid_v1.py', 'test_result_sha256':D/'TEST_RESULT.json',
             'sample_sha256':SAMPLE, 'control_body_sha256':D/'control.body',
             'target_body_sha256':D/'target.body'}
    if any(sha(path) != m[key] for key,path in paths.items()):
        raise ValueError('pinned input mismatch')
    if m['library_sha256'] != '3f9b82d0ce290efc280dd4e70e1963045bc95aa527cf880387e6f8ccbcb525f5':
        raise ValueError('unexpected capture helper')
    if m['sample_sha256'] != '445105154437335a95353a37aecbe93609d89a48bdee3b99fbcb54be33de8513':
        raise ValueError('unexpected public sample')
    if (D/'control.body').read_bytes() != multipart(CONTROL_PRED) or (D/'target.body').read_bytes() != multipart(TARGET_PRED):
        raise ValueError('body differs from frozen form')
    sample = parse_csv(SAMPLE.read_bytes())
    if sum(row['filename']==CONTROL and all(row[k]==v for k,v in CONTROL_KEY.items()) for row in sample) != 1:
        raise ValueError('sample control tuple not unique')
    test = json.loads((D/'TEST_RESULT.json').read_text(encoding='utf-8'))
    if (test.get('returncode') != 0 or test.get('tests_expected') != 11
            or sha(D/'TEST_STDOUT.raw') != test.get('stdout_sha256')
            or sha(D/'TEST_STDERR.raw') != test.get('stderr_sha256')):
        raise ValueError('offline tests not established')
    version = subprocess.run(['C:/Windows/System32/curl.exe','--disable','--version'],
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,check=True).stdout.decode('ascii').splitlines()[0]
    match = re.match(r'^curl (\d+)\.(\d+)\.(\d+)',version)
    if not match or tuple(map(int,match.groups())) < (8,4,0):
        raise ValueError('curl streaming body cap unavailable')
    return m,version


def main(expected):
    m,version = validate(expected)
    lib = load('capture_helpers',LIB)
    tr = load('reviewed_post_transport',D/'native_transport_post_v1.py')
    tr.PAYLOADS = {'control':(D/'control.body',m['control_body_sha256']),
                   'target':(D/'target.body',m['target_body_sha256'])}
    tr.LIMITS.update(body_bytes=CAP,header_bytes=65536,stdout_bytes=4096,stderr_bytes=262144,
                     curl_seconds=45,process_seconds=48,poll_seconds=0.02,owned_process_cleanup_seconds=2)
    out = D/'capture-v1'
    out.mkdir(exist_ok=False)
    save(out/'CLAIM.json',{'started_utc':datetime.now(timezone.utc).isoformat(),
                           'manifest_sha256':expected,'curl_version':version})
    token = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    lease = {'session':'astra-20261031T2113Z-01a193cc','owner_token':token,'directory':str(D),
             'purpose':'SEDR5 sample-control then target specid query','adapter_pid':os.getpid(),
             'acquired_utc':now.isoformat(),'expires_utc':(now+timedelta(minutes=4)).isoformat()}
    try:
        save(LOCK,lease)
    except FileExistsError:
        save(out/'RESULTS.json',{'status':'STOP_EXISTING_LEASE','requests_started':0})
        return 1
    owner = {'pid':None,'identity':None}
    cleanup_confirmed = True
    status = 'STOP_NOT_STARTED'
    summaries = {}
    interrupted = None
    try:
        deadline = time.perf_counter_ns()+110_000_000_000
        for name in ('control','target'):
            owner = {'pid':None,'identity':None}
            payload_hash = m[name+'_body_sha256']
            request = {'name':name,'method':'POST','url':URL,'payload_sha256':payload_hash,
                       'manifest_sha256':expected,'protocol_sha256':m['protocol_sha256'],
                       'scope':'public catalogue identity metadata; no RV analysis'}
            def on_spawn(proc, stage=name):
                lib.bind_owned_pid(LOCK,token,out,stage,proc,owner)
            cleanup_confirmed = False
            record = tr.fetch(out,request,name,deadline,owner_callback=on_spawn)
            cleanup_confirmed = record.get('cleanup_status') in ('NOT_STARTED','EXIT_CONFIRMED')
            if not cleanup_confirmed:
                status = 'STOP_OWNED_PROCESS_EXIT_UNCONFIRMED'
                break
            raw, headers = out/(name+'.raw'), out/(name+'.headers')
            valid = (record.get('status') == 'HTTP_COMPLETE_UNPARSED' and record.get('http_status') == 200
                     and record.get('ssl_verify_result') == 0 and record.get('num_redirects') == 0
                     and record.get('effective_url') == URL and record.get('returncode') == 0
                     and raw.is_file() and raw.stat().st_size <= CAP and headers.is_file()
                     and headers.stat().st_size <= 65536 and sha(raw) == record.get('raw_sha256')
                     and sha(headers) == record.get('headers_sha256'))
            if not valid or not lib.valid_http_headers(headers.read_bytes(),200,raw.stat().st_size):
                status = 'STOP_TRANSPORT_OR_HEADERS_'+name.upper()
                break
            kind,rows = wire.parse_csv(raw.read_bytes())
            if kind != 'QUERY_PREFIXED':
                status = 'STOP_UNEXPECTED_QUERY_SCHEMA_'+name.upper()
                break
            if name == 'control':
                summaries['control'] = {'row_count':len(rows),'same_specid_filename_and_sample_tuple':control_passes(rows)}
                if not control_passes(rows):
                    status = 'STOP_CONTROL_UNVERIFIED'
                    break
                time.sleep(1)
            else:
                summaries['target'] = identity_summary(rows)
                status = ('TARGET_SPECID_ROWS_IDENTITY_UNVALIDATED' if summaries['target']['all_exact_specid']
                          else 'TARGET_EMPTY_OR_FOREIGN_UNRESOLVED')
    except BaseException as exc:
        status = 'STOP_EXCEPTION'
        summaries['error_type'] = type(exc).__name__
        interrupted = exc
    finally:
        current = json.loads(LOCK.read_text(encoding='utf-8')) if LOCK.exists() else {}
        if current.get('owner_token') == token and cleanup_confirmed:
            LOCK.unlink()
        elif current.get('owner_token') == token:
            current.update({'cleanup_status':'EXIT_UNCONFIRMED','last_owned_pid':owner['pid'],
                            'last_owned_process':owner['identity'],
                            'instruction':'Do not overwrite lease or kill by PID alone.'})
            tmp = LOCK.with_name(LOCK.name+'.'+token+'.tmp')
            save(tmp,current)
            if json.loads(LOCK.read_text(encoding='utf-8')).get('owner_token') != token:
                raise RuntimeError('lease owner changed')
            os.replace(tmp,LOCK)
        result = {'finished_utc':datetime.now(timezone.utc).isoformat(),'status':status,
                  'manifest_sha256':expected,'summaries':summaries,
                  'request_files':[p.name for p in sorted(out.glob('*.request.json'))],
                  'owned_process_exit_confirmed':cleanup_confirmed,'last_owned_pid':owner['pid'],
                  'last_owned_process':owner['identity'],
                  'lease_released':not LOCK.exists(),'holdout_evaluated':False,'rv_analysis_performed':False,
                  'native_headers_and_diagnostics':'local only; privacy review required before packaging'}
        save(out/'RESULTS.json',result)
    visible = {key:{k:v for k,v in value.items() if k != 'identity_rows'} if isinstance(value,dict) else value
               for key,value in summaries.items()}
    print(json.dumps({'status':status,'summaries':visible,'lease_released':result['lease_released']}),flush=True)
    if interrupted is not None and not isinstance(interrupted,Exception):
        raise interrupted
    return 0 if status == 'TARGET_SPECID_ROWS_IDENTITY_UNVALIDATED' else 1


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: query_specid_v1.py MANIFEST_SHA256')
    raise SystemExit(main(sys.argv[1]))
