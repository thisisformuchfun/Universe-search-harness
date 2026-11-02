"""Synthetic protocol fixtures only; never production observations."""
import json
import io
import tempfile
import unittest
import urllib.error
from datetime import datetime,timedelta,timezone
from email.message import Message
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch
from harness2.universe.connectors.public_archives import (
 PublicSkyConnector, ArchiveError, parse_votable, _safe_id, _check_composite_duplicates,
 load_csv_snapshot, sha256, GAIA_TAP, _validate_endpoint)

ID='5991734159714775296'

class Response(io.BytesIO):
 def __init__(self,raw,headers=None):
  super().__init__(raw);self.status=200;self.headers=headers or {}
 def geturl(self):return GAIA_TAP
def votable(rows=None,status='OK',tail=''):
 rows=rows if rows is not None else [(ID,'Orbital')]
 body=''.join('<TR><TD>'+sid+'</TD><TD>'+kind+'</TD></TR>' for sid,kind in rows)
 return (f'<VOTABLE><RESOURCE><INFO name="QUERY_STATUS" value="{status}"/>'
 '<TABLE><FIELD name="source_id" datatype="long"/><FIELD name="nss_solution_type" datatype="char" arraysize="*"/>'
 f'<DATA><TABLEDATA>{body}</TABLEDATA></DATA></TABLE>{tail}</RESOURCE></VOTABLE>').encode()

