import os,sys,time,json,ctypes
from pathlib import Path
START=time.perf_counter()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
BASE=Path(__file__).resolve().parent
os.environ['XDG_CACHE_HOME']=str(Path(sys.argv[-1]).parent/'cache')
import numpy as np
import arviz as az
from scipy.special import logsumexp,ndtr
from backend import Backend,DP,physical

def forward(t,c,s):
    u=np.array(t,copy=True);u[...,1]=np.polynomial.polynomial.polyval(t[...,0],c)+s*t[...,1];return u
def inverse(u,c,s):
    t=np.array(u,copy=True);t[...,1]=(u[...,1]-np.polynomial.polynomial.polyval(u[...,0],c))/s;return t
def proposal_log(t):return -3.5*np.log1p(np.sum(t*t,axis=-1)/5)
def value_function(b):
    b.lib.value_only.argtypes=[ctypes.c_void_p,DP];b.lib.value_only.restype=ctypes.c_double
    def value(u):
        u=np.ascontiguousarray(u,dtype=float);return b.lib.value_only(b.ptr,u.ctypes.data_as(DP))
    return value

def train(data,prep):
    start=time.perf_counter();b=Backend(data,prep['mode'],prep['L']);value=value_function(b)
    rng=np.random.default_rng(954200000);u=rng.normal(size=(4096,2))/np.sqrt(rng.chisquare(5,size=(4096,1))/5)
    lp=np.array([value(x) for x in u]);lw=lp-proposal_log(u);w=np.exp(lw-logsumexp(lw))
    X=np.polynomial.polynomial.polyvander(u[:,0],3)
    c=np.linalg.lstsq(X*np.sqrt(w[:,None]),u[:,1]*np.sqrt(w),rcond=None)[0]
    s=float(np.sqrt(w@((u[:,1]-X@c)**2)))
    assert np.isfinite(c).all() and s>0
    result=dict(coefficients=c.tolist(),scale=s,importance_ess=float(1/(w@w)),seconds=time.perf_counter()-start,seed=954200000,proposals=4096)
    b.close();return result

def preflight(data,prep,transport):
    c=np.array(transport['coefficients']);s=transport['scale'];b=Backend(data,prep['mode'],prep['L']);v=value_function(b)
    bt=Backend(data,prep['mode'],prep['L'],transport=(c,s));rng=np.random.default_rng(954200099)
    value_error=gradient_error=roundtrip_error=balance_error=0.
    for _ in range(40):
        t=rng.normal(size=2);u=forward(t,c,s)
        value_error=max(value_error,abs(v(u)-b.value(u)[0]),abs(bt.value(t)[0]-v(u)-np.log(s)))
        roundtrip_error=max(roundtrip_error,float(np.max(abs(inverse(u,c,s)-t))))
        lp,g=bt.value(t);fd=[]
        for j in range(2):
            d=np.eye(2)[j]*1e-5;fd.append((bt.value(t+d)[0]-bt.value(t-d)[0])/2e-5)
        gradient_error=max(gradient_error,float(np.max(abs(g-fd)/(1+abs(g)))))
        a=rng.normal(size=2);z=rng.normal(size=2);la=v(a);lz=v(z);qa=proposal_log(a);qz=proposal_log(z);sa=-.5*(a@a);sz=-.5*(z@z)
        forward_flux=la+qz+min(0.,sz-sa+qa-qz)+min(0.,lz-la-sz+sa)
        reverse_flux=lz+qa+min(0.,sa-sz+qz-qa)+min(0.,la-lz-sa+sz)
        balance_error=max(balance_error,abs(forward_flux-reverse_flux))
    b.close();bt.close()
    return dict(value_error=float(value_error),gradient_error=float(gradient_error),roundtrip_error=float(roundtrip_error),balance_error=float(balance_error),passed=bool(value_error<1e-8 and gradient_error<1e-4 and roundtrip_error<1e-10 and balance_error<1e-10))

