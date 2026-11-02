import unittest
import numpy as np
import reference_metadata_v2 as m

def row(): return {'planid':'plate','spid':'15','fiberid':'142','ra':'166.9787490000','dec':'16.3964380000','obsid':'331215142'}
def header(): return {'PLANID':'plate','SPID':15,'FIBERID':142,'RA':166.978749,'DEC':16.396438}
class ReferenceMetadataTests(unittest.TestCase):
    def test_matching_identity(self):
        x=m.identify(header(),row()); self.assertFalse(x['header_obsid_present']); self.assertFalse(x['independent_astrometry_established'])
    def test_wrong_coordinate_stops(self):
        h=header(); h['RA']=166.978750
        with self.assertRaises(ValueError): m.identify(h,row())
    def test_missing_or_wrong_id_stops(self):
        h=header(); del h['DEC']
        with self.assertRaises(ValueError): m.identify(h,row())
        h=header(); h['SPID']='15'
        with self.assertRaises(ValueError): m.identify(h,row())
    def test_strictly_ascending_and_descending(self):
        a=m.order_counts([1.,2.,3.]); d=m.order_counts([3.,2.,1.])
        self.assertEqual((a['increasing_pairs'],a['decreasing_pairs']),(2,0))
        self.assertEqual((d['increasing_pairs'],d['decreasing_pairs']),(0,2))
    def test_equal_mixed_and_nonfinite(self):
        x=m.order_counts([1.,1.,0.,float('nan'),2.])
        self.assertEqual((x['finite_adjacent_pairs'],x['equal_pairs'],x['decreasing_pairs']),(2,1,1))
    def test_masked_or_wrong_shape_stops(self):
        with self.assertRaises(ValueError): m.order_counts(np.ma.array([1.,2.],mask=[False,True]))
        with self.assertRaises(ValueError): m.order_counts([[1.,2.]])
    def test_nonfinite_and_out_of_range_coordinates_stop(self):
        for key,value in [('RA',float('inf')),('RA',360.),('DEC',-91.)]:
            h=header(); h[key]=value; r=row(); r[key.lower()]=str(value)
            with self.assertRaises(ValueError): m.identify(h,r)
    def test_present_obsid_must_match(self):
        h=header(); h['OBSID']=123
        with self.assertRaises(ValueError): m.identify(h,row())
        h['OBSID']=331215142; self.assertTrue(m.identify(h,row())['header_obsid_present'])
    def test_valid_frame_labels(self):
        mins=['10000001','10000002','10000003']*2; arms=['b']*3+['r']*3
        self.assertEqual(len(m.frame_labels(mins,arms,'10000001')),6)
    def test_duplicate_or_unknown_frame_labels_stop(self):
        mins=['10000001','10000001','10000003']*2; arms=['b']*3+['r']*3
        with self.assertRaises(ValueError): m.frame_labels(mins,arms,'10000001')
        mins=['10000001','10000002','10000003']*2; arms=['b','x','b','r','r','r']
        with self.assertRaises(ValueError): m.frame_labels(mins,arms,'10000001')
    def test_missing_nominal_minute_stops(self):
        mins=['10000001','10000002','10000003']*2; arms=['b']*3+['r']*3
        with self.assertRaises(ValueError): m.frame_labels(mins,arms,'99999999')

if __name__=='__main__': unittest.main()
