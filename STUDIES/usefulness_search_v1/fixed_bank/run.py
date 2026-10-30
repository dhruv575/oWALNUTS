import concurrent.futures,hashlib,json,random,shutil,sys,time
from pathlib import Path
import psutil
root=Path(__file__).resolve().parent;out=root/'run01';out.mkdir(exist_ok=False)
assert shutil.disk_usage('/').free>=1024**3 and shutil.disk_usage('/dev/shm').free>=2*1024**3 and psutil.virtual_memory().available>=18*1024**3
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
inputs={str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['bank.py','validate.py','experiment.py','run.py','PROTOCOL.md']};(out/'INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
v=out/'validation';v.mkdir();r=execute([sys.executable,str(root/'validate.py')],str(root),180,v,2*1024**3,32*1024**2,v/'worker.log',output_scan_interval=2);(v/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained'] and json.loads((root/'VALIDATION.json').read_text())['passed']
jobs=[dict(d=d,arm=arm,seed=seed) for d in [1,8] for arm in ['local','augmented','bank','is'] for seed in range(942100001,942100017)];random.Random(942000001).shuffle(jobs);(out/'MANIFEST.json').write_text(json.dumps(jobs,indent=2)+'\n');t=time.monotonic()
def run(item):
 i,j=item;p=out/f'{i:03d}';p.mkdir();r=execute([sys.executable,str(root/'experiment.py'),str(j['d']),j['arm'],str(j['seed']),str(p)],str(root),600,p,2*1024**3,32*1024**2,p/'worker.log',output_scan_interval=2);(p/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');return dict(index=i,**j,**r)
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for f in concurrent.futures.as_completed([pool.submit(run,item) for item in enumerate(jobs)]):
  results.append(f.result());(out/'PROGRESS.json').write_text(json.dumps(dict(completed=len(results),seconds=time.monotonic()-t))+'\n')
(out/'FINAL.json').write_text(json.dumps(dict(results=results,seconds=time.monotonic()-t,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n')
