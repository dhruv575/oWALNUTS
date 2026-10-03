"""Fixed prior-Fisher path whitening for the hierarchical flow target.

Mass convention: momentum covariance M=K=L L', where K is approximate POSITION
PRECISION. q_path=mu_ref+a*(q_mu-mu_ref)+L'^-1 u_path. The optional fixed shear
a=K^-1 Q_AR 1 cancels the local mean/path cross Hessian. Nothing here reads truth,
held-out observations, or observed y values. Construction is fixed before fitting.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import numpy as np


def tridiagonal_cholesky(diagonal, off_diagonal):
    """O(T) lower-bidiagonal Cholesky; fails on invalid/non-SPD input."""
    d, off = np.asarray(diagonal,float), np.asarray(off_diagonal,float)
    if d.ndim != 1 or len(d) == 0 or off.shape != (len(d)-1,) or not np.isfinite(d).all() or not np.isfinite(off).all():
        raise ValueError('Invalid finite tridiagonal arrays')
    lower = np.empty_like(d); sub = np.empty_like(off)
    pivot = d[0]
    for i in range(len(d)):
        if i:
            sub[i-1] = off[i-1]/lower[i-1]
            pivot = d[i]-sub[i-1]**2
        if not np.isfinite(pivot) or pivot <= 0:
            raise ValueError('Path precision is not numerically positive definite')
        lower[i] = np.sqrt(pivot)
    return lower, sub


def solve_lower(rhs, diagonal, subdiagonal, xp=np):
    """L^-1 rhs over the last axis, O(T); JAX uses an associative affine scan."""
    rhs = xp.asarray(rhs); d = xp.asarray(diagonal); b = xp.asarray(subdiagonal)
    if rhs.ndim < 1 or rhs.shape[-1] != d.shape[0]:
        raise ValueError('Triangular solve dimension mismatch')
    if xp is np:
        out = np.empty_like(rhs,dtype=float)
        out[...,0] = rhs[...,0]/d[0]
        for i in range(1,len(d)):
            out[...,i] = (rhs[...,i]-b[i-1]*out[...,i-1])/d[i]
        return out
    # x_i=A_i*x_(i-1)+B_i. Composition (A2*A1, A2*B1+B2)
    # is associative, giving logarithmic depth rather than a sequential scan.
    from jax import lax
    aa = xp.concatenate((xp.zeros_like(d[:1]),-b/d[1:]))
    aa = xp.broadcast_to(aa,rhs.shape)
    bb = rhs/d
    aa,bb = xp.moveaxis(aa,-1,0),xp.moveaxis(bb,-1,0)
    def compose(left,right):
        a1,b1 = left; a2,b2 = right
        return a2*a1,a2*b1+b2
    _,out = lax.associative_scan(compose,(aa,bb),axis=0)
    return xp.moveaxis(out,0,-1)


def solve_upper(rhs, diagonal, subdiagonal, xp=np):
    """L'^-1 rhs using the reversed lower-bidiagonal problem."""
    return solve_lower(xp.asarray(rhs)[...,::-1],xp.asarray(diagonal)[::-1],
                       xp.asarray(subdiagonal)[::-1],xp)[...,::-1]


def multiply_upper(value, diagonal, subdiagonal, xp=np):
    value = xp.asarray(value); d=xp.asarray(diagonal); b=xp.asarray(subdiagonal)
    return value*d+xp.concatenate((value[...,1:]*b,xp.zeros_like(value[...,:1])),axis=-1)


