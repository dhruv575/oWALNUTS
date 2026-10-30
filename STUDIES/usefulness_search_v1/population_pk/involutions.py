"""Exact model-specific involutions; no claim that density is symmetric."""
import numpy as np
def global_exchange(x):
 y=np.array(x,dtype=float,copy=True);z=x[6:-1].reshape(12,3);zz=z.copy()
 y[0],y[1]=x[1],x[0];y[2]=x[2]+x[1]-x[0];y[3],y[4]=x[4],x[3]
 zz[:,0],zz[:,1]=z[:,1],z[:,0]
 zz[:,2]=z[:,2]+np.exp(x[4]-x[5])*z[:,1]-np.exp(x[3]-x[5])*z[:,0]
 y[6:-1]=zz.ravel();return y
def local_exchange(x,subject):
 y=np.array(x,dtype=float,copy=True);tau=np.exp(x[3:6]);start=6+3*subject
 q=x[:3]+tau*x[start:start+3];v=q.copy();v[0],v[1]=q[1],q[0];v[2]=q[2]+q[1]-q[0]
 y[start:start+3]=(v-x[:3])/tau;return y
def move(x,log_density,transform,rng):
 y=transform(x);old=float(log_density(x));new=float(log_density(y))
 if not np.isfinite(old):raise ValueError('Current density must be finite')
 # Every transformation supplied by this module has absolute determinant one.
 accepted=bool(np.isfinite(new) and np.log(rng.random())<min(0.,new-old))
 return (y if accepted else x.copy()),accepted,new-old
