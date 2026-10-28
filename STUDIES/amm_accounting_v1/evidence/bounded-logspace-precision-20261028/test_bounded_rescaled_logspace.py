from pathlib import Path
import numpy as np
import pytest
import mpmath as mp
from bounded_rescaled_logspace import target
from bounded_scale_rescaled import target as composed

@pytest.mark.parametrize('cap',[.5,1.,2.])
@pytest.mark.parametrize('n',[1,12,250])
def test_representable_parity(cap,n):
    for tied in [True,False]:
        y=np.zeros(n) if tied else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n))
        for mu,eta,b in [(2*np.log(.005),2.,.3),(-170.,-10.,-.2),(2*np.log(.005),-20.,0.)]:
            q=np.r_[mu,eta,b,np.linspace(-1.,1.,n)]
            v,g=target(q,y,cap);a,h=composed(q,y,cap)
            np.testing.assert_allclose(v,a,rtol=1e-11,atol=1e-8)
            np.testing.assert_allclose(g,h,rtol=1e-8,atol=1e-7)

def mp_density(q,y,cap):
    q=list(map(mp.mpf,q));y=list(map(mp.mpf,y));mu,eta,b=q[:3];z=q[3:];rho=mp.mpf('.95')
    l=mp.log(cap)-mp.log(1+mp.exp(eta));sigma=mp.exp(l)
    h=[mu+sigma*z[0]/mp.sqrt(1-rho*rho)]
    for zi in z[1:]:h.append(mu+rho*(h[-1]-mu)+sigma*zi)
    s=mp.fsum(h)/(2*len(h));beta=mp.exp(s)*b
    def normal(x,m,sd):return -(x-m)**2/(2*sd**2)-mp.log(sd)-mp.log(2*mp.pi)/2
    v=normal(mu,2*mp.log(mp.mpf('.005')),1)+normal(l,mp.log(mp.mpf('.2')),mp.mpf('.5'))+normal(beta,0,mp.mpf('.002'))
    v+=mp.fsum(normal(x,0,1) for x in z)
    v-=mp.log(mp.erfc(-(mp.log(cap)-mp.log(mp.mpf('.2')))/mp.mpf('.5')/mp.sqrt(2))/2)
    v-=mp.log(1+mp.exp(-eta));v+=s
    tc=mp.loggamma(3)-mp.loggamma(mp.mpf('2.5'))-mp.log(5*mp.pi)/2
    return v+mp.fsum(tc-hi/2-3*mp.log(1+(yi-beta)**2/(5*mp.exp(hi))) for yi,hi in zip(y,h))

def test_captured_failure_against_arbitrary_precision():
    p=Path(__file__).parent/'evidence/bounded-failure-capture-20261028/CAPTURE.npz'
    with np.load(p) as f:q=f['capture'][1:];y=f['y']
    v,g=target(q,y,.5)
    with mp.workdps(90):
        expected=mp_density(q,y,.5)
        assert abs(mp.mpf(v)-expected)<mp.mpf('0.001')
        for i in [0,1,2,3,len(q)-1]:
            def fun(x):
                values=list(map(mp.mpf,q));values[i]=x
                return mp_density(values,y,.5)
            derivative=float(mp.diff(fun,mp.mpf(q[i])))
            np.testing.assert_allclose(g[i],derivative,rtol=1e-9,atol=1e-8)

@pytest.mark.parametrize('b',[-.3,0.,.3])
def test_underflowing_scales_with_nonzero_innovation(b):
    q=np.r_[-2000.,-2.,b,[-1.,.4,.7,-.2]];y=np.array([0.,.001,0.,-.002])
    v,g=target(q,y,2.)
    with mp.workdps(90):
        expected=mp_density(q,y,2.)
        np.testing.assert_allclose(v,float(expected),rtol=1e-12,atol=1e-8)
        for i in range(len(q)):
            def fun(x):
                values=list(map(mp.mpf,q));values[i]=x
                return mp_density(values,y,2.)
            np.testing.assert_allclose(g[i],float(mp.diff(fun,mp.mpf(q[i]))),rtol=1e-9,atol=1e-8)
