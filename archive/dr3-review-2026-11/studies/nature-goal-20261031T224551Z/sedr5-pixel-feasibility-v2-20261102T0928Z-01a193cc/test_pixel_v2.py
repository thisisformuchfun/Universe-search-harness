import unittest
import numpy as np
import pixel_feasibility_v2 as p

class FrameMetricsTests(unittest.TestCase):
    def test_counts_and_signed_proxy(self):
        m=p.frame_metrics([2.,-1.,float('nan'),3.],[4.,1.,1.,0.],[1.,2.,3.,4.],[0,0,0,0])
        self.assertEqual((m['finite_flux'],m['positive_invvar'],m['joint_numeric_count']),(3,3,2))
        self.assertEqual(m['median_signed_flux_sqrt_invvar_proxy'],1.5)
    def test_mask_is_counted_not_interpreted(self):
        m=p.frame_metrics([1.,2.],[1.,1.],[1.,2.],[0,2])
        self.assertEqual((m['zero_pixelmask'],m['joint_numeric_count']),(1,1))
    def test_empty_proxy_is_null(self):
        m=p.frame_metrics([1.],[0.],[1.],[0]); self.assertIsNone(m['median_signed_flux_sqrt_invvar_proxy'])
    def test_nonfinite_wavelength_pairs_not_counted(self):
        m=p.frame_metrics([1.]*4,[1.]*4,[1.,float('nan'),2.,2.],[0]*4)
        self.assertEqual((m['finite_adjacent_loglam_pairs'],m['nonincreasing_finite_loglam_pairs']),(1,1))
    def test_shape_and_type_rejected(self):
        with self.assertRaises(ValueError): p.frame_metrics([1.],[1.,2.],[1.],[0])
        with self.assertRaises(ValueError): p.frame_metrics([1.],[1.],[1.],['bad'])
    def test_infinite_proxy_excluded(self):
        m=p.frame_metrics([1e308],[1e308],[1.],[0])
        self.assertEqual(m['joint_numeric_count'],1); self.assertEqual(m['finite_signed_proxy_count'],0)
        self.assertIsNone(m['median_signed_flux_sqrt_invvar_proxy'])
    def test_finite_median_does_not_overflow(self):
        m=p.frame_metrics([1e308,1e308],[1.,1.],[1.,2.],[0,0])
        self.assertEqual(m['median_signed_flux_sqrt_invvar_proxy'],1e308)
    def test_integer_wavelength_order_is_not_rounded(self):
        m=p.frame_metrics([1.,1.],[1.,1.],np.array([2**53,2**53+1],dtype=np.uint64),[0,0])
        self.assertEqual(m['nonincreasing_finite_loglam_pairs'],0)
    def test_subnormal_median_is_preserved(self):
        tiny=np.nextafter(0.,1.)
        m=p.frame_metrics([tiny,tiny],[1.,1.],[1.,2.],[0,0])
        self.assertEqual(m['median_signed_flux_sqrt_invvar_proxy'],tiny)
    def test_extra_labels_are_rejected(self):
        fake={'MJM':[np.array([x[0] for x in p.LABELS])],
              'COLOR':[np.array([x[1] for x in p.LABELS]+['r'])]}
        with self.assertRaises(ValueError): p.labels(fake)
    def test_masked_array_is_rejected(self):
        with self.assertRaises(ValueError): p.frame_metrics(np.ma.array([1.],mask=[True]),[1.],[1.],[0])

if __name__=='__main__': unittest.main()
