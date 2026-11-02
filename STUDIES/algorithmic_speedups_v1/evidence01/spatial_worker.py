import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,sys,time,hashlib
START=time.perf_counter()
from pathlib import Path
os.environ['XDG_CACHE_HOME']=str(Path(sys.argv[-1]).parent/'cache')
import numpy as np
import arviz as az
from scipy.optimize import minimize
from grid import GridGP

BASE=Path(__file__).resolve().parent

def diagnostics(values):
    ds=az.convert_to_dataset({'p':values})
    result={k:np.asarray(fn(ds).p) for k,fn in [
        ('rhat',lambda d:az.rhat(d,method='rank')),
        ('bulk',lambda d:az.ess(d,method='bulk')),
        ('tail',lambda d:az.ess(d,method='tail')),
        ('mcse',lambda d:az.mcse(d,method='mean'))]}
    result.update(mean=values.mean((0,1)),sd=values.reshape(-1,values.shape[-1]).std(0,ddof=1))
    passed=all(np.isfinite(v).all() for v in result.values()) and max(result['rhat'])<=1.01 and min(result['bulk'])>=400 and min(result['tail'])>=400
    return bool(passed),{k:[float(x) if np.isfinite(x) else None for x in v] for k,v in result.items()}

def blocked(model,seed,warmup,draws,sweeps):
    rng=np.random.default_rng(seed)
    def beta_objective(b):
        f=model.design@b
        return -model.likelihood(f)+.5*(b@b),-(model.design.T@(model.counts-model.exposure*np.exp(f)))+b
    fit=minimize(beta_objective,np.zeros(3),jac=True,method='BFGS')
    g=np.r_[fit.x+rng.normal(0,.1,3),rng.normal(0,.1,model.n)]
    h=np.array([.3,0.])+rng.normal(0,.3,2)
    factor=model.factor(h);f=model.field(factor,g);ll=model.likelihood(f)
    scale=.12;accepted=0;shrink=0
    output=np.empty((draws,model.n+5))
    for iteration in range(warmup+draws):
        proposed=h+rng.normal(size=2)*scale
        try:
            next_factor=model.factor(proposed);next_f=model.field(next_factor,g);next_ll=model.likelihood(next_f)
            ratio=next_ll-ll+model.hyperprior(proposed)-model.hyperprior(h)
        except (ValueError,FloatingPointError,OverflowError):ratio=-np.inf
        accept=np.log(rng.random())<ratio
        if accept:h,factor,f,ll=proposed,next_factor,next_f,next_ll
        if iteration<warmup:scale=float(np.clip(scale*np.exp((float(accept)-.3)/(iteration+10)**.6),.005,1.))
        else:accepted+=int(accept)
        for _ in range(sweeps):
            nu=rng.normal(size=len(g));direction=model.field(factor,nu)
            threshold=ll+np.log(rng.random());angle=rng.uniform(0,2*np.pi);low=angle-2*np.pi;high=angle
            for attempt in range(1000):
                co,si=np.cos(angle),np.sin(angle)
                trial=f*co+direction*si;trial_ll=model.likelihood(trial)
                if trial_ll>threshold:
                    g=g*co+nu*si;f=trial;ll=trial_ll;break
                if angle<0:low=angle
                else:high=angle
                angle=rng.uniform(low,high)
            else:raise RuntimeError('slice bracket limit; no unaccepted candidate retained')
            shrink+=attempt
        if iteration>=warmup:output[iteration-warmup]=np.r_[h,g]
        if iteration%500==0:print(json.dumps(dict(iteration=iteration,seed=seed,scale=scale)),flush=True)
    return output,dict(hyper_accept=accepted/draws,scale=scale,slice_shrinks=shrink)

def main(method,seed,destination):
    out=Path(destination);out.mkdir(exist_ok=False);seed=int(seed)
    data=json.loads((BASE/'GP-TRAIN.json').read_text());model=GridGP(data,dense=method=='blocked_dense')
    warmup,draws=1000,2000;arrays=[];chain_info=[];start=time.perf_counter();div=0
    if method.startswith('blocked'):
        for chain in range(4):
            q,info=blocked(model,seed+100*chain,warmup,draws,4 if method=='blocked_grid4' else 1)
            arrays.append(q);chain_info.append(info)
        q=np.asarray(arrays)
        sampling_seconds=time.perf_counter()-start
        fit_factor_calls=model.factor_calls
        np.savez_compressed(out/'DRAWS.npz',q=q)
        # Physical fields are already represented by the same full GP prior,
        # but the whitening differs from the old Cholesky-coordinate target.
        physical=[]
        for row in q.reshape(-1,q.shape[-1]):
            field=model.field(model.factor(row[:2]),row[2:])
            physical.append(np.r_[np.exp(row[:2]),np.asarray(data['coef_scale'])*row[2:5],field,np.exp(field)])
        values=np.asarray(physical).reshape(4,draws,-1)
    elif method=='nuts':
        import nutpie,bridgestan as bs
        runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030');sys.path.insert(0,str(runtime))
        from native_common import native_model,counter_handle,counter_read
        old=Path('/home/ubuntu/lanes/spatial-counts-preflight-20261030')
        shim=old/'evidence/counted_model.so';counter=counter_handle(shim);counter.ow_reset_target_calls()
        trace=nutpie.sample(native_model(shim,BASE/'GP-TRAIN.json',old/'spatial_gp.stan'),draws=draws,tune=warmup,chains=4,cores=4,seed=seed,progress_bar=False,save_warmup=False,adaptation='diag',target_accept=.99,maxdepth=12,store_unconstrained=True,step_size_jitter=0.)
        q=np.asarray(trace.sample_stats.unconstrained_draw).copy();div=int(trace.sample_stats.diverging.sum());chain_info=counter_read(counter);trace.close()
        sampling_seconds=time.perf_counter()-start;np.savez_compressed(out/'DRAWS.npz',q=q)
        fit_factor_calls=0
        target=bs.StanModel(str(old/'spatial_gp_model.so'),data=(BASE/'GP-TRAIN.json').read_text(),seed=1)
        names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'beta.{j}' for j in range(1,4)]+[f'f.{j}' for j in range(1,201)]]
        v=np.array([target.param_constrain(z,include_tp=True,include_gq=False)[ix] for z in q.reshape(-1,q.shape[-1])]).reshape(4,draws,-1)
        values=np.concatenate([v,np.exp(v[:,:,5:])],axis=2)
    else:raise ValueError(method)
    passed,stats=diagnostics(values);passed=passed and div==0
    result=dict(method=method,seed=seed,passed=passed,divergences=div,warmup=warmup,draws=draws,chains=4,sampling_seconds=sampling_seconds,worker_seconds=time.perf_counter()-START,chain_info=chain_info,fit_factor_calls=fit_factor_calls,postprocess_factor_calls=model.factor_calls-fit_factor_calls,likelihood_calls=model.likelihood_calls,stats=stats,scope='Exploratory pilot; combined historical spatial reference remains unqualified')
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='stats'}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
