"""Twelve isolated literal copies exercise full bounded-integral workloads."""
import argparse,os,time
from pathlib import Path
import numpy as np
from worker import admit,exclusive,startup,save_array,sha
from bounded_loss import evaluate,baseline,precision,score,action,COST
def literal(n):
    j=np.arange(4*n).reshape(4,n);a=np.empty((4,n,4));a[:,:,0]=-10+.04*(j%7);a[:,:,1]=np.log(.12+.002*(j%5));a[:,:,2]=.0001*((j%9)-4);a[:,:,3]=-10+.03*(j%11);return a
def run(spec,out,shard):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);os.environ['NUMBA_CACHE_DIR']=str(out/'numba-cache');start=time.perf_counter();result=dict(status='failed',shard=shard,pid=os.getpid(),candidate_draws=1600,reference_draws=16000,integral_gate_pass=False,precision_pass=False,policy_checks=False)
    exclusive(out/'readiness-start.json',result)
    try:
        backend,result['startup_seconds']=startup(spec)
        for kind,n,cap in [('candidate',400,spec['bounds']['origin_seconds']),('reference',4000,spec['bounds']['reference_origin_seconds'])]:
            value=evaluate(literal(n),backend,time.perf_counter()+cap);a=value.pop('per_chain_draw_downside');result[kind]=value
            value['functional']=save_array(out/(kind+'-functional.npy'),a);value['precision']=precision(a);value['score']=score(value['mean_downside'],.001)
        result['baseline']=baseline(dict(status='ok',location=0.,scale=.01,df=5),backend.Backend('exact_t5'),time.perf_counter()+30)
        result['baseline']['score']=score(result['baseline']['mean_downside'],.001)
        result['integral_gate_pass']=all(result[k]['status']=='ok' for k in ('candidate','reference','baseline'));result['precision_pass']=all(result[k]['precision']['status']=='available' for k in ('candidate','reference'));result['policy_checks']=action(COST)=='retain' and action(COST+1e-10)=='convert'
        if not all(result[k] for k in ('integral_gate_pass','precision_pass','policy_checks')):raise ValueError('Literal acceptance checks failed')
        result['status']='complete'
    except Exception as error:result['error']=repr(error)
    result['seconds']=time.perf_counter()-start;exclusive(out/'readiness-final.json',result);return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--shard',type=int,required=True);p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    if not 0<=a.shard<12:raise ValueError('Fixed shard required')
    spec=admit(a.manifest,expected_status='development_authorized');before=sha(a.manifest);r=run(spec,a.out,a.shard);admit(a.manifest,expected_status='development_authorized')
    if sha(a.manifest)!=before:raise ValueError('Manifest drift')
    return 0 if r['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
