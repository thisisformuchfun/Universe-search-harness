"""Strict reader for one pinned, untrusted NOIRLab TAP schema response."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import hashlib,json,xml.etree.ElementTree as ET
D=Path(__file__).resolve().parent
TABLES={'sdss_dr17.specobj','sdss_dr17.x1p5__specobj__gaia_dr3__gaia_source'}
COLS={'id1','id2','distance','ra1','dec1','ra2','dec2','specobjid','plate','mjd','fiberid','ra','dec','run2d','class','subclass','snmedian','zwarning'}
FIELDS=['table_name','column_name','datatype','unit','description']
PINS={'query':'97f91cbe7fab05f415e3914ac7ec7bf4f6f369830b547aa15ef64ccd287ec6d2',
 'raw':'86def01aba2baa9ef9263b7477c9c7efed6cec611ad164caf29b066052903b23',
 'request':'19a61fc6163a6a2b5daa8b5e0c3b3f5f06fe70b3ddd97ac892fa8966f17de8c9',
 'native':'0bb57ac0950e48100b1de74da9cd57e4441f763223f5435e4b7786622f9d9512',
 'result':'d0f33cd29e21e0a1f665ca12762982646f3102151f2db2658bd58301da577b19',
 'finish':'f6cf3fbb9ba3e36a824da8d8f2537ffc4424d53f53c9da23afd04a5ca05cb3d7',
 'protocol':'2ac501e518257e5abad62a81f84702215295bd9080a6dc4c704b4ca3cb115f91'}
def digest(data):return hashlib.sha256(data).hexdigest()
def blank(value):return value is None or not value.strip()
def xmlblank(value):return value is None or all(c in ' \t\r\n' for c in value)
def whitespace_container(node):
    if not xmlblank(node.text):raise ValueError('mixed container text')
    if any(not xmlblank(child.tail) for child in node):raise ValueError('mixed child tail')
def parse_schema(raw,query):
    if len(raw)>1000000 or b'\x00' in raw or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe or oversized XML')
    raw.decode('utf-8','strict'); root=ET.fromstring(raw)
    if root.tag!='VOTABLE' or root.attrib.get('version')!='1.2':raise ValueError('unsupported VOTable root')
    if any(not isinstance(n.tag,str) or n.tag.startswith('{') for n in root.iter()):raise ValueError('unsupported element namespace')
    whitespace_container(root)
    resources=[n for n in root if n.tag=='RESOURCE']
    if len(resources)!=1 or resources[0].attrib.get('type')!='results' or len(root)!=1:raise ValueError('results resource ambiguity')
    resource=resources[0];whitespace_container(resource)
    if any(n.tag not in ('INFO','TABLE','DESCRIPTION') for n in resource):raise ValueError('unexpected resource child')
    descriptions=[n for n in resource if n.tag=='DESCRIPTION']
    if len(descriptions)>1 or any(n.attrib or len(n) for n in descriptions):raise ValueError('invalid resource description')
    direct_infos=[n for n in resource if n.tag=='INFO']
    if any(len(n) or not xmlblank(n.text) or set(n.attrib)!={'name','value'} or n.attrib['name'] not in ('QUERY_STATUS','QUERY','TableRows') for n in direct_infos):raise ValueError('invalid INFO')
    if len([n for n in root.iter() if n.tag=='INFO'])!=len(direct_infos):raise ValueError('INFO outside results resource')
    statuses=[n.attrib.get('value') for n in direct_infos if n.attrib.get('name','').upper()=='QUERY_STATUS']
    if statuses!=['OK']:raise ValueError('TAP status absent, multiple, error or overflow')
    queries=[n.attrib.get('value') for n in direct_infos if n.attrib.get('name')=='QUERY']
    if queries!=[query]:raise ValueError('query echo mismatch')
    rowinfo=[n.attrib.get('value') for n in direct_infos if n.attrib.get('name')=='TableRows']
    if len(rowinfo)!=1 or not rowinfo[0] or not rowinfo[0].isdigit():raise ValueError('missing/invalid reported row count')
    tables=[n for n in resource if n.tag=='TABLE']
    if len(tables)!=1:raise ValueError('table ambiguity')
    table=tables[0]
    status_node=next(n for n in direct_infos if n.attrib.get('name')=='QUERY_STATUS')
    if list(resource).index(status_node)>list(resource).index(table):raise ValueError('leading QUERY_STATUS required')
    if table.attrib:raise ValueError('unsupported TABLE attributes')
    whitespace_container(table)
    fields=[n for n in table if n.tag=='FIELD'];data_nodes=[n for n in table if n.tag=='DATA']
    if len(table)!=len(fields)+1 or len(data_nodes)!=1 or [n.attrib.get('name') for n in fields]!=FIELDS:
        raise ValueError('unexpected table structure')
    for n in fields:
        whitespace_container(n)
        if n.attrib.get('datatype')!='char' or n.attrib.get('arraysize')!='64':raise ValueError('unexpected field type')
        if any(ch.tag!='DESCRIPTION' or ch.attrib or len(ch) for ch in n):raise ValueError('unsupported field/null definition')
        if len(n)>1:raise ValueError('field description ambiguity')
    data=data_nodes[0]
    if data.attrib:raise ValueError('unsupported DATA attributes')
    whitespace_container(data)
    if len(data)!=1 or data[0].tag!='TABLEDATA':raise ValueError('unsupported data encoding or hierarchy')
    block=data[0]
    if block.attrib:raise ValueError('unsupported TABLEDATA attributes')
    whitespace_container(block); rows=[];seen=set()
    for tr in block:
        if tr.tag!='TR' or tr.attrib:raise ValueError('unexpected TABLEDATA child or attributes')
        whitespace_container(tr);cells=list(tr)
        if len(cells)!=len(FIELDS) or any(c.tag!='TD' or c.attrib or len(c) for c in cells):raise ValueError('invalid/null-attributed row')
        vals=[c.text if c.text is not None else None for c in cells]
        if any(v is not None and len(v)>64 for v in vals):raise ValueError('cell exceeds declared width')
        row=dict(zip(FIELDS,vals));key=(row['table_name'],row['column_name'])
        if key[0] not in TABLES or key[1] not in COLS or key in seen or blank(row['datatype']):raise ValueError('unexpected, duplicate or blank schema row')
        seen.add(key);rows.append(row)
    if len(rows)>=100 or int(rowinfo[0])!=len(rows):raise ValueError('query cap or reported count mismatch')
    return {'status_values':statuses,'reported_rows':int(rowinfo[0]),'row_count':len(rows),'rows':rows,
            'empty_cell_semantics':'empty or null; no semantic distinction inferred','reader_scope':'specific unnamespaced VOTable 1.2 TABLEDATA fixture'}
def main():
    paths={'query':D/'QUERY.adql','raw':D/'capture/schema_probe.raw','request':D/'capture/schema_probe.request.json',
      'native':D/'capture/schema_probe.json','result':D/'capture/RESULT.json','finish':D/'capture/FINISH.json','protocol':D/'PROTOCOL.md'}
    frozen={key:path.read_bytes() for key,path in paths.items()}
    for key,data in frozen.items():
        if digest(data)!=PINS[key]:raise ValueError('pinned evidence mismatch: '+key)
    query=frozen['query'].decode('utf-8-sig').strip(); raw=frozen['raw']
    req=json.loads(frozen['request']);native=json.loads(frozen['native']);result=json.loads(frozen['result']);finish=json.loads(frozen['finish'])
    url='https://datalab.noirlab.edu/tap/sync?'+urlencode([('REQUEST','doQuery'),('LANG','ADQL'),('FORMAT','votable'),('MAXREC','101'),('QUERY',query)])
    if (req['request'].get('url')!=url or req['request'].get('method')!='GET'
        or req['request'].get('protocol_sha256')!=PINS['protocol'] or native.get('url')!=url
        or native.get('effective_url')!=url or native.get('request_sha256')!=PINS['request']
        or native.get('status')!='HTTP_COMPLETE_UNPARSED' or native.get('http_status')!=200
        or native.get('ssl_verify_result')!=0 or native.get('num_redirects')!=0 or native.get('returncode')!=0
        or native.get('raw_sha256')!=PINS['raw'] or native.get('raw_bytes')!=len(raw)
        or result.get('body_sha256')!=PINS['raw'] or result.get('status')!='HTTP_COMPLETE_VOTABLE_UNVALIDATED'
        or finish.get('terminal_sha256')!=PINS['result'] or not finish.get('lease_released')
        or not finish.get('owned_process_exit_confirmed')):raise ValueError('transport evidence mismatch')
    parsed=parse_schema(raw,query)
    out={'created_utc':datetime.now(timezone.utc).isoformat(),'input_sha256':PINS['raw'],
         'query_sha256':PINS['query'],'evidence_pins':PINS,'result':parsed,
         'interpretation':'finite TAP schema rows only; no source or orbit evidence'}
    with (D/'SCHEMA_INVENTORY_V3.json').open('x',encoding='utf8') as f:json.dump(out,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'input_sha256':PINS['raw'],'status':parsed['status_values'],'row_count':parsed['row_count'],
         'schema_key_count':len(parsed['rows'])}))
if __name__=='__main__':main()
