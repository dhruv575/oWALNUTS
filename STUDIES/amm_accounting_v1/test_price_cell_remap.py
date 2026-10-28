import unittest
import numpy as np
from scipy.special import expit
from price_cell_remap import shift


def paths(q,n,rho):
    h=np.empty((len(q),n));h[:,0]=q[:,0]+np.exp(q[:,1])*q[:,3]/np.sqrt(1-rho*rho)
    for i in range(1,n):h[:,i]=q[:,0]+rho*(h[:,i-1]-q[:,0])+np.exp(q[:,1])*q[:,3+i]
    return h


class Remap(unittest.TestCase):
    def test_physical_overlap_and_ownership(self):
        for n in (2,12,250):
            for rho in (-.8,0.,.95):
                q=np.sin(np.arange(4*(3+2*n)).reshape(4,-1)*.13)
                q[:,0]=-10.;q[:,1]=-1.6
                m=2+np.cos(q);s=np.array([.1,.2,.3,.4])
                lo=np.arange(n+1)*.001;hi=lo+.0005
                before=[a.copy() for a in (q,m,s,lo,hi)]
                new,metric,steps=shift(q,m,s,lo[:-1],hi[:-1],lo[1:],hi[1:],rho)
                np.testing.assert_allclose(paths(new,n,rho)[:,:-1],paths(q,n,rho)[:,1:],rtol=1e-13,atol=1e-13)
                oldx=lo[:-1]+(hi[:-1]-lo[:-1])*expit(q[:,3+n:])
                newx=lo[1:]+(hi[1:]-lo[1:])*expit(new[:,3+n:])
                np.testing.assert_array_equal(newx[:,:-1],oldx[:,1:])
                np.testing.assert_array_equal(new[:,-1],0.)
                np.testing.assert_array_equal(new[:,3+n-1],0.)
                np.testing.assert_array_equal(metric[:,[3,3+n-1,3+2*n-1]],1.)
                np.testing.assert_array_equal(metric[:,:3],m[:,:3])
                np.testing.assert_array_equal(metric[:,4:3+n-1],m[:,5:3+n])
                np.testing.assert_array_equal(metric[:,3+n:-1],m[:,4+n:])
                for a,b in zip((q,m,s,lo,hi),before):np.testing.assert_array_equal(a,b)
                self.assertFalse(np.shares_memory(new,q));self.assertFalse(np.shares_memory(metric,m));self.assertFalse(np.shares_memory(steps,s))

    def test_reject_incompatible_cells_and_states(self):
        q=np.zeros((4,7));m=np.ones_like(q);s=np.ones(4);lo=np.array([0.,1.,2.]);hi=lo+.1
        with self.assertRaises(ValueError):shift(q,m,s,lo[:-1],hi[:-1],lo[1:]+.01,hi[1:]+.01)
        for bad in (0.,-1.,np.nan):
            broken=m.copy();broken[0,0]=bad
            with self.assertRaises(ValueError):shift(q,broken,s,lo[:-1],hi[:-1],lo[1:],hi[1:])
        with self.assertRaises(ValueError):shift(q,m,s,lo[:-1],hi[:-1],lo[1:],hi[1:],rho=1.)


if __name__=='__main__':unittest.main()