class ConnectorTests(unittest.TestCase):
 def test_ids_exact(self):
  self.assertEqual(parse_votable(votable())[0]['source_id'],ID)
  for bad in [float(ID),True,'5.99e18','1.0','-1','0']:
   with self.assertRaises(ArchiveError):_safe_id(bad)
 def test_error_overflow(self):
  for status in ['ERROR','OVERFLOW','UNKNOWN']:
   with self.assertRaises(ArchiveError):parse_votable(votable(status=status))
  with self.assertRaises(ArchiveError):parse_votable(votable(tail='<INFO name="QUERY_STATUS" value="OVERFLOW"/>'))
 def test_truncation_html_binary(self):
  for raw in [votable()[:-10],b'<html>error</html>',b'<VOTABLE/>',votable().replace(b'TABLEDATA',b'BINARY')]:
   with self.assertRaises(ArchiveError):parse_votable(raw)
 def test_schema_and_entities(self):
  with self.assertRaises(ArchiveError):parse_votable(votable(),('missing',))
  with self.assertRaises(ArchiveError):parse_votable(b'<!DOCTYPE x>'+votable())
 def test_array(self):
  raw=b'<VOTABLE><RESOURCE><INFO name="QUERY_STATUS" value="OK"/><TABLE><FIELD name="corr_vec" datatype="float" arraysize="*"/><DATA><TABLEDATA><TR><TD>0.1 -0.2 NaN</TD></TR></TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>'
  self.assertEqual(parse_votable(raw)[0]['corr_vec'],[0.1,-0.2,None])
 def test_distinct_solutions_preserved(self):
  rows=parse_votable(votable([(ID,'Orbital'),(ID,'AstroSpectroSB1')]))
  _check_composite_duplicates(rows)
  with self.assertRaises(ArchiveError):_check_composite_duplicates(rows+rows[:1])
 def test_endpoint_allowlist(self):
  for url in ['http://gea.esac.esa.int/a','https://evil.test/','https://user:pass@gea.esac.esa.int/a','https://gea.esac.esa.int:8443/a']:
   with self.assertRaises(ArchiveError):_validate_endpoint(url)
 def test_cache_explicit_and_tamper(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(d)
   with patch.object(c,'_request',return_value=(votable(),{'http_status':200})) as request:
    r=c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2)
    self.assertFalse(r.provenance['cache_reused'])
    self.assertTrue(c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2,offline=True).provenance['cache_reused'])
    self.assertEqual(request.call_count,1)
   with patch.object(c,'_request',side_effect=ArchiveError('offline')):
    with self.assertRaises(ArchiveError):c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2)
   next(Path(d).glob('*.xml')).write_bytes(votable([(ID,'Other')]))
   with self.assertRaises(ArchiveError):c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2,offline=True)
 def test_cache_keeps_prior_live_versions(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(d);q='SELECT TOP 1 source_id FROM x'
   with patch.object(c,'_request',side_effect=[(votable([(ID,'Orbital')]),{'http_status':200}),(votable([(ID,'Other')]),{'http_status':200})]):
    first=c.tap(GAIA_TAP,q,2);c.tap(GAIA_TAP,q,2)
   old=c.tap(GAIA_TAP,q,2,offline=True,expected_sha256=first.provenance['raw_sha256'])
   self.assertEqual(old.rows[0]['nss_solution_type'],'Orbital')
   self.assertEqual(c.tap(GAIA_TAP,q,2,offline=True).rows[0]['nss_solution_type'],'Other')
 def test_identical_response_preserves_first_metadata_and_each_retrieval(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(d);q='SELECT TOP 1 source_id FROM x'
   with patch.object(c,'_request',return_value=(votable(),{'http_status':200})):
    first=c.tap(GAIA_TAP,q,2)
    path=Path(d)/(first.provenance['cache_key']+'.'+first.provenance['raw_sha256']+'.json')
    original=path.read_bytes();second=c.tap(GAIA_TAP,q,2)
   self.assertEqual(path.read_bytes(),original)
   self.assertNotEqual(first.provenance['event_id'],second.provenance['event_id'])
   events=[json.loads(p.read_text()) for p in (Path(d)/'attempts').glob('*.json')]
   self.assertEqual(len(events),2)
   self.assertTrue(all(e['raw_sha256']==sha256(votable()) and e['request']['query']==q for e in events))
   self.assertEqual(c.tap(GAIA_TAP,q,2,offline=True).provenance['event_id'],second.provenance['event_id'])
 def test_failed_tap_responses_are_preserved_before_parsing(self):
  for raw in [votable(status='ERROR'),votable(status='OVERFLOW'),votable()[:-8]]:
   with self.subTest(raw=raw[:80]),tempfile.TemporaryDirectory() as d:
    c=PublicSkyConnector(d,retries=0);q='SELECT TOP 1 source_id FROM x'
    with patch.object(c.opener,'open',return_value=Response(raw)):
     with self.assertRaisesRegex(ArchiveError,'evidence='):c.tap(GAIA_TAP,q,2)
    events=[json.loads(p.read_text()) for p in (Path(d)/'attempts').glob('*.json')]
    self.assertEqual({e['outcome'] for e in events},{'HTTP_RESPONSE','TAP_PARSE_ERROR'})
    self.assertTrue(all(e['raw_sha256']==sha256(raw) and e['http_status']==200 for e in events))
    self.assertEqual(next(Path(d).glob('*.xml')).read_bytes(),raw)
    with self.assertRaisesRegex(ArchiveError,'No verified cache'):c.tap(GAIA_TAP,q,2,offline=True)
 def test_http_error_and_network_attempt_evidence(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(d,retries=1);q='SELECT TOP 1 source_id FROM x'
   headers=Message();headers['Content-Type']='text/plain';headers['Retry-After']='0'
   failure=urllib.error.HTTPError(GAIA_TAP,503,'unavailable',headers,io.BytesIO(b'service unavailable'))
   with patch.object(c.opener,'open',side_effect=[failure,urllib.error.URLError('test network failure')]),patch('time.sleep'):
    with self.assertRaisesRegex(ArchiveError,'network failure'):c.tap(GAIA_TAP,q,2)
   events=[json.loads(p.read_text()) for p in (Path(d)/'attempts').glob('*.json')]
   self.assertEqual(len(events),2)
   http=next(e for e in events if e['outcome']=='HTTP_ERROR')
   network=next(e for e in events if e['outcome']=='NETWORK_ERROR')
   self.assertEqual(http['http_status'],503);self.assertEqual(http['retry_after'],'0')
   self.assertEqual((Path(d)/http['raw_file']).read_bytes(),b'service unavailable')
   self.assertEqual(network['attempts'],2);self.assertIsNone(network['raw_sha256'])
   self.assertTrue(all(e['request']['query']==q and e['started_at_utc'] and e['fetched_at_utc'] for e in events))
 def test_long_retry_after_defers_without_early_retry(self):
  for retry in ['120',format_datetime(datetime.now(timezone.utc)+timedelta(minutes=3),usegmt=True)]:
   with self.subTest(retry=retry),tempfile.TemporaryDirectory() as d:
    c=PublicSkyConnector(d,retries=2);headers=Message();headers['Retry-After']=retry
    failure=urllib.error.HTTPError(GAIA_TAP,429,'wait',headers,io.BytesIO(b'rate limited'))
    with patch.object(c.opener,'open',side_effect=failure) as opened,patch('time.sleep') as sleep:
     with self.assertRaisesRegex(ArchiveError,'deferred without early retry'):c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2)
    self.assertEqual(opened.call_count,1);sleep.assert_not_called()
 def test_oversized_and_truncated_body_evidence_is_not_cache(self):
  for raw,headers in [(b'x'*2048,{'Content-Length':'2048'}),(votable(),{'Content-Length':'9999'})]:
   with self.subTest(headers=headers),tempfile.TemporaryDirectory() as d:
    c=PublicSkyConnector(d,retries=0,max_bytes=1024)
    with patch.object(c.opener,'open',return_value=Response(raw,headers)):
     with self.assertRaises(ArchiveError):c.tap(GAIA_TAP,'SELECT TOP 1 source_id FROM x',2)
    event=json.loads(next((Path(d)/'attempts').glob('*.json')).read_text())
    self.assertFalse(event['body_complete']);self.assertLessEqual(event['bytes'],1024)
    self.assertEqual((Path(d)/event['raw_file']).read_bytes(),raw[:1024])
 def test_snapshot_hash(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.csv';p.write_text('source_id,nss_solution_type\n'+ID+',Orbital\n')
   self.assertEqual(load_csv_snapshot(p,sha256(p.read_bytes()),('source_id',))[0]['source_id'],ID)
   with self.assertRaises(ArchiveError):load_csv_snapshot(p,'bad',('source_id',))
 def test_keyset_query(self):
  q=PublicSkyConnector.nss_query(10,(ID,'Orbital'))
  self.assertIn("source_id = "+ID+" AND nss_solution_type > 'Orbital'",q)
  self.assertIn('corr_vec',q)
  with self.assertRaises(ArchiveError):PublicSkyConnector.nss_query(10,(ID,"x' OR 1=1"))
 def test_pagination_resume(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(Path(d)/'cache')
   pages=[votable([('10','AstroSpectroSB1'),('10','Orbital')]),votable([('11','Orbital')])]
   with patch.object(c,'_request',side_effect=[(pages[0],{'http_status':200}),ArchiveError('interrupted'),(pages[1],{'http_status':200})]) as request:
    # Required schema is separately exercised; this protocol fixture has only keys.
    with patch('harness2.universe.connectors.public_archives.NSS_REQUIRED',frozenset({'source_id','nss_solution_type'})):
     with self.assertRaisesRegex(ArchiveError,'interrupted'):
      c.gaia_nss_pages(Path(d)/'run',page_size=2,max_pages=2)
     state=json.loads((Path(d)/'run/acquisition.json').read_text())
     self.assertFalse(state['complete']);self.assertEqual(state['rows'],2)
     self.assertEqual(state['config']['max_pages'],2)
     for cap in [1,3]:
      with self.assertRaisesRegex(ArchiveError,'configuration mismatch'):
       c.gaia_nss_pages(Path(d)/'run',page_size=2,max_pages=cap,resume=True)
     self.assertEqual(request.call_count,2)
     r=c.gaia_nss_pages(Path(d)/'run',page_size=2,max_pages=2,resume=True)
     self.assertTrue(r.provenance['complete']);self.assertEqual(len(r.rows),3)
     with self.assertRaises(ArchiveError):c.gaia_nss_pages(Path(d)/'run',page_size=3,max_pages=2,resume=True)
 def test_resume_after_first_request_interruption(self):
  with tempfile.TemporaryDirectory() as d:
   c=PublicSkyConnector(Path(d)/'cache');out=Path(d)/'run'
   with patch.object(c,'_request',side_effect=ArchiveError('interrupted before first page')):
    with self.assertRaisesRegex(ArchiveError,'interrupted'):c.gaia_nss_pages(out,page_size=2,max_pages=2)
   state=json.loads((out/'acquisition.json').read_text())
   self.assertEqual(state['pages'],[]);self.assertEqual(state['config']['max_pages'],2)
   with patch.object(c,'_request',return_value=(votable([('10','Orbital')]),{'http_status':200})),patch('harness2.universe.connectors.public_archives.NSS_REQUIRED',frozenset({'source_id','nss_solution_type'})):
    result=c.gaia_nss_pages(out,page_size=2,max_pages=2,resume=True)
   self.assertEqual(len(result.rows),1);self.assertTrue(result.provenance['complete'])

if __name__=='__main__':unittest.main()
