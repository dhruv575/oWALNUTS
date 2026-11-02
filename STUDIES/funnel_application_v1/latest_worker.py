import os,sys,time,json,hashlib
from pathlib import Path
START=time.perf_counter()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
os.environ['XDG_CACHE_HOME']=str(Path(sys.argv[-1]).parent/'cache')
if sys.argv[2] != 'walnuts_old':sys.path.insert(0,'/dev/shm/owalnuts-latest-e7139bed/integrations/python/python')
from backend import *
import nutpie,arviz as az
def diagnose(f,reference,div=0,depth=0):
    continuous=f[...,:26];ds=az.convert_to_dataset({'p':continuous});stats={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]}
    mean=f.mean((0,1));refmean=np.array(reference['mean']);refsd=np.array(reference['sd']);errors=abs(mean-refmean);mcse=[]
    for j in [26,27]:
        v=f[...,j];mcse.append(0. if v.var()==0 else float(np.asarray(az.mcse(az.convert_to_dataset({'p':v}),method='mean').p)))
    health=bool(all(np.isfinite(v).all() for v in stats.values()) and max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400 and div==0 and depth==0)
    accuracy=bool(reference['passed'] and np.all(errors[:26]<=np.maximum(.05*refsd[:26],4*stats['mcse'])) and max(errors[26:])<=.02)
    precision=bool(max(stats['mcse']/refsd[:26])<=.05 and max(mcse)<=.01)
    return dict(passed=health and accuracy and precision,health=health,accuracy=accuracy,precision=precision,mean=mean.tolist(),sd=f.reshape(-1,28).std(0,ddof=1).tolist(),errors=errors.tolist(),probability_mcse=mcse,stats={k:[float(v) if np.isfinite(v) else None for v in values] for k,values in stats.items()})
def main(case,engine,space,accept,seed,phase,destination):
    out=Path(destination);out.mkdir(exist_ok=False);seed=int(seed);accept=float(accept);data=json.loads((BASE/(case+'.json')).read_text());reference=json.loads((BASE/'references'/(case+'.json')).read_text());assert reference['passed']
    draws,warmup=(int(phase.split('_')[1]),1000);b=Backend(data,space,seed);start=time.perf_counter()
    if engine.startswith('walnuts'):
        trace=owalnuts.sample(b.walnuts,dim=14,init=b.starts,chains=4,threads=1,warmup=warmup,draws=draws,seed=seed,tuning=owalnuts.Tuning(max_depth=11,max_error=1.),adaptation=owalnuts.Adaptation(target_accept=accept))
        q=trace.samples;div=int(trace.divergent[:,warmup:].sum());depth=int((trace.depth[:,warmup:]>=11).sum())
    else:
        trace=nutpie.sample(b.nuts,chains=4,cores=1,tune=warmup,draws=draws,seed=seed,progress_bar=False,save_warmup=False,target_accept=accept,maxdepth=11,low_rank_modified_mass_matrix=False,transform_adapt=False)
        q=np.asarray(trace.posterior.q.values).copy();div=int(trace.sample_stats.diverging.sum());depth=int(trace.sample_stats.maxdepth_reached.sum());trace.close();assert b.initial_calls==4
    kernel=time.perf_counter()-start;counts=b.counts();b.close();p=to_physical(q,data,space);f=features(p);summary=diagnose(f,reference,div,depth)
    np.savez_compressed(out/'DRAWS.npz',q=q)
    result=dict(runtime_path=owalnuts.__file__,extension_sha256=hashlib.sha256(Path(owalnuts._owalnuts.__file__).read_bytes()).hexdigest(),case=case,engine=engine,space=space,accept=accept,seed=seed,phase=phase,warmup=warmup,draws=draws,kernel_seconds=kernel,worker_seconds=time.perf_counter()-START,target_calls=counts[0],target_errors=counts[1],divergences=div,depth_hits=depth,summary=summary)
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k!='summary'}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
