"""Normalized conditional importance proposal in the raw model coordinates.

NumPy's covariance factor is used only to construct a proposal. Exact compiled
Stan log density must supply every importance numerator. No density-equivalence
assumption is made between numerical covariance factorizations.
"""
import numpy as np
from scipy.special import gammaln,logsumexp
from scipy.linalg import solve_triangular,cho_solve

class ConditionalProposal:
    def __init__(self,data):
        self.x=np.asarray(data['x']);self.y=np.asarray(data['k']);self.d=len(self.x)
        assert self.d==data['N'] and self.y.shape==(self.d,)
        self.dist=(self.x[:,None]-self.x[None,:])**2
        self.lo=np.log([.5,.0001]);self.hi=np.log([20.,10.]);self.width=(self.hi-self.lo)/41
        self.area=float(np.prod(self.width));self.counts=dict(factors=0,solves=0,objectives=0,iterations=0)
    @staticmethod
    def prior(h):
        rho,alpha=np.exp(h)
        return float(25*np.log(4)-gammaln(25)+25*h[0]-4*rho+np.log(np.sqrt(2/np.pi)/2)+h[1]-alpha*alpha/8)
    def factor(self,h):
        rho,alpha=np.exp(h);self.counts['factors']+=1
        return np.linalg.cholesky(alpha**2*np.exp(-.5*self.dist/rho**2)+np.eye(self.d)*1e-10)
    def objective(self,z,L):
        self.counts['objectives']+=1;f=L@z
        with np.errstate(over='ignore'):rate=np.exp(f)
        return float(self.y@f-rate.sum()-.5*z@z),rate
    def solve(self,h):
        self.counts['solves']+=1;L=self.factor(h);z=np.zeros(self.d)
        for _ in range(100):
            self.counts['iterations']+=1;v,rate=self.objective(z,L);g=L.T@(self.y-rate)-z;H=np.eye(self.d)+(L.T*rate)@L;C=np.linalg.cholesky(H)
            if np.max(np.abs(g))<1e-7:return z,C,L,v
            step=cho_solve((C,True),g);slope=float(g@step);scale=1.
            for _ in range(40):
                dz=scale*step;df=L@dz;self.counts['objectives']+=1
                with np.errstate(over='ignore'):remainder=np.expm1(df)-df
                small=abs(df)<1e-5;t=df[small];remainder[small]=t*t*(.5+t*(1/6+t/24))
                delta=float(g@dz-.5*dz@dz-rate@remainder)
                if np.isfinite(delta) and delta>=1e-4*scale*slope:z+=dz;break
                scale*=.5
            else:raise RuntimeError('Conditional line search failed')
        raise RuntimeError('Conditional Newton did not converge')
    def conditional_logq(self,z,mode,C):
        delta=C.T@(z-mode);r=float(delta@delta);ld=float(np.log(np.diag(C)).sum());d=self.d
        normal=ld-d/2*np.log(2*np.pi)-r/2
        student=ld-d*np.log(1.5)+gammaln((5+d)/2)-gammaln(2.5)-d/2*np.log(5*np.pi)-(5+d)/2*np.log1p(r/(2.25*5))
        return float(np.logaddexp(np.log(.9)+normal,np.log(.1)+student))
    def grid(self):
        scores=np.empty((41,41))
        for i in range(41):
            for j in range(41):
                h=self.lo+(np.array([i,j])+.5)*self.width;_,C,_,v=self.solve(h);scores[i,j]=self.prior(h)+v-np.log(np.diag(C)).sum()
        prob=np.exp(scores-logsumexp(scores));assert np.isfinite(prob).all() and np.isclose(prob.sum(),1,atol=1e-12)
        return prob,scores
    def hyper_logq(self,h,prob):
        idx=np.floor((h-self.lo)/self.width).astype(int);grid=-np.inf
        if np.all(idx>=0) and np.all(idx<41):grid=np.log(.95)+np.log(prob[tuple(idx)])-np.log(self.area)
        return float(np.logaddexp(grid,np.log(.05)+self.prior(h)))
    def propose(self,rng,prob):
        if rng.random()<.95:
            i,j=np.unravel_index(rng.choice(41*41,p=prob.ravel()),(41,41));h=self.lo+(np.array([i,j])+rng.random(2))*self.width
        else:h=np.log([rng.gamma(25,1/4),abs(rng.normal(scale=2))])
        mode,C,_,_=self.solve(h);e=rng.normal(size=self.d)
        if rng.random()<.1:e*=1.5/np.sqrt(rng.chisquare(5)/5)
        z=mode+solve_triangular(C.T,e,lower=False)
        return np.r_[h,z],self.hyper_logq(h,prob)+self.conditional_logq(z,mode,C)
