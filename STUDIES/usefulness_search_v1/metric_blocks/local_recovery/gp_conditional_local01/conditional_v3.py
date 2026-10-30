import json
import numpy as np
from scipy.special import gammaln,logsumexp
from common import MODELS,NAME,Target
data=json.loads((MODELS/(NAME+'.data.json')).read_text());X=np.array(data['x']);K=np.array(data['k']);D=len(X);DIST=(X[:,None]-X[None,:])**2
COUNTS=dict(solves=0,objective=0,iterations=0,factor_backend_calls=0)
FACTOR_BACKEND=Target()
LO=np.log([.5,.1]);HI=np.log([20.,10.]);WIDTH=(HI-LO)/41;AREA=float(np.prod(WIDTH))
def prior(h):
 rho,alpha=np.exp(h)
 return float(25*np.log(4)-gammaln(25)+25*h[0]-4*rho+np.log(np.sqrt(2/np.pi)/2)+h[1]-alpha*alpha/8)
def kernel(h):
 q=np.r_[h,np.zeros(D)];columns=[]
 for j in range(D):
  q[2+j]=1.;a=FACTOR_BACKEND.model.param_constrain(q,include_tp=True,include_gq=False);columns.append(np.asarray(a)[FACTOR_BACKEND.indices[2:]]);q[2+j]=0.;COUNTS['factor_backend_calls']+=1
 L=np.column_stack(columns);assert np.all(np.diag(L)>0) and np.max(np.abs(np.triu(L,1)))<1e-12
 return L
def objective(z,L):
 COUNTS['objective']+=1;f=L@z
 with np.errstate(over='ignore'):rate=np.exp(f)
 return float(K@f-rate.sum()-.5*z@z),rate
def solve(h):
 COUNTS['solves']+=1;L=kernel(h);z=np.zeros(D)
 for iteration in range(100):
  COUNTS['iterations']+=1;v,rate=objective(z,L);g=L.T@(K-rate)-z;H=np.eye(D)+(L.T*rate)@L
  if np.max(np.abs(g))<1e-7:return z,np.linalg.cholesky(H),L,v
  step=np.linalg.solve(H,g);slope=float(g@step);scale=1.
  for _ in range(40):
   candidate=z+scale*step;dz=scale*step;df=L@dz;COUNTS['objective']+=1
   with np.errstate(over='ignore'):remainder=np.expm1(df)-df
   small=np.abs(df)<1e-5;vsmall=df[small];remainder[small]=vsmall*vsmall*(.5+vsmall*(1/6+vsmall/24))
   difference=float(g@dz-.5*dz@dz-rate@remainder)
   if np.isfinite(difference) and difference>=1e-4*scale*slope:z=candidate;break
   scale*=.5
  else:raise RuntimeError('Conditional line search failed')
 raise RuntimeError('Conditional Newton did not converge')
def conditional_logq(z,mode,C):
 delta=C.T@(z-mode);r=float(delta@delta);ld=float(np.log(np.diag(C)).sum())
 normal=ld-D/2*np.log(2*np.pi)-r/2
 student=ld-D*np.log(1.5)+gammaln((5+D)/2)-gammaln(2.5)-D/2*np.log(5*np.pi)-(5+D)/2*np.log1p(r/(2.25*5))
 return float(np.logaddexp(np.log(.9)+normal,np.log(.1)+student))
def hyper_logq(h,prob):
 idx=np.floor((h-LO)/WIDTH).astype(int);grid=-np.inf
 if np.all(idx>=0) and np.all(idx<41):grid=np.log(.95)+np.log(prob[idx[0],idx[1]])-np.log(AREA)
 return float(np.logaddexp(grid,np.log(.05)+prior(h)))
def propose(rng,prob):
 if rng.random()<.95:
  i,j=np.unravel_index(rng.choice(41*41,p=prob.ravel()),(41,41));h=LO+(np.array([i,j])+rng.random(2))*WIDTH
 else:h=np.log([rng.gamma(25,1/4),abs(rng.normal(scale=2))])
 mode,C,L,v=solve(h);e=rng.normal(size=D)
 if rng.random()<.1:e*=1.5/np.sqrt(rng.chisquare(5)/5)
 z=mode+np.linalg.solve(C.T,e);q=np.r_[h,z];lq=hyper_logq(h,prob)+conditional_logq(z,mode,C)
 return q,lq
