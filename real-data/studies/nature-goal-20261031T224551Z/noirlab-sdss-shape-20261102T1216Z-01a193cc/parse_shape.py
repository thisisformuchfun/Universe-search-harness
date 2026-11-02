"""Strict fixed-fixture reader for the non-held 14-value NOIRLab shape control."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import hashlib,json,math,re,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parent
NAMES=['x_specobjid','gaia_source_id','ra1','dec1','ra2','dec2','distance','s_specobjid','plate','mjd','fiberid','fiber_ra','fiber_dec','run2d']
TYPES=['long','long','double','double','double','double','double','long','short','int','short','double','double','char']
PINS={'query':'93f70657397332201f9e57ce653d158ac42b411eaa2b03540c33e6d4c9778308',
 'protocol':'f20273833aec24a5a5b4a4f6952eeb43aab9ac45fbd0346c4a852cbac2f3ac21',
 'raw':'7c2a79ab93566c877e94d6dc4e674e7bc85c4920cf375cc4d0bbbf0ccf2ddf5f',
 'request':'2893c7ca16f9ff0c7d4a230f30b6bf4f43439f3c04cdd03ee3016d3378bfcabf',
 'native':'3f98af9a41f2255e567710c7e6da7eba8f89b7509cc8e4cf415433127a99f429',
 'result':'3c6f0933b846495d9ac973b3802c05cb54ea51fa52606a8bd23e665a1c31ef1e',
 'finish':'01a189a16b73fa97ae0165b59fe08da3c6efa19883a5c7d09362e3f92c72aa98'}
def digest(b):return hashlib.sha256(b).hexdigest()
def xmlblank(s):return s is None or all(c in ' \t\r\n' for c in s)
def container(n):
 if not xmlblank(n.text) or any(not xmlblank(c.tail) for c in n):raise ValueError('mixed XML text')
def separation(ra1,dec1,ra2,dec2):
 a,b,c,d=map(math.radians,(ra1,dec1,ra2,dec2))
 z=math.sin((b-d)/2)**2+math.cos(b)*math.cos(d)*math.sin((a-c)/2)**2
 return math.degrees(2*math.asin(math.sqrt(min(1,max(0,z)))))*3600
def parse_shape(raw,query):
 if len(raw)>1000000 or b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe XML')
 raw.decode('utf8','strict');root=ET.fromstring(raw)
 if root.tag!='VOTABLE' or root.attrib.get('version')!='1.2' or any(not isinstance(n.tag,str) or n.tag.startswith('{') for n in root.iter()):raise ValueError('unsupported VOTable')
 container(root)
 if len(root)!=1 or root[0].tag!='RESOURCE' or root[0].attrib!={'type':'results'}:raise ValueError('resource ambiguity')
 resource=root[0];container(resource)
 if any(n.tag not in ('DESCRIPTION','INFO','TABLE') for n in resource):raise ValueError('unexpected resource child')
 descriptions=[n for n in resource if n.tag=='DESCRIPTION']
 if len(descriptions)>1 or any(n.attrib or len(n) for n in descriptions):raise ValueError('bad resource description')
 infos=[n for n in resource if n.tag=='INFO'];tables=[n for n in resource if n.tag=='TABLE']
 if len([n for n in root.iter() if n.tag=='INFO'])!=len(infos) or any(len(n) or not xmlblank(n.text) or set(n.attrib)!={'name','value'} or n.attrib['name'] not in ('QUERY_STATUS','QUERY','TableRows') for n in infos):raise ValueError('bad INFO')
 statuses=[n.attrib['value'] for n in infos if n.attrib['name']=='QUERY_STATUS']
 queries=[n.attrib['value'] for n in infos if n.attrib['name']=='QUERY']
 counts=[n.attrib['value'] for n in infos if n.attrib['name']=='TableRows']
 if statuses!=['OK'] or queries!=[query] or len(counts)!=1 or not counts[0].isdigit() or len(tables)!=1:raise ValueError('bad TAP status, echo or count')
 table=tables[0]
 if list(resource).index(next(n for n in infos if n.attrib['name']=='QUERY_STATUS'))>list(resource).index(table) or table.attrib:raise ValueError('missing leading status or unsupported TABLE attributes')
 container(table);fields=[n for n in table if n.tag=='FIELD'];data=[n for n in table if n.tag=='DATA']
 if len(fields)!=len(NAMES) or len(data)!=1 or len(table)!=len(fields)+1:raise ValueError('bad table structure')
 for field,name,typ in zip(fields,NAMES,TYPES):
  container(field)
  if field.attrib.get('name')!=name or field.attrib.get('ID')!=name or field.attrib.get('datatype')!=typ:raise ValueError('field identity/type mismatch')
  if typ=='char' and field.attrib.get('arraysize')!='32':raise ValueError('unsupported char width')
  if any(c.tag!='DESCRIPTION' or c.attrib or len(c) for c in field) or len(field)>1:raise ValueError('unsupported field/null definition')
 data=data[0]
 if data.attrib:raise ValueError('DATA attributes unsupported')
 container(data)
 if len(data)!=1 or data[0].tag!='TABLEDATA' or data[0].attrib:raise ValueError('unsupported DATA encoding')
 block=data[0];container(block);records=[];seen=set()
 for tr in block:
  if tr.tag!='TR' or tr.attrib:raise ValueError('bad row')
  container(tr);cells=list(tr)
  if len(cells)!=len(NAMES) or any(c.tag!='TD' or c.attrib or len(c) or c.text is None for c in cells):raise ValueError('null/bad cell')
  row=dict(zip(NAMES,[c.text for c in cells]))
  for k in ('x_specobjid','gaia_source_id','s_specobjid','plate','mjd','fiberid'):
   if not re.fullmatch(r'0|[1-9][0-9]*',row[k]):raise ValueError('noncanonical integer')
  if any(int(row[k])>9223372036854775807 for k in ('x_specobjid','gaia_source_id','s_specobjid')):raise ValueError('long out of range')
  if any(int(row[k])>32767 for k in ('plate','fiberid')) or int(row['mjd'])>2147483647:raise ValueError('integer out of range')
  allowed={str(i) for i in range(1,14)}|{'1607896637338835712'}
  if row['gaia_source_id'] not in allowed or row['x_specobjid']!=row['s_specobjid']:raise ValueError('wrong source or join')
  if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',row['run2d']):raise ValueError('invalid run2d')
  key=(row['gaia_source_id'],row['x_specobjid'],row['plate'],row['mjd'],row['fiberid'],row['run2d'])
  if key in seen:raise ValueError('duplicate identity')
  seen.add(key)
  for k in ('ra1','dec1','ra2','dec2','distance','fiber_ra','fiber_dec'):
   if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',row[k]):raise ValueError('noncanonical float')
   row[k]=float(row[k])
   if not math.isfinite(row[k]):raise ValueError('nonfinite coordinate')
  if not all(0<=row[k]<360 for k in ('ra1','ra2','fiber_ra')) or not all(-90<=row[k]<=90 for k in ('dec1','dec2','fiber_dec')) or not 0<=row['distance']<=1.5:raise ValueError('out-of-range geometry')
  if abs(row['ra1']-row['fiber_ra'])>1e-9 or abs(row['dec1']-row['fiber_dec'])>1e-9:raise ValueError('crossmatch/fibre coordinates disagree')
  sep=separation(row['ra1'],row['dec1'],row['ra2'],row['dec2'])
  if abs(sep-row['distance'])>0.01:raise ValueError('separation inconsistent under degree assumption')
  row['computed_separation_arcsec_assuming_degrees']=sep
  if row['gaia_source_id']=='1607896637338835712':
   row['fiber_to_paper_rounded_arcsec_assuming_degrees']=separation(row['fiber_ra'],row['fiber_dec'],214.1778,52.2620)
   row['gaia_to_paper_rounded_arcsec_assuming_degrees']=separation(row['ra2'],row['dec2'],214.1778,52.2620)
  records.append(row)
 if len(records)>=201 or int(counts[0])!=len(records):raise ValueError('capped or inconsistent row count')
 if not any(r['gaia_source_id']=='1607896637338835712' and (r['plate'],r['mjd'],r['fiberid'])==('7028','56449','220') for r in records):raise ValueError('published expected tuple missing')
 return {'status':'PASS_FIXED_14_VALUE_SHAPE_CONTROL','row_count':len(records),'records':records,
   'coordinate_assumption':'crossmatch RA/Dec interpreted as degrees; unit cells were blank',
   'scope':'14-value shape only; preserve sentinels; no completeness, fibre light, RV or orbit conclusion'}
def main():
 paths={'query':D/'QUERY.adql','protocol':D/'PROTOCOL.md','raw':D/'capture/shape_control.raw',
  'request':D/'capture/shape_control.request.json','native':D/'capture/shape_control.json',
  'result':D/'capture/RESULT.json','finish':D/'capture/FINISH.json'}
 frozen={k:p.read_bytes() for k,p in paths.items()}
 for k,v in frozen.items():
  if digest(v)!=PINS[k]:raise ValueError('pinned evidence mismatch: '+k)
 query=frozen['query'].decode('utf-8-sig').strip();req=json.loads(frozen['request']);n=json.loads(frozen['native']);r=json.loads(frozen['result']);fin=json.loads(frozen['finish'])
 url='https://datalab.noirlab.edu/tap/sync?'+urlencode([('REQUEST','doQuery'),('LANG','ADQL'),('FORMAT','votable'),('MAXREC','201'),('QUERY',query)])
 if (req['request'].get('url')!=url or req['request'].get('method')!='GET' or req['request'].get('protocol_sha256')!=PINS['protocol']
  or n.get('url')!=url or n.get('effective_url')!=url or n.get('request_sha256')!=PINS['request']
  or n.get('status')!='HTTP_COMPLETE_UNPARSED' or n.get('http_status')!=200 or n.get('ssl_verify_result')!=0
  or n.get('num_redirects')!=0 or n.get('returncode')!=0 or n.get('raw_sha256')!=PINS['raw']
  or n.get('raw_bytes')!=len(frozen['raw']) or r.get('body_sha256')!=PINS['raw']
  or r.get('status')!='HTTP_COMPLETE_VOTABLE_UNVALIDATED' or fin.get('terminal_sha256')!=PINS['result']
  or not fin.get('lease_released') or not fin.get('owned_process_exit_confirmed')):raise ValueError('transport proof mismatch')
 parsed=parse_shape(frozen['raw'],query)
 out={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':PINS['raw'],'query_sha256':PINS['query'],'evidence_pins':PINS,'result':parsed}
 with (D/'SHAPE_CONTROL.json').open('x',encoding='utf8') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({'status':parsed['status'],'rows':parsed['row_count'],'records':parsed['records']},indent=2))
if __name__=='__main__':main()
