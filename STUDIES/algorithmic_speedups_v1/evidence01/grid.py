"""Exact grid GP algebra with additive jitter and symmetric whitening.

The square-root derivative solves S dS + dS S = dK. In the product
eigenbasis, the rho derivative has two small families of dense blocks.
No eigenvector derivatives, eigenvalue clipping, or jitter approximation.
"""
import numpy as np
from scipy.linalg import eigh

JITTER = 1e-10

class GridGP:
    def __init__(self, data, dense=False):
        self.data=data; self.dense=dense; self.n=data['N']
        x=np.asarray(data['x']); self.x=np.unique(x[:,0]);self.y=np.unique(x[:,1])
        assert len(self.x)*len(self.y)==self.n
        expected=np.array([[a,b] for a in self.x for b in self.y])
        assert np.array_equal(x,expected), 'explicit grid order required'
        self.nx,self.ny=len(self.x),len(self.y)
        self.dx=(self.x[:,None]-self.x[None,:])**2
        self.dy=(self.y[:,None]-self.y[None,:])**2
        self.dist=((x[:,None,:]-x[None,:,:])**2).sum(2)
        self.design=np.asarray(data['design'])*np.asarray(data['coef_scale'])
        self.counts=np.asarray(data['y']);self.exposure=float(data['exposure'])
        self.factor_calls=0;self.likelihood_calls=0

    def factor(self,h):
        rho,alpha=np.exp(h)
        if not np.isfinite(rho+alpha) or rho<=0 or alpha<=0:raise ValueError('invalid hyperparameters')
        self.factor_calls+=1
        kx=np.exp(-.5*self.dx/rho**2);ky=np.exp(-.5*self.dy/rho**2)
        if self.dense:
            k=alpha**2*np.exp(-.5*self.dist/rho**2)+np.eye(self.n)*JITTER
            lam,q=eigh(k,check_finite=False)
            if np.min(lam)<=0:raise ValueError('nonpositive covariance eigenvalue')
            root=np.sqrt(lam)
            dk=alpha**2*np.exp(-.5*self.dist/rho**2)*self.dist/rho**2
            dr=(q.T@dk@q)/(root[:,None]+root[None,:])
            da=(lam-JITTER)/root
            return ('dense',q,root,dr,da)
        lx,ux=eigh(kx,check_finite=False);ly,uy=eigh(ky,check_finite=False)
        product=alpha**2*lx[:,None]*ly[None,:]
        lam=product+JITTER
        if np.min(lam)<=0:raise ValueError('nonpositive product covariance eigenvalue')
        root=np.sqrt(lam)
        bx=ux.T@(kx*self.dx/rho**2)@ux
        by=uy.T@(ky*self.dy/rho**2)@uy
        # Index order (x, x', y), and (x, y, y').
        drx=alpha**2*bx[:,:,None]*ly[None,None,:]/(root[:,None,:]+root[None,:,:])
        dry=alpha**2*lx[:,None,None]*by[None,:,:]/(root[:,:,None]+root[:,None,:])
        return ('grid',ux,uy,root,drx,dry,product/root)

    def apply(self,factor,u):
        if factor[0]=='dense':
            _,q,root,_,_=factor
            return q@(root*(q.T@u))
        _,ux,uy,root,*_=factor
        z=ux.T@u.reshape(self.nx,self.ny)@uy
        return (ux@(root*z)@uy.T).ravel()

    def field(self,factor,gaussian):
        return self.design@gaussian[:3]+self.apply(factor,gaussian[3:])

    def likelihood(self,f):
        self.likelihood_calls+=1
        if not np.isfinite(f).all() or np.max(f)>700:return -np.inf
        return float(self.counts@(np.log(self.exposure)+f)-self.exposure*np.exp(f).sum())

    @staticmethod
    def hyperprior(h):
        rho,alpha=np.exp(h)
        return 2*h[0]-rho+h[1]-alpha*alpha/8

    def evaluate(self,q):
        h=q[:2];g=q[2:];factor=self.factor(h)
        f=self.field(factor,g);rate=self.exposure*np.exp(f)
        likelihood_gradient=self.counts-rate
        lp=self.likelihood(f)+self.hyperprior(h)-.5*(g@g)
        gradient=np.empty_like(q)
        gradient[2:5]=self.design.T@likelihood_gradient-g[:3]
        gradient[5:]=self.apply(factor,likelihood_gradient)-g[3:]
        if self.dense:
            _,eigen,root,dr,da=factor
            z=eigen.T@g[3:];v=eigen.T@likelihood_gradient
            gr=v@(dr@z);ga=v@(da*z)
        else:
            _,ux,uy,root,drx,dry,da=factor
            z=ux.T@g[3:].reshape(self.nx,self.ny)@uy
            v=ux.T@likelihood_gradient.reshape(self.nx,self.ny)@uy
            dz=np.einsum('ikj,kj->ij',drx,z)+np.einsum('ijk,ik->ij',dry,z)
            gr=np.sum(v*dz);ga=np.sum(v*da*z)
        rho,alpha=np.exp(h)
        gradient[:2]=[gr+2-rho,ga+1-alpha*alpha/4]
        return float(lp),gradient
