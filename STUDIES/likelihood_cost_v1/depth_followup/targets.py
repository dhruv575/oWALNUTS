"""Actual dense Gaussian regression evaluated in curved posterior coordinates."""
import numpy as np
from numba import njit
from geometry import Target as Geometry

SIZES=[64,2048]

@njit(cache=False,error_model='numpy')
def core(q,kind,P):
    if kind==2:return -.5*np.dot(q,q),-q
    d=len(q);b=P[0,0];z=q.copy()
    for i in range(0,d,2):z[i+1]-=b*(q[i]*q[i]-1)
    if kind==1:lp=-.5*np.dot(z,z);gz=-z
    else:
        n=int(P[0,1]);L=P[1:d+1];mean=P[d+1];X=P[d+2:d+2+n];y=P[d+2+n:].ravel()[:n]
        theta=mean+L@z;residual=y-X@theta
        lp=-.5*np.dot(theta,theta)-.5*np.dot(residual,residual)-P[0,2]
        gz=L.T@(X.T@residual-theta)
    g=gz.copy()
    for i in range(0,d,2):g[i]-=2*b*q[i]*gz[i+1]
    return lp,g

class Target(Geometry):
    def __init__(self,n,kind=0,dim=24,curvature=5.):
        super().__init__(dim,curvature);self.n=int(n);self.kind=int(kind)
        rng=np.random.default_rng(755100000+n)
        X=rng.normal(size=(n,dim))/np.sqrt(n);beta=rng.normal(size=dim);y=X@beta+rng.normal(size=n)
        cov=np.linalg.inv(np.eye(dim)+X.T@X);L=np.linalg.cholesky(cov);mean=cov@(X.T@y)
        P=np.zeros((dim+2+n+(n+dim-1)//dim,dim));P[0,:3]=[curvature,n,-.5*np.dot(mean,mean)-.5*np.dot(y-X@mean,y-X@mean)]
        P[1:dim+1]=L;P[dim+1]=mean;P[dim+2:dim+2+n]=X;P[dim+2+n:].ravel()[:n]=y
        self.precision=P;self.X=X;self.y=y;self.mean=mean;self.L=L
    def initial(self):
        q=super().initial()
        return self.inverse(q) if self.kind==2 else q
