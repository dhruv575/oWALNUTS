"""Literal end-to-end comparator readiness through the immutable evidence loop."""
import argparse,os,sys,time
from pathlib import Path
import numpy as np
from literal_reference import load,write
from rolling_reuse_readiness import validate
from rolling_nutpie_adapter import DrawResident
from resource_monitor import execute

def worker(manifest,out):
    spec=validate(manifest);out=Path(out);out.mkdir(exist_ok=False)
    loop=load(spec['linear_runner'],'fixed_linear_loop');evaluator=load(spec['evaluator'],'fixed_reuse_evaluator')
    seeds=spec['seed_map']
    if spec['seeds']!=[seeds['initial'],seeds['initial']+1,seeds['warm'],seeds['warm']+1,seeds['warm']+4,seeds['warm']+5]:raise ValueError('Fixed external seed map')
    settings=dict(stan_path=spec['stan'],capture_path=spec['capture'],bridgestan_sdk=str(Path(spec['sdk_makefile']).parent),adapter=spec['adapter'],engine_options=spec['engine_options'])
    y=np.resize(np.array([.001,-.002,.0005,0.,.003]),253)
    def score(draws,window,label,tick):
        return dict(evaluator.evaluate_observation(draws,label,deadline=time.monotonic()+20),status='ok')
    result=loop.run_lane(y,updates=2,seeds=seeds,score_ticks=[1,2],retain_ticks=[1,2],k=400,output=out/'lane',score_hook=score,
        engine_factory=lambda history,seed_map:DrawResident(history,seed_map,settings,out/'nutpie',[1,2]))
    validate(manifest);write(out/'FINAL.json',result)
    return 0 if result['status']=='complete' else 1

def supervise(manifest,out):
    validate(manifest);out=Path(out);out.mkdir(exist_ok=False)
    if len(os.sched_getaffinity(0))!=4:raise ValueError('Four allocated cores')
    receipt=execute([sys.executable,str(Path(__file__).resolve()),str(manifest),str(out/'fit'),'--worker'],str(out),900,out,
        4*1024**3,512*1024**2,out/'worker.log',output_scan_interval=5,utilization_path=out/'utilization.jsonl',phase_reserved_cores={'startup':4})
    write(out/'SUPERVISION.json',receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('out');p.add_argument('--worker',action='store_true');a=p.parse_args()
    raise SystemExit((worker if a.worker else supervise)(a.manifest,a.out))
