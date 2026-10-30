import hashlib,json,sys,time,subprocess
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs,nutpie
base=Path(__file__).resolve().parent
runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030')
sys.path.insert(0,str(runtime))
from native_common import counter_handle,counter_read,native_model
group=int(sys.argv[1]);out=base/'results'/str(group);seed=951500001+group
data=base/'GP-TRAIN.json';so=runtime/'models/raw.so';shim=runtime/'preflight/raw/counted_model.so';source=runtime/'models/raw.stan';binary=runtime/'gp-wal-tuned-runner'
assert hashlib.sha256(data.read_bytes()).hexdigest()=='8c328146cfe6e1956256af63bb3b39cfc0d27be4b8ea7b796d842240056b5576'
manifest=json.loads((base/'INPUT-HASHES.json').read_text())
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in manifest.items())
d=json.loads(data.read_text())['N']+2;assert d==81
arrays={};start=time.perf_counter()
if group<3:
    cfg=dict(draws=4000,tune=1100,chains=4,cores=4,seed=seed,save_warmup=True,progress_bar=False,adaptation='diag',target_accept=[.9,.95,.99][group],maxdepth=10,store_unconstrained=True,step_size_jitter=0.)
    (out/'INPUT.json').write_text(json.dumps(cfg,indent=2))
    c=counter_handle(shim);c.ow_reset_target_calls()
    trace=nutpie.sample(native_model(shim,data,source),**cfg)
    calls=counter_read(c)
    for g in ['sample_stats','warmup_sample_stats']:
        for k,v in trace[g].data_vars.items():
            a=np.asarray(v.values)
            if a.dtype.kind in 'biuf':arrays[g+'__'+k]=a.copy()
    trace.close();q=arrays['sample_stats__unconstrained_draw'];div=int(arrays['sample_stats__diverging'].sum())
    assert calls['gradient']>=sum(arrays[g+'__n_steps'].sum() for g in ['sample_stats','warmup_sample_stats']) and all(calls[k]==0 for k in ['value','hessian','hvp'])
else:
    cfg=dict(model=str(so),data=str(data),starts=np.random.default_rng(seed).uniform(-2,2,(4,d)).tolist(),seed=seed,warmup=1100,draws=4000,arm='dense',target_accept=.9)
    (out/'INPUT.json').write_text(json.dumps(cfg,indent=2))
    subprocess.run([str(binary),str(out/'INPUT.json'),str(out/'RAW.json')],check=True)
    raw=json.loads((out/'RAW.json').read_text());q=np.asarray(raw['draws']);div=int(raw['retained_divergences']);calls=dict(value=0,gradient=raw['target_calls'],hessian=0,hvp=0)
    arrays['sample_stats__unconstrained_draw']=q
seconds=time.perf_counter()-start
assert q.shape==(4,4000,d) and np.isfinite(q).all()
np.savez_compressed(out/'DRAWS-STATS.npz',**arrays)
target=bs.StanModel(str(so),data=data.read_text(),seed=1);names=target.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,80)]]
v=np.asarray([target.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,d)]).reshape(4,4000,d);v=np.concatenate([v,np.exp(v[:,:,2:])],axis=2);assert v.shape==(4,4000,160) and np.isfinite(v).all()
np.savez_compressed(out/'FUNCTIONALS.npz',values=v)
ds=az.convert_to_dataset({'p':v});stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda x:az.rhat(x,method='rank')),('bulk',lambda x:az.ess(x,method='bulk')),('tail',lambda x:az.ess(x,method='tail')),('mcse',lambda x:az.mcse(x,method='mean'))]};stats.update(mean=v.mean((0,1)),sd=v.reshape(-1,160).std(0,ddof=1))
passed=all(np.isfinite(x).all() for x in stats.values()) and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400 and div==0
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in manifest.items())
result=dict(group=group,seed=seed,method='native' if group<3 else 'wal',passed=bool(passed),divergences=div,seconds=seconds,calls=calls,stats={k:x.tolist() for k,x in stats.items()})
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps({k:result[k] for k in ['group','method','passed','divergences','seconds']}),flush=True)
