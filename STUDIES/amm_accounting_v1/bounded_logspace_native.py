"""Direct native log-space target; explicit certified negative-overflow rejection."""
import hashlib,json,math
import numpy as np
from scipy.special import log_ndtr
from bounded_scale_native import NativeBounded

def compile_target(y,cap,rho=.95):
    import numba,owalnuts
    obs=np.array(y,dtype=np.float64,copy=True)
    if obs.ndim!=1 or not len(obs) or not np.isfinite(obs).all():raise ValueError('Finite observations')
    if not np.isfinite(cap) or cap<=0 or not np.isfinite(rho) or not -1<rho<1:raise ValueError('Cap/rho')
    obs.setflags(write=False);n=len(obs);dim=n+3
    digest=hashlib.sha256(json.dumps(dict(y=obs.tolist(),cap=cap,rho=rho),sort_keys=True).encode()).hexdigest()
    normalizer=float(log_ndtr((np.log(cap)-np.log(.2))/.5));nc=.5*np.log(2*np.pi)
    tc=math.lgamma(3.)-math.lgamma(2.5)-.5*np.log(5*np.pi)
    max_float=np.finfo(np.float64).max;log_max=np.log(max_float)
    weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=rho*weights[i]
    weights[0]/=np.sqrt(1-rho*rho);weights.setflags(write=False)
    @numba.njit(error_model='numpy')
    def difference(la,sa,lb,sb):
        if sa==0:return lb,-sb
        if sb==0:return la,sa
        if sa!=sb:return np.logaddexp(la,lb),sa
        if la==lb:return -np.inf,0.
        if la>lb:return la+np.log(-np.expm1(lb-la)),sa
        return lb+np.log(-np.expm1(la-lb)),-sb
    @numba.njit(error_model='numpy')
    def evaluate(q,g):
        for j in range(dim):
            if not np.isfinite(q[j]):return np.nan
        mu=q[0];eta=q[1];b=q[2];l=np.log(cap)-np.logaddexp(0.,eta);sigma=np.exp(l)
        a=np.empty(n);a[0]=q[3]/np.sqrt(1-rho*rho)
        for i in range(1,n):a[i]=rho*a[i-1]+q[3+i]
        abar=np.mean(a);s=.5*(mu+sigma*abar);h=mu+sigma*a
        if not np.isfinite(s):return np.nan
        for i in range(n):
            if not np.isfinite(h[i]):return np.nan
        logb=np.log(abs(b)) if b!=0 else -np.inf;sb=np.sign(b)
        log_penalty=2*s+2*logb-2*np.log(.002)-np.log(2.)
        # Drop nonpositive quadratic priors and likelihood residual terms to bound
        # log density above by U - beta^2/(2*.002^2). If penalty>4*MAX and
        # finite U<=MAX, the mathematical log density is below -MAX.
        upper=-(n+3)*nc-np.log(.5)-np.log(.002)-normalizer+s
        for i in range(n):upper+=tc-.5*h[i]
        if b!=0 and log_penalty>log_max+np.log(4.) and np.isfinite(upper) and upper<=max_float:
            return -np.inf
        penalty=np.exp(log_penalty) if b!=0 else 0.
        beta_db=sb*np.exp(2*s+logb-2*np.log(.002)) if b!=0 else 0.
        value=-.5*(mu-2*np.log(.005))**2-nc-.5*((l-np.log(.2))/.5)**2-np.log(.5)-nc
        value+=-penalty-np.log(.002)-nc-normalizer-np.logaddexp(0.,-eta)+s
        for i in range(n):value+=-.5*q[3+i]**2-nc
        di=np.empty(n);kb=-2*penalty;db=-beta_db
        for i in range(n):
            delta=.5*sigma*(abar-a[i])
            ly=np.log(abs(obs[i]))-.5*h[i] if obs[i]!=0 else -np.inf
            lr,sr=difference(ly,np.sign(obs[i]),logb+delta,sb)
            den=np.logaddexp(np.log(5.),2*lr)
            value+=tc-.5*h[i]-3*np.logaddexp(0.,2*lr-np.log(5.))
            di[i]=-.5+3*np.exp(2*lr-den)
            if sr!=0:
                db+=6*sr*np.exp(lr+delta-den)
                if b!=0:kb+=6*sr*sb*np.exp(lr+logb+delta-den)
        factor=kb+1.
        g[0]=-(mu-2*np.log(.005))+np.sum(di)+.5*factor
        gl=-(l-np.log(.2))/.25+sigma*np.dot(di,a)+.5*factor*sigma*abar
        g[1]=-np.exp(-np.logaddexp(0.,-eta))*gl+np.exp(-np.logaddexp(0.,eta));g[2]=db
        adj=di.copy()
        for i in range(n-1,0,-1):adj[i-1]+=rho*adj[i]
        adj[0]/=np.sqrt(1-rho*rho)
        for i in range(n):g[3+i]=-q[3+i]+sigma*adj[i]+.5*factor*sigma*weights[i]
        if not np.isfinite(value):return np.nan
        for j in range(dim):
            if not np.isfinite(g[j]):return np.nan
        return value
    @numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
    def callback(d,qp,gp,user):
        if d!=dim:return np.nan
        q=numba.carray(qp,dim);g=numba.carray(gp,dim)
        for j in range(dim):g[j]=np.nan
        value=evaluate(q,g)
        if not np.isfinite(value):
            for j in range(dim):g[j]=np.nan
        return value
    names=['mu','eta','b']+[f'z[{i}]' for i in range(n)]
    return NativeBounded(owalnuts.from_cfunc(callback,dim,parameter_names=names),callback,dim,digest,evaluate)
