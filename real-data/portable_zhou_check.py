"""Offline reproduction of the finite ID comparison in the portable handoff."""
from pathlib import Path
from collections import Counter
import hashlib, json, re

ROOT=Path(__file__).resolve().parent
STUDY=ROOT/'studies'/'nature-goal-20261031T224551Z'/'zhou-mrt-20261102T1041Z-01a193cc'
BODY=STUDY/'capture-v9'/'table.raw'
TARGET=ROOT/'followups'/'held14-20261031T214650Z'/'HELD_OBJECTS.json'
PINS={BODY:'94f41f32f8c0d34798fc223d4af10fd19a16fc63bc9e30069a6d2ff4ead90267',
      TARGET:'989a7695c1f7110d54e703d2fd55ee4e016511b8adf568ca4ef5c2e370519d09'}
PREVIEW={'1893474166810285952':'II','470096784872760192':'II',
         '3369415484530173696':'III','2876854139510029184':'III'}
TYPE_I={'3443894276188890752','1560560462739675904'}
def read(path):
    with path.open('rb') as f: data=f.read(2000001)
    if len(data)>2000000 or hashlib.sha256(data).hexdigest()!=PINS[path]:
        raise ValueError('input exceeds bound or hash mismatch')
    return data
def main():
    body=read(BODY); targets=read(TARGET)
    if body.count(b'# Data table:')!=1: raise ValueError('data marker mismatch')
    rows=[row for row in body.split(b'# Data table:',1)[1].splitlines() if row.strip()]
    if len(rows)!=17 or any(len(row)!=197 for row in rows): raise ValueError('table shape mismatch')
    table={}
    for row in rows:
        ident,typ=row[:19].strip(b' '),row[62:65].strip(b' ')
        if not re.fullmatch(rb'[1-9][0-9]{0,18}',ident) or typ not in (b'II',b'III'):
            raise ValueError('invalid ID or type')
        key=ident.decode('ascii')
        if key in table: raise ValueError('duplicate ID')
        table[key]=typ.decode('ascii')
    held=[row['source_id'] for row in json.loads(targets)['sources']]
    if (len(held)!=14 or len(set(held))!=14 or any(not isinstance(x,str) or
        not re.fullmatch('[1-9][0-9]{0,18}',x) for x in held)):
        raise ValueError('invalid held IDs')
    a=sorted(set(held)&set(table)); b=sorted(set(held)&TYPE_I)
    if (a or b or Counter(table.values())!=Counter({'II':5,'III':12})
        or any(table.get(k)!=v for k,v in PREVIEW.items()) or set(table)&TYPE_I):
        raise ValueError('unexpected comparison result')
    print(json.dumps({'table2_unique_ids':17,'table1_type_i_ids':2,'held_targets':14,
                      'table2_matches':a,'type_i_matches':b,
                      'scope':'one paper only; nonmatch does not establish novelty',
                      'publisher_page_association':'not revalidated by this offline check'}))
if __name__=='__main__': main()
