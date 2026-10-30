import concurrent.futures,json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
jobs=json.loads((base/'JOBS.json').read_text());prior=json.loads((base/'results/SUMMARY.json').read_text());failed={x['name'] for x in prior['rows'] if not x['completed']};assert failed=={jobs[i]['name'] for i in [24,25,34]}
root=base/'repair01';root.mkdir(exist_ok=False)
def run(i):
    out=root/jobs[i]['name'];out.mkdir();s=execute([sys.executable,str(base/'repair_predictive_probability.py'),str(i)],str(base),300,out,768*1024**2,32*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');return dict(name=jobs[i]['name'],completed=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists(),supervision=s)
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:rows=list(pool.map(run,[24,25,34]))
(root/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows),indent=2)+'\n');print(json.dumps([dict(name=x['name'],completed=x['completed']) for x in rows]))
