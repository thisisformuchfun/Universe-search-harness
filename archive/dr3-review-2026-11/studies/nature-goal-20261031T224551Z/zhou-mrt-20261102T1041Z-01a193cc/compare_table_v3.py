"""Validate the published fixed-width Gaia IDs and compare the frozen 14."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib, json, os, re, sys

D = Path(__file__).resolve().parent
S = D.parents[2]
TARGET = S/'followups'/'held14-20261031T214650Z'/'HELD_OBJECTS.json'
BODY = D/'capture-v9'/'table.raw'
CAPTURE_RESULT = D/'capture-v9'/'RESULTS.json'
ARTICLE = D.parent/'zhou-iop-route-v4-20261102T1034Z-01a193cc'/'capture-v9'/'article.raw'
ARTICLE_INSPECTION = D.parent/'zhou-iop-route-v4-20261102T1034Z-01a193cc'/'ARTICLE_INSPECTION.json'
MANIFEST = D/'COMPARE_MANIFEST_V3.json'
BODY_SHA = '94f41f32f8c0d34798fc223d4af10fd19a16fc63bc9e30069a6d2ff4ead90267'
TARGET_SHA = '989a7695c1f7110d54e703d2fd55ee4e016511b8adf568ca4ef5c2e370519d09'
CAPTURE_SHA = '6e3b841afed3198e9232456404149c9449aab1a050dd4e0fd03db2d50e8be76f'
ARTICLE_SHA = '88beb44cd30930f0f48dbb6746a2abe040d6f014ce26cc0aae7f069cef221ae6'
INSPECTION_SHA = '0525d00a0a7ebe771abc10c0ea74b1c2e59fb3b87960a5657ce30943d75ebf5c'
PREVIEW = {'1893474166810285952':'II', '470096784872760192':'II',
           '3369415484530173696':'III', '2876854139510029184':'III'}
TYPE_I = ('3443894276188890752', '1560560462739675904')
TARGET_IDS = ('632497706010874240', '824344003814438528', '1533365584518328576',
              '1538284425878995712', '2245423750054837888', '2852726284550996352',
              '3316050687674598656', '4299244434901041024', '4491401821468887552',
              '5591318172608607232', '5928370816455687808', '5929746958324419200',
              '5959603097090964992', '5991734159714775296')
HEADER_MARKERS = (b'Authors: Zhou, J.; Gu, W.-M.',
    b'Table: Catalog of Type II and Type III Long-period Binary Candidates for Compact-object Follow-up Observations',
    b'tab2.txt   197    17', b'Byte-by-byte Description of file: apjaeaa3at2_mrt.txt',
    b'1-19      I19      ---      GaiaDR3', b'63-65     A3       ---      Type')

def sha(data): return hashlib.sha256(data).hexdigest()

def read_verified(path, expected, limit=2000000):
    with path.open('rb') as f:
        data = f.read(limit+1)
    if len(data)>limit or sha(data)!=expected:
        raise ValueError('input exceeds bound or hash mismatch')
    return data

def parse_table(body):
    if len(body)>2000000 or b'\x00' in body: raise ValueError('invalid bytes')
    body.decode('ascii', errors='strict')
    if body.count(b'# Data table:') != 1: raise ValueError('data marker mismatch')
    header, data = body.split(b'# Data table:',1)
    if any(header.count(marker) != 1 for marker in HEADER_MARKERS): raise ValueError('header mismatch')
    lines = [line for line in data.splitlines() if line.strip()]
    if len(lines) != 17: raise ValueError('unexpected record count')
    ids = {}
    for line in lines:
        if len(line) != 197: raise ValueError('record width mismatch')
        field, typ = line[:19].strip(b' '), line[62:65].strip(b' ')
        if not re.fullmatch(rb'[1-9][0-9]{0,18}', field) or typ not in (b'II',b'III'):
            raise ValueError('invalid fixed-width ID or type')
        ident = field.decode('ascii')
        if ident in ids: raise ValueError('duplicate ID')
        ids[ident] = typ.decode('ascii')
    if Counter(ids.values()) != Counter({'II':5,'III':12}): raise ValueError('type counts mismatch')
    if any(ids.get(key) != value for key,value in PREVIEW.items()): raise ValueError('preview controls failed')
    if any(key in ids for key in TYPE_I): raise ValueError('Type I repeated in Table 2')
    return ids

def parse_targets(raw):
    obj = json.loads(raw)
    values = [item['source_id'] for item in obj['sources']]
    if (len(values) != 14 or any(not isinstance(x,str) or not re.fullmatch('[1-9][0-9]{0,18}',x) for x in values)
        or len(set(values)) != 14 or set(values) != set(TARGET_IDS)):
        raise ValueError('frozen held IDs mismatch')
    return values

def main(expected):
    if not re.fullmatch('[0-9a-f]{64}',expected): raise ValueError('manifest mismatch')
    manifest_bytes = read_verified(MANIFEST,expected,limit=100000)
    m = json.loads(manifest_bytes)
    inputs = {'body_sha256':BODY, 'target_sha256':TARGET, 'capture_result_sha256':CAPTURE_RESULT,
              'script_sha256':Path(__file__), 'tests_sha256':D/'test_compare_table_v3.py',
              'test_result_sha256':D/'COMPARE_TEST_RESULT_V3.json',
              'article_sha256':ARTICLE, 'inspection_sha256':ARTICLE_INSPECTION}
    blobs = {key:read_verified(path,m[key]) for key,path in inputs.items()}
    if m['body_sha256'] != BODY_SHA or m['target_sha256'] != TARGET_SHA or m['capture_result_sha256'] != CAPTURE_SHA:
        raise ValueError('unexpected pinned source')
    if m['article_sha256'] != ARTICLE_SHA or m['inspection_sha256'] != INSPECTION_SHA:
        raise ValueError('unexpected publisher-page evidence')
    test = json.loads(blobs['test_result_sha256'])
    if test.get('returncode') != 0 or test.get('tests_expected') != 12:
        raise ValueError('test evidence mismatch')
    read_verified(D/'COMPARE_TEST_STDOUT_V3.raw',test.get('stdout_sha256'))
    read_verified(D/'COMPARE_TEST_STDERR_V3.raw',test.get('stderr_sha256'))
    capture = json.loads(blobs['capture_result_sha256'])
    if capture.get('status') != 'STOP_UNPARSED_CONTENT' or capture.get('owned_process_exit_confirmed') is not True:
        raise ValueError('unexpected transport state')
    table = parse_table(blobs['body_sha256'])
    targets = parse_targets(blobs['target_sha256'])
    matches_17 = sorted(set(targets) & set(table))
    matches_type_i = sorted(set(targets) & set(TYPE_I))
    result = {'finished_utc':datetime.now(timezone.utc).isoformat(), 'comparison_manifest_sha256':expected,
              'table_body_sha256':BODY_SHA, 'publisher_article_sha256':ARTICLE_SHA,
              'publisher_inspection_sha256':INSPECTION_SHA, 'target_sha256':TARGET_SHA, 'target_count':14,
              'table2_rows':len(table), 'table2_unique_ids':len(table), 'type_counts':dict(Counter(table.values())),
              'preview_controls_passed':len(PREVIEW), 'table1_type_i_count':2,
              'table2_matches':matches_17, 'table1_type_i_matches':matches_type_i,
              'identifier_handling':'exact ASCII decimal strings; fixed-width field; never float',
              'scope':'this published 19-object sample only; nonmatch is not novelty or a BH conclusion',
              'holdout_evaluated':False, 'science_policy_changed':False}
    encoded = (json.dumps(result,indent=2)+'\n').encode()
    with (D/'COMPARISON_RESULT_V3.json').open('xb') as f: f.write(encoded); f.flush(); os.fsync(f.fileno())
    print(json.dumps(result))

if __name__ == '__main__':
    if len(sys.argv)!=2: raise SystemExit('usage: compare_table_v3.py MANIFEST_SHA256')
    main(sys.argv[1])
