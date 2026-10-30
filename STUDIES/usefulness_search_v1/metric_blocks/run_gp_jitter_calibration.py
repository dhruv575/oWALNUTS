import json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_jitter_calibration01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert json.loads((l/'gp_jitter_test02/SUMMARY.json').read_text())['passed']
rows=[];configs=[0.,.25,.5,.75]
for si,seed in enumerate([947800001,947800002]):
    for amplitude in configs if si==0 else list(reversed(configs)):
        mode='walnuts_dense';accept=.9
        assert shutil.disk_usage(r).free>1024**3;folder=r/f'jitter-{amplitude}-{seed}';folder.mkdir();result=execute([sys.executable,str(p/'gp_jitter_calibration_worker.py'),str(folder),mode,str(accept),str(seed),str(amplitude)],str(p),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));completed=result['exit_code']==0 and result['group_drained'] and (folder/'SUMMARY.json').exists();row=json.loads((folder/'SUMMARY.json').read_text()) if completed else dict(amplitude=amplitude,mode=mode,target_accept=accept,seed=seed,passed=False,completed=False);rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(dict(completed=len(rows),amplitude=amplitude,mode=mode,accept=accept,passed=row['passed'],worker_completed=completed)),flush=True)
eligible=[]
for amplitude in configs:
    subset=[x for x in rows if x['amplitude']==amplitude]
    if len(subset)==2 and all(x['passed'] for x in subset):eligible.append(dict(amplitude=amplitude,calls_per_min_bulk_ess_geomean=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in subset]))))))
eligible.sort(key=lambda x:(x['calls_per_min_bulk_ess_geomean'],x['amplitude']));(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,eligible=eligible,selected=eligible[0] if eligible else None),indent=2)+'\n')
