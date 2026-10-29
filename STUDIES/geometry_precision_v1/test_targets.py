import unittest
import numpy as np
from scipy.stats import norm,multivariate_normal,multivariate_t
from scipy.special import logsumexp
from targets import Target,NAMES,core


class TargetTests(unittest.TestCase):
    def test_gradients(self):
        for name in NAMES:
            t=Target(name)
            for q in t.initial():
                h=1e-5
                numerical=np.array([(t(q+np.eye(t.dim)[i]*h)[0]-t(q-np.eye(t.dim)[i]*h)[0])/(2*h) for i in range(t.dim)])
                np.testing.assert_allclose(t(q)[1],numerical,rtol=2e-5,atol=2e-5)

    def test_independent_densities(self):
        for name in NAMES:
            t=Target(name)
            def density(q):
                k=t.kind
                if k in (0,5):return norm.logpdf(q).sum()
                if k==1:return multivariate_normal.logpdf(q,cov=t.cov)
                if k==2:
                    z=q.copy();z[1]-=2*(z[0]**2-1);return norm.logpdf(z).sum()
                if k in (3,4,6):
                    s=1.5 if k==3 else 3. if k==4 else 1.
                    l=1.5*np.tanh(2*q[0]) if k==6 else q[0]/2
                    return norm.logpdf(q[0],scale=s)+norm.logpdf(q[1:],scale=np.exp(l)).sum()
                if k==7:return multivariate_t.logpdf(q,shape=np.eye(t.dim),df=3)
                return logsumexp([norm.logpdf(q[0],-3),norm.logpdf(q[0],3)])-np.log(2)+norm.logpdf(q[1:]).sum()
            a,b=t.initial()[:2]
            self.assertAlmostEqual(t(a)[0]-t(b)[0],density(a)-density(b),places=8)

    def test_exact_generators_and_probability_transforms(self):
        for name in NAMES:
            t=Target(name);u=t.uniforms(t.iid(50000,655100000+t.kind))
            self.assertLess(np.max(abs(u.mean(axis=0)-.5)),.006)
            self.assertLess(np.max(abs(u.var(axis=0)-1/12)),.003)
            self.assertLess(np.max(abs(np.cov(u.T)-np.eye(t.dim)/12)),.003)
            f=t.features(t.iid(50000,655200000+t.kind))
            self.assertLess(np.max(abs(f.mean(axis=0)-t.truth())),.007)


if __name__=='__main__':unittest.main()
