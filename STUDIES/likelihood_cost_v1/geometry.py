import numpy as np
from scipy.special import ndtr

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
