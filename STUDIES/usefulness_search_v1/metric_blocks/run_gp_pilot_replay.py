import json,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_pilot_replay01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
rows=[]
for fold in range(4):
    d=r/f'fold-{fold}';d.mkdir();result=execute([sys.executable,str(p/'gp_pilot_replay_worker.py'),str(d),str(fold)],str(p),180,d,2*1024**3,64*1024**2,d/'worker.log',output_scan_interval=2)
    (d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');complete=result['exit_code']==0 and result['group_drained'] and (d/'SUMMARY.json').exists()
    row=json.loads((d/'SUMMARY.json').read_text()) if complete else dict(fold=fold,passed=False,supervision=result);rows.append(row);print(json.dumps(dict(fold=fold,passed=row['passed'])),flush=True)
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,passed=all(x['passed'] for x in rows),rows=rows),indent=2)+'\n')
