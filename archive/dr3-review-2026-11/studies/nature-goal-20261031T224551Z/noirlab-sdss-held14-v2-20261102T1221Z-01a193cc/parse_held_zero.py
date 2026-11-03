"""Strict fixed-fixture reader for one original-14 NOIRLab zero-row response."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import hashlib,json,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parent
POS=D.parent/'noirlab-sdss-positive-v3-20261102T1205Z-01a193cc'
SHAPE=D.parent/'noirlab-sdss-shape-20261102T1216Z-01a193cc'
GAIA=D.parents[2]/'followups/held14-20261031T214650Z/evidence/gaia/source_all14.parsed.json'
HELD=D.parents[2]/'followups/held14-20261031T214650Z/HELD_OBJECTS.json'
NAMES=['x_specobjid','gaia_source_id','ra1','dec1','ra2','dec2','distance','s_specobjid','plate','mjd','fiberid','fiber_ra','fiber_dec','run2d']
TYPES=['long','long','double','double','double','double','double','long','short','int','short','double','double','char']
PINS={'query':'61ff172fefa3ed8f9081b1095d471d63b820fcbfb33e097474c31183e6db96e6',
 'protocol':'6254c6db77af4acc38a5d40a1df15afa692249b1c3c86ec0878c294ca0c9bb8b',
 'raw':'141ee7d0db411c2a2d8019648c9d7a1446f1354c09c9282e83d42293f38bf4a7',
 'request':'21a9a0dd47903a8c1f409f2b81e44775c6c73df45dba9663125d09c2fddf598f',
 'native':'e4023467599ff2ff766a890084665538f6bbf62c7b9213812873a282f42bd016',
 'result':'171f01cb3a896158162f9dfc51155e5214717dff336b74046c99d852b3afe87d',
 'finish':'beab0fe660eb401d348aa40f4966a8d7c1cb22cf494ccee2483ab78c257a62be',
 'positive_raw':'4a2ca013b79bbe7bd1d57286f7504554f640139034c8f1e2dce35183a7f809f5',
 'manifest':'492881e4f72087336be505980092257fcd5957ff66ee6a9d61219906d597ef1a','gaia':'ac3b2ef6fdbc44b732404d1e5f8db4801185f1a10977959c4a1318d9cd426862',
 'held':'989a7695c1f7110d54e703d2fd55ee4e016511b8adf568ca4ef5c2e370519d09','positive_query':'35501f4e6b6234ccc1a88498cac569992da849b6b3a498fdaa839f261d32c28b',
 'shape_inventory':'bb7ced87ae4a75f9ca429edef539fce86349d02d177ce6b123a134f1adc243f7','shape_review':'968829fe9809564d3ee1989cc51140ca3e034475e501cc3d4087618aa3675d22'}
def digest(b):return hashlib.sha256(b).hexdigest()
def blank(s):return s is None or all(c in ' \t\r\n' for c in s)
def container(n):
 if not blank(n.text) or any(not blank(c.tail) for c in n):raise ValueError('mixed XML text')
def get_root(raw):
 if len(raw)>1000000 or b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe XML')
 raw.decode('utf8','strict');root=ET.fromstring(raw)
 if root.tag!='VOTABLE' or root.attrib.get('version')!='1.2' or any(not isinstance(n.tag,str) or n.tag.startswith('{') for n in root.iter()):raise ValueError('unsupported VOTable')
 container(root)
 if len(root)!=1 or root[0].tag!='RESOURCE' or root[0].attrib!={'type':'results'}:raise ValueError('resource ambiguity')
 res=root[0];container(res)
 if any(n.tag not in ('DESCRIPTION','INFO','TABLE') for n in res):raise ValueError('unexpected resource child')
 desc=[n for n in res if n.tag=='DESCRIPTION']
 if len(desc)>1 or any(n.attrib or len(n) for n in desc):raise ValueError('invalid description')
 infos=[n for n in res if n.tag=='INFO'];tables=[n for n in res if n.tag=='TABLE']
 if len([n for n in root.iter() if n.tag=='INFO'])!=len(infos) or any(len(n) or not blank(n.text) or set(n.attrib)!={'name','value'} or n.attrib['name'] not in ('QUERY_STATUS','QUERY','TableRows') for n in infos):raise ValueError('invalid INFO')
 if len(tables)!=1 or tables[0].attrib:raise ValueError('invalid TABLE')
 statuses=[n.attrib['value'] for n in infos if n.attrib['name']=='QUERY_STATUS']
 if statuses!=['OK'] or list(res).index(next(n for n in infos if n.attrib['name']=='QUERY_STATUS'))>list(res).index(tables[0]):raise ValueError('invalid TAP status')
 table=tables[0];container(table);fields=[n for n in table if n.tag=='FIELD'];data=[n for n in table if n.tag=='DATA']
 if len(fields)!=len(NAMES) or len(data)!=1 or len(table)!=len(fields)+1:raise ValueError('invalid table structure')
 for field,name,typ in zip(fields,NAMES,TYPES):
  container(field)
  if field.attrib.get('name')!=name or field.attrib.get('ID')!=name or field.attrib.get('datatype')!=typ:raise ValueError('field identity/type mismatch')
  if typ=='char' and field.attrib.get('arraysize')!='32':raise ValueError('char width mismatch')
  if any(c.tag!='DESCRIPTION' or c.attrib or len(c) for c in field) or len(field)>1:raise ValueError('field/null definition unsupported')
 data=data[0]
 if data.attrib:raise ValueError('unsupported DATA attributes')
 container(data)
 if len(data)!=1 or data[0].tag!='TABLEDATA' or data[0].attrib:raise ValueError('TABLEDATA missing')
 block=data[0];container(block)
 return infos,fields,block
def parse_held_zero(raw,query,positive_raw):
 infos,fields,block=get_root(raw);_,pfields,_=get_root(positive_raw)
 queries=[n.attrib['value'] for n in infos if n.attrib['name']=='QUERY']
 counts=[n.attrib['value'] for n in infos if n.attrib['name']=='TableRows']
 if queries!=[query] or counts!=['0'] or len(block)!=0:raise ValueError('empty result, count or query mismatch')
 if [dict(x.attrib) for x in fields]!=[dict(x.attrib) for x in pfields]:raise ValueError('FIELD attributes differ from positive')
 return {'status':'COMPLETE_ZERO_SELECTED_CROSSMATCH','row_count':0,'fields_match_positive':True,
         'scope':'zero rows only for this clean-view nearest-neighbor predicate; not proof of no spectra'}
def verify_ids_and_query(frozen,query):
 gaia=json.loads(frozen['gaia'].decode('utf8'));held=json.loads(frozen['held'].decode('utf8'))['sources']
 ids=[r.get('source_id') for r in gaia]; hids=[r.get('source_id') for r in held]
 if len(ids)!=14 or len(set(ids))!=14 or any(type(x) is not str or not x.isdecimal() for x in ids) or len(hids)!=14 or set(ids)!=set(hids):raise ValueError('original 14 mismatch')
 prior=frozen['positive_query'].decode('utf-8-sig').strip(); anchor='WHERE x.id2=1607896637338835712 ORDER BY x.id1'
 if prior.count(anchor)!=1 or not prior.startswith('SELECT TOP 20 '):raise ValueError('positive anchor mismatch')
 ids=sorted(ids,key=int); expected=prior.replace('SELECT TOP 20 ','SELECT TOP 201 ',1).replace(anchor,'WHERE x.id2 IN ('+','.join(ids)+') ORDER BY x.id2,x.id1')
 if query!=expected:raise ValueError('target query mismatch')
 if json.loads(frozen['shape_inventory'])['result']['status']!='PASS_FIXED_14_VALUE_SHAPE_CONTROL':raise ValueError('shape control not accepted')
 return ids

def main():
 paths={'query':D/'QUERY.adql','protocol':D/'PROTOCOL.md','raw':D/'capture/held14_search.raw',
  'request':D/'capture/held14_search.request.json','native':D/'capture/held14_search.json','result':D/'capture/RESULT.json',
  'finish':D/'capture/FINISH.json','positive_raw':POS/'capture/spec_positive.raw',
  'manifest':D/'MANIFEST.json','gaia':GAIA,'held':HELD,'positive_query':POS/'QUERY.adql',
  'shape_inventory':SHAPE/'SHAPE_CONTROL.json','shape_review':SHAPE/'INDEPENDENT_PARSER_REVIEW.md'}
 frozen={k:p.read_bytes() for k,p in paths.items()}
 for k,v in frozen.items():
  if digest(v)!=PINS[k]:raise ValueError('pinned evidence mismatch: '+k)
 query=frozen['query'].decode('utf-8-sig').strip();req=json.loads(frozen['request']);n=json.loads(frozen['native']);r=json.loads(frozen['result']);fin=json.loads(frozen['finish'])
 url='https://datalab.noirlab.edu/tap/sync?'+urlencode([('REQUEST','doQuery'),('LANG','ADQL'),('FORMAT','votable'),('MAXREC','201'),('QUERY',query)])
 if (req['request'].get('url')!=url or req['request'].get('method')!='GET' or req['request'].get('protocol_sha256')!=PINS['protocol'] or req['request'].get('manifest_sha256')!=PINS['manifest']
  or n.get('url')!=url or n.get('effective_url')!=url or n.get('request_sha256')!=PINS['request']
  or n.get('status')!='HTTP_COMPLETE_UNPARSED' or n.get('http_status')!=200 or n.get('ssl_verify_result')!=0
  or n.get('num_redirects')!=0 or n.get('returncode')!=0 or n.get('raw_sha256')!=PINS['raw']
  or n.get('raw_bytes')!=len(frozen['raw']) or r.get('body_sha256')!=PINS['raw']
  or r.get('status')!='HTTP_COMPLETE_VOTABLE_UNVALIDATED' or fin.get('terminal_sha256')!=PINS['result']
  or not fin.get('lease_released') or not fin.get('owned_process_exit_confirmed')):raise ValueError('transport proof mismatch')
 ids=verify_ids_and_query(frozen,query)
 parsed=parse_held_zero(frozen['raw'],query,frozen['positive_raw'])
 parsed['queried_source_ids']=ids
 parsed['shape_control_status']=json.loads(frozen['shape_inventory'])['result']['status']
 out={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':PINS['raw'],'query_sha256':PINS['query'],'evidence_pins':PINS,'result':parsed}
 with (D/'HELD14_CROSSMATCH_ZERO.json').open('x',encoding='utf8') as f:json.dump(out,f,indent=2);f.write('\n')
 print(json.dumps(parsed))
if __name__=='__main__':main()
