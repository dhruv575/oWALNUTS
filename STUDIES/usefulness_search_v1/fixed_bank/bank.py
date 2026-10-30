"""Research-only fixed Student-mixture independence MH."""
import numpy as np
from scipy.special import gammaln,logsumexp

class FixedBank:
 def __init__(self,centers,factors,weights,df=5.):
  self.centers=np.array(centers,dtype=float,copy=True);self.L=np.array(factors,dtype=float,copy=True);w=np.array(weights,dtype=float,copy=True)
  if self.centers.ndim!=2 or min(self.centers.shape)<1:raise ValueError('Nonempty centers required')
  self.k,self.d=self.centers.shape
  if self.L.shape!=(self.k,self.d,self.d) or w.shape!=(self.k,):raise ValueError('Incompatible bank shapes')
  if not all(np.isfinite(v).all() for v in [self.centers,self.L,w]) or np.any(w<=0) or not np.isfinite(df) or df<=0:raise ValueError('Finite positive weights and df required')
  sign,ld=np.linalg.slogdet(self.L)
  if np.any(sign==0):raise ValueError('Singular proposal factor')
  self.inv=np.linalg.inv(self.L);self.df=float(df);self.weights=w/w.sum()
  self.norm=np.log(self.weights)+gammaln((df+self.d)/2)-gammaln(df/2)-self.d/2*np.log(df*np.pi)-ld
  if not np.isfinite(self.inv).all() or not np.isfinite(self.norm).all():raise ValueError('Unrepresentable proposal')
  for v in [self.centers,self.L,self.inv,self.weights,self.norm]:v.setflags(write=False)
 def logq(self,y):
  z=np.einsum('kij,kj->ki',self.inv,np.asarray(y)-self.centers)
  return float(logsumexp(self.norm-(self.df+self.d)/2*np.log1p(np.sum(z*z,axis=1)/self.df)))
 def propose(self,rng):
  j=int(rng.choice(self.k,p=self.weights));return self.centers[j]+self.L[j]@rng.normal(size=self.d)/np.sqrt(rng.chisquare(self.df)/self.df)
 def sweep(self,positions,log_density,rng):
  x=np.array(positions,dtype=float,copy=True)
  if x.ndim!=2 or x.shape[1]!=self.d or not np.isfinite(x).all():raise ValueError('Invalid current positions')
  lp=np.array([log_density(q) for q in x]);calls=len(x)
  if not np.isfinite(lp).all():raise ValueError('Invalid current density')
  accepted=[];invalid=0
  for i in range(len(x)):
   y=self.propose(rng)
   if not np.isfinite(y).all():invalid+=1;accepted.append(False);continue
   proposed=float(log_density(y));calls+=1
   if not np.isfinite(proposed):invalid+=1;accepted.append(False);continue
   ratio=proposed-lp[i]+self.logq(x[i])-self.logq(y)
   if np.isnan(ratio):raise ValueError('Invalid Hastings ratio')
   accept=np.log(rng.random())<min(0.,ratio);accepted.append(bool(accept))
   if accept:x[i]=y
  return x,dict(accepted=accepted,invalid=invalid,target_calls=calls)
