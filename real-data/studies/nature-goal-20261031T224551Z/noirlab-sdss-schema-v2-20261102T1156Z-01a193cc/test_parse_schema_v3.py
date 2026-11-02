import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('schema_parser_v3',P/'parse_schema_v3.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
Q='SELECT example'
def sample(rows='',reported='0'):
 fields=''.join('<FIELD name="%s" datatype="char" arraysize="64"><DESCRIPTION>field</DESCRIPTION></FIELD>'%n for n in m.FIELDS)
 return ('<VOTABLE version="1.2"><RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>'
  '<INFO name="QUERY" value="'+Q+'"/><INFO name="TableRows" value="'+reported+'"/>'
  '<TABLE>'+fields+'<DATA><TABLEDATA>'+rows+'</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>').encode()
def one(datatype='adql:DOUBLE',tdattr=''):
 cells=['sdss_dr17.specobj','ra',datatype,'','right ascension']
 return '<TR>'+''.join('<TD'+(tdattr if i==2 else '')+'>'+x+'</TD>' for i,x in enumerate(cells))+'</TR>'
class StrictSchemaTests(unittest.TestCase):
 def test_valid_empty_and_row(self):
  self.assertEqual(m.parse_schema(sample(),Q)['row_count'],0)
  out=m.parse_schema(sample(one(), '1'),Q);self.assertEqual(out['row_count'],1);self.assertIsNone(out['rows'][0]['unit'])
 def test_plain_resource_description_allowed(self):
  raw=sample().replace(b'<RESOURCE type="results">',b'<RESOURCE type="results"><DESCRIPTION>metadata</DESCRIPTION>')
  self.assertEqual(m.parse_schema(raw,Q)['row_count'],0)
 def test_error_and_trailing_overflow_rejected(self):
  for raw in (sample().replace(b'value="OK"',b'value="ERROR"'),sample().replace(b'</RESOURCE>',b'<INFO name="QUERY_STATUS" value="OVERFLOW"/></RESOURCE>')):
   with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_status_outside_resource_rejected(self):
  raw=sample().replace(b'<INFO name="QUERY_STATUS" value="OK"/>',b'').replace(b'<RESOURCE type="results">',b'<INFO name="QUERY_STATUS" value="OK"/><RESOURCE type="results">')
  with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_tabledata_outside_data_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample().replace(b'<DATA>',b'').replace(b'</DATA>',b''),Q)
 def test_field_null_declaration_rejected(self):
  raw=sample(one(),'1').replace(b'<DESCRIPTION>field</DESCRIPTION>',b'<VALUES null="adql:DOUBLE"/>',1)
  with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_nil_td_rejected(self):
  raw=sample(one(tdattr=' nil="true"'),'1')
  with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_mixed_text_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample().replace(b'<TABLEDATA>',b'<TABLEDATA>garbage'),Q)
 def test_whitespace_datatype_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample(one('   '),'1'),Q)
 def test_foreign_namespace_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample().replace(b'<VOTABLE ',b'<VOTABLE xmlns="urn:wrong" '),Q)
 def test_duplicate_and_count_mismatch_rejected(self):
  for raw in (sample(one()+one(),'2'),sample(one(),'2')):
   with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_oversize_cell_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample(one('x'*65),'1'),Q)
 def test_query_mismatch_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample(),'other')
 def test_table_nrows_mismatch_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample(one(),'1').replace(b'<TABLE>',b'<TABLE nrows="17">'),Q)
 def test_nil_data_and_row_attributes_rejected(self):
  for raw in (sample(one(),'1').replace(b'<DATA>',b'<DATA nil="true">'),sample(one(),'1').replace(b'<TR>',b'<TR nil="true">')):
   with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_only_post_table_status_rejected(self):
  raw=sample().replace(b'<INFO name="QUERY_STATUS" value="OK"/>',b'').replace(b'</TABLE>',b'</TABLE><INFO name="QUERY_STATUS" value="OK"/>')
  with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_nested_info_rejected(self):
  raw=sample().replace(b'<INFO name="QUERY_STATUS" value="OK"/>',b'<INFO name="QUERY_STATUS" value="OK"><bogus/></INFO>')
  with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_field_mixed_text_and_description_tail_rejected(self):
  for raw in (sample().replace(b'<DESCRIPTION>field</DESCRIPTION>',b'bad<DESCRIPTION>field</DESCRIPTION>',1),sample().replace(b'</DESCRIPTION></FIELD>',b'</DESCRIPTION>bad</FIELD>',1)):
   with self.assertRaises(ValueError):m.parse_schema(raw,Q)
 def test_non_xml_whitespace_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(sample().replace(b'<TABLEDATA>',b'<TABLEDATA>\xc2\xa0'),Q)
 def test_entity_and_malformed_rejected(self):
  with self.assertRaises(ValueError):m.parse_schema(b'<!DOCTYPE VOTABLE><VOTABLE version="1.2"/>',Q)
  with self.assertRaises(ET.ParseError):m.parse_schema(b'<VOTABLE version="1.2">',Q)
if __name__=='__main__':unittest.main(verbosity=2)
