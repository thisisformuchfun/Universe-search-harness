import csv,io,socket,subprocess,unittest
from unittest.mock import patch
import reference_capture_v1 as r

def sample(rows,header=None):
    out=io.StringIO(newline=''); w=csv.writer(out,lineterminator='\r\n')
    w.writerow(r.FIELDS if header is None else header); w.writerows(rows); return out.getvalue().encode()
def row(**changes):
    d={k:'' for k in r.FIELDS}
    d.update(specid=r.SPECID,obsdate='2015-03-09',planid=r.PLATE,spid='15',fiberid='142',
             iexp='0',mjm='82211011',obsid='331215142',filename=r.REFERENCE)
    d.update(changes); return [d[k] for k in r.FIELDS]

class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.net=patch.object(socket,'socket',side_effect=AssertionError('network forbidden'))
        cls.child=patch.object(subprocess,'Popen',side_effect=AssertionError('child forbidden'))
        cls.net.start(); cls.child.start()
        cls.lib=r.load('reference_test_helpers',r.LIB)
    @classmethod
    def tearDownClass(cls): cls.child.stop(); cls.net.stop()
    def test_sample_identity(self):
        self.assertEqual(r.sample_identity(sample([row()]))['filename'],r.REFERENCE)
    def test_wrong_or_duplicate_sample_identity_stops(self):
        with self.assertRaises(ValueError): r.sample_identity(sample([row(fiberid='143')]))
        with self.assertRaises(ValueError): r.sample_identity(sample([row(),row()]))
    def test_sample_schema_and_width_are_strict(self):
        with self.assertRaises(ValueError): r.sample_identity(sample([],r.FIELDS[:-1]))
        with self.assertRaises(ValueError): r.sample_identity(sample([['short']]))
    def test_root_exact_link(self):
        self.assertTrue(self.lib.exact_child(b'<a href="20150309/">x</a>',r.DAY+'/'))
        self.assertFalse(self.lib.exact_child(b'<a href="20150309/">x</a><a href="20150309/">x</a>',r.DAY+'/'))
    def test_ambiguous_base_rejected(self):
        self.assertFalse(self.lib.exact_child(b'<base href="/"><a href="20150309/">x</a>',r.DAY+'/'))
    def test_fixed_stage_order_and_caps(self):
        self.assertEqual([x[0] for x in r.STAGES],['day','plan','product'])
        self.assertEqual(sum(x[2] for x in r.STAGES),5000000)
        self.assertTrue(all(x[1].startswith(r.BASE) for x in r.STAGES))
    def test_stop_on_missing_child_or_bad_fits_prefix(self):
        ok={'status':'HTTP_COMPLETE_UNPARSED'}
        self.assertEqual(self.lib.decide('day',ok,b'<a href="other/">x</a>',r.PLATE+'/'),'STOP_INDEX_UNVALIDATED')
        self.assertEqual(self.lib.decide('product',ok,b'not fits',None),'STOP_PRODUCT_PREFIX')
    def test_bad_manifest_rejected_before_child(self):
        with self.assertRaises(ValueError): r.validate_inputs('not-a-hash')

if __name__=='__main__': unittest.main()
