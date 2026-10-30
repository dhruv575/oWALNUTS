import json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_wal_calibration01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
assert json.loads((l/'gp_wal_driver_test02/SUMMARY.json').read_text())['passed']
rows=[];configs=[(m,a) for a in [.8,.9,.99] for m in ['walnuts_auto','walnuts_dense']]
for si,seed in enumerate([946400001,946400002]):
    for mode,accept in configs if si==0 else list(reversed(configs)):
        assert shutil.disk_usage(r).free>1024**3;folder=r/f'{mode}-{accept}-{seed}';folder.mkdir();result=execute([sys.executable,str(p/'gp_wal_calibration_worker.py'),str(folder),mode,str(accept),str(seed)],str(p),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));completed=result['exit_code']==0 and result['group_drained'] and (folder/'SUMMARY.json').exists();row=json.loads((folder/'SUMMARY.json').read_text()) if completed else dict(mode=mode,target_accept=accept,seed=seed,passed=False,completed=False);rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(dict(completed=len(rows),mode=mode,accept=accept,passed=row['passed'],worker_completed=completed)),flush=True)
eligible=[]
for mode,accept in configs:
    subset=[x for x in rows if x['mode']==mode and x['target_accept']==accept]
    if len(subset)==2 and all(x['passed'] for x in subset):eligible.append(dict(mode=mode,target_accept=accept,calls_per_min_bulk_ess_geomean=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in subset]))))))
eligible.sort(key=lambda x:(x['calls_per_min_bulk_ess_geomean'],-x['target_accept'],x['mode']!='walnuts_auto'));(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,eligible=eligible,selected=eligible[0] if eligible else None),indent=2)+'\n')
