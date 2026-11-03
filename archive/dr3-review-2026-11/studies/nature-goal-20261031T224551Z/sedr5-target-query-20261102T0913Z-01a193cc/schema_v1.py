"""Exact observed SEDR5 CSV projections; no RV inference."""
import csv,io

FIELDS='specid obsdate planid spid fiberid iexp mjm sng sni subclass rv rverr rvpa teff logg feh minchi2 npix nabsline fratio fratio_b fratio_r obsid designation gid ra dec spec filename'.split()
PREFIXED=['sexprv_'+field for field in FIELDS]
CONTROL='20150309/HD110643N151055B02/20150309_HD110643N151055B02_15_142.fit'
TARGET='20150108/HD122456N425117B01/20150108_HD122456N425117B01_01_037.fit'
CONTROL_KEY={'specid':'20150309HD110643N151055B0215142','iexp':'0','mjm':'82211011','obsid':'331215142'}
CAP=524288

def parse_csv(raw):
    if not raw or len(raw)>CAP or b'\x00' in raw: raise ValueError('unsupported response bytes or size')
    reader=csv.reader(io.StringIO(raw.decode('utf-8-sig',errors='strict'),newline=''),strict=True)
    header=next(reader,None)
    if header==FIELDS: schema='SAMPLE_UNPREFIXED'
    elif header==PREFIXED: schema='QUERY_PREFIXED'
    else: raise ValueError('unexpected CSV projection')
    result=[]
    for row in reader:
        if len(row)!=len(FIELDS) or len(result)>=1000: raise ValueError('unexpected row width or count')
        result.append(dict(zip(FIELDS,row)))
    return schema,result

def control_passes(rows):
    return bool(rows) and all(row['filename']==CONTROL for row in rows) and sum(
        all(row[k]==v for k,v in CONTROL_KEY.items()) for row in rows)==1

def identity_summary(rows):
    keys=('specid','obsdate','planid','spid','fiberid','iexp','mjm','obsid','gid','filename')
    return {'row_count':len(rows),'all_exact_filename':bool(rows) and all(r['filename']==TARGET for r in rows),
            'identity_rows':[{k:r[k] for k in keys} for r in rows]}
