"""Exact blocked Gibbs for a robust AR latent-price + observed-flow regression.
New synthetic model, not the previous stochastic-volatility target.
"""
import numpy as np
from numba import njit

@njit
def filter_state(y,x,mask,beta,q,r,lam,rho):
 t=len(y);m=np.empty(t);p=np.empty(t);logp=0.;mean=0.;variance=q/(1-rho*rho)
 for i in range(t):
  if i:mean=rho*m[i-1];variance=rho*rho*p[i-1]+q
  if mask[i]:
   noise=r/lam[i];s=variance+noise;residual=y[i]-beta*x[i]-mean
   logp+=-.5*(np.log(2*np.pi*s)+residual*residual/s)
   gain=variance/s;mean+=gain*residual;variance*=noise/s
  m[i]=mean;p[i]=variance
 return m,p,logp

@njit
def ffbs(y,x,mask,beta,q,r,lam,rho):
 m,p,_=filter_state(y,x,mask,beta,q,r,lam,rho);t=len(y);h=np.empty(t);h[-1]=m[-1]+np.sqrt(p[-1])*np.random.normal()
 for i in range(t-2,-1,-1):
  predicted=rho*rho*p[i]+q;gain=p[i]*rho/predicted
  mean=m[i]+gain*(h[i+1]-rho*m[i]);variance=p[i]*q/predicted
  h[i]=mean+np.sqrt(variance)*np.random.normal()
 return h

@njit
def chain(y,x,mask,rho,seed,warmup,draws):
 np.random.seed(seed);t=len(y);beta=0.;q=.02;r=.09;lam=np.ones(t);result=np.empty((draws,t+3));nobs=np.sum(mask)
 for step in range(warmup+draws):
  h=ffbs(y,x,mask,beta,q,r,lam,rho)
  precision=4.;weighted=0.
  for i in range(t):
   if mask[i]:precision+=lam[i]*x[i]*x[i]/r;weighted+=lam[i]*x[i]*(y[i]-h[i])/r
  beta=weighted/precision+np.random.normal()/np.sqrt(precision)
  ss=(1-rho*rho)*h[0]*h[0]
  for i in range(1,t):ss+=(h[i]-rho*h[i-1])**2
  q=1/np.random.gamma(3.+t/2,1/(.04+.5*ss))
  ss=0.
  for i in range(t):
   if mask[i]:ss+=lam[i]*(y[i]-h[i]-beta*x[i])**2
  r=1/np.random.gamma(3.+nobs/2,1/(.18+.5*ss))
  for i in range(t):
   if mask[i]:lam[i]=np.random.gamma(3.,1/(2.5+.5*(y[i]-h[i]-beta*x[i])**2/r))
  if step>=warmup:
   result[step-warmup,0]=beta;result[step-warmup,1]=np.sqrt(q);result[step-warmup,2]=np.sqrt(r);result[step-warmup,3:]=h
 return result

def simulate(seed=29,t=512):
 rng=np.random.default_rng(seed);rho=.98;q=.12**2;r=.3**2;beta=.25;x=rng.normal(size=t);h=np.empty(t);h[0]=rng.normal(0,np.sqrt(q/(1-rho*rho)))
 for i in range(1,t):h[i]=rho*h[i-1]+rng.normal(0,np.sqrt(q))
 y=h+beta*x+.3*rng.standard_t(5,t);mask=rng.uniform(size=t)>.2
 return dict(y=y,x=x,mask=mask,rho=rho),dict(beta=beta,sigma_state=np.sqrt(q),sigma_obs=np.sqrt(r))

@njit
def seed_rng(seed):
 np.random.seed(seed)
