import hashlib,json,sys,time,subprocess
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs,nutpie
from native_common import LOCAL,STUDY,model_files,counter_handle,counter_read,native_model
root=Path(sys.argv[1]);mode=sys.argv[2];accept=float(sys.argv[3]);seed=int(sys.argv[4]);name='gp_pois_regr-gp_pois_regr';fold=int(sys.argv[5]);transform=sys.argv[6]
if transform=='raw':
    so,data,source=model_files(name);shim=LOCAL/'nativemodels01'/name/'counted_model.so'
else:
    target_dir='bounded_gp_target01' if transform=='bounded' else 'gp_transport_target01'
    target_build=json.loads((LOCAL/target_dir/'SUMMARY.json').read_text());assert target_build['passed'];so=Path(target_build['library']);assert hashlib.sha256(so.read_bytes()).hexdigest()==target_build['library_sha256'];data=LOCAL/target_dir/f'fold-{fold}-{transform}.json';source=STUDY/('bounded_gp.stan' if transform=='bounded' else 'gp_transport.stan');shim=LOCAL/('bounded_gp_counter01' if transform=='bounded' else 'gp_transport_smoke01')/'counted_model.so'
build=json.loads((shim.parent/'BUILD.json').read_text());assert hashlib.sha256(shim.read_bytes()).hexdigest()==build['shim_sha256'];refpath=LOCAL/'localscaled01/REFERENCES.json';ref=json.loads(refpath.read_text())[name];assert ref['passed']
kwargs=dict(draws=8000,tune=1100,chains=4,cores=4,seed=seed,save_warmup=True,progress_bar=False,adaptation=mode,target_accept=accept,maxdepth=10,store_unconstrained=True,step_size_jitter=0.)
if mode=='low_rank':kwargs.update(mass_matrix_eigval_cutoff=2.,mass_matrix_gamma=1e-5)
build=json.loads((LOCAL/'gp_wal_build02/SUMMARY.json').read_text());assert build['passed'];artifact=build['rows'][1];binary=Path(artifact['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==artifact['binary_sha256']
arrays={}
if mode.startswith('walnuts_'):
    spec=dict(model=str(so),data=str(data),starts=np.random.default_rng(seed).uniform(-2,2,(4,13)).tolist(),seed=seed,warmup=1100,draws=8000,arm=mode.removeprefix('walnuts_'),target_accept=accept);(root/'INPUT.json').write_text(json.dumps(spec,indent=2));t0=time.perf_counter();subprocess.run([str(binary),str(root/'INPUT.json'),str(root/'RAW.json')],check=True);elapsed=time.perf_counter()-t0;raw=json.loads((root/'RAW.json').read_text());q=np.asarray(raw['draws']);counts=dict(value=0,gradient=raw['target_calls'],hessian=0,hvp=0);arrays['sample_stats__unconstrained_draw']=q;arrays['sample_stats__diverging']=np.asarray([raw['retained_divergences']])
else:
    (root/'INPUT.json').write_text(json.dumps(dict(model=str(so),data=str(data),settings=kwargs),indent=2));c=counter_handle(shim);c.ow_reset_target_calls();t0=time.perf_counter();trace=nutpie.sample(native_model(shim,data,source),**kwargs);elapsed=time.perf_counter()-t0;counts=counter_read(c);assert all(counts[k]==0 for k in ['value','hessian','hvp'])
    for group in ['sample_stats','warmup_sample_stats']:
        for k,v in trace[group].data_vars.items():
            a=np.asarray(v.values)
            if a.dtype.kind in 'biuf':arrays[group+'__'+k]=a.copy()
    q=arrays['sample_stats__unconstrained_draw'];trace.close();assert counts['gradient']>=sum(arrays[g+'__n_steps'].sum() for g in ['sample_stats','warmup_sample_stats'])
assert q.shape[:2]==(4,8000) and np.isfinite(q).all();np.savez_compressed(root/'DRAWS-STATS.npz',**arrays)
target=bs.StanModel(str(so),data=data.read_text(),seed=1)
def cname(n):
    parts=n.split('.');return parts[0]+'['+','.join(parts[1:])+']' if len(parts)>1 and all(x.isdigit() for x in parts[1:]) else n
names=[cname(n) for n in target.param_names(include_tp=True,include_gq=False)];ix=[names.index(n) for n in ref['names']];d=q.shape[-1];values=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,d)]).reshape(4,8000,-1);np.savez_compressed(root/'FUNCTIONALS.npz',values=values);ds=az.convert_to_dataset({'p':values});mean=values.mean((0,1));sd=values.reshape(-1,values.shape[-1]).std(0,ddof=1);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);rh=np.asarray(az.rhat(ds,method='rank').p);mcse=np.asarray(az.mcse(ds,method='mean').p);z=abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2);delta=abs(mean-ref['mean'])/ref['sd'];sderr=abs(sd/ref['sd']-1);div=int(arrays['sample_stats__diverging'].sum());passed=all(np.isfinite(x).all() for x in [mean,sd,bulk,tail,rh,mcse,z,delta,sderr]) and max(rh)<=1.01 and min(bulk)>=400 and min(tail)>=400 and div==0 and max(z)<=4.5 and max(delta)<=.1 and max(sderr)<=.1
out=dict(fold=fold,transform=transform,model=name,mode=mode,target_accept=accept,seed=seed,passed=bool(passed),calls=counts,post_import_sampling_seconds=elapsed,rhat=float(max(rh)),bulk=float(min(bulk)),tail=float(min(tail)),divergences=div,max_z=float(max(z)),max_mean_sd=float(max(delta)),max_sd_error=float(max(sderr)),calls_per_min_bulk_ess=float(counts['gradient']/min(bulk)),maxdepth_hits=int(arrays['sample_stats__maxdepth_reached'].sum()) if not mode.startswith('walnuts_') else None,final_step_sizes=arrays['sample_stats__step_size'][:,-1].tolist() if not mode.startswith('walnuts_') else None,functionals={k:v.tolist() for k,v in dict(mean=mean,sd=sd,bulk=bulk,tail=tail,rhat=rh,mcse=mcse).items()},inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),STUDY/'BOUNDED-GP-VALIDATION-PROTOCOL.md',so,data,source,shim,refpath,binary]});(root/'SUMMARY.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');print(json.dumps({k:out[k] for k in ['mode','target_accept','seed','passed','rhat','bulk','tail','divergences','calls_per_min_bulk_ess']}),flush=True)
