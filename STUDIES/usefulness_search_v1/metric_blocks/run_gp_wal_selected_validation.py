import hashlib,json,sys,shutil
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_wal_selected_validation01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'));from resource_monitor import execute
cal=l/'gp_wal_calibration01/SUMMARY.json';s=json.loads(cal.read_text());selected=s['selected'];assert selected is not None;(r/'SELECTION.json').write_text(json.dumps(dict(selected=selected,calibration_sha256=hashlib.sha256(cal.read_bytes()).hexdigest(),calibration_gradient_calls=sum(x['calls']['gradient'] for x in s['rows'])),indent=2));rows=[]
for i,seed in enumerate(range(946500001,946500009)):
    arms=[('low_rank',.99),(selected['mode'],selected['target_accept'])]
    for mode,accept in arms if i%2==0 else list(reversed(arms)):
        assert shutil.disk_usage(r).free>1024**3;folder=r/f'{mode}-{seed}';folder.mkdir();result=execute([sys.executable,str(p/'gp_wal_selected_worker.py'),str(folder),mode,str(accept),str(seed)],str(p),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2));completed=result['exit_code']==0 and result['group_drained'] and (folder/'SUMMARY.json').exists();row=json.loads((folder/'SUMMARY.json').read_text()) if completed else dict(mode=mode,seed=seed,passed=False,completed=False);rows.append(row);(r/'PROGRESS.json').write_text(json.dumps(rows,indent=2));print(json.dumps(dict(completed=len(rows),mode=mode,seed=seed,passed=row['passed'],worker_completed=completed)),flush=True)
all_pass=all(x['passed'] for x in rows);comparison=None
if all_pass:
    ratios=[]
    for seed in range(946500001,946500009):
        n=next(x for x in rows if x['mode']=='low_rank' and x['seed']==seed);w=next(x for x in rows if x['mode']==selected['mode'] and x['seed']==seed);ratios.append(n['calls_per_min_bulk_ess']/w['calls_per_min_bulk_ess'])
    logs=np.log(ratios);boot=np.random.default_rng(946600001).choice(logs,(10000,8),replace=True).mean(1);comparison=dict(walnuts_native_efficiency_ratio=float(np.exp(logs.mean())),interval=np.exp(np.quantile(boot,[.025,.975])).tolist(),paired_ratios=ratios)
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all_pass,signal_passed=all_pass and comparison['interval'][0]>1.2,comparison=comparison,rows=rows),indent=2)+'\n')
