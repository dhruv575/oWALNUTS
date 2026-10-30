import json,time
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from backend import Backend,ROOT

def run():
    out=ROOT/'prepared';out.mkdir(exist_ok=False)
    for path in sorted((ROOT/'data').glob('*.json')):
        if path.name=='CASES.json':continue
        start=time.monotonic();data=json.loads(path.read_text());d=data['P'];b=Backend(data);base=np.array(data['prior_mean']);fits=[]
        guesses=[base]+[base+.7*np.sin(np.arange(d)+j) for j in range(1,5)]
        if data['linear']:
            x=base.copy();x[0],x[1]=base[1],base[0];x[-2]+=base[1]-base[0];guesses.append(x)
        def objective(q):
            try:lp,g=b.value(q);return -lp,-g
            except ValueError:return 1e100,np.zeros(d)
        for x in guesses:
            fit=minimize(objective,x,jac=True,method='L-BFGS-B',bounds=[(-10,12)]*d,options={'maxiter':500,'ftol':1e-12,'gtol':1e-6})
            lp,g=b.value(fit.x);fits.append(dict(q=fit.x.tolist(),lp=lp,gradient_max=float(np.max(abs(g))),success=bool(fit.success)))
        fits.sort(key=lambda x:-x['lp']);mode=np.array(fits[0]['q']);H=np.empty((d,d));h=1e-4
        for i in range(d):
            e=np.zeros(d);e[i]=h;H[:,i]=-(b.value(mode+e)[1]-b.value(mode-e)[1])/(2*h)
        H=(H+H.T)/2;eig,V=np.linalg.eigh(H);clipped=np.clip(eig,1e-4,1e8);cov=(V/clipped)@V.T;L=np.linalg.cholesky(cov)
        starts=mode+(.7*np.sin(np.arange(1,5)[:,None]*np.arange(1,d+1)[None,:]))@L.T
        # Include distinct competitive modes rather than initializing all chains at one mode.
        alternatives=[f for f in fits[1:] if fits[0]['lp']-f['lp']<12 and np.linalg.norm(np.linalg.solve(L,np.array(f['q'])-mode))>3]
        if alternatives:starts[0]=alternatives[0]['q']
        result=dict(mode=mode.tolist(),cov=cov.tolist(),L=L.tolist(),hessian_eigenvalues=eig.tolist(),laplace_valid=bool(eig.min()>0 and fits[0]['gradient_max']<.01),starts=starts.tolist(),optimizations=fits,seconds=time.monotonic()-start)
        (out/path.name).write_text(json.dumps(result,indent=2)+'\n');b.close();print(path.stem,result['seconds'],result['laplace_valid'],flush=True)

if __name__=='__main__':run()
