"""Development-only centered-path block ESS for the unchanged augmented target."""
from functools import lru_cache
import math
import numpy as np
from hybrid import EvaluationBudget,elliptical
from interwoven import admit,sweep_interwoven


@lru_cache(maxsize=128)
def geometry(n,rho,lo,hi):
    if not 0<=lo<hi<=n or not abs(rho)<1:raise ValueError('Block geometry')
    diagonal=np.full(n,1+rho*rho)
    if n==1:diagonal[0]=1-rho*rho
    else:diagonal[[0,-1]]=1.
    width=hi-lo
    q=np.diag(diagonal[lo:hi])
    if width>1:q+=np.diag(np.full(width-1,-rho),1)+np.diag(np.full(width-1,-rho),-1)
    lower=np.linalg.cholesky(q)
    transform=np.linalg.solve(lower.T,np.eye(width))
    left=np.zeros(width);right=np.zeros(width)
    if lo>0:left[0]=rho
    if hi<n:right[-1]=rho
    left=np.linalg.solve(q,left);right=np.linalg.solve(q,right)
    for a in (lower,transform,left,right):a.setflags(write=False)
    return lower,transform,left,right


def conditional(h,mu,sigma,rho,lo,hi):
    h=np.asarray(h,dtype=float)
    if h.ndim!=1 or not np.isfinite(h).all() or not np.isfinite(mu) or not np.isfinite(sigma) or sigma<=0:
        raise ValueError('Finite path and positive scale required')
    lower,transform,left,right=geometry(len(h),rho,lo,hi)
    mean=np.full(hi-lo,mu,dtype=float)
    if lo>0:mean+=left*(h[lo-1]-mu)
    if hi<len(h):mean+=right*(h[hi]-mu)
    return mean,lower,transform*sigma


def update_path(model,q,lam,rng,budget,block_size=16):
    admit(model)
    if type(block_size) is not int or block_size<1:raise ValueError('Positive block size')
    q=np.asarray(q,dtype=float).copy();h=model.path(q);sigma=math.exp(q[1])
    lam=np.asarray(lam,dtype=float)
    if lam.shape!=(model.t,) or not np.isfinite(lam).all() or np.any(lam<=0):raise ValueError('Precision values')
    residual=model.y-q[2]
    for lo in range(0,model.t,block_size):
        hi=min(lo+block_size,model.t);mean,lower,transform=conditional(h,q[0],sigma,model.rho,lo,hi)
        white=lower.T@(h[lo:hi]-mean)/sigma
        observed=model.observed[lo:hi]
        def likelihood(value):
            candidate=mean+transform@value
            with np.errstate(over='raise',invalid='raise'):
                result=float(np.sum(-.5*candidate[observed]-.5*lam[lo:hi][observed]*residual[lo:hi][observed]**2*np.exp(-candidate[observed])))
            if not math.isfinite(result):raise FloatingPointError('Nonfinite block likelihood')
            return result
        updated=elliptical(white,lambda value:budget.evaluate('centered_block_ess',likelihood,value),rng)
        h[lo:hi]=mean+transform@updated
    q[model.offset]=math.sqrt(1-model.rho**2)*(h[0]-q[0])/sigma
    q[model.offset+1:]=(h[1:]-q[0]-model.rho*(h[:-1]-q[0]))/sigma
    if not np.isfinite(q).all():raise FloatingPointError('Nonfinite mapped block update')
    return q


def sweep_blocked(model,q,rng,*,budget=None):
    budget=EvaluationBudget() if budget is None else budget
    q,lam=sweep_interwoven(model,q,rng,budget=budget)
    return update_path(model,q,lam,rng,budget),lam
