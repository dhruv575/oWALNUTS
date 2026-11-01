import hashlib
import importlib.metadata
import json
import subprocess
import time
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
from scipy.optimize import minimize
ROOT=Path(__file__).resolve().parent

def solve(q,t,theta,linear=False):
    c,k=np.exp(q)
    f=lambda t,s:[s[1],-c*s[1]-k*(s[0] if linear else np.sin(s[0]))]
    r=solve_ivp(f,(0,float(max(t))),[theta,0],t_eval=t,method='DOP853',rtol=1e-12,atol=1e-12)
    assert r.success;return r.y[0]

def main():
    started=time.monotonic()
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.suffix in ['.py','.cpp','.md']}
    subprocess.run(['g++','-std=c++17','-O3','-fPIC','-shared',str(ROOT/'pendulum.cpp'),'-o',str(ROOT/'pendulum.so')],check=True,timeout=90)
    from backend import Backend,physical,unconstrained,linear_prediction
    from sampling import fit
    data_root=ROOT/'data';data_root.mkdir(exist_ok=False)
    prep_root=ROOT/'prepared';prep_root.mkdir(exist_ok=False)
    truth=np.log([.2,2.25]);train=np.arange(1,7)*.25;future=np.array([2.,3.,4.,5.,6.]);checks=[]
    for case,theta in enumerate([.3,2.]):
        latent=solve(truth,train,theta);forecast=solve(truth,future,theta)
        observed=latent+np.random.default_rng(953000001+case).normal(0,.05,len(train))
        held=forecast+np.random.default_rng(953000101+case).normal(0,.05,len(future))
        data=dict(P=2,theta=theta,sigma=.05,times=train.tolist(),observed=observed.tolist(),future_times=future.tolist())
        (data_root/f'case{case}.json').write_text(json.dumps(data,indent=2)+'\n')
        (data_root/f'case{case}-evaluation.json').write_text(json.dumps(dict(log_parameters=truth.tolist(),latent_future=forecast.tolist(),future_observations=held.tolist()),indent=2)+'\n')
        for linear in [False,True]:
            d={**data,'linear':linear};tag=f'case{case}'+('-linear' if linear else '')
            b=Backend(d);half=Backend(d,step=.005)
            rng=np.random.default_rng(953010001+case)
            points=[truth,np.log([.2,2.])]+[np.array([-5.,-2.])+np.array([6.,4.])*rng.uniform(.1,.9,2) for _ in range(12)]
            angle_error=0.;step_error=0.;gradient_error=0.;density_error=0.
            for i,q in enumerate(points):
                pred=b.predict(q,future);expected=solve(q,future,theta,linear)
                angle_error=max(angle_error,float(max(abs(pred-expected))))
                step_error=max(step_error,float(max(abs(pred-half.predict(q,future)))))
                if linear:
                    c,k=np.exp(q);analytic=np.array([(expm(np.array([[0.,1.],[-k,-c]])*t)@np.array([theta,0.]))[0] for t in future])
                    assert np.allclose(linear_prediction(q,future,theta)[0],analytic,atol=1e-10,rtol=1e-10)
                if i<8:
                    z=unconstrained(q);v,g=b.value(z);eps=1e-5
                    fd=np.array([(b.value(z+e)[0]-b.value(z-e)[0])/(2*eps) for e in np.eye(2)*eps])
                    gradient_error=max(gradient_error,float(max(abs(fd-g)/np.maximum(1,abs(g)))))
                    prior=-.5*np.sum(((q-np.log([.2,2.]))/[.8,.5])**2)
                    ss=(q-np.array([-5.,-2.]))/[6.,4.]
                    numerical=-.5*np.sum(((np.array(d['observed'])-solve(q,train,theta,linear))/.05)**2)+prior+np.log(np.array([6.,4.])*ss*(1-ss)).sum()
                    density_error=max(density_error,abs(v-numerical))
            assert angle_error<=2e-6 and step_error<=2e-6 and gradient_error<=2e-4
            assert density_error<=2e-4
            white_center=np.array([.2,-.1]);A=np.array([[1.2,.1],[.3,.8]])
            wb=Backend(d,white_center,A);z=np.array([.1,.3]);v,g=wb.value(z);rv,rg=b.value(white_center+A@z)
            assert np.allclose(v,rv,rtol=1e-12,atol=1e-12) and np.allclose(g,A.T@rg,rtol=1e-12,atol=1e-12);wb.close()
            before=time.monotonic();initial=unconstrained(np.log([.2,2.]));fits=[]
            for j in range(5):
                x=initial+.5*np.sin(np.arange(2)+j) if j else initial
                r=minimize(lambda z:(-b.value(z)[0],-b.value(z)[1]),x,jac=True,method='BFGS',options={'gtol':1e-7,'maxiter':300})
                v,g=b.value(r.x);fits.append(dict(q=r.x.tolist(),lp=v,gradient_max=float(max(abs(g))),success=bool(r.success)))
            fits.sort(key=lambda r:-r['lp']);mode=np.array(fits[0]['q']);eps=1e-4
            H=np.column_stack([-(b.value(mode+e)[1]-b.value(mode-e)[1])/(2*eps) for e in np.eye(2)*eps]);H=(H+H.T)/2
            eigen=np.linalg.eigvalsh(H);valid=bool(min(eigen)>0 and fits[0]['gradient_max']<=1e-4)
            if not valid:raise ValueError('MAP/Hessian admission failed: '+tag)
            cov=np.linalg.inv(H);L=np.linalg.cholesky(cov)
            starts=mode+.7*np.sin(np.arange(1,5)[:,None]*np.arange(1,3)[None,:])@L.T
            prep=dict(mode=mode.tolist(),cov=cov.tolist(),L=L.tolist(),starts=starts.tolist(),laplace_valid=valid,optimizations=fits,seconds=time.monotonic()-before)
            (prep_root/(tag+'.json')).write_text(json.dumps(prep,indent=2)+'\n')
            if not linear:
                for engine in ['nuts','walnuts']:
                    q,info=fit(d,prep,engine+'_white_90',953020001+case,20,30)
                    assert q.shape==(4,20,2) and np.isfinite(q).all() and info['target_calls']>0
                    checks.append(dict(case=case,engine=engine,scope='ABI finite smoke only',**info))
            checks.append(dict(case=case,linear=linear,angle_error=angle_error,step_error=step_error,gradient_error=gradient_error,density_error=density_error))
            b.close();half.close()
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in sources.items())
    result=dict(passed=True,checks=checks,sources=sources,library_sha256=hashlib.sha256((ROOT/'pendulum.so').read_bytes()).hexdigest(),seconds=time.monotonic()-started,
                packages={n:importlib.metadata.version(n) for n in ['owalnuts','nutpie','numpy','scipy','arviz','psutil']})
    (ROOT/'PREFLIGHT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
