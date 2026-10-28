"""Bounded next-increment CDF, integrating the new Gaussian SV innovation.

This is a latent-increment functional, not an observed-price-cell forecast.
Gauss-Hermite order must be checked for each downstream use.
"""
import numpy as np
from scipy.special import roots_hermitenorm,stdtr


def conditional_cdf(threshold,mu,sigma,beta,last_h,*,rho=.95,order=64):
    if not np.isfinite(threshold) or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Finite threshold and stationary rho')
    if type(order)is not int or order<2 or order>256:raise ValueError('Quadrature order 2..256')
    mu,sigma,beta,last_h=np.broadcast_arrays(*[np.asarray(v,dtype=float) for v in (mu,sigma,beta,last_h)])
    if any(not np.isfinite(v).all() for v in (mu,sigma,beta,last_h)) or np.any(sigma<0):raise ValueError('Finite parameters and nonnegative sigma')
    nodes,weights=roots_hermitenorm(order)
    h=mu[...,None]+rho*(last_h-mu)[...,None]+sigma[...,None]*nodes
    with np.errstate(over='ignore',under='ignore',invalid='ignore'):
        standardized=(threshold-beta)[...,None]*np.exp(-.5*h)
    # Exact zero numerator has CDF .5 even at vanishing conditional scale.
    standardized=np.where((threshold-beta)[...,None]==0,0.,standardized)
    values=np.sum(stdtr(5,standardized)*weights,axis=-1)/np.sqrt(2*np.pi)
    if not np.isfinite(values).all():raise ValueError('Nonfinite predictive quadrature')
    return np.clip(values,0.,1.)


def last_volatility(draws):
    q=np.asarray(draws,dtype=float)
    if q.ndim<1 or q.shape[-1]<5 or (q.shape[-1]-3)%2 or not np.isfinite(q).all():raise ValueError('Full finite price-cell coordinates')
    n=(q.shape[-1]-3)//2;mu=q[...,0];sigma=np.exp(q[...,1])
    h=mu+sigma*q[...,3]/np.sqrt(1-.95**2)
    for i in range(1,n):h=mu+.95*(h-mu)+sigma*q[...,3+i]
    return h
