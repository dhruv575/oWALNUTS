import numpy as np
import pytest
from scipy.stats import norm
from scipy.special import log_ndtr
from bounded_rescaled_slice import physical,likelihood,transition
from bounded_scale_rescaled import target

@pytest.mark.parametrize('cap',[.5,1.,2.])
@pytest.mark.parametrize('n',[1,12,250])
def test_complete_change_of_variables(cap,n):
    core=np.r_[.4,1.3,.2,np.linspace(-.4,.6,n)]
    p,h,log_scale=physical(core,cap)
    gap=np.log(cap)-p[1];eta=gap+np.log(-np.expm1(-gap))
    q=np.r_[p[0],eta,core[2],p[3:]]
    mass=log_ndtr((np.log(cap)-np.log(.2))/.5)
    # d l / d w = phi(w) / normalized truncated-Normal density(l).
    log_dl_dw=norm.logpdf(core[1])-norm.logpdf(p[1],loc=np.log(.2),scale=.5)+mass
    log_deta_dl=np.logaddexp(0.,-eta)
    direct=target(q,np.zeros(n),cap)[0]+log_dl_dw+log_deta_dl
    independent=norm.logpdf(core).sum()+likelihood(core,np.zeros(n),cap)
    np.testing.assert_allclose(direct,independent,rtol=1e-12,atol=1e-10)

def test_transition_ownership_and_finite_stress():
    core=np.r_[-3.,3.,.1,np.full(12,-10.)];before=core.copy()
    value=likelihood(core,np.zeros(12),2.)
    assert np.isfinite(value)
    state,calls=transition(core,np.zeros(12),2.,np.random.default_rng(42))
    assert np.isfinite(state).all() and calls>=4
    np.testing.assert_array_equal(core,before)
