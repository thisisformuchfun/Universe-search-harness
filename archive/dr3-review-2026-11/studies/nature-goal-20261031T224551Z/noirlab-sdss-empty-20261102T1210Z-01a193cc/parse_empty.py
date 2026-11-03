"""Strict fixed-fixture reader for the NOIRLab forced-empty serialization control."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import hashlib,json,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parent
POS=D.parent/'noirlab-sdss-positive-v3-20261102T1205Z-01a193cc'
NAMES=['x_specobjid','gaia_source_id','ra1','dec1','ra2','dec2','distance','s_specobjid','plate','mjd','fiberid','fiber_ra','fiber_dec','run2d']
TYPES=['long','long','double','double','double','double','double','long','short','int','short','double','double','char']
PINS={'query':'fb7d5e6a5b0c6317d2973f95cf9afa7b6760d76f59ad7d5069036da98df83717',
 'protocol':'28322ad11d7604aafbc68a22076bf19a85c49ce6cabfa2fcaf6e217e1717cea5',
 'raw':'8a389807a54877647888c99308b49c539e134a9a4a1e68921d9a270e5d1b9d3e',
 'request':'5f84f9d51e8d3c8dea4d3f21c053e47daa5e3af76e5c902f9c616d7ea734140f',
 'native':'5903728cec5e77ba9b0fff1e7d76fe647d917b9069dfe17aacf16bbf0f4b6e4f',
 'result':'c80cf635080b26d22514708193564846b8a41f4786bd69f49c35f1c81f323a21',
 'finish':'738987fcaa4fb0ae585078d7e61feced161085c836348934282f5a497f96b957',
 'positive_raw':'4a2ca013b79bbe7bd1d57286f7504554f640139034c8f1e2dce35183a7f809f5'}
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
def parse_empty(raw,query,positive_raw):
 infos,fields,block=get_root(raw);_,pfields,_=get_root(positive_raw)
 queries=[n.attrib['value'] for n in infos if n.attrib['name']=='QUERY']
 counts=[n.attrib['value'] for n in infos if n.attrib['name']=='TableRows']
 if queries!=[query] or counts!=['0'] or len(block)!=0:raise ValueError('empty result, count or query mismatch')
 if [dict(x.attrib) for x in fields]!=[dict(x.attrib) for x in pfields]:raise ValueError('FIELD attributes differ from positive')
 return {'status':'PASS_FIXED_EMPTY_SERIALIZATION','row_count':0,'fields_match_positive':True,
         'scope':'contradictory predicate may bypass join; no source coverage conclusion'}
def main():
 paths={'query':D/'QUERY.adql','protocol':D/'PROTOCOL.md','raw':D/'capture/spec_empty.raw',
  'request':D/'capture/spec_empty.request.json','native':D/'capture/spec_empty.json','result':D/'capture/RESULT.json',
  'finish':D/'capture/FINISH.json','positive_raw':POS/'capture/spec_positive.raw'}
 frozen={k:p.read_bytes() for k,p in paths.items()}
 for k,v in frozen.items():
  if digest(v)!=PINS[k]:raise ValueError('pinned evidence mismatch: '+k)
 query=frozen['query'].decode('utf-8-sig').strip();req=json.loads(frozen['request']);n=json.loads(frozen['native']);r=json.loads(frozen['result']);fin=json.loads(frozen['finish'])
 url='https://datalab.noirlab.edu/tap/sync?'+urlencode([('REQUEST','doQuery'),('LANG','ADQL'),('FORMAT','votable'),('MAXREC','21'),('QUERY',query)])
 if (req['request'].get('url')!=url or req['request'].get('method')!='GET' or req['request'].get('protocol_sha256')!=PINS['protocol']
  or n.get('url')!=url or n.get('effective_url')!=url or n.get('request_sha256')!=PINS['request']
  or n.get('status')!='HTTP_COMPLETE_UNPARSED' or n.get('http_status')!=200 or n.get('ssl_verify_result')!=0
  or n.get('num_redirects')!=0 or n.get('returncode')!=0 or n.get('raw_sha256')!=PINS['raw']
  or n.get('raw_bytes')!=len(frozen['raw']) or r.get('body_sha256')!=PINS['raw']
  or r.get('status')!='HTTP_COMPLETE_VOTABLE_UNVALIDATED' or fin.get('terminal_sha256')!=PINS['result']
  or not fin.get('lease_released') or not fin.get('owned_process_exit_confirmed')):raise ValueError('transport proof mismatch')
 parsed=parse_empty(frozen['raw'],query,frozen['positive_raw'])
 out={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':PINS['raw'],'query_sha256':PINS['query'],'evidence_pins':PINS,'result':parsed}
 with (D/'EMPTY_CONTROL.json').open('x',encoding='utf8') as f:json.dump(out,f,indent=2);f.write('\n')
 print(json.dumps(parsed))
if __name__=='__main__':main()