def main(method,seed,destination):
    out=Path(destination);out.mkdir(exist_ok=False);seed=int(seed)
    data=json.loads((BASE/'PHYSICS-DATA.json').read_text());prep=json.loads((BASE/'PHYSICS-PREP.json').read_text())
    if method=='prepare':
        transport=train(data,prep);checks=preflight(data,prep,transport)
        (out/'TRANSPORT.json').write_text(json.dumps(transport,indent=2));(out/'SUMMARY.json').write_text(json.dumps(checks,indent=2))
        assert checks['passed'];return
    transport=json.loads((BASE/'physics_repair01/prepare/artifact/TRANSPORT.json').read_text())
    c=np.array(transport['coefficients']);s=transport['scale'];mapped='transport' in method
    mode=np.array(prep['mode']);L=np.array(prep['L']);initial=np.linalg.solve(L,(np.array(prep['starts'])-mode).T).T
    training_seconds=transport['seconds'] if mapped else 0.
    start=time.perf_counter();counts={};div=depth=0
    if method.startswith(('mh','da')):
        delayed=method.startswith('da');b=Backend(data,mode,L);value=value_function(b);rng=np.random.default_rng(seed);chains=[];accepted=stage1=0
        for chain in range(4):
            t=inverse(initial[chain],c,s) if mapped else initial[chain].copy()
            logp=value(forward(t,c,s) if mapped else t)+(np.log(s) if mapped else 0.);q=proposal_log(t);sur=-.5*(t@t);rows=[]
            for i in range(7000):
                candidate=rng.normal(size=2)/np.sqrt(rng.chisquare(5)/5);nq=proposal_log(candidate);nsur=-.5*(candidate@candidate)
                first=not delayed or np.log(rng.random())<nsur-sur+q-nq
                if first:
                    stage1+=1;new=value(forward(candidate,c,s) if mapped else candidate)+(np.log(s) if mapped else 0.)
                    ratio=new-logp-(nsur-sur) if delayed else new-logp+q-nq
                    if np.log(rng.random())<ratio:t,logp,q,sur=candidate,new,nq,nsur;accepted+=1
                if i>=1000:rows.append(t.copy())
            chains.append(rows)
        t=np.array(chains);counts=dict(target_calls=b.counts()[0],acceptance=accepted/28000,stage1_fraction=stage1/28000);b.close()
        u=forward(t,c,s) if mapped else t;z=u@L.T+mode
    else:
        import nutpie,owalnuts
        raw=method.endswith('raw');starts=np.array(prep['starts']) if raw else inverse(initial,c,s) if mapped else initial
        b=Backend(data,None if raw else mode,None if raw else L,starts,transport=(c,s) if mapped else None);b.reset()
        if method.startswith('nuts'):
            trace=nutpie.sample(b.nuts,chains=4,cores=1,tune=500,draws=4000,seed=seed,progress_bar=False,save_warmup=False,target_accept=.9,maxdepth=11,low_rank_modified_mass_matrix=False,transform_adapt=False)
            t=np.asarray(trace.posterior.q.values).copy();div=int(trace.sample_stats.diverging.sum());depth=int(trace.sample_stats.maxdepth_reached.sum());trace.close()
        else:
            trace=owalnuts.sample(b.walnuts,dim=2,init=starts,chains=4,threads=1,warmup=500,draws=4000,seed=seed,tuning=owalnuts.Tuning(max_depth=11,max_error=1.),adaptation=owalnuts.Adaptation(target_accept=.9))
            t=trace.samples;div=int(trace.divergent[:,500:].sum());depth=int((trace.depth[:,500:]>=11).sum())
        counts=dict(target_calls=b.counts()[0]);b.close();u=forward(t,c,s) if mapped else t;z=t if raw else u@L.T+mode
    sampling_seconds=time.perf_counter()-start
    q=physical(z);b=Backend(data);pred=b.predict_batch(q.reshape(-1,2)).reshape(*q.shape[:2],5);b.close()
    f=np.concatenate([q,np.exp(q),pred],axis=2);ds=az.convert_to_dataset({'p':f})
    stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]}
    probability=ndtr(pred[:,:,2]/.05);pmcse=float(np.asarray(az.mcse(az.convert_to_dataset({'p':probability})).p)) if probability.var()>0 else 0.
    mean=f.mean((0,1));reference=json.loads((BASE/'PHYSICS-REFERENCE.json').read_text())['summary'];tol=np.r_[.1*np.array(reference['sd'])[:4],np.full(5,.02)]
    errors=abs(mean-reference['mean']);perror=abs(probability.mean()-reference['probability'])
    diagnostic=bool(all(np.isfinite(x).all() for x in stats.values()) and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400 and div==0 and depth==0)
    accuracy=bool(np.all(errors<=tol) and perror<=.02);precision=bool(np.all(stats['mcse']<=tol/2) and pmcse<=.01)
    np.savez_compressed(out/'DRAWS.npz',z=z,pred=pred)
    result=dict(method=method,seed=seed,passed=diagnostic and accuracy and precision,diagnostic_pass=diagnostic,accuracy_pass=accuracy,precision_pass=precision,sampling_seconds=sampling_seconds,training_seconds=training_seconds,total_seconds=time.perf_counter()-START+training_seconds+prep['seconds'],divergences=div,depth_hits=depth,mean=mean.tolist(),errors=errors.tolist(),probability_error=float(perror),probability_mcse=pmcse,stats={k:v.tolist() for k,v in stats.items()},**counts)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k!='stats'}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
