import math
import unittest
from exact_iid_quantile_control import ranks,control

class ExactIIDTests(unittest.TestCase):
    def test_exact_small_binomial_enumeration_and_tight_ranks(self):
        for n in [1,2,7,25,100]:
            for p in [.01,.05,.25,.5,.95,.99]:
                r=ranks(n,p);mass=[math.comb(n,k)*p**k*(1-p)**(n-k) for k in range(n+1)];a,b=r['lower_rank'],r['upper_rank'];tail=.05/4
                self.assertLessEqual(sum(mass[:a]),tail+1e-14);self.assertLessEqual(sum(mass[b:]),tail+1e-14)
                self.assertAlmostEqual(sum(mass[a:b]),r['coverage_probability'],places=12)
                if a<n:self.assertGreater(sum(mass[:a+1]),tail)
                if b>0:self.assertGreater(sum(mass[b-1:]),tail)
    def test_joint_two_endpoint_multinomial_coverage(self):
        for n,pl,pu in [(20,.25,.75),(60,.05,.95)]:
            a=ranks(n,pl);b=ranks(n,pu);covered=0.
            for k in range(n+1):
                for middle in range(n-k+1):
                    high=n-k-middle;mass=math.comb(n,k)*math.comb(n-k,middle)*pl**k*(pu-pl)**middle*(1-pu)**high
                    if a['lower_rank']<=k<a['upper_rank'] and b['lower_rank']<=k+middle<b['upper_rank']:covered+=mass
            self.assertGreaterEqual(covered,.95)
    def test_small_sample_infinite_endpoints(self):
        result=control([0.],iid_confirmed=True)
        self.assertTrue(all(r['lower']==-math.inf and r['upper']==math.inf for r in result['rows']))
    def test_order_indexing_affine_equivariance_and_miss_retained(self):
        x=list(range(200));a=control(x,iid_confirmed=True);b=control([3+2*v for v in reversed(x)],mean=3,sd=2,iid_confirmed=True)
        for r,s in zip(a['rows'],b['rows']):
            self.assertEqual(r['lower'],x[r['lower_rank']-1]);self.assertEqual(r['upper'],x[r['upper_rank']-1]);self.assertEqual(s['lower'],3+2*r['lower']);self.assertAlmostEqual(s['truth'],3+2*r['truth'])
        self.assertFalse(a['both_or_all_covered']);self.assertEqual(a['n'],200)
    def test_extreme_tails_large_n(self):
        for p in [1e-8,1-1e-8,.05,.95]:
            r=ranks(1000000,p,alpha=1e-10);self.assertLessEqual(r['lower_noncoverage'],r['tail_budget']);self.assertLessEqual(r['upper_noncoverage'],r['tail_budget'])
    def test_reject_unacknowledged_and_invalid(self):
        with self.assertRaises(ValueError):control([0.,1.])
        for x in [[],[math.nan],[True]]:
            with self.assertRaises(ValueError):control(x,iid_confirmed=True)
        for kwargs in [dict(probabilities=(.5,.5)),dict(probabilities=(0.,)),dict(alpha=0),dict(sd=0)]:
            with self.assertRaises(ValueError):control([0.],iid_confirmed=True,**kwargs)
if __name__=='__main__':unittest.main()
