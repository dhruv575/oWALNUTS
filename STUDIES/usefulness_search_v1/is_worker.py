import time
START=time.monotonic()
import ctypes,json,sys
from pathlib import Path
import numpy as np
from scipy.special import logsumexp
from scipy.stats import multivariate_t
import arviz as az
OLD=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029')
sys.path.insert(0,str(OLD/'source'))
from backend import Backend,DP

class Density:
    def __init__(self,data):
        self.lib=ctypes.CDLL(str(OLD/'build/model_model.so'));self.err=ctypes.c_void_p()
        self.lib.bs_model_construct.argtypes=[ctypes.c_char_p,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p)];self.lib.bs_model_construct.restype=ctypes.c_void_p
        self.lib.bs_log_density.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_bool,DP,DP,ctypes.POINTER(ctypes.c_void_p)];self.lib.bs_log_density.restype=ctypes.c_int
        self.lib.bs_free_error_msg.argtypes=[ctypes.c_void_p];self.lib.bs_model_destruct.argtypes=[ctypes.c_void_p]
        self.ptr=self.lib.bs_model_construct(json.dumps(data).encode(),1,ctypes.byref(self.err));assert self.ptr
        self.errors=0
    def value(self,q):
        q=np.ascontiguousarray(q);v=np.empty(1);err=ctypes.c_void_p()
        status=self.lib.bs_log_density(self.ptr,False,True,q.ctypes.data_as(DP),v.ctypes.data_as(DP),ctypes.byref(err))
        if err.value:self.lib.bs_free_error_msg(err)
        if status or not np.isfinite(v[0]):self.errors+=1;return -np.inf
        return v[0]
    def close(self):self.lib.bs_model_destruct(self.ptr)

def run(arm,n,rep,out):
    n=int(n);rep=int(rep);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    data=json.loads((OLD/'data/stan_public.json').read_text());prep=json.loads((OLD/'prepared/stan_public.json').read_text());mode=np.array(prep['mode']);L=np.array(prep['L']);d=len(mode);b=Density(data)
    original=Backend(data);base=b.value(mode);baseline=original.value(mode)[0];checks=[]
    for j in range(6):
        point=mode+.1*np.sin(np.arange(d)+j);error=abs((b.value(point)-base)-(original.value(point)[0]-baseline));assert error<1e-4;checks.append(error)
    original.close();b.errors=0
    seed=905000000+(['normal','mixture'].index(arm))*100000+([4096,16384].index(n))*10000+rep;rng=np.random.default_rng(seed)
    start=time.monotonic();z=rng.normal(size=(n,d))
    if arm=='mixture':
        choose=rng.random(n)<.5;z[choose]*=(2/np.sqrt(rng.chisquare(5,choose.sum())/5))[:,None]
    q=z@L.T+mode;lp_normal=-.5*np.sum(z*z,axis=1)-.5*d*np.log(2*np.pi)-np.log(np.diag(L)).sum()
    proposal=lp_normal if arm=='normal' else np.logaddexp(lp_normal,multivariate_t.logpdf(q,loc=mode,shape=4*np.array(prep['cov']),df=5))-np.log(2)
    lp=np.array([b.value(x) for x in q]);logw=lp-proposal;assert np.isfinite(logw).any();w=np.exp(logw-logsumexp(logw));seconds=time.monotonic()-start;errors=b.errors;b.close()
    sd=np.sqrt(np.diag(prep['cov']));f=np.column_stack([q,q*q,q<mode-1.645*sd,q>mode+1.645*sd]);mean=w@f;mcse=np.sqrt(np.sum((w[:,None]*(f-mean))**2,axis=0));_,k=az.psislw(logw)
    np.savez_compressed(out/'draws.npz',q=q,weights=w,log_density=lp,log_proposal=proposal)
    original=Backend(data);posterior_checks=[]
    for i in np.unique(np.r_[np.argsort(w)[-16:],np.linspace(0,n-1,8,dtype=int)]):
        if np.isfinite(lp[i]):posterior_checks.append(abs((lp[i]-base)-(original.value(q[i])[0]-baseline)))
    original.close()
    result=dict(arm=arm,n=n,rep=rep,seed=seed,status='ok',seconds=seconds,preparation_seconds=prep['seconds'],weight_ess=float(1/(w@w)),max_weight=float(w.max()),pareto_k=float(k),mean=mean.tolist(),mcse=mcse.tolist(),density_errors=errors,value_gradient_difference_checks=checks,posterior_density_max_difference=max(posterior_checks),density_accuracy_pass=bool(max(posterior_checks)<=.001),total_seconds=time.monotonic()-START+prep['seconds'])
    (out/'RESULT.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
if __name__=='__main__':run(*sys.argv[1:])
