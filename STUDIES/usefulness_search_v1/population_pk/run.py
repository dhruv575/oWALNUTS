import concurrent.futures,hashlib,json,os,queue,random,shutil,sys,time
from pathlib import Path
ROOT=Path('/dev/shm/population-pk-20261029')
MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
MONITOR=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py')
sys.path.insert(0,str(MONITOR.parent))
from resource_monitor import execute
jobs=[(m,r) for m in ('linear','nonlinear') for r in range(4)]
random.Random(928199999).shuffle(jobs)
out=ROOT/'run01';out.mkdir(exist_ok=False)
OLD=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029')
files=list(ROOT.glob('*.py'))+[ROOT/'PROTOCOL.md',MONITOR,OLD/'source/backend.py',OLD/'source_data/Theoph.csv',OLD/'build/model_model.so',OLD/'build/adapter.so']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out/'MANIFEST.json').write_text(json.dumps(dict(jobs=jobs,dependencies=hashes,pid=os.getpid()),indent=2)+'\n')
cores=queue.Queue()
for c in range(8):cores.put(str(c))
def job(item):
 i,(m,rep)=item;folder=out/f'{i:03d}';folder.mkdir();core=cores.get()
 try:
  if shutil.disk_usage('/').free<1024**3 or shutil.disk_usage(ROOT).free<4*1024**3:return dict(index=i,status='not_started_disk_floor')
  cmd=['taskset','-c',core,sys.executable,str(ROOT/'worker.py'),m,str(rep),str(folder/'result')]
  r=execute(cmd,str(ROOT),300,folder,1024**3,8*1024**2,folder/'worker.log',output_scan_interval=2)
  (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['group_drained'];return dict(index=i,**r)
 finally:cores.put(core)
done=[];start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
 for f in concurrent.futures.as_completed([pool.submit(job,x) for x in enumerate(jobs)]):
  done.append(f.result());(out/'STATUS.json').write_text(json.dumps(dict(completed=len(done),planned=len(jobs),seconds=time.monotonic()-start))+'\n')
(out/'FINAL.json').write_text(json.dumps(dict(jobs=done,seconds=time.monotonic()-start,dependencies_unchanged=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())),indent=2)+'\n')
