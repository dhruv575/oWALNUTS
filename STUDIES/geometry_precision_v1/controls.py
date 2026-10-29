import time,sys,json,traceback
from pathlib import Path
source=Path(__file__).resolve().parent.parent/'source'
if source.is_dir():sys.path.insert(0,str(source))
import numpy as np
from scipy.optimize import minimize,brentq
from targets import Target,NAMES
from metrics import assess


def laplace(t):
    start=time.monotonic();candidates=[];failed=0
    starts=list(t.initial())+[np.zeros(t.dim)]
    analytic=np.zeros(t.dim)
    if t.kind==2:analytic[1]=-2
    if t.kind in (3,4):analytic[0]=-.5*(t.dim-1)*(1.5 if t.kind==3 else 3.)**2
    if t.kind==6:analytic[0]=brentq(lambda v:v+3*(t.dim-1)*(1-np.tanh(2*v)**2),-10,0)
    if t.kind==8:analytic[0]=brentq(lambda v:v-3*np.tanh(3*v),1,4)
    starts.append(analytic)
    for q in starts:
        try:
            f=minimize(lambda x:(-t(x)[0],-t(x)[1]),q,jac=True,method='BFGS',options={'gtol':1e-7,'maxiter':500})
            if np.max(abs(t(f.x)[1]))<1e-4:candidates.append((t(f.x)[0],f.x))
            else:failed+=1
        except Exception:failed+=1
    if not candidates:raise ValueError('No stationary MAP')
    q=max(candidates,key=lambda x:x[0])[1];h=1e-5
    H=np.column_stack([-(t(q+np.eye(t.dim)[i]*h)[1]-t(q-np.eye(t.dim)[i]*h)[1])/(2*h) for i in range(t.dim)])
    H=(H+H.T)/2
    if np.linalg.eigvalsh(H).min()<=0:raise ValueError('Nonpositive MAP Hessian')
    return q,np.linalg.inv(H),dict(setup_seconds=time.monotonic()-start,failed_map_starts=failed,map=q.tolist(),precision=H.tolist())


def run(name,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);t=Target(name);rows=[]
    try:mean,cov,lp=laplace(t)
    except Exception as exc:mean=cov=None;lp=dict(status='failed',error=repr(exc))
    for rep in range(8):
        for i,d in enumerate([250,1000,3000]):
            seed=635000000+t.kind*100000+rep*100+i;start=time.monotonic()
            q=t.iid(4*d,seed).reshape(4,d,t.dim)
            rows.append(dict(name=name,method='iid',rep=rep,draws=d,seed=seed,metrics=assess(t,q),seconds=time.monotonic()-start))
        if mean is not None:
            seed=635000000+t.kind*100000+rep*100+10;start=time.monotonic()
            # Cholesky avoids silently repairing an indefinite covariance.
            q=(np.random.default_rng(seed).normal(size=(12000,t.dim))@np.linalg.cholesky(cov).T+mean).reshape(4,3000,t.dim)
            rows.append(dict(name=name,method='laplace',rep=rep,draws=3000,seed=seed,metrics=assess(t,q),seconds=time.monotonic()-start,**lp))
        else:rows.append(dict(name=name,method='laplace',rep=rep,**lp))
        (out/'RESULTS.json').write_text(json.dumps(rows,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':run(*sys.argv[1:])
