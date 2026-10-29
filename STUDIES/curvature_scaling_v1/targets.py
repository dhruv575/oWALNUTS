"""Independent curved pairs; unit-Jacobian exact Gaussian coordinates."""
import numpy as np
from scipy.special import ndtr
from numba import njit

CASES=[(d,b) for d in (8,24) for b in (.5,2.,5.)]

@njit(cache=False,error_model='numpy')
def core(q,kind,precision):
    b=precision[0,0];z=q.copy();g=-q.copy()
    for i in range(0,len(q),2):
        z[i+1]=q[i+1]-b*(q[i]*q[i]-1)
        g[i]=-q[i]+2*b*q[i]*z[i+1];g[i+1]=-z[i+1]
    return -.5*np.dot(z,z),g

class Target:
    def __init__(self,dim,curvature):
        self.dim=int(dim);self.b=float(curvature);self.kind=0
        self.precision=np.array([[self.b]])
    def forward(self,z):
        q=np.array(z,copy=True);q[...,1::2]+=self.b*(q[...,::2]**2-1);return q
    def inverse(self,q):
        z=np.array(q,copy=True);z[...,1::2]-=self.b*(z[...,::2]**2-1);return z
    def initial(self):
        z=.5*np.sin(np.arange(1,5)[:,None]*np.arange(1,self.dim+1)[None,:])
        return self.forward(z)
    def iid(self,n,seed):return self.forward(np.random.default_rng(seed).normal(size=(n,self.dim)))
    def features(self,q):
        u=ndtr(self.inverse(q));a=u[:,::2];b=u[:,1::2]
        return np.column_stack([u,(u[:,:3]<.05).astype(float),(u[:,:3]>.95).astype(float),((a<.5)&(b<.5)).astype(float),(a-.5)*(b-.5)])
    def truth(self):return np.r_[np.full(self.dim,.5),np.full(6,.05),np.full(self.dim//2,.25),np.zeros(self.dim//2)]
    def tolerance(self):return np.r_[np.full(self.dim,.015),np.full(6,.01),np.full(self.dim//2,.02),np.full(self.dim//2,.005)]
