import unittest
import numpy as np
import orientation_v1 as o

def fields(wave):
    return {'LOGLAM':np.array(wave,dtype='>f4'),'FLUX':np.array([10.,20.,30.],dtype='>f4'),
            'INVVAR':np.array([1.,2.,3.],dtype='>f4'),'PIXELMASK':np.array([0,1,2],dtype='u1'),
            'SKYFLUX':np.array([4.,5.,6.],dtype='>f4'),'FLUXCORR':np.array([7.,8.,9.],dtype='>f4')}

class OrientationTests(unittest.TestCase):
    def test_ascending_keeps_pairing(self):
        original=fields([1,2,3]); ordered,reverse=o.orient(original)
        self.assertFalse(reverse); self.assertEqual(ordered['FLUX'].tolist(),[10,20,30])
    def test_descending_reverses_every_field(self):
        original=fields([3,2,1]); ordered,reverse=o.orient(original)
        self.assertTrue(reverse)
        for key in o.FIELDS: self.assertEqual(ordered[key].tobytes(),original[key][::-1].tobytes())
    def test_duplicate_grid_rejected(self):
        with self.assertRaises(ValueError): o.orient(fields([1,1,2]))
    def test_nonmonotone_grid_rejected(self):
        with self.assertRaises(ValueError): o.orient(fields([1,3,2]))
    def test_nonfinite_grid_rejected(self):
        with self.assertRaises(ValueError): o.orient(fields([1,float('nan'),3]))
    def test_mask_and_shape_rejected(self):
        x=fields([1,2,3]); x['FLUX']=np.ma.array(x['FLUX'],mask=[False,True,False])
        with self.assertRaises(ValueError): o.orient(x)
        x=fields([1,2,3]); x['FLUX']=x['FLUX'][:2]
        with self.assertRaises(ValueError): o.orient(x)
    def test_dtype_and_bytes_roundtrip(self):
        x=fields([3,2,1]); x['FLUX'][1]=float('nan'); ordered,rev=o.orient(x)
        for key in o.FIELDS:
            self.assertEqual(ordered[key].dtype,x[key].dtype)
            self.assertEqual(ordered[key][::-1].tobytes(),x[key].tobytes())
    def test_input_is_not_mutated_or_aliased(self):
        x=fields([3,2,1]); before={k:v.tobytes() for k,v in x.items()}; ordered,rev=o.orient(x)
        ordered['FLUX'][0]=999
        self.assertTrue(all(x[k].tobytes()==before[k] for k in o.FIELDS))

if __name__=='__main__': unittest.main()
