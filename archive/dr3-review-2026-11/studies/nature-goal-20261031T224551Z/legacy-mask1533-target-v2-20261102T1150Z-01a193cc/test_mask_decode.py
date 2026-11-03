import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mask_decoder',P/'read_target_mask.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class BitTests(unittest.TestCase):
 def test_every_single_bit(self):
  for bit,name in enumerate(m.BIT_NAMES):
   result=m.decode(1<<bit)
   self.assertEqual([n for n,v in result.items() if v],[name])
 def test_combined_bits(self):
  result=m.decode((1<<2)|(1<<4)|(1<<11))
  self.assertEqual({n for n,v in result.items() if v},{'SATUR_G','SATUR_Z','MEDIUM'})
 def test_signed_high_bit(self):
  result=m.decode(-32768)
  self.assertEqual([n for n,v in result.items() if v],['ALLMASK_I'])
 def test_zero(self):self.assertFalse(any(m.decode(0).values()))
if __name__=='__main__':unittest.main(verbosity=2)
