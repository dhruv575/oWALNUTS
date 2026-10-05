"""Specialist research Gibbs/ESS/slice comparator. Does not use oWALNUTS.

Finite numerical failures abort explicitly. Slice caps abort the run, rather than
returning an unaccepted point. Fixed slice widths; no retained adaptation.
"""
import math
import numpy as np
from scipy.special import gammaln


class EvaluationBudget:
    """Counts started density calls, including rejected slice/ellipse proposals."""
    def __init__(self, maximum=100000):
        if type(maximum) is not int or maximum < 1:raise ValueError('Positive evaluation cap required')
        self.maximum=maximum;self.calls={};self.exhausted=False

    def evaluate(self, kind, function, value):
        if sum(self.calls.values()) >= self.maximum:
            self.exhausted=True
            raise RuntimeError('Hybrid total evaluation cap exhausted')
        self.calls[kind]=self.calls.get(kind,0)+1
        return function(value)


def augmented_log_density(model,q,lam):
    """Normalized NC joint p(q,y_observed,lambda_observed)."""
    mu,ls,beta,gamma,z=model.unpack(q);pr=model.priors
    means=np.r_[pr.mu_mean,pr.log_sigma_mean,np.zeros(model.dimension-2)]
    sd=np.r_[pr.mu_sd,pr.log_sigma_sd,np.full(model.p,pr.beta_sd),np.full(model.k,pr.gamma_sd),np.ones(model.t)]
    lam=np.asarray(lam,dtype=float)
    if lam.shape!=(model.t,) or not np.isfinite(lam).all() or np.any(lam<=0):raise ValueError('Positive finite per-state lambda required')
    lp=float(np.sum(-.5*((q-means)/sd)**2-np.log(sd)-.5*np.log(2*np.pi)))
    h=model.path(q);obs=model.observed;r=model.y-model.x@beta;a=model.nu/2
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        v=lam[obs];hh=h[obs];rr=r[obs]
        lp+=float(np.sum(-.5*np.log(2*np.pi)-.5*hh+.5*np.log(v)-.5*v*rr**2*np.exp(-hh)))
        lp+=float(np.sum(a*np.log(a)-gammaln(a)+(a-1)*np.log(v)-a*v))
    if not math.isfinite(lp):raise FloatingPointError('Nonfinite augmented density')
    return lp


def sample_precisions(model,q,rng):
    h=model.path(q);beta=model.unpack(q)[2];obs=model.observed;r=model.y-model.x@beta
    lam=np.ones(model.t) # Missing positions have no auxiliary random variable.
    with np.errstate(over='raise',invalid='raise'):
        rate=(model.nu+r[obs]**2*np.exp(-h[obs]))/2
        lam[obs]=rng.gamma((model.nu+1)/2,1/rate)
    if not np.isfinite(lam).all() or np.any(lam<=0):raise FloatingPointError('Invalid gamma draw')
    return lam


def beta_conditional(model,q,lam):
    h=model.path(q);obs=model.observed;X=model.x[obs];y=model.y[obs]
    with np.errstate(over='raise',invalid='raise'):
        d=np.asarray(lam)[obs]*np.exp(-h[obs])
    precision=np.eye(model.p)/model.priors.beta_sd**2+X.T@(d[:,None]*X)
    L=np.linalg.cholesky(precision);mean=np.linalg.solve(L.T,np.linalg.solve(L,X.T@(d*y)))
    return mean,L


def elliptical(z,log_likelihood,rng,*,max_evaluations=10000):
    z=np.asarray(z);direction=rng.normal(size=z.shape);threshold=log_likelihood(z)+math.log(rng.uniform())
    angle=rng.uniform(0,2*np.pi);lo=angle-2*np.pi;hi=angle
    for _ in range(max_evaluations):
        proposal=z*np.cos(angle)+direction*np.sin(angle)
        value=log_likelihood(proposal)
        if not math.isfinite(value):raise FloatingPointError('Nonfinite ESS likelihood')
        if value>=threshold:return proposal
        if angle<0:lo=angle
        else:hi=angle
        angle=rng.uniform(lo,hi)
    raise RuntimeError('ESS evaluation cap exhausted')


def scalar_slice(value,log_density,rng,*,width,max_steps=1000):
    """Randomized finite stepping-out allocation and shrinkage; cap aborts."""
    threshold=log_density(value)+math.log(rng.uniform());lo=value-width*rng.uniform();hi=lo+width
    left=int(rng.integers(max_steps));right=max_steps-1-left
    while left and log_density(lo)>threshold:lo-=width;left-=1
    while right and log_density(hi)>threshold:hi+=width;right-=1
    for _ in range(max_steps):
        proposal=rng.uniform(lo,hi);lp=log_density(proposal)
        if not math.isfinite(lp):raise FloatingPointError('Nonfinite scalar slice density')
        if lp>=threshold:return proposal
        if proposal<value:lo=proposal
        else:hi=proposal
    raise RuntimeError('Slice shrinkage cap exhausted')


def sweep(model,q,rng,*,budget=None):
    """One invariant augmented Gibbs sweep; caller discards all work if it fails."""
    q=np.asarray(q,dtype=float).copy();model.unpack(q)
    budget=EvaluationBudget() if budget is None else budget
    lam=sample_precisions(model,q,rng)
    mean,L=beta_conditional(model,q,lam)
    q[2:2+model.p]=mean+np.linalg.solve(L.T,rng.normal(size=model.p))
    def likelihood(z):
        candidate=q.copy();candidate[model.offset:]=z
        # Remove the Gaussian z prior exactly; ESS supplies that prior.
        return augmented_log_density(model,candidate,lam)+.5*float(z@z)+len(z)/2*np.log(2*np.pi)
    q[model.offset:]=elliptical(q[model.offset:],lambda z:budget.evaluate('ess',likelihood,z),rng)
    indices=[0,1]+list(range(2+model.p,model.offset))
    widths=[model.priors.mu_sd,model.priors.log_sigma_sd]+[model.priors.gamma_sd]*model.k
    for j,width in zip(indices,widths):
        def density(value):
            candidate=q.copy();candidate[j]=value
            return augmented_log_density(model,candidate,lam)
        q[j]=scalar_slice(q[j],lambda value:budget.evaluate('scalar_'+str(j),density,value),rng,width=width)
    return q,lam
