import unittest
import numpy as np
from targets import Target
from controls import laplace
from warm import Shifted


class SupplementalTests(unittest.TestCase):
    def test_laplace_exact_gaussian(self):
        for name in ['isotropic','correlated']:
            t=Target(name);mean,cov,info=laplace(t)
            np.testing.assert_allclose(mean,0,atol=1e-7)
            np.testing.assert_allclose(cov,t.cov if name=='correlated' else np.eye(t.dim),atol=1e-7)

    def test_translation_density_gradient_and_truth(self):
        for name in ['correlated','banana']:
            a=Target(name);b=Shifted(name,2.)
            q=a.iid(100,655400000)
            np.testing.assert_allclose(b.features(q+b.offset),a.features(q),atol=1e-12)
            for x in q[:3]:
                self.assertAlmostEqual(a(x)[0],b(x+b.offset)[0])
                np.testing.assert_allclose(a(x)[1],b(x+b.offset)[1],atol=1e-12)


if __name__=='__main__':unittest.main()
