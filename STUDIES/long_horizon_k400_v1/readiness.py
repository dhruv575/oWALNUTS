"""Literal-only integrated readiness; deliberately never calls data_model.generate."""
import argparse,concurrent.futures,json,os,sys,time
from pathlib import Path
import numpy as np
from runtime import admit,module,evaluator,save_array
from linear_runner import run_lane,exclusive
from checkpoint import checkpoint
from resource_monitor import execute
from worker import reference_job

def literal():return .005*np.sin(np.arange(2251,dtype=float)*.37)+.001*np.cos(np.arange(2251,dtype=float)*.11)

def lane(spec,root,index):
    import owalnuts
    deps=spec['dependencies'];backend=module(deps['resident_adapter'],'literal_resident');target=module(deps['sv_target'],'literal_target');score=evaluator(spec)
    # Reuse only prior development seeds; duplication between literal lanes is intentional.
    seeds=dict(initial=99371041,warm=99371042)
    result=run_lane(literal(),updates=4,seeds=seeds,score_ticks=[1,4],retain_ticks=[1,4],engine_factory=lambda y,s:backend.DrawResident(owalnuts,target,y,s),score_hook=lambda a,w,y,t:checkpoint(a,w,y,t,score),output=root/f'lane-{index}')
    if result['status']!='complete':raise ValueError('Literal lane incomplete '+repr(result))

def main():
    p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('output');p.add_argument('--lane',type=int);p.add_argument('--reference',action='store_true');a=p.parse_args();spec=admit(a.manifest,readiness=True);root=Path(a.output)
    if a.lane is not None:lane(spec,root,a.lane);return
    if a.reference:
        dev=json.loads(json.dumps(spec));dev['protocol']['seeds']['reference_base']=99371042
        if reference_job(dev,root,0)['status']!='complete':raise ValueError('Literal reference incomplete')
        admit(a.manifest,readiness=True);return
    root.mkdir(exist_ok=False);here=Path(__file__).resolve().parent;deadline=time.monotonic()+570;records=[]
    def execute_one(command,name,scope):
        r=execute(command,here,max(.001,deadline-time.monotonic()),scope,4*1024**3,1024**3,root/(name+'.log'),output_scan_interval=2);exclusive(root/(name+'-monitor.json'),r)
        if r.get('exit_code')!=0 or r.get('status')!='exited' or not r.get('group_drained') or r.get('orphaned_children_after_leader_exit'):raise RuntimeError('Literal job failed '+name)
        return r
    records.append(execute_one([sys.executable,'-m','unittest','discover','-s',str(here),'-p','test_*.py'],'fixtures',root))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(execute_one,['taskset','-c',cores,sys.executable,str(__file__),a.manifest,str(root),'--lane',str(i)],f'lane-{i}',root/f'lane-{i}') for i,cores in enumerate(('0-3','4-7','8-11','12-15'))]
        for f in futures:records.append(f.result())
    # Same production reference worker/extractor/scorer, fixed development seed and literal data.
    data=root/'data';data.mkdir();y=literal();entries={name:save_array(data/(name+'.npy'),y) for name in ('control_y','shift_y')};exclusive(data/'DATA.json',dict(arrays=entries))
    records.append(execute_one(['taskset','-c','0-3',sys.executable,str(__file__),a.manifest,str(root),'--reference'],'reference',root/'references'))
    admit(a.manifest,readiness=True);exclusive(root/'READINESS.json',dict(status='complete',study_data_generated=False,reserved_study_seeds_consumed=False,development_seeds=[99371041,99371042],planned_lanes=4,updates_per_lane=4,reference_draw_shape=[4,4000,4],phase_monitors=records,source_runtime_postcheck=True))
if __name__=='__main__':main()
