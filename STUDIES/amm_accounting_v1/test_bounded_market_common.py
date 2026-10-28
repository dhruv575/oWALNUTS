import numpy as np
import pytest
from bounded_market_common import cell,physical_draws,differences

@pytest.mark.parametrize('n',[1,12,250])
def test_physical_reconstruction(n):
    s=np.zeros((2,3,n+3));s[:,:,0]=-10;s[:,:,1]=1.3;s[:,:,2]=.2
    s[:,:,3:]=np.linspace(-.7,.4,n);original=s.copy()
    values,joint=physical_draws(s,1.)
    sigma=np.exp(-np.logaddexp(0.,1.3));h=[-10+sigma*s[0,0,3]/np.sqrt(1-.95**2)]
    for z in s[0,0,4:]:h.append(-10+.95*(h[-1]+10)+sigma*z)
    np.testing.assert_allclose(joint[:,:,3],h[-1],rtol=1e-13)
    np.testing.assert_allclose(values['beta'],np.exp(np.mean(h)/2)*.2,rtol=1e-13)
    np.testing.assert_array_equal(s,original)

def test_complete_schedule_and_decomposition():
    rows=[cell(i) for i in range(72)]
    assert sorted(set(r[0] for r in rows))==list(range(24))
    assert all([r[1] for r in rows[3*i:3*i+3]]==[.5,1.,2.] for i in range(24))
    assert len({seed+offset for _,_,seed in rows for offset in [0,1,4]})==216
    assert differences(1.2,.9,1.)==dict(model=1.2-1.,inference=.9-1.2,total=.9-1.)
    for invalid in [-1,72,True]:
        with pytest.raises(ValueError):cell(invalid)
