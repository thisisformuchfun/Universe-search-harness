"""Bounded read-only public-archive I/O. No synthetic production fallback.

All query results retain original bytes, a content hash and acquisition provenance.
Cache reuse is explicit: offline=True. A live request is never rescued with old data.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
import csv
import hashlib
from http.client import HTTPException, IncompleteRead
import io
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import xml.etree.ElementTree as ET

GAIA_TAP = 'https://gea.esac.esa.int/tap-server/tap/sync'
VIZIER_TAP = 'https://tapvizier.cds.unistra.fr/TAPVizieR/tap/sync'
SIMBAD_TAP = 'https://simbad.cds.unistra.fr/simbad/sim-tap/sync'
TRUSTED_HOSTS = frozenset({'gea.esac.esa.int', 'tapvizier.cds.unistra.fr', 'simbad.cds.unistra.fr'})
KNOWN_TABLES = ('J/MNRAS/518/2991/table2', 'J/MNRAS/521/5927/table')
ID_FIELDS = frozenset({'source_id', 'gaiadr3', 'gaia_dr3', 'dr3_source_id'})
NSS_COLUMNS = ('source_id', 'nss_solution_type', 'ra', 'dec', 'ra_error', 'dec_error',
 'parallax', 'parallax_error', 'pmra', 'pmra_error', 'pmdec', 'pmdec_error',
 'a_thiele_innes', 'a_thiele_innes_error', 'b_thiele_innes', 'b_thiele_innes_error',
 'f_thiele_innes', 'f_thiele_innes_error', 'g_thiele_innes', 'g_thiele_innes_error',
 'c_thiele_innes', 'c_thiele_innes_error', 'h_thiele_innes', 'h_thiele_innes_error',
 'center_of_mass_velocity', 'center_of_mass_velocity_error', 'period', 'period_error',
 'eccentricity', 'eccentricity_error', 't_periastron', 't_periastron_error',
 'bit_index', 'corr_vec', 'significance', 'goodness_of_fit', 'efficiency', 'flags')
NSS_REQUIRED = frozenset({'source_id','nss_solution_type','parallax','period',
                         'a_thiele_innes','b_thiele_innes','f_thiele_innes','g_thiele_innes'})
NSS_FILTER = ('parallax > 0 AND parallax/parallax_error > 10 AND period > 0 '
 'AND period/period_error > 10 AND significance > 10 '
 'AND a_thiele_innes IS NOT NULL AND b_thiele_innes IS NOT NULL '
 'AND f_thiele_innes IS NOT NULL AND g_thiele_innes IS NOT NULL')

class ArchiveError(RuntimeError):
    """A request/data integrity error; caller must mark coverage incomplete."""

@dataclass
class ArchiveResult:
    rows: list[dict]
    provenance: dict
    def to_dict(self):
        return asdict(self)

def utc_now():
    return datetime.now(timezone.utc).isoformat()

def sha256(data: bytes):
    return hashlib.sha256(data).hexdigest()

def atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')
    tmp.replace(path)

def _safe_id(value, field='source_id') -> str:
    # Reject floats even when integral: precision may already have been lost.
    if isinstance(value, bool) or isinstance(value, float):
        raise ArchiveError(f'{field} must be an exact integer string, not {type(value).__name__}')
    result = str(value).strip()
    if not re.fullmatch(r'[0-9]{1,20}', result) or int(result) <= 0:
        raise ArchiveError(f'Invalid {field}: {result!r}')
    return result

def _normalise_ids(row):
    for key, value in list(row.items()):
        if key.lower() in ID_FIELDS and value is not None and value != '':
            row[key] = _safe_id(value, key)
    return row

def parse_votable(raw: bytes, required=()) -> list[dict]:
    """Parse TABLEDATA only. Unknown/binary representations fail, never guess.

    IDs are kept as decimal text. Numeric arrays such as corr_vec become lists.
    The full response is checked for final QUERY_STATUS, including OVERFLOW.
    """
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ArchiveError('DTD/entity declarations are not accepted')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ArchiveError(f'Malformed/truncated VOTable: {exc}') from exc
    local = lambda e: e.tag.rsplit('}', 1)[-1]
    if local(root) != 'VOTABLE':
        raise ArchiveError('Archive returned a non-VOTable response')
    statuses = [e for e in root.iter() if local(e) == 'INFO' and e.get('name','').upper() == 'QUERY_STATUS']
    if not statuses:
        raise ArchiveError('Missing TAP QUERY_STATUS')
    for e in statuses:
        status = e.get('value','').upper()
        if status != 'OK':
            raise ArchiveError(f'TAP QUERY_STATUS={status}: {(e.text or "")[:500]}')
    tables = [e for e in root.iter() if local(e) == 'TABLE']
    if len(tables) != 1:
        raise ArchiveError(f'Expected one result table, got {len(tables)}')
    table = tables[0]
    fields = [e for e in table if local(e) == 'FIELD']
    names = [e.get('name') or e.get('ID') for e in fields]
    if not names or None in names or len(names) != len(set(names)):
        raise ArchiveError('Missing/duplicate field names')
    if not set(required).issubset(names):
        raise ArchiveError(f'Missing required columns: {sorted(set(required)-set(names))}')
    tdata = next((e for e in table.iter() if local(e) == 'TABLEDATA'), None)
    if tdata is None:
        raise ArchiveError('Unsupported VOTable serialization; TABLEDATA required')
    rows = []
    for tr in tdata:
        if local(tr) != 'TR':
            continue
        cells = [e.text or '' for e in tr if local(e) == 'TD']
        if len(cells) != len(fields):
            raise ArchiveError('Result row width does not match schema')
        row = {}
        for name, field, value in zip(names, fields, cells):
            value = value.strip()
            dtype = field.get('datatype','char')
            array = field.get('arraysize')
            if not value:
                parsed = None
            elif name.lower() in ID_FIELDS:
                parsed = _safe_id(value, name)
            elif dtype in {'char','unicodeChar'}:
                parsed = value
            elif array and array != '1':
                try:
                    parsed = [float(x) for x in value.split()]
                except ValueError as exc:
                    raise ArchiveError(f'Malformed array in {name}') from exc
                # NaN array entries are preserved as None, not guessed correlations.
                parsed = [x if math.isfinite(x) else None for x in parsed]
            elif dtype in {'short','int','long','unsignedByte'}:
                try:
                    parsed = int(value)
                except ValueError as exc:
                    raise ArchiveError(f'Malformed integer in {name}') from exc
            elif dtype in {'float','double'}:
                try:
                    parsed = float(value)
                except ValueError as exc:
                    raise ArchiveError(f'Malformed numeric in {name}') from exc
                if not math.isfinite(parsed):
                    parsed = None
            elif dtype == 'boolean':
                parsed = value in {'1','T','true'}
            else:
                raise ArchiveError(f'Unsupported VOTable datatype {dtype}')
            row[name] = parsed
        rows.append(_normalise_ids(row))
    return rows

def load_csv_snapshot(path: Path, expected_sha256: str, required=NSS_REQUIRED):
    raw = Path(path).read_bytes()
    if sha256(raw) != expected_sha256:
        raise ArchiveError('Snapshot SHA-256 mismatch')
    try:
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if not set(required).issubset(reader.fieldnames or []):
            raise ArchiveError('Snapshot schema missing required columns')
        rows = []
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ArchiveError('Malformed CSV row width')
            rows.append(_normalise_ids(row))
    except UnicodeDecodeError as exc:
        raise ArchiveError('Snapshot is not UTF-8') from exc
    _check_composite_duplicates(rows)
    return rows

def _check_composite_duplicates(rows):
    seen = set()
    for row in rows:
        if 'source_id' not in row or 'nss_solution_type' not in row:
            continue
        key = (_safe_id(row['source_id']), str(row['nss_solution_type']))
        if key in seen:
            raise ArchiveError(f'Duplicate NSS composite key: {key}')
        seen.add(key)

def _validate_endpoint(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != 'https' or u.hostname not in TRUSTED_HOSTS or u.username or u.password or u.port not in (None,443):
        raise ArchiveError('Endpoint must use HTTPS on an allowlisted public archive host')

class _TrustedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_endpoint(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class PublicSkyConnector:
    def __init__(self, cache_dir='data/cache', timeout=30, retries=2, max_bytes=32*1024*1024):
        if not 1 <= timeout <= 180 or not 0 <= retries <= 5 or not 1024 <= max_bytes <= 128*1024*1024:
            raise ValueError('Invalid request bounds')
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.retries = retries
        self.max_bytes = max_bytes
        self.opener = urllib.request.build_opener(_TrustedRedirect())

    def _record_attempt(self, request, http, raw=None, outcome='HTTP_RESPONSE'):
        """Write immutable evidence before interpretation, including failed attempts.

        A raw hash covers only the stored bytes. body_complete=False explicitly
        marks a partial/capped body; such bytes never become a usable cache entry.
        Each retrieval has its own metadata even if its content is unchanged.
        """
        key = sha256(json.dumps(request,sort_keys=True).encode())
        event_id = uuid.uuid4().hex
        evidence = dict(http, request=request, cache_key=key, cache_reused=False,
                        fetched_at_utc=utc_now(), outcome=outcome, event_id=event_id)
        self.cache_dir.mkdir(parents=True,exist_ok=True)
        if raw is not None:
            digest = sha256(raw)
            rawpath = self.cache_dir/(key+'.'+digest+'.xml')
            try:
                with rawpath.open('xb') as handle: handle.write(raw)
            except FileExistsError:
                if sha256(rawpath.read_bytes()) != digest:
                    raise ArchiveError('Existing content-addressed evidence changed')
            evidence.update(raw_sha256=digest, bytes=len(raw), raw_file=rawpath.name)
        else:
            evidence.update(raw_sha256=None, bytes=0, raw_file=None)
        events = self.cache_dir/'attempts';events.mkdir(exist_ok=True)
        eventpath = events/(key+'.'+event_id+'.json')
        evidence['retrieval_record'] = 'attempts/'+eventpath.name
        with eventpath.open('x',encoding='utf-8') as handle:
            json.dump(evidence,handle,indent=2,allow_nan=False)
        return evidence

    def _read_bounded_body(self, response):
        chunks=[];size=0;error=None
        while size<=self.max_bytes:
            try:
                part=response.read(min(65536,self.max_bytes+1-size))
            except IncompleteRead as exc:
                part=exc.partial;chunks.append(part);size+=len(part)
                error='IncompleteRead';break
            except (TimeoutError,OSError) as exc:
                error=type(exc).__name__+': '+str(exc);break
            if not part:break
            chunks.append(part);size+=len(part)
        raw=b''.join(chunks)
        capped=len(raw)>self.max_bytes
        return raw[:self.max_bytes],error,capped

    @staticmethod
    def _retry_delay(headers, attempt):
        delay=float(min(30,2**attempt));retry=headers.get('Retry-After')
        if retry:
            try:
                requested=float(retry)
            except ValueError:
                try:
                    stamp=parsedate_to_datetime(retry)
                    if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
                    requested=(stamp-datetime.now(timezone.utc)).total_seconds()
                except (TypeError,ValueError,OverflowError):
                    requested=None
            if requested is not None and math.isfinite(requested):
                delay=max(0,requested)
        return delay

    def _request(self, endpoint, query, maxrec):
        _validate_endpoint(endpoint)
        params = {'REQUEST':'doQuery','LANG':'ADQL','FORMAT':'votable_plain','QUERY':query,'MAXREC':str(maxrec)}
        url = endpoint + '?' + urllib.parse.urlencode(params)
        request = {'endpoint':endpoint,'query':query,'maxrec':maxrec,'format':'votable_plain'}
        for attempt in range(self.retries + 1):
            started=utc_now()
            try:
                req = urllib.request.Request(url, headers={'User-Agent':'UniverseRealHarness/1.0 (read-only scientific audit)', 'Accept':'application/x-votable+xml,text/xml'})
                with self.opener.open(req, timeout=self.timeout) as response:
                    _validate_endpoint(response.geturl())
                    length = response.headers.get('Content-Length')
                    raw,read_error,capped = self._read_bounded_body(response)
                    try:declared_length=int(length) if length is not None else None
                    except ValueError:declared_length=None;read_error='Invalid Content-Length'
                    complete=not read_error and not capped and (declared_length is None or len(raw)==declared_length)
                    http = self._record_attempt(request,{
                        'http_status':response.status,'content_type':response.headers.get('Content-Type'),
                        'effective_url':response.geturl(),'attempts':attempt+1,
                        'started_at_utc':started,'content_length':length,'body_complete':complete,
                        'body_capped':capped,'read_error':read_error},raw)
                    if not complete:
                        reason='Response exceeds configured byte cap' if capped else 'Incomplete HTTP body'
                        raise ArchiveError(reason+'; evidence='+http['retrieval_record'])
                    return raw,http
            except urllib.error.HTTPError as exc:
                raw,read_error,capped=self._read_bounded_body(exc)
                length=exc.headers.get('Content-Length')
                try:declared_length=int(length) if length is not None else None
                except ValueError:declared_length=None;read_error='Invalid Content-Length'
                complete=not read_error and not capped and (declared_length is None or len(raw)==declared_length)
                http=self._record_attempt(request,{
                    'http_status':exc.code,'content_type':exc.headers.get('Content-Type'),
                    'effective_url':exc.geturl(),'attempts':attempt+1,'started_at_utc':started,
                    'retry_after':exc.headers.get('Retry-After'),'content_length':length,'body_complete':complete,
                    'body_capped':capped,'read_error':read_error},raw,outcome='HTTP_ERROR')
                exc.close()
                if exc.code not in {408,429,500,502,503,504} or attempt == self.retries:
                    raise ArchiveError(f'HTTP {exc.code} from {endpoint}; evidence='+http['retrieval_record']) from exc
                delay = self._retry_delay(exc.headers,attempt)
                if delay>30:
                    raise ArchiveError(f'HTTP {exc.code}: Retry-After requires {delay:.1f}s; deferred without early retry; evidence='+http['retrieval_record']) from exc
                time.sleep(delay)
            except (TimeoutError, urllib.error.URLError, OSError, HTTPException) as exc:
                http=self._record_attempt(request,{'http_status':None,'attempts':attempt+1,
                    'started_at_utc':started,'body_complete':False,'network_error':type(exc).__name__+': '+str(exc)},
                    outcome='NETWORK_ERROR')
                if attempt == self.retries:
                    raise ArchiveError(f'Archive network failure: {type(exc).__name__}: {exc}; evidence='+http['retrieval_record']) from exc
                time.sleep(min(10,2**attempt))
        raise ArchiveError('Request attempts exhausted')

    def tap(self, endpoint, query, maxrec=1000, offline=False, refresh=False, required=(), expected_sha256=None):
        """Live by default. offline=True is the ONLY path that reads cached bytes.

        refresh is accepted for compatibility; live requests always refresh.
        """
        _validate_endpoint(endpoint)
        if not isinstance(query,str) or not query.strip().upper().startswith('SELECT ') or len(query)>64000:
            raise ArchiveError('Only bounded SELECT ADQL queries are supported')
        if not 1 <= maxrec <= 100000:
            raise ArchiveError('MAXREC outside bounded range')
        request = {'endpoint':endpoint,'query':query,'maxrec':maxrec,'format':'votable_plain'}
        key = sha256(json.dumps(request,sort_keys=True).encode())
        if expected_sha256 is not None and (not offline or not re.fullmatch(r'[0-9a-f]{64}',expected_sha256)):
            raise ArchiveError('Expected digest is valid only for explicit offline reads')
        metapath = self.cache_dir / (key+'.'+expected_sha256+'.json' if expected_sha256 else key+'.json')
        if offline:
            try:
                meta = json.loads(metapath.read_text())
                digest=meta.get('raw_sha256','')
                if not re.fullmatch(r'[0-9a-f]{64}',digest):raise ArchiveError('Invalid cache digest')
                rawpath=self.cache_dir/(key+'.'+digest+'.xml')
                raw = rawpath.read_bytes()
            except (FileNotFoundError,json.JSONDecodeError) as exc:
                raise ArchiveError(f'No verified cache for request {key}') from exc
            if meta.get('request') != request or meta.get('raw_sha256') != sha256(raw) or meta.get('bytes') != len(raw):
                raise ArchiveError('Cache provenance/hash mismatch')
            rows = parse_votable(raw,required)
            if meta.get('row_count') != len(rows):
                raise ArchiveError('Cache row-count mismatch')
            provenance = dict(meta, cache_reused=True, cache_checked_utc=utc_now())
        else:
            raw,http = self._request(endpoint,query,maxrec)
            if 'retrieval_record' not in http:
                http=self._record_attempt(request,http,raw)
            try:
                rows = parse_votable(raw,required)
                if len(rows)>maxrec:raise ArchiveError('Archive ignored MAXREC')
                _check_composite_duplicates(rows)
            except (ArchiveError,ValueError,TypeError) as exc:
                evidence=self._record_attempt(request,dict(http,parse_error=str(exc)),raw,outcome='TAP_PARSE_ERROR')
                raise ArchiveError(str(exc)+'; evidence='+evidence['retrieval_record']) from exc
            provenance = dict(http,row_count=len(rows))
            self.cache_dir.mkdir(parents=True,exist_ok=True)
            digest=provenance['raw_sha256']
            immutable_meta=self.cache_dir/(key+'.'+digest+'.json')
            # The first successful interpretation of these bytes remains fixed.
            # The newest retrieval gets a separate event and the explicit latest index.
            if not immutable_meta.exists():
                with immutable_meta.open('x',encoding='utf-8') as handle:
                    json.dump(provenance,handle,indent=2,allow_nan=False)
            atomic_json(metapath,provenance)
        _check_composite_duplicates(rows)
        return ArchiveResult(rows,provenance)

    def query_gaia_dr3_tap(self, query, maxrec=1000, **kwargs):
        return self.tap(GAIA_TAP,query,maxrec,**kwargs)

    def gaia_schema(self, offline=False):
        q="SELECT column_name,datatype,description FROM TAP_SCHEMA.columns WHERE table_name='gaiadr3.nss_two_body_orbit'"
        result=self.tap(GAIA_TAP,q,1000,offline=offline,required=('column_name','datatype'))
        missing=set(NSS_COLUMNS)-{r['column_name'] for r in result.rows}
        if missing:raise ArchiveError(f'Gaia NSS schema changed/missing: {sorted(missing)}')
        return result

    @staticmethod
    def nss_query(page_size=500,cursor=None):
        if not 1<=page_size<=10000:raise ValueError('page_size must be 1..10000')
        suffix=''
        if cursor:
            sid=_safe_id(cursor[0]);kind=str(cursor[1])
            if not re.fullmatch(r'[A-Za-z0-9_]+',kind):raise ArchiveError('Invalid NSS cursor solution type')
            suffix=f" AND (source_id > {sid} OR (source_id = {sid} AND nss_solution_type > '{kind}'))"
        return f'SELECT TOP {page_size} '+','.join(NSS_COLUMNS)+' FROM gaiadr3.nss_two_body_orbit WHERE '+NSS_FILTER+suffix+' ORDER BY source_id,nss_solution_type'

    def gaia_nss_pages(self, output_dir, page_size=500, max_pages=2, resume=False, offline=False):
        """Bounded keyset pagination. max_pages is TOTAL pages, not extra pages.

        Resume requires the original page cap. A full final page means bounded/
        incomplete, NOT complete. Source-id+solution type is the key.
        """
        if not 1<=max_pages<=10000:raise ValueError('max_pages must be 1..10000')
        self.nss_query(page_size)  # Validate bounds before creating acquisition state.
        out=Path(output_dir);mp=out/'acquisition.json'
        config={'version':2,'endpoint':GAIA_TAP,'page_size':page_size,'max_pages':max_pages,'filter':NSS_FILTER,'columns':list(NSS_COLUMNS)}
        if resume:
            try:manifest=json.loads(mp.read_text())
            except (FileNotFoundError,json.JSONDecodeError) as exc:raise ArchiveError('Missing/invalid resume manifest') from exc
            if manifest.get('config')!=config:raise ArchiveError('Resume configuration mismatch')
        else:
            if mp.exists():raise ArchiveError('Acquisition exists; use resume or a new output directory')
            manifest={'config':config,'started_at_utc':utc_now(),'pages':[],'cursor':None,
                      'complete':False,'rows':0,'coverage':'not_yet_acquired'}
            atomic_json(mp,manifest)
        rows=[]
        verified_cursor=None
        for page in manifest['pages']:
            if page['query'] != self.nss_query(page_size,verified_cursor):
                raise ArchiveError('Resume page query does not follow keyset sequence')
            cached=self.tap(GAIA_TAP,page['query'],page_size+1,offline=True,required=NSS_REQUIRED,expected_sha256=page['raw_sha256'])
            if cached.provenance['raw_sha256']!=page['raw_sha256']:raise ArchiveError('Resume page hash mismatch')
            cached_keys=[(int(r['source_id']),r['nss_solution_type']) for r in cached.rows]
            if cached_keys != sorted(cached_keys) or len(set(cached_keys)) != len(cached_keys):
                raise ArchiveError('Cached page is not strictly ordered')
            if verified_cursor and cached_keys and cached_keys[0] <= (int(verified_cursor[0]),verified_cursor[1]):
                raise ArchiveError('Cached cursor failed to advance')
            if cached_keys:verified_cursor=[str(cached_keys[-1][0]),cached_keys[-1][1]]
            rows.extend(cached.rows)
        if manifest['cursor'] != verified_cursor:
            raise ArchiveError('Resume cursor does not match verified page data')
        if manifest['pages'] and bool(manifest['complete']) != (len(cached.rows)<page_size):
            raise ArchiveError('Resume completeness inconsistent with page data')
        while len(manifest['pages'])<max_pages and not manifest['complete']:
            q=self.nss_query(page_size,manifest['cursor'])
            result=self.tap(GAIA_TAP,q,page_size+1,offline=offline,required=NSS_REQUIRED)
            keys=[(int(r['source_id']),r['nss_solution_type']) for r in result.rows]
            if keys!=sorted(keys) or len(set(keys))!=len(keys):raise ArchiveError('NSS page is not strictly ordered')
            if manifest['cursor'] and keys and keys[0] <= (int(manifest['cursor'][0]),manifest['cursor'][1]):
                raise ArchiveError('NSS cursor failed to advance')
            if len(result.rows)>page_size:raise ArchiveError('NSS TOP limit ignored')
            rows.extend(result.rows)
            manifest['pages'].append({'query':q,**result.provenance})
            if keys:manifest['cursor']=[str(keys[-1][0]),keys[-1][1]]
            manifest['complete']=len(result.rows)<page_size
            manifest['rows']=len(rows);manifest['updated_at_utc']=utc_now()
            manifest['coverage']='complete_within_fixed_selection' if manifest['complete'] else 'bounded_partial_selection'
            atomic_json(mp,manifest)
        _check_composite_duplicates(rows)
        return ArchiveResult(rows,manifest)

    def gaia_ranked_pilot(self, limit=500, offline=False):
        """Real proxy-ranked acquisition; reproduces original selection, not injected truth.

        Fetches full covariance fields in addition to the original pilot columns.
        f_proxy is only a ranking bound, NOT companion mass or a probability.
        """
        if not 1 <= limit <= 10000: raise ValueError('limit must be 1..10000')
        proxy=('POWER(a_thiele_innes*a_thiele_innes+b_thiele_innes*b_thiele_innes+'
               'f_thiele_innes*f_thiele_innes+g_thiele_innes*g_thiele_innes,1.5)*365.25*365.25/'
               '(parallax*parallax*parallax*period*period)')
        q=f'SELECT TOP {limit} '+','.join(NSS_COLUMNS)+','+proxy+' AS f_proxy FROM gaiadr3.nss_two_body_orbit WHERE '+NSS_FILTER+' ORDER BY f_proxy DESC,source_id,nss_solution_type'
        result=self.tap(GAIA_TAP,q,limit+1,offline=offline,required=NSS_REQUIRED)
        result.provenance['coverage']='bounded_proxy_ranked_selection_not_full_sky'
        return result

    def gaia_context(self, source_ids, offline=False):
        ids=sorted(set(_safe_id(x) for x in source_ids),key=int)
        if not 1<=len(ids)<=100:raise ValueError('Context queries require 1..100 source IDs')
        q=('SELECT source_id,ra,dec,parallax,parallax_error,ruwe,phot_g_mean_mag,phot_bp_mean_mag,'
           'phot_rp_mean_mag,phot_bp_rp_excess_factor,ipd_frac_multi_peak,duplicated_source,'
           'astrometric_excess_noise,visibility_periods_used FROM gaiadr3.gaia_source WHERE source_id IN ('+','.join(ids)+')')
        return self.tap(GAIA_TAP,q,len(ids)+1,offline=offline,required=('source_id','ruwe'))

    def vizier_known_catalogs(self, offline=False):
        results={}
        for table in KNOWN_TABLES:
            column = 'GaiaDR3' if table == KNOWN_TABLES[0] else 'Source'
            q=f'SELECT {column} AS source_id FROM "{table}"'
            results[table]=self.tap(VIZIER_TAP,q,10000,offline=offline,required=('source_id',))
        return results

    def simbad_exact_ids(self, source_ids, offline=False):
        ids=sorted(set(_safe_id(x) for x in source_ids),key=int)
        if not 1<=len(ids)<=100:raise ValueError('SIMBAD queries require 1..100 source IDs')
        terms=','.join("'Gaia DR3 "+x+"'" for x in ids)
        q=('SELECT i.id,b.main_id,b.otype,b.ra,b.dec FROM ident AS i JOIN basic AS b '
           'ON i.oidref=b.oid WHERE i.id IN ('+terms+')')
        result=self.tap(SIMBAD_TAP,q,1000,offline=offline,required=('id','main_id','otype'))
        result.provenance['interpretation']='A match is prior identification, not necessarily a BH. No match is NOT novelty clearance.'
        return result

    def probe(self):
        checks=[]
        samples=[('gaia',GAIA_TAP,'SELECT TOP 1 source_id,nss_solution_type FROM gaiadr3.nss_two_body_orbit'),
                 ('vizier',VIZIER_TAP,'SELECT TOP 1 GaiaDR3 FROM "J/MNRAS/518/2991/table2"'),
                 ('simbad',SIMBAD_TAP,"SELECT TOP 1 id FROM ident WHERE id='Gaia DR3 4373465352415301632'")]
        for name,endpoint,q in samples:
            try:
                r=self.tap(endpoint,q,2)
                checks.append({'service':name,'status':'PASS_LIVE','rows':len(r.rows),'provenance':r.provenance})
            except Exception as exc:
                checks.append({'service':name,'status':'FAILED_LIVE','checked_at_utc':utc_now(),'error':str(exc),'endpoint':endpoint,'query':q})
        return {'checked_at_utc':utc_now(),'checks':checks,'all_passed':all(x['status']=='PASS_LIVE' for x in checks)}
