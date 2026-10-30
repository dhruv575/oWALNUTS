import hashlib,json,sys,time
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs,nutpie
from native_common import LOCAL,STUDY,model_files,counter_handle,counter_read,native_model
out=Path(sys.argv[1]);scenario=int(sys.argv[2]);rep=int(sys.argv[3]);seed=949500001+2*scenario+rep;name='gp_pois_regr-gp_pois_regr'
so,_,source=model_files(name);data=LOCAL/f'gp_fresh_data01/scenario-{scenario}/DATA.json';manifest=json.loads((LOCAL/'gp_fresh_data01/SUMMARY.json').read_text());assert hashlib.sha256(data.read_bytes()).hexdigest()==manifest['rows'][scenario]['data_sha256']
shim=LOCAL/'nativemodels01'/name/'counted_model.so';build=json.loads((shim.parent/'BUILD.json').read_text());assert hashlib.sha256(shim.read_bytes()).hexdigest()==build['shim_sha256']
kwargs=dict(draws=8000,tune=2000,chains=4,cores=4,seed=seed,save_warmup=True,progress_bar=False,adaptation='diag',target_accept=.999,maxdepth=10,store_unconstrained=True,step_size_jitter=0.)
(out/'INPUT.json').write_text(json.dumps(dict(data=str(data),settings=kwargs),indent=2)+'\n')
c=counter_handle(shim);c.ow_reset_target_calls();t=time.perf_counter();trace=nutpie.sample(native_model(shim,data,source),**kwargs);elapsed=time.perf_counter()-t;calls=counter_read(c);arrays={}
for group in ['sample_stats','warmup_sample_stats']:
    for k,v in trace[group].data_vars.items():
        a=np.asarray(v.values)
        if a.dtype.kind in 'biuf':arrays[group+'__'+k]=a.copy()
trace.close();q=arrays['sample_stats__unconstrained_draw'];assert q.shape==(4,8000,13) and np.isfinite(q).all()
assert calls['gradient']>=sum(arrays[g+'__n_steps'].sum() for g in ['sample_stats','warmup_sample_stats']) and all(calls[k]==0 for k in ['value','hessian','hvp'])
np.savez_compressed(out/'DRAWS-STATS.npz',**arrays);target=bs.StanModel(str(so),data=data.read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);indices=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,12)]]
values=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[indices] for x in q.reshape(-1,13)]).reshape(4,8000,13);values=np.concatenate([values,np.exp(values[:,:,2:])],axis=2);assert np.isfinite(values).all();np.savez_compressed(out/'FUNCTIONALS.npz',values=values)
ds=az.convert_to_dataset({'p':values});stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]};stats.update(mean=values.mean((0,1)),sd=values.reshape(-1,24).std(0,ddof=1));div=int(arrays['sample_stats__diverging'].sum())
passed=all(np.isfinite(v).all() for v in stats.values()) and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=1000 and min(stats['tail'])>=1000 and div==0
result=dict(scenario=scenario,rep=rep,seed=seed,passed=bool(passed),divergences=div,calls=calls,seconds=elapsed,stats={k:v.tolist() for k,v in stats.items()},inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),STUDY/'GP-FRESH-REFERENCE-PROTOCOL.md',so,data,source,shim]})
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(scenario=scenario,rep=rep,passed=bool(passed),divergences=div)),flush=True)
