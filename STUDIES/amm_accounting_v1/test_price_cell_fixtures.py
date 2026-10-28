import unittest
import numpy as np
from price_cell_fixtures import fixture
from price_cell_sv import target


class Fixtures(unittest.TestCase):
    def test_fixed_design(self):
        for n in (12,250):
            for width in (.001,.00001):
                data,latent=fixture(n,width)
                self.assertTrue(np.all(latent>=data['lower_cell']))
                self.assertTrue(np.all(latent<data['upper_cell']))
                self.assertTrue(np.any(np.diff(data['lower_cell'])==0))
                q=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)]
                v,g=target(q,data['lower_cell'],data['upper_cell'],0.)
                self.assertTrue(np.isfinite(v));self.assertTrue(np.isfinite(g).all())
                self.assertEqual(g.shape,(3+2*n,))


if __name__=='__main__':unittest.main()
