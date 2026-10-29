"""Normalized generative targets with exact probability transforms."""
import numpy as np
from scipy.special import ndtr,ndtri
from scipy.stats import t as student
from numba import njit

NAMES=['isotropic','correlated','banana','funnel_moderate','funnel_severe','funnel_noncentered','changing_scale','student_t','mixture']
DIMENSIONS=[12,12,8,10,10,10,12,10,6]


@njit(cache=False,error_model='numpy')
def core(q,kind,precision):
    d=len(q);g=np.empty(d)
    if kind in (0,5):return -.5*np.dot(q,q),-q
    if kind==1:
        g=-precision@q
        return .5*np.dot(q,g),g
    if kind==2:
        z=q.copy();z[1]=q[1]-2*(q[0]*q[0]-1)
        g=-z;g[0]=-q[0]+4*q[0]*z[1]
        return -.5*np.dot(z,z),g
    if kind in (3,4,6):
        v=q[0];s=1.5 if kind==3 else 3.
        if kind==6:
            h=np.tanh(2*v);l=1.5*h;dl=3*(1-h*h);s=1.
        else:l=v/2;dl=.5
        ss=np.dot(q[1:],q[1:]);inv=np.exp(-2*l);scaled=ss*inv
        lp=-.5*(v/s)**2-.5*scaled-(d-1)*l
        g[0]=-v/(s*s)+(scaled-(d-1))*dl
        g[1:]=-q[1:]*inv
        return lp,g
    if kind==7:
        ss=np.dot(q,q);g=-(3+d)*q/(3+ss)
        return -.5*(3+d)*np.log1p(ss/3),g
    # Equal mixture N(-3,1)/N(+3,1) on q0; independent normal remainder.
    a=-.5*(q[0]-3)**2;b=-.5*(q[0]+3)**2
    lp=np.logaddexp(a,b)-np.log(2.)-.5*np.dot(q[1:],q[1:])
    g=-q;g[0]=-q[0]+3*np.tanh(3*q[0])
    return lp,g


class Target:
    def __init__(self,name):
        self.name=name;self.kind=NAMES.index(name);self.dim=DIMENSIONS[self.kind]
        self.cov=.95*np.ones((self.dim,self.dim))+.05*np.eye(self.dim)
        self.L=np.linalg.cholesky(self.cov);self.precision=np.linalg.inv(self.cov)
        self.calls=0;self.nonfinite=0
        core(np.zeros(self.dim),self.kind,self.precision)

    def __call__(self,q):
        self.calls+=1
        if self.calls>30000000:raise RuntimeError('Thirty-million target-call cap')
        lp,g=core(q,self.kind,self.precision)
        if not np.isfinite(lp) or not np.isfinite(g).all():
            self.nonfinite+=1
            raise FloatingPointError('Nonfinite target evaluation; fail closed')
        return float(lp),np.ascontiguousarray(g)

    def initial(self):
        q=.5*np.sin(np.arange(1,5)[:,None]*np.arange(1,self.dim+1)[None,:])
        if self.kind in (3,4):q[:,0]=[-3,-1,1,3]
        if self.kind==2:q[:,1]+=2*(q[:,0]**2-1)
        if self.kind==8:q[:,0]=[-3,-1,1,3]
        return q

    def iid(self,n,seed):
        rng=np.random.default_rng(seed);q=rng.normal(size=(n,self.dim))
        if self.kind==1:q=q@self.L.T
        elif self.kind==2:q[:,1]+=2*(q[:,0]**2-1)
        elif self.kind in (3,4):
            q[:,0]*=1.5 if self.kind==3 else 3.;q[:,1:]*=np.exp(q[:,0,None]/2)
        elif self.kind==6:q[:,1:]*=np.exp(1.5*np.tanh(2*q[:,0,None]))
        elif self.kind==7:q/=np.sqrt(rng.chisquare(3,n)[:,None]/3)
        elif self.kind==8:q[:,0]+=rng.choice([-3.,3.],n)
        return q

    def uniforms(self,q):
        z=np.array(q,copy=True)
        if self.kind==1:z=np.linalg.solve(self.L,z.T).T
        elif self.kind==2:z[:,1]-=2*(z[:,0]**2-1)
        elif self.kind in (3,4):
            z[:,1:]*=np.exp(-z[:,0,None]/2);z[:,0]/=1.5 if self.kind==3 else 3.
        elif self.kind==6:z[:,1:]*=np.exp(-1.5*np.tanh(2*z[:,0,None]))
        elif self.kind==7:
            # Multivariate t Rosenblatt transform: conditional df=3+i,
            # scale^2=(3+sum(previous squared coordinates))/(3+i).
            result=np.empty_like(z);ss=np.zeros(len(z))
            for i in range(self.dim):
                result[:,i]=student.cdf(z[:,i]/np.sqrt((3+ss)/(3+i)),df=3+i);ss+=z[:,i]**2
            return result
        u=ndtr(z)
        if self.kind==8:u[:,0]=.5*ndtr(z[:,0]-3)+.5*ndtr(z[:,0]+3)
        return u

    def features(self,q):
        u=self.uniforms(q)
        return np.column_stack([u,(u[:,:3]<.05).astype(float),(u[:,:3]>.95).astype(float),
            ((u[:,0]<.5)&(u[:,1]<.5)).astype(float),(u[:,0]-.5)*(u[:,1]-.5)])

    def truth(self):return np.r_[np.full(self.dim,.5),np.full(6,.05),.25,0.]
    def tolerance(self):return np.r_[np.full(self.dim,.015),np.full(6,.01),.02,.005]
