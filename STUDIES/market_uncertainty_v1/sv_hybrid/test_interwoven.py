import math
from pathlib import Path
import sys
import numpy as np
from scipy.stats import norm
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'sv_prototype'))
from target import Target, Priors
from hybrid import EvaluationBudget
from interwoven import centered_mu_conditional, centered_scale_log_density, centered_update


def fixture(n=7):
    model = Target(np.linspace(-.003, .005, n), np.ones((n,1)), np.empty((n,0)), np.ones(n, dtype=bool), rho=.95, nu=5., priors=Priors(-10.,1.,-1.6,.5,.002,.03))
    q = np.r_[-10.2, -1.8, .0001, np.linspace(-1.,1.,n)]
    return model, q


def centered_joint(model, q, h, mu, ls):
    candidate = q.copy()
    candidate[:2] = mu, ls
    candidate[model.offset] = np.sqrt(1-model.rho**2)*(h[0]-mu)/np.exp(ls)
    candidate[model.offset+1:] = (h[1:]-mu-model.rho*(h[:-1]-mu))/np.exp(ls)
    # p(mu,ls,beta,h,y) = p(mu,ls,beta,z,y) * |dz/dh|.
    return model.value_gradient(candidate)[0]-model.t*ls+.5*np.log(1-model.rho**2)


@pytest.mark.parametrize('n',[1,7,250])
def test_conditionals_match_full_target_with_coordinate_jacobian(n):
    model,q = fixture(n)
    h = model.path(q)
    mean,sd = centered_mu_conditional(model,h,q[1])
    a,b = -10.1,-9.8
    np.testing.assert_allclose(centered_joint(model,q,h,a,q[1])-centered_joint(model,q,h,b,q[1]), norm.logpdf(a,mean,sd)-norm.logpdf(b,mean,sd), atol=2e-10)
    a,b = -1.9,-1.3
    np.testing.assert_allclose(centered_joint(model,q,h,q[0],a)-centered_joint(model,q,h,q[0],b), centered_scale_log_density(model,h,q[0],a)-centered_scale_log_density(model,h,q[0],b), atol=2e-10)


def test_remap_preserves_physical_path_and_does_not_mutate_input():
    model,q = fixture(250)
    before = q.copy()
    budget = EvaluationBudget(10000)
    updated = centered_update(model,q,np.random.default_rng(731),budget)
    np.testing.assert_array_equal(q,before)
    np.testing.assert_allclose(model.path(updated),model.path(q),atol=5e-14,rtol=0)
    assert updated[2] == q[2]
    assert budget.calls['centered_scale'] > 1


def test_exhaustion_returns_no_partial_state():
    model,q = fixture()
    before = q.copy()
    with pytest.raises(RuntimeError,match='evaluation cap'):
        centered_update(model,q,np.random.default_rng(732),EvaluationBudget(1))
    np.testing.assert_array_equal(q,before)
