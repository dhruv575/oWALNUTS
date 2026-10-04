import unittest
import numpy as np
from flow_starts import canonical_starts,to_noncentered
from geometry import FixedGeometry


class MatchedStartTests(unittest.TestCase):
    def data(self):
        return dict(y=np.zeros((8,2)).tolist(),x=np.zeros((8,2)).tolist(),rho=.95,nu=5.)

    def test_supplied_starts_are_copied_and_roundtrip(self):
        d=self.data();q=np.random.default_rng(9991).normal(size=(3,16))*.25
        q[:,3]=-1.5;q[:,2]=[-1.4,-.8,-1.]
        d['initial_positions']=q.tolist()
        got=canonical_starts(d,3);np.testing.assert_array_equal(got,q)
        got[0,0]=99.;self.assertNotEqual(d['initial_positions'][0][0],99.)
        u=to_noncentered(q,d);h=np.zeros((3,8));sig=np.exp(u[:,3]);mu=u[:,2]
        h[:,0]=mu+sig*u[:,8]/np.sqrt(1-d['rho']**2)
        for t in range(1,8):h[:,t]=mu+d['rho']*(h[:,t-1]-mu)+sig*u[:,8+t]
        np.testing.assert_allclose(h,q[:,8:],atol=1e-14)
        for shear in [False,True]:
            geometry=FixedGeometry.from_data(d,shear)
            np.testing.assert_allclose(geometry.to_canonical(geometry.to_transformed(q)),q,atol=1e-14)

    def test_rejects_bad_shape_count_nonfinite(self):
        d=self.data()
        for bad in [[],[[0.]],np.zeros((2,16)).tolist(),np.full((3,16),np.nan).tolist()]:
            d['initial_positions']=bad
            with self.assertRaises(ValueError):canonical_starts(d,3)
        for chains in [0,-1,True,1.5]:
            with self.assertRaises(ValueError):canonical_starts(self.data(),chains)

    def test_historical_default_preserved(self):
        q=canonical_starts(self.data(),4)
        np.testing.assert_array_equal(q[:,:4],np.tile([0.,-1.,-1.,-1.5],(4,1)))
        np.testing.assert_array_equal(q[:,4:8],0.)
        np.testing.assert_array_equal(q[:,8:],-1.)


if __name__=='__main__':unittest.main()
