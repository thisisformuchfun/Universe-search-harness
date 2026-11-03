import importlib.util
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('shape_reader',P/'parse_shape.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
RAW=(P/'capture/shape_control.raw').read_bytes();QUERY=(P/'QUERY.adql').read_text(encoding='utf-8-sig').strip()
class PositiveTests(unittest.TestCase):
 def reject(self,b):
  self.assertNotEqual(b,RAW)
  with self.assertRaises((ValueError,ET.ParseError)):m.parse_shape(b,QUERY)
 def test_expected_control(self):
  out=m.parse_shape(RAW,QUERY);self.assertEqual(out['row_count'],1)
  self.assertEqual(out['records'][0]['gaia_source_id'],'1607896637338835712')
  self.assertEqual(out['records'][0]['x_specobjid'],'7912885126627088384')
 def test_trailing_overflow(self):self.reject(RAW.replace(b'</RESOURCE>',b'<INFO name="QUERY_STATUS" value="OVERFLOW"/></RESOURCE>'))
 def test_missing_or_moved_status(self):self.reject(RAW.replace(b'name="QUERY_STATUS"',b'name="OTHER_STATUS"'))
 def test_bad_query_echo(self):
  with self.assertRaises(ValueError):m.parse_shape(RAW,QUERY+' changed')
 def test_decimal_gaia_id_rejected(self):self.reject(RAW.replace(b'<TD>1607896637338835712</TD>',b'<TD>1.6078966373388357e18</TD>'))
 def test_different_join_key_rejected(self):self.reject(RAW.replace(b'<TD>7912885126627088384</TD>',b'<TD>7912885126627088383</TD>',1))
 def test_wrong_tuple_rejected(self):self.reject(RAW.replace(b'<TD>220</TD>',b'<TD>221</TD>'))
 def test_nonfinite_and_bad_separation_rejected(self):
  for value in (b'NaN',b'1.8'):
   self.reject(RAW.replace(b'<TD>0.2583826592661557</TD>',b'<TD>'+value+b'</TD>'))
 def test_nil_cell_and_null_field_rejected(self):
  self.reject(RAW.replace(b'<TD>7028</TD>',b'<TD nil="true">7028</TD>'))
  anchor=b'<DESCRIPTION>ID in left/first table (specobjid)</DESCRIPTION>'
  self.reject(RAW.replace(anchor,b'<VALUES null="foo"/>'+anchor,1))
 def test_field_id_mismatch_and_table_attr_rejected(self):
  self.reject(RAW.replace(b'ID="x_specobjid"',b'ID="wrong"',1))
  self.reject(RAW.replace(b'<TABLE>',b'<TABLE nrows="17">',1))
 def test_duplicate_row_rejected(self):
  a=RAW.index(b'<TR>');b=RAW.index(b'</TR>',a)+len(b'</TR>');row=RAW[a:b]
  altered=RAW[:b]+row+RAW[b:]
  altered=altered.replace(b'name="TableRows" value="1"',b'name="TableRows" value="2"')
  self.reject(altered)
 def test_mixed_text_and_namespace_rejected(self):
  self.reject(RAW.replace(b'<TABLEDATA>',b'<TABLEDATA>bad',1))
  self.reject(RAW.replace(b'<VOTABLE ',b'<VOTABLE xmlns="urn:wrong" ',1))
 def test_out_of_range_long_and_underscore_float_rejected(self):
  self.reject(RAW.replace(b'<TD>7912885126627088384</TD>',b'<TD>9223372036854775808</TD>'))
  self.reject(RAW.replace(b'<TD>0.2583826592661557</TD>',b'<TD>0.258_3826592661557</TD>'))
 def test_unexpected_sentinel_row_is_preserved(self):
  a=RAW.index(b'<TR>');b=RAW.index(b'</TR>',a)+len(b'</TR>');row=RAW[a:b]
  sentinel=row.replace(b'<TD>1607896637338835712</TD>',b'<TD>1</TD>')
  altered=RAW[:a]+sentinel+RAW[a:]
  altered=altered.replace(b'name="TableRows" value="1"',b'name="TableRows" value="2"')
  result=m.parse_shape(altered,QUERY);self.assertEqual(result['row_count'],2)
  self.assertEqual([r['gaia_source_id'] for r in result['records']],['1','1607896637338835712'])
 def test_source_outside_control_list_rejected(self):
  a=RAW.index(b'<TR>');b=RAW.index(b'</TR>',a)+len(b'</TR>');row=RAW[a:b]
  outsider=row.replace(b'<TD>1607896637338835712</TD>',b'<TD>14</TD>')
  altered=RAW[:b]+outsider+RAW[b:]
  altered=altered.replace(b'name="TableRows" value="1"',b'name="TableRows" value="2"')
  self.reject(altered)
 def test_doctype_and_truncated_xml_rejected(self):
  self.reject(b'<!DOCTYPE VOTABLE>'+RAW)
  self.reject(RAW[:-20])
if __name__=='__main__':unittest.main(verbosity=2)
