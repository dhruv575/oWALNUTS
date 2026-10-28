import unittest
import numpy as np
from confirmation_bootstrap import circular_indices,paired_means,summarize

class BootstrapTests(unittest.TestCase):
    def test_wrap_and_truncate(self):
        np.testing.assert_array_equal(circular_indices(np.array([[4,2]]),5,3),[[4,0,1,2,3]])

    def test_exact_enumerated_small_distribution(self):
        # All 3^2 equally probable block-start combinations; second block truncates.
        starts=np.array([[a,b] for a in range(3) for b in range(3)])
        x=np.array([1.,2.,8.]);ix=circular_indices(starts,3,2)
        observed=x[ix].mean(axis=1)
        expected=np.array([(x[a]+x[(a+1)%3]+x[b])/3 for a,b in starts])
        np.testing.assert_array_equal(observed,expected)
        self.assertAlmostEqual(observed.mean(),x.mean())

    def test_pairing_and_chunk_invariance(self):
        a=np.arange(17,dtype=float);x=np.column_stack([a,a+5,2*a])
        one=paired_means(x,17,6,81,200,1);many=paired_means(x,17,6,81,200,31)
        np.testing.assert_array_equal(one,many)
        np.testing.assert_allclose(one[:,1]-one[:,0],5,atol=1e-14)
        np.testing.assert_array_equal(one[:,2],2*one[:,0])

    def test_full_length_circular_block_mean(self):
        x=np.arange(13.)[:,None];r=paired_means(x,13,13,18,100)
        np.testing.assert_array_equal(r,np.full((100,1),6.))

    def test_constant_interval_and_missing_rejection(self):
        result=summarize(np.full((20,1),.5),20,4,11,100)
        self.assertEqual(result['lower_9875'],[.5]);self.assertEqual(result['interval_95'],[[.5,.5]])
        for data in [np.zeros((19,1)),np.full((20,1),np.nan),np.full((20,1),np.inf)]:
            with self.assertRaises(ValueError):paired_means(data,20,4,11)

if __name__=='__main__':unittest.main()
