import csv
import numpy as np
from model import OLD

def data():
 rows=list(csv.DictReader((OLD/'source_data/Theoph.csv').open()));weights=[];doses=[];c0=[];times=[];observed=[]
 for subject in range(1,13):
  rr=sorted([r for r in rows if int(r['Subject'])==subject],key=lambda r:float(r['Time']))
  weights.append(float(rr[0]['Wt']));doses.append(weights[-1]*float(rr[0]['Dose']));c0.append(float(rr[0]['conc']));times.append([float(r['Time']) for r in rr[-2:]]);observed.append([float(r['conc']) for r in rr[-2:]])
 return [np.array(v) for v in [weights,doses,c0,times,observed]]

def prediction(q):
 weights,doses,c0,times,_=data();phys=q[...,:3,None]+np.exp(q[...,3:6,None])*np.moveaxis(q[...,6:-1].reshape(q.shape[:-1]+(12,3)),-1,-2);phys=np.moveaxis(phys,-1,-2)
 lka=phys[...,0,None];lke=phys[...,1,None];vol=phys[...,2,None]+np.log(weights[:,None]);ad=np.abs(lka-lke)
 with np.errstate(divide='ignore',over='ignore',invalid='raise'):
  logsep=np.log(-np.expm1(-ad));logd=np.maximum(lka,lke)+logsep+np.log(times)
  small=logd<np.log(1e-4);d=np.exp(np.minimum(logd,np.log(700.)))
  logphi=-d/2+d*d/24-d**4/2880+d**6/181440
  slow_decay=np.exp(np.minimum(lka,lke))*times
  near=np.log(doses[:,None])-vol+lka+np.log(times)-slow_decay+logphi
  # Mask the removable singularity before evaluating the separated expression.
  safe_sep=np.where(small,0.,logsep);safe_d=np.where(small,1.,d)
  far=np.log(doses[:,None])-vol+(lka-np.maximum(lka,lke))-safe_sep+np.log(-np.expm1(-safe_d))-slow_decay
  lb=np.where(small,near,far)
  logc0=np.full_like(c0,-np.inf);nz=c0>0;logc0[nz]=np.log(c0[nz]);la=logc0[:,None]-np.exp(lke)*times
 return np.logaddexp(la,lb).reshape(q.shape[:-1]+(24,))

def features(q):return np.concatenate([q,prediction(q),np.exp(q[...,-1:])],axis=-1)
