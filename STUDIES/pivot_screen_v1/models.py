"""Small proper targets and known-truth decision problems for pivot triage."""
import numpy as np
from scipy.special import expit, logit
from scipy.stats import nbinom

SCENARIOS=['easy','near_tie','sparse','heterogeneous','misspecified']
CANDIDATES=['hierarchical_ab','revenue_ab','contextual_bandit','inventory']


class Target:
    def __init__(self, kind, data):
        self.kind,self.data=kind,data
        self.mean=np.asarray(data['prior_mean']);self.sd=np.asarray(data['prior_sd'])
        self.dim=len(self.mean)

    def __call__(self,q):
        d=self.data; z=(q-self.mean)/self.sd
        lp=-.5*np.dot(z,z);g=-(q-self.mean)/self.sd**2
        if self.kind=='logistic':
            v=d['X']@q;p=expit(v)
            lp+=np.sum(d['y']*v-d['n']*np.logaddexp(0,v))
            g+=d['X'].T@(d['y']-d['n']*p)
        elif self.kind=='inventory':
            v=d['X']@q;r=d['dispersion'];p=expit(v-np.log(r))
            lp+=np.sum(d['y']*v-(d['y']+r)*np.logaddexp(np.log(r),v))
            g+=d['X'].T@(d['y']-(d['y']+r)*p)
        elif self.kind=='revenue':
            p=expit(q[:2]);lp+=np.sum(d['success']*q[:2]-d['n']*np.logaddexp(0,q[:2]))
            g[:2]+=d['success']-d['n']*p
            t=expit(q[4:6]);s=.2+1.6*t
            for a in range(2):
                residual=d['logs'][a]-q[2+a];ss=np.dot(residual,residual);n=len(residual)
                lp+=-n*np.log(s[a])-.5*ss/s[a]**2
                g[2+a]+=residual.sum()/s[a]**2
                g[4+a]+=(-n/s[a]+ss/s[a]**3)*1.6*t[a]*(1-t[a])
        else:raise ValueError(self.kind)
        return float(lp),np.ascontiguousarray(g)


def hierarchy_design(segments=8):
    X=np.zeros((segments*2,2+2*segments))
    for s in range(segments):
        for a in range(2):
            X[2*s+a,0]=1;X[2*s+a,1]=a
            X[2*s+a,2+s]=.7;X[2*s+a,2+segments+s]=.35*a
    return X


def generate(candidate,scenario,seed):
    rng=np.random.default_rng(seed);S=8
    if candidate=='hierarchical_ab':
        alpha=logit(.12)+rng.normal(0,.7,S)
        delta=np.full(S,.45 if scenario=='easy' else .04 if scenario=='near_tie' else .25)
        if scenario=='heterogeneous':delta=np.linspace(-.8,.8,S)
        delta*=rng.choice([-1.,1.])
        truth=expit(alpha[:,None]+delta[:,None]*np.array([0,1]))
        n=np.full((S,2),5 if scenario=='sparse' else 50)
        sampling=truth if scenario!='misspecified' else rng.beta(truth*12,(1-truth)*12)
        y=rng.binomial(n,sampling)
        target=Target('logistic',dict(X=hierarchy_design(),y=y.ravel(),n=n.ravel(),prior_mean=np.r_[logit(.12),0,np.zeros(2*S)],prior_sd=np.r_[1,.5,np.ones(2*S)]))
        return dict(target=target,truth=truth,n=n,y=y)
    if candidate=='revenue_ab':
        n=np.full(2,35 if scenario=='sparse' else 250)
        p=np.array([.10,.12]);mu=np.log([30.,35.]);sigma=np.array([.9,1.1])
        if scenario=='near_tie':p[:]=.1;mu=np.log([30.,30.3]);sigma[:]=1.
        if scenario=='heterogeneous':p=np.array([.18,.08]);mu=np.log([20.,55.]);sigma=np.array([.6,1.3])
        if rng.random()<.5:p=p[::-1].copy();mu=mu[::-1].copy();sigma=sigma[::-1].copy()
        mixture=.05 if scenario=='misspecified' else 0.
        truth=p*np.exp(mu+sigma**2/2)*(1+4*mixture)
        observations=[];logs=[];success=[]
        for a in range(2):
            conversion=rng.random(n[a])<p[a]
            values=np.exp(rng.normal(mu[a],sigma[a],n[a]))
            if mixture:values*=np.where(rng.random(n[a])<mixture,5.,1.)
            values*=conversion;observations.append(values);logs.append(np.log(values[conversion]));success.append(int(conversion.sum()))
        target=Target('revenue',dict(n=n,success=np.array(success),logs=logs,prior_mean=np.r_[np.full(2,logit(.1)),np.full(2,np.log(30.)),np.zeros(2)],prior_sd=np.ones(6)))
        return dict(target=target,truth=truth,observations=observations,n=n)
    if candidate=='inventory':
        n=3 if scenario=='sparse' else 50 if scenario=='easy' else 15
        mu=np.exp(np.log(15)+rng.normal(0,1.2 if scenario=='heterogeneous' else .5,S))
        if scenario=='near_tie':mu=np.full(S,15.)
        r=1. if scenario=='misspecified' else 5.
        y=rng.negative_binomial(r,r/(r+mu[:,None]),size=(S,n))
        X=np.zeros((S*n,1+S));X[:,0]=1
        for s in range(S):X[s*n:(s+1)*n,1+s]=.7
        target=Target('inventory',dict(X=X,y=y.ravel(),dispersion=5.,prior_mean=np.r_[np.log(15.),np.zeros(S)],prior_sd=np.ones(1+S)))
        return dict(target=target,truth=mu,true_dispersion=r,y=y,n=n)
    if candidate=='contextual_bandit':
        x=np.clip(rng.normal(size=100),-2,2)
        beta=np.array([-1.,.4,.6,.3])
        if scenario=='near_tie':beta[2:]=[.04,.04]
        if scenario=='sparse':beta=[-3.,.4,.4,.3]
        if scenario=='heterogeneous':beta=[-1.,.4,-.1,1.4]
        beta=np.array(beta);beta[2:]*=rng.choice([-1.,1.])
        X=np.stack([bandit_features(x,np.zeros(100)),bandit_features(x,np.ones(100))],axis=1)
        p=expit(X@beta+(.7*x[:,None]**2*np.array([0,1]) if scenario=='misspecified' else 0))
        uniforms=rng.random((100,2));potential=(uniforms<p).astype(int)
        initial=np.tile([0,1],10);rng.shuffle(initial)
        return dict(x=x,X=X,truth=p,potential=potential,initial=initial)
    raise ValueError(candidate)


