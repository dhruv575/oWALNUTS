import unittest
import numpy as np
from scipy.special import expit
from scipy.stats import binom,norm,nbinom
from models import generate,Target,bandit_target,inventory_cost,CANDIDATES,SCENARIOS


class ScreenTests(unittest.TestCase):
    def test_all_gradients_against_finite_differences(self):
        for candidate in CANDIDATES:
            for scenario in SCENARIOS:
                p=generate(candidate,scenario,77)
                target=p.get('target') or bandit_target(p['X'][:20,0],p['potential'][:20,0])
                q=target.mean+np.random.default_rng(8).normal(0,.3,target.dim);h=1e-5
                numeric=np.array([(target(q+np.eye(target.dim)[i]*h)[0]-target(q-np.eye(target.dim)[i]*h)[0])/(2*h) for i in range(target.dim)])
                np.testing.assert_allclose(target(q)[1],numeric,rtol=2e-5,atol=2e-5)

    def test_likelihood_differences_against_scipy(self):
        for candidate in ['hierarchical_ab','revenue_ab','inventory']:
            p=generate(candidate,'heterogeneous',18);t=p['target'];d=t.data
            def independent(q):
                lp=norm.logpdf(q,t.mean,t.sd).sum()
                if t.kind=='logistic':return lp+binom.logpmf(d['y'],d['n'],expit(d['X']@q)).sum()
                if t.kind=='inventory':return lp+nbinom.logpmf(d['y'],5,5/(5+np.exp(d['X']@q))).sum()
                lp+=binom.logpmf(d['success'],d['n'],expit(q[:2])).sum()
                for a in range(2):lp+=norm.logpdf(d['logs'][a],q[2+a],.2+1.6*expit(q[4+a])).sum()
                return lp
            a=t.mean;b=a+.17
            self.assertAlmostEqual(t(b)[0]-t(a)[0],independent(b)-independent(a),places=8)

    def test_inventory_loss_matches_enumeration_and_optimum(self):
        k=np.arange(5000)
        for mu,r in [(3.,1.),(20.,5.),(80.,2.)]:
            q=int(nbinom.ppf(.8,r,r/(r+mu)))
            for a in [0,q,q+4]:
                expected=np.sum(nbinom.pmf(k,r,r/(r+mu))*(4*np.maximum(k-a,0)+np.maximum(a-k,0)))
                self.assertAlmostEqual(inventory_cost(a,mu,r),expected,places=8)
            self.assertLessEqual(inventory_cost(q,mu,r),inventory_cost(q+1,mu,r)+1e-10)
            self.assertLessEqual(inventory_cost(q,mu,r),inventory_cost(q-1,mu,r)+1e-10)

    def test_seed_blocks_disjoint_and_simulations_deterministic(self):
        blocks=[base+c*1000000+s*100000+r*1000 for base in [529100000,539100000] for c in range(4) for s in range(5) for r in range(20)]
        self.assertEqual(len(blocks),len(set(blocks)))
        self.assertGreaterEqual(min(np.diff(sorted(blocks))),1000)
        a=generate('contextual_bandit','easy',5);b=generate('contextual_bandit','easy',5)
        np.testing.assert_array_equal(a['potential'],b['potential'])
        self.assertEqual(len(a['initial']),20)

    def test_bandit_target_copies_only_observed_history(self):
        p=generate('contextual_bandit','misspecified',8)
        X=[p['X'][t,a] for t,a in enumerate(p['initial'])];y=[p['potential'][t,a] for t,a in enumerate(p['initial'])]
        target=bandit_target(X,y);before=target(target.mean)
        p['potential'][20:]=1-p['potential'][20:];p['truth'][20:]=0
        after=target(target.mean)
        self.assertEqual(before[0],after[0]);np.testing.assert_array_equal(before[1],after[1])


if __name__=='__main__':unittest.main()
