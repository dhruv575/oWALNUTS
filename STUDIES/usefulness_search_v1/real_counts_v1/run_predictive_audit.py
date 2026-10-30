import concurrent.futures,json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
jobs=json.loads((base/'JOBS.json').read_text());root=base/'audit01';root.mkdir(exist_ok=False)
def run(i):
    out=root/jobs[i]['name'];out.mkdir();s=execute([sys.executable,str(base/'audit_predictive_worker.py'),str(i)],str(base),300,out,768*1024**2,16*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');return dict(name=jobs[i]['name'],passed=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists(),supervision=s)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for f in concurrent.futures.as_completed([pool.submit(run,i) for i in range(36)]):
        row=f.result();rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(name=row['name'],passed=row['passed'])),flush=True)
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=all(x['passed'] for x in rows),rows=rows),indent=2)+'\n')
