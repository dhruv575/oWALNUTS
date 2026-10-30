import concurrent.futures,hashlib,json,os,random,shutil,sys,time
from pathlib import Path
import psutil
root=Path(__file__).resolve().parent;out=root/'mixing01';out.mkdir(exist_ok=False)
assert shutil.disk_usage('/').free>=1024**3 and shutil.disk_usage('/dev/shm').free>=2*1024**3 and psutil.virtual_memory().available>=18*1024**3
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
inputs={str(root/n):hashlib.sha256((root/n).read_bytes()).hexdigest() for n in ['mixing.py','move.py','MIXING-PROTOCOL.md','run_mixing.py']}
jobs=[dict(d=d,start=start,arm=arm,seed=seed) for d in [1,8] for start in ['cold','covered'] for arm in ['local','ensemble'] for seed in range(941000001,941000017)]
random.Random(941000000).shuffle(jobs);(out/'MANIFEST.json').write_text(json.dumps(dict(inputs=inputs,jobs=jobs),indent=2)+'\n')
t=time.monotonic()
def run(item):
 i,j=item;folder=out/f'{i:03d}';folder.mkdir()
 r=execute([sys.executable,str(root/'mixing.py'),str(j['d']),j['start'],j['arm'],str(j['seed']),str(folder)],str(root),600,folder,2*1024**3,32*1024**2,folder/'worker.log',output_scan_interval=2)
 (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');return dict(index=i,**j,**r)
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for f in concurrent.futures.as_completed([pool.submit(run,item) for item in enumerate(jobs)]):
  results.append(f.result());(out/'PROGRESS.json').write_text(json.dumps(dict(completed=len(results),total=len(jobs),seconds=time.monotonic()-t))+'\n')
(out/'FINAL.json').write_text(json.dumps(dict(results=results,seconds=time.monotonic()-t,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n')