def bandit_features(x,a):
    return np.column_stack([np.ones(len(x)),x,a,x*a])


def bandit_target(X,y):
    return Target('logistic',dict(X=np.asarray(X),y=np.asarray(y),n=np.ones(len(y)),prior_mean=np.array([-1.,0,0,0]),prior_sd=np.array([1.,1.,.7,.7])))


def functional(problem,draws,candidate):
    if candidate=='hierarchical_ab':return expit(draws@problem['target'].data['X'].T).reshape(len(draws),8,2)
    if candidate=='revenue_ab':
        s=.2+1.6*expit(draws[:,4:6])
        return expit(draws[:,:2])*np.exp(draws[:,2:4]+s*s/2)
    if candidate=='inventory':return np.exp(draws[:,0,None]+.7*draws[:,1:])
    raise ValueError(candidate)


def inventory_cost(q,mu,r):
    p=r/(r+mu)
    shortage=mu*nbinom.sf(q-1,r+1,p)-q*nbinom.sf(q,r,p)
    return 5*shortage+q-mu


def inventory_actions(mu_draws):
    # Binary search the posterior mixture's 80% quantile, without truncating demand.
    sample=mu_draws[np.linspace(0,len(mu_draws)-1,min(512,len(mu_draws)),dtype=int)]
    actions=[]
    for s in range(8):
        p=5/(5+sample[:,s]);lo=-1;hi=max(1,int(nbinom.ppf(.999,5,p).max()))
        while lo+1<hi:
            mid=(lo+hi)//2
            if nbinom.cdf(mid,5,p).mean()>=.8:hi=mid
            else:lo=mid
        actions.append(hi)
    return np.array(actions)


def decision(problem,values,candidate):
    if candidate in ['hierarchical_ab','revenue_ab']:
        action=np.argmax(values.mean(axis=0),axis=-1)
        truth=problem['truth']
        selected=np.take_along_axis(truth,np.asarray(action)[...,None],axis=-1).squeeze(-1)
        regret=float(np.mean(truth.max(axis=-1)-selected))
        scale=float(np.mean(truth.max(axis=-1)))
    else:
        action=inventory_actions(values);truth=problem['truth'];r=problem['true_dispersion']
        oracle=nbinom.ppf(.8,r,r/(r+truth))
        regret=float(np.mean(inventory_cost(action,truth,r)-inventory_cost(oracle,truth,r)))
        scale=float(np.mean(inventory_cost(oracle,truth,r)))
    return dict(action=np.asarray(action).tolist(),regret=regret,normalized_regret=regret/max(scale,1e-12))
