import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest
from scipy.integrate import quad
from scipy.stats import norm
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'sv_prototype'))
from target import Target,Priors
from hybrid import augmented_log_density,beta_conditional,sweep,elliptical
P=Priors(-4.,1.,-2.,.5,.2,.1)

def model(observed=(True,)):
 n=len(observed)
 return Target(np.linspace(.01,.03,n),np.ones((n,1)),np.ones((n,1))*.2,list(observed),rho=.7,nu=5.,priors=P)

def test_augmented_integral_equals_normalized_student_marginal():
 m=model();q=np.array([-4.,-2.,.01,.03,.2]);base=m.value_gradient(q)[0]
 integral,error=quad(lambda l:np.exp(augmented_log_density(m,q,np.array([l]))-base),0,np.inf,epsabs=1e-10)
 assert abs(integral-1)<1e-9

def test_gaussian_conditional_density_ratios_and_precision():
 m=model((True,False,True));q=np.array([-4.,-2.,.01,.03,.2,-.1,.3]);lam=np.array([.8,1.,1.2])
 mean,L=beta_conditional(m,q,lam);h=m.path(q);d=lam[m.observed]*np.exp(-h[m.observed])
 np.testing.assert_allclose(L@L.T,[[1/P.beta_sd**2+d.sum()]])
 a=q.copy();b=q.copy();a[2]=-.05;b[2]=.1
 expected=norm.logpdf(a[2],mean[0],1/L[0,0])-norm.logpdf(b[2],mean[0],1/L[0,0])
 np.testing.assert_allclose(augmented_log_density(m,a,lam)-augmented_log_density(m,b,lam),expected,atol=1e-12)

def test_missing_state_kept_and_one_sweep_is_finite_no_input_mutation():
 m=model((True,False,True));q=np.array([-4.,-2.,.01,.03,.2,-.1,.3]);before=q.copy()
 moved=q.copy();moved[m.offset+1]+=1
 assert m.path(moved)[2]!=m.path(q)[2]
 result,lam=sweep(m,q,np.random.default_rng(907))
 assert result.shape==q.shape and np.isfinite(result).all() and lam[1]==1
 np.testing.assert_array_equal(q,before)

def test_numerical_failure_never_returns_unaccepted_state():
 with pytest.raises(FloatingPointError):
  elliptical(np.zeros(2),lambda z:float('nan'),np.random.default_rng(908))
 m=model();q=np.array([-4.,1000.,.01,.03,.2])
 with pytest.raises((OverflowError,FloatingPointError)):
  augmented_log_density(m,q,[1.])

def test_exact_gaussian_stationarity_controls():
 from hybrid import scalar_slice
 # Gaussian prior N(0,I), Gaussian likelihood centered at [1,-1], sd .5:
 # posterior mean [.8,-.8], variance .2. Use independent initialized posterior
 # states, one transition each: detects invariant-kernel bugs without burn-in.
 rng=np.random.default_rng(92011);out=[];scalar=[]
 for _ in range(4000):
  z=rng.normal([.8,-.8],np.sqrt(.2))
  out.append(elliptical(z,lambda x:-.5*np.sum((x-np.array([1.,-1.]))**2)/.25,rng))
  x=rng.normal(1.3,.7)
  scalar.append(scalar_slice(x,lambda a:-.5*((a-1.3)/.7)**2,rng,width=.8))
 out=np.asarray(out);scalar=np.asarray(scalar)
 np.testing.assert_allclose(out.mean(axis=0),[.8,-.8],atol=.035)
 np.testing.assert_allclose(out.var(axis=0),[.2,.2],atol=.025)
 assert abs(scalar.mean()-1.3)<.045
 assert abs(scalar.var()-.49)<.05


def test_evaluation_budget_counts_rejections_and_aborts_without_mutation():
 from hybrid import EvaluationBudget
 m=model((True,False,True));q=np.array([-4.,-2.,.01,.03,.2,-.1,.3]);original=q.copy()
 budget=EvaluationBudget(1)
 with pytest.raises(RuntimeError,match='total evaluation cap'):
  sweep(m,q,np.random.default_rng(92012),budget=budget)
 assert sum(budget.calls.values())==1 and budget.exhausted
 np.testing.assert_array_equal(q,original)
 budget=EvaluationBudget(10000)
 sweep(m,q,np.random.default_rng(92013),budget=budget)
 assert budget.calls['ess']>=2
 assert all(budget.calls['scalar_'+str(j)]>=2 for j in (0,1,3))