@dataclass(frozen=True)
class FixedGeometry:
    global_dimension: int
    prior_diagonal: np.ndarray
    prior_off_diagonal: np.ndarray
    precision_diagonal: np.ndarray
    lower_diagonal: np.ndarray
    lower_subdiagonal: np.ndarray
    shear: np.ndarray
    mu_reference: float = -1.
    sigma_reference: float = math.exp(-1.5)

    @classmethod
    def from_data(cls,data,mean_shear=False):
        """Use only T,G,rho,nu and fixed prior medians; never inspect y values."""
        shape = np.shape(data['y'])
        if len(shape) != 2 or min(shape) < 1:
            raise ValueError('Require nonempty rectangular T by G data shape')
        t,g = shape; rho=float(data['rho']); nu=float(data['nu'])
        if not np.isfinite([rho,nu]).all() or abs(rho)>=1 or nu<=2:
            raise ValueError('Require finite abs(rho)<1, nu>2')
        sigma=math.exp(-1.5); inv=1/sigma**2
        prior=np.full(t,(1+rho*rho)*inv)
        if t==1:prior[0]=(1-rho*rho)*inv
        else:prior[0]=prior[-1]=inv
        off=np.full(t-1,-rho*inv)
        precision=prior+g*nu/(2*(nu+3))
        lower,sub=tridiagonal_cholesky(precision,off)
        qones=prior.copy()
        qones[:-1]+=off; qones[1:]+=off
        shear=solve_upper(solve_lower(qones,lower,sub),lower,sub) if mean_shear else np.zeros(t)
        arrays=[prior,off,precision,lower,sub,shear]
        for array in arrays:array.setflags(write=False)
        return cls(4+2*g,*arrays)

    @property
    def dimension(self):
        return self.global_dimension+len(self.lower_diagonal)

    @property
    def log_abs_det_jacobian(self):
        """log|dq/du|; the fixed shear has unit block-triangular determinant."""
        return -float(np.log(self.lower_diagonal).sum())

    def _check(self,value):
        if value.ndim < 1 or value.shape[-1]!=self.dimension:
            raise ValueError('Position/gradient dimension mismatch')

    def to_canonical(self,u,xp=np):
        u=xp.asarray(u);self._check(u);k=self.global_dimension
        path=self.mu_reference+xp.asarray(self.shear)*(u[...,2:3]-self.mu_reference)
        path=path+solve_upper(u[...,k:],self.lower_diagonal,self.lower_subdiagonal,xp)
        return xp.concatenate((u[...,:k],path),axis=-1)

    def to_transformed(self,q,xp=np):
        q=xp.asarray(q);self._check(q);k=self.global_dimension
        path=q[...,k:]-self.mu_reference-xp.asarray(self.shear)*(q[...,2:3]-self.mu_reference)
        u=multiply_upper(path,self.lower_diagonal,self.lower_subdiagonal,xp)
        return xp.concatenate((q[...,:k],u),axis=-1)

    def pullback_gradient(self,canonical_gradient,xp=np):
        """J' grad_q; includes a' grad_h in the unchanged global mu coordinate."""
        gradient=xp.asarray(canonical_gradient);self._check(gradient);k=self.global_dimension
        mu=gradient[...,2:3]+xp.sum(gradient[...,k:]*xp.asarray(self.shear),axis=-1,keepdims=True)
        globals_=xp.concatenate((gradient[...,:2],mu,gradient[...,3:k]),axis=-1)
        path=solve_lower(gradient[...,k:],self.lower_diagonal,self.lower_subdiagonal,xp)
        return xp.concatenate((globals_,path),axis=-1)

    def metadata(self):
        return {'kind':'fixed_prior_fisher_mean_shear' if np.any(self.shear) else 'fixed_prior_fisher',
                'sigma_reference':self.sigma_reference,'mu_reference':self.mu_reference,
                'global_dimension':self.global_dimension,'path_dimension':len(self.shear),
                'log_abs_det_jacobian':self.log_abs_det_jacobian,
                'uses_observed_values':False,'uses_truth':False}


def transformed_log_density(u,data,geometry,xp=np,gamma=None):
    from model import log_density
    if gamma is None:
        if xp is np:
            from scipy.special import gammaln as gamma
        else:
            from jax.scipy.special import gammaln as gamma
    return log_density(geometry.to_canonical(u,xp),data,xp,gamma)+geometry.log_abs_det_jacobian
