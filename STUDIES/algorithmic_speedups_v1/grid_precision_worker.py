import os,sys,time,json
from pathlib import Path
START=time.perf_counter()
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
os.environ['XDG_CACHE_HOME']=str(Path(sys.argv[-1]).parent/'cache')
import numpy as np,nutpie
from grid_backend import Native
from spatial_worker import diagnostics
BASE=Path(__file__).resolve().parent
def main(method,seed,destination):
    seed=int(seed);out=Path(destination);out.mkdir(exist_ok=False)
    data=json.loads((BASE/'GP-TRAIN.json').read_text());target=Native(data,seed);model=target.model
    start=time.perf_counter()
    trace=nutpie.sample(target.compiled,draws=4000,tune=1000,chains=4,cores=4,seed=seed,progress_bar=False,save_warmup=False,adaptation='diag',target_accept=.99,maxdepth=12,step_size_jitter=0.)
    q=np.asarray(trace.posterior.q).copy();div=int(trace.sample_stats.diverging.sum());depth=int(trace.sample_stats.maxdepth_reached.sum());trace.close()
    sampling_seconds=time.perf_counter()-start;counts=target.counts();target.close()
    np.savez_compressed(out/'DRAWS.npz',q=q)
    physical=[]
    for row in q.reshape(-1,205):
        field=model.field(model.factor(row[:2]),row[2:]);physical.append(np.r_[np.exp(row[:2]),np.asarray(data['coef_scale'])*row[2:5],field,np.exp(field)])
    values=np.array(physical).reshape(4,4000,-1);passed,stats=diagnostics(values)
    result=dict(method=method,seed=seed,passed=passed and div==0 and depth==0,divergences=div,depth_hits=depth,sampling_seconds=sampling_seconds,worker_seconds=time.perf_counter()-START,target_calls=counts[0],target_errors=counts[1],stats=stats,scope='Exploratory pilot; independent spatial reference not qualified')
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps({k:v for k,v in result.items() if k!='stats'}),flush=True)
if __name__=='__main__':main(*sys.argv[1:])
