import csv,sys
from pathlib import Path
import numpy as np
OLD=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029')
sys.path.insert(0,str(OLD/'source'))
from backend import Backend

class Population:
 def __init__(self,kind,tol=1e-10,solver=0):
  self.linear=kind=='linear';self.d=3 if self.linear else 4;self.backends=[];self.weights=[];self.holdout=[]
  rows=list(csv.DictReader((OLD/'source_data/Theoph.csv').open()))
  self.mu=np.array([0,np.log(.1),np.log(.5)] if self.linear else [0,np.log(5),np.log(.15),np.log(.5)])
  self.sd=np.array([1.2,1.2,.7] if self.linear else [1.2,1.5,1.5,.7])
  for subject in range(1,13):
   rr=sorted([r for r in rows if int(r['Subject'])==subject],key=lambda r:float(r['Time']));assert len(rr)==11 and float(rr[0]['Time'])==0
   post=rr[1:];train=post[:-2];weight=float(rr[0]['Wt']);self.weights.append(weight);self.holdout.append([float(r['conc']) for r in post[-2:]])
   data=dict(P=self.d+1,N=8,times=[float(r['Time']) for r in train],concentration=[float(r['conc']) for r in train],Npred=10,pred_times=[float(r['Time']) for r in post],dose=weight*float(rr[0]['Dose']),fixed_v=1.,c0=float(rr[0]['conc']),infer_v=1,linear=int(self.linear),half_cauchy=0,prior_mean=[0.]*(self.d+1),prior_sd=[1e6]*(self.d+1),tol=tol,solver=solver)
   self.backends.append(Backend(data))
  self.weights=np.array(self.weights);self.holdout=np.array(self.holdout);self.dim=14*self.d+1
 def unpack(self,x):
  d=self.d;mu=x[:d];lt=x[d:2*d];z=x[2*d:-1].reshape(12,d);tau=np.exp(lt);q=mu+tau*z
  q[:,-1]+=np.log(self.weights)
  if not self.linear:q[:,2]+=np.log(self.weights)
  return mu,lt,z,tau,np.column_stack([q,np.full(12,x[-1])])
 def start(self):return np.r_[self.mu,np.full(self.d,np.log(.3)),np.zeros(12*self.d),np.log(.2)]
 def value(self,x):
  mu,lt,z,tau,q=self.unpack(x);g=np.zeros_like(q);lp=0.
  for i,b in enumerate(self.backends):
   v,gg=b.value(q[i]);lp+=v+.5*np.sum(q[i]**2)/1e12;g[i]=gg+q[i]/1e12
  lp+=-.5*np.sum(((mu-self.mu)/self.sd)**2)-.5*np.sum(z*z)-.5*np.sum((tau/.5)**2)+np.sum(lt)-.5*((x[-1]-np.log(.2))/.7)**2
  grad=np.r_[g[:,:-1].sum(0)-(mu-self.mu)/self.sd**2,(g[:,:-1]*tau*z).sum(0)+1-(tau/.5)**2,(g[:,:-1]*tau-z).ravel(),g[:,-1].sum()-(x[-1]-np.log(.2))/.7**2]
  if not np.isfinite(lp) or not np.isfinite(grad).all():raise ValueError('nonfinite population density')
  return float(lp),grad
 def predict(self,x):return np.array([b.predict(q) for b,q in zip(self.backends,self.unpack(x)[-1])])
 def close(self):
  for b in self.backends:b.close()
