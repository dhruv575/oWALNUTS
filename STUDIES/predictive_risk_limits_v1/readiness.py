"""Literal-only full-size engineering replay, one independently contained shard."""
import argparse,os,time
from pathlib import Path
import numpy as np
from worker import admit,exclusive,sha,startup
from inputs import module
from evaluator import tails,roots,precision,baseline,score

def literal(count):
    # Fixed heterogeneous components; no RNG or market values.
    a=np.empty((4,count,4));j=np.arange(4*count).reshape(4,count)
    a[:,:,0]=-10+.04*(j%7);a[:,:,1]=np.log(.12+.002*(j%5));a[:,:,2]=.0001*((j%9)-4);a[:,:,3]=-10+.03*(j%11)
    return a

def equivalence(draws,backend,deadline):
    a=draws.reshape(-1,4);m=a[:,0]+.95*(a[:,3]-a[:,0]);b=backend.Backend('exact_t5')
    for nodes in (64,128):
        args=(m,np.exp(a[:,1]),a[:,2],5,nodes,deadline,64*1024**2)
        old=backend.ConfiguredReturnCDF(*args,chunk=512,backend=b).quantiles()['quantiles']
        new=roots(backend.ConfiguredReturnCDF(*args,chunk=512,backend=b))['quantiles']
        if not np.allclose(np.asarray(old)[[0,2]],new,rtol=0,atol=1e-12):raise ValueError('Inherited tail root mismatch')
    return True

def run(spec,out,shard):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);os.environ['NUMBA_CACHE_DIR']=str(out/'numba-cache');start=time.perf_counter();result=dict(status='failed',shard=shard,pid=os.getpid(),candidate_draws=1600,reference_draws=16000,equivalence_pass=False,precision_pass=False)
    exclusive(out/'readiness-start.json',result)
    try:
        backend,density,result['startup_seconds']=startup(spec,reference=True)
        small=literal(400);large=literal(4000)
        result['candidate']=tails(small,backend,time.perf_counter()+spec['bounds']['origin_seconds'])
        pipeline_start=time.perf_counter();deadline=pipeline_start+spec['bounds']['reference_origin_seconds']
        result['reference']=tails(large,backend,deadline)
        result['reference_precision']=precision(large,result['reference'],density,deadline)
        result['candidate_precision']=precision(small,result['candidate'],density,deadline)
        result['full_reference_pipeline_seconds']=time.perf_counter()-pipeline_start
        result['precision_pass']=all(result[k]['status']=='available' for k in ['candidate_precision','reference_precision'])
        if not result['precision_pass']:raise ValueError('Literal precision pipeline unavailable')
        result['equivalence_pass']=equivalence(small,backend,time.perf_counter()+60)
        result['literal_score']=score(result['candidate'],.001)
        result['literal_baseline']=score(baseline(dict(status='ok',location=0.,scale=.01,df=5)),.001)
        result['status']='complete'
    except Exception as error:result['error']=repr(error)
    result['seconds']=time.perf_counter()-start;exclusive(out/'readiness-final.json',result);return result

def main():
    p=argparse.ArgumentParser();p.add_argument('--shard',type=int,required=True);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if not 0<=a.shard<12:raise ValueError('Invalid shard')
    spec=admit(a.manifest,expected_status='development_authorized');before=sha(a.manifest);r=run(spec,a.out,a.shard);admit(a.manifest,expected_status='development_authorized')
    if sha(a.manifest)!=before:raise ValueError('Manifest drift')
    return 0 if r['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
