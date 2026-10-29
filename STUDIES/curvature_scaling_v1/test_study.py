import unittest
import numpy as np
from targets import Target,core,CASES
from native import Native
from worker import CONFIGS,sample
from analyze import ladder,ratios,score

class StudyTests(unittest.TestCase):
    def test_exact_transform_and_gradient(self):
        rng=np.random.default_rng(735000000)
        for d,b in CASES:
            t=Target(d,b);z=rng.normal(size=(5,d));q=t.forward(z)
            np.testing.assert_allclose(t.inverse(q),z,atol=1e-13)
            for x in q:
                lp,g=core(x,0,t.precision);self.assertAlmostEqual(lp,-.5*np.dot(t.inverse(x),t.inverse(x)),places=10)
                numerical=[]
                for i in range(d):
                    e=np.zeros(d);e[i]=1e-5
                    numerical.append((core(x+e,0,t.precision)[0]-core(x-e,0,t.precision)[0])/2e-5)
                np.testing.assert_allclose(g,numerical,atol=1e-6,rtol=1e-6)
    def test_exact_iid_functionals_and_initial_mapping(self):
        for i,(d,b) in enumerate(CASES):
            t=Target(d,b);q=t.iid(50000,735100000+i);f=t.features(q)
            self.assertEqual(f.shape,(50000,len(t.truth())))
            self.assertLess(np.max(abs(f.mean(axis=0)-t.truth())),.006)
            np.testing.assert_allclose(t.inverse(t.initial()),Target(d,0).initial(),atol=1e-14)
    def test_native_values_and_recoverable_overflow(self):
        t=Target(8,5);o=Native(t)
        for q in t.initial():
            status,lp,g,other,h=o.values(q);want,grad=core(q,0,t.precision)
            self.assertEqual(status,0);self.assertAlmostEqual(lp,want);self.assertAlmostEqual(other,want)
            np.testing.assert_array_equal(g,grad);np.testing.assert_array_equal(h,grad)
        status,lp,g,other,h=o.values(np.full(8,1e200))
        self.assertEqual(status,1);self.assertEqual(other,-np.inf);self.assertTrue(np.isfinite(h).all())
    def test_configurations_on_known_gaussian(self):
        for i,(name,c) in enumerate(CONFIGS.items()):
            t=Target(8,0);o=Native(t);q,info=sample(t,o,c,735200000+i,1000)
            self.assertEqual(q.shape,(4,1000,8));self.assertLess(np.max(abs(q.mean(axis=(0,1)))),.13)
            self.assertLess(np.max(abs(q.var(axis=(0,1))-1)),.22)
    def test_censoring_and_costs(self):
        fail=dict(draws=3000,status='failed',total_seconds=3)
        good=dict(draws=6000,status='ok',metrics=dict(passed=True),total_seconds=5,seconds=2,materialize_seconds=.1,target_calls=100)
        r=ladder([fail,good]);self.assertTrue(r['reached']);self.assertEqual(r['total'],8);self.assertIsNone(r['kernel'])
        self.assertFalse(ladder([fail])['reached']);self.assertEqual(score(fail),1e12)
        self.assertEqual(ratios([dict(reached=True,kernel=4)]*8,[dict(reached=True,kernel=2)]*8,'kernel')['interval95'],[2.,2.])

if __name__=='__main__':unittest.main()
