"""Bounded Linux engineering replay; no acquisition or scientific seed use."""
import argparse,json,os,time
from pathlib import Path
from worker import admit
from linear_runner_snapshot import exclusive
from resource_monitor_snapshot import execute

STAGES=[('candidate',180),('baselines',90),('reference',300),('report',30)]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--out',required=True);parser.add_argument('--inner',action='store_true');args=parser.parse_args()
    manifest=Path(args.manifest).resolve();spec=admit(manifest,expected_status='development_authorized');root=Path(args.out).resolve()
    for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
    if not args.inner:
        root.mkdir(parents=True,exist_ok=False)
        exclusive(root/'OUTER-START.json',dict(scope='Fixed literal engineering replay',cap_seconds=600))
        result=execute(['taskset','-c','0-3',spec['python'],str(Path(__file__).resolve()),'--inner','--manifest',str(manifest),'--out',str(root)],Path(__file__).parent,600,root,4*1024**3,1024**3,root/'outer.log',ownership_env='OWALNUTS_READINESS_TOKEN',output_scan_interval=2)
        result['complete']=result['status']=='exited' and result.get('exit_code')==0 and result.get('group_drained')is True
        admit(manifest,expected_status='development_authorized');exclusive(root/'OUTER-FINAL.json',result)
        return 0 if result['complete'] else 1
    started=time.monotonic();state=dict(status='running',stages=[]);exclusive(root/'INNER-START.json',state)
    for stage,limit in STAGES:
        cap=min(limit,590-(time.monotonic()-started))
        if cap<=0:state['status']='budget_exhausted';break
        result=execute([spec['python'],str(Path(__file__).with_name('readiness.py')),stage,'--manifest',str(manifest),'--out',str(root/'literal')],Path(__file__).parent,cap,root,4*1024**3,1024**3,root/(stage+'.log'),output_scan_interval=2)
        result['stage']=stage;state['stages'].append(result);exclusive(root/('monitor-'+stage+'.json'),result)
        if result['status']!='exited' or result.get('exit_code')!=0 or result.get('group_drained')is not True:state['status']='failed';break
    else:state['status']='complete'
    admit(manifest,expected_status='development_authorized');state['elapsed_seconds']=time.monotonic()-started;exclusive(root/'INNER-FINAL.json',state)
    return 0 if state['status']=='complete' else 1

if __name__=='__main__':raise SystemExit(main())
