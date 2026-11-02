import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('empty_reader',P/'parse_empty.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RAW=(P/'capture/spec_empty.raw').read_bytes();POS=(m.POS/'capture/spec_positive.raw').read_bytes();Q=(P/'QUERY.adql').read_text(encoding='utf-8-sig').strip()
class EmptyTests(unittest.TestCase):
 def reject(self,b):
  self.assertNotEqual(b,RAW)
  with self.assertRaises((ValueError,ET.ParseError)):m.parse_empty(b,Q,POS)
 def test_valid_empty(self):self.assertEqual(m.parse_empty(RAW,Q,POS)['row_count'],0)
 def test_trailing_overflow_or_error(self):
  for s in (b'OVERFLOW',b'ERROR'):self.reject(RAW.replace(b'</RESOURCE>',b'<INFO name="QUERY_STATUS" value="'+s+b'"/></RESOURCE>'))
 def test_wrong_query(self):
  with self.assertRaises(ValueError):m.parse_empty(RAW,Q+' changed',POS)
 def test_missing_tabledata(self):self.reject(RAW.replace(b'<TABLEDATA>',b'').replace(b'</TABLEDATA>',b''))
 def test_row_or_count_nonzero(self):
  self.reject(RAW.replace(b'<TABLEDATA>',b'<TABLEDATA><TR/>'))
  self.reject(RAW.replace(b'name="TableRows" value="0"',b'name="TableRows" value="1"'))
 def test_mismatched_field_type_or_id(self):
  self.reject(RAW.replace(b'datatype="long"',b'datatype="double"',1))
  self.reject(RAW.replace(b'ID="x_specobjid"',b'ID="wrong"',1))
 def test_null_field_definition(self):
  anchor=b'<DESCRIPTION>ID in left/first table (specobjid)</DESCRIPTION>'
  self.reject(RAW.replace(anchor,b'<VALUES null="0"/>'+anchor,1))
 def test_nil_or_mixed_tabledata(self):
  self.reject(RAW.replace(b'<TABLEDATA>',b'<TABLEDATA nil="true">'))
  self.reject(RAW.replace(b'<TABLEDATA>',b'<TABLEDATA>bad'))
 def test_status_outside_resource_or_after_table(self):
  info=b'<INFO name="QUERY_STATUS" value="OK"/>'
  self.assertIn(info,RAW)
  self.reject(RAW.replace(info,b'').replace(b'<RESOURCE type="results">',info+b'<RESOURCE type="results">'))
  self.reject(RAW.replace(info,b'').replace(b'</TABLE>',b'</TABLE>'+info))
 def test_doctype_namespace_and_truncation(self):
  self.reject(b'<!DOCTYPE VOTABLE>'+RAW)
  self.reject(RAW.replace(b'<VOTABLE ',b'<VOTABLE xmlns="urn:wrong" ',1))
  self.reject(RAW[:-20])
 def test_positive_fields_must_match(self):
  with self.assertRaises(ValueError):m.parse_empty(RAW,Q,POS.replace(b'unit="deg"',b'unit="rad"',1))
if __name__=='__main__':unittest.main(verbosity=2)
