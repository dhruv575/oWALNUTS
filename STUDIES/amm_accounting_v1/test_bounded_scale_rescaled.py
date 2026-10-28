import numpy as np
import pytest
from bounded_scale_rescaled import physical,target
from bounded_scale_sv import target as original


@pytest.mark.parametrize('cap',[.5,1.,2.])
@pytest.mark.parametrize('n',[1,12,250])
def test_change_of_variables_and_gradient(cap,n):
    q=np.r_[2*np.log(.005),-2.,.3,np.linspace(-.8,.5,n)]
    y=np.zeros(n);p,jac,scale,d=physical(q,cap)
    value,grad=target(q,y,cap);v,_=original(p,y,cap)
    assert value==v+jac
    assert p[2]==scale*q[2]
    # Every coordinate, including coupling through mean(h).
    numeric=[]
    for k in range(len(q)):
        step=1e-5;plus=q.copy();minus=q.copy();plus[k]+=step;minus[k]-=step
        numeric.append((target(plus,y,cap)[0]-target(minus,y,cap)[0])/(2*step))
    np.testing.assert_allclose(grad,numeric,rtol=2e-5,atol=2e-6)


def test_strongly_negative_latent_volatility_and_input_ownership():
    q=np.r_[-170.,-5.,.3,np.zeros(12)];before=q.copy()
    value,grad=target(q,np.zeros(12),2.)
    assert np.isfinite(value) and np.isfinite(grad).all()
    np.testing.assert_array_equal(q,before)
    p,_,_,_=physical(q,2.);assert 0<abs(p[2])<1e-30
