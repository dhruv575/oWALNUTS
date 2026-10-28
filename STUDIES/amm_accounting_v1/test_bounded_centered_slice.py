import numpy as np
import pytest
from scipy.stats import norm
from bounded_centered_slice import center,residual,transition
from bounded_rescaled_slice import likelihood

@pytest.mark.parametrize('n',[1,12,250])
@pytest.mark.parametrize('cap',[.5,1.,2.])
def test_exact_reference_change(n,cap):
    c=center(n,cap);q=.4*c+np.linspace(-.5,.5,n+3);y=np.zeros(n)
    expected=norm.logpdf(q).sum()+likelihood(q,y,cap)
    actual=norm.logpdf(q,loc=c).sum()+residual(q,y,cap)
    np.testing.assert_allclose(actual,expected,rtol=1e-12,atol=1e-9)
    # Independently construct the stationary-AR linear map and its mean weights.
    matrix=np.zeros((n,n));matrix[0,0]=1/np.sqrt(1-.95**2)
    for i in range(1,n):matrix[i]=.95*matrix[i-1];matrix[i,i]=1
    np.testing.assert_allclose(c[3:],-(n-1)/2*cap*matrix.mean(axis=0))

def test_transition_input_ownership():
    q=center(12,2.);original=q.copy()
    state,calls=transition(q,np.zeros(12),2.,np.random.default_rng(42))
    assert np.isfinite(state).all() and calls>=4
    np.testing.assert_array_equal(q,original)
