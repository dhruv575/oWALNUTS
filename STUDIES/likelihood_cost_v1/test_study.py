import unittest
import numpy as np
from targets import Target,core,SIZES
from native import Native
from sampling import sample
from worker import CONFIGS
from analyze import ratio

class Tests(unittest.TestCase):
    def test_direct_matches_analytic_posterior_and_gradient(self):
        rng=np.random.default_rng(775000000)
        for n in SIZES:
            t=Target(n);P=t.precision
            np.testing.assert_allclose(t.L@t.L.T,np.linalg.inv(np.eye(24)+t.X.T@t.X),atol=1e-13)
            for q in t.forward(rng.normal(size=(5,24))):
                lp,g=core(q,0,P);exact,h=core(q,1,P)
                self.assertAlmostEqual(lp,exact,places=9);np.testing.assert_allclose(g,h,atol=1e-10)
                numeric=[]
                for i in range(24):
                    e=np.zeros(24);e[i]=1e-5
                    numeric.append((core(q+e,0,P)[0]-core(q-e,0,P)[0])/2e-5)
                np.testing.assert_allclose(g,numeric,atol=1e-6,rtol=1e-6)
    def test_native_and_recoverable_overflow(self):
        t=Target(64);o=Native(t)
        for q in t.initial():
            status,lp,g,other,h=o.values(q);expected,grad=core(q,0,t.precision)
            self.assertEqual(status,0);self.assertAlmostEqual(lp,expected);self.assertAlmostEqual(other,expected)
            np.testing.assert_allclose(g,grad);np.testing.assert_allclose(h,grad)
        status,lp,g,other,h=o.values(np.full(24,1e200));self.assertEqual(status,1);self.assertEqual(other,-np.inf)
    def test_all_arms_on_known_flat_geometry(self):
        for i,(name,c) in enumerate(CONFIGS.items()):
            t=Target(64,c['kind'],curvature=0);o=Native(t);q,info=sample(t,o,c,775100000+i,1000)
            self.assertEqual(q.shape,(4,1000,24));self.assertLess(np.max(abs(q.mean(axis=(0,1)))),.15)
            self.assertLess(np.max(abs(q.var(axis=(0,1))-1)),.25)
    def test_exact_functionals_and_reparam_initialization(self):
        t=Target(64);q=t.iid(50000,775200000)
        self.assertLess(np.max(abs(t.features(q).mean(axis=0)-t.truth())),.006)
        np.testing.assert_allclose(t.inverse(t.initial()),Target(64,2).initial(),atol=1e-13)
    def test_ratios_keep_failed_pairs_out(self):
        a=[dict(passed=True,kernel=4),dict(passed=False,kernel=.1)];b=[dict(passed=True,kernel=2)]*2
        r=ratio(a,b,'kernel');self.assertEqual(r['pairs'],1);self.assertEqual(r['interval95'],[2.,2.])

if __name__=='__main__':unittest.main()
