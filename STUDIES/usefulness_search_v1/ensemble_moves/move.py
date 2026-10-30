"""Research-only sequential MH sweep; fixed Student proposal scales."""
import numpy as np
from scipy.special import gammaln,logsumexp

class EnsembleMove:
 def __init__(self,factors,df=5.):
  L=np.array(factors,dtype=float,copy=True)
  if L.ndim!=3 or L.shape[0]<2 or L.shape[1]!=L.shape[2] or not np.isfinite(L).all():raise ValueError('Expected C>=2 finite square factors')
  if not np.isfinite(df) or df<=0:raise ValueError('Positive finite degrees of freedom required')
  sign,logdet=np.linalg.slogdet(L)
  if np.any(sign==0):raise ValueError('Proposal factors must be nonsingular')
  self.L=L;self.inv=np.linalg.inv(L);self.C,self.d=L.shape[:2];self.df=float(df)
  self.norm=gammaln((df+self.d)/2)-gammaln(df/2)-self.d/2*np.log(df*np.pi)-logdet
  self.L.setflags(write=False);self.inv.setflags(write=False);self.norm.setflags(write=False)
 def logq(self,y,positions,excluded):
  indices=np.arange(self.C)!=excluded
  z=np.einsum('cij,cj->ci',self.inv[indices],np.asarray(y)-positions[indices])
  components=self.norm[indices]-(self.df+self.d)/2*np.log1p(np.sum(z*z,axis=1)/self.df)
  return float(logsumexp(components)-np.log(self.C-1))
 def sweep(self,positions,log_density,rng):
  x=np.array(positions,dtype=float,copy=True)
  if x.shape!=(self.C,self.d) or not np.isfinite(x).all():raise ValueError('Invalid current ensemble')
  lp=np.array([log_density(q) for q in x],dtype=float)
  if not np.isfinite(lp).all():raise ValueError('Current density must be finite')
  accepted=np.zeros(self.C,dtype=bool);invalid=0
  for i in rng.permutation(self.C):
   choices=np.delete(np.arange(self.C),i);j=int(rng.choice(choices))
   y=x[j]+self.L[j]@rng.normal(size=self.d)/np.sqrt(rng.chisquare(self.df)/self.df)
   proposed=float(log_density(y))
   if not np.isfinite(proposed):invalid+=1;continue
   ratio=proposed-lp[i]+self.logq(x[i],x,i)-self.logq(y,x,i)
   if np.isnan(ratio):raise ValueError('Invalid Hastings ratio')
   if np.log(rng.random())<min(0.,ratio):x[i]=y;lp[i]=proposed;accepted[i]=True
  return x,dict(accepted=accepted.tolist(),invalid=invalid,target_calls=2*self.C)
