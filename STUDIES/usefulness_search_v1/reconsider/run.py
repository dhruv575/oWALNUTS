import concurrent.futures,hashlib,json,os,queue,random,shutil,sys,time
from pathlib import Path
ROOT=Path('/dev/shm/reconsider-20261029')
MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
MONITOR=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py')
sys.path.insert(0,str(MONITOR.parent))
from resource_monitor import execute
binary=ROOT/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb'
models=['earnings-logearn_interaction','kidiq-kidscore_momhsiq','garch-garch11','gp_pois_regr-gp_pois_regr']
jobs=[(m,a,s) for m in models for a in ('diag','auto2','reconsider') for s in range(927100001,927100004)]
random.Random(927199999).shuffle(jobs)
out=ROOT/'run01';out.mkdir(exist_ok=False)
files=[binary,MONITOR,Path(__file__),ROOT/'prepare.py',ROOT/'src/walnutpie.rs',ROOT/'tests/metric_autoselect_hessian.rs']+[MODELS/(m+suffix) for m in models for suffix in ('.data.json','_model.so')]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(out/'MANIFEST.json').write_text(json.dumps(dict(jobs=jobs,dependencies=hashes,pid=os.getpid()),indent=2)+'\n')
cores=queue.Queue()
for c in ('0-3','4-7','8-11'):cores.put(c)
def job(item):
 i,(m,a,s)=item;folder=out/f'{i:03d}';folder.mkdir();core=cores.get()
 try:
  if shutil.disk_usage('/').free<1024**3 or shutil.disk_usage(ROOT).free<4*1024**3:return dict(index=i,status='not_started_disk_floor')
  cmd=['env','STUDY_SELECT_WINDOW=2','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','taskset','-c',core,str(binary),str(MODELS/(m+'_model.so')),str(MODELS/(m+'.data.json')),'auto' if a=='auto2' else a,str(s),str(folder/'RESULT.json'),'4']
  r=execute(cmd,str(ROOT),600,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
  (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['group_drained'];return dict(index=i,**r)
 finally:cores.put(core)
done=[];start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for f in concurrent.futures.as_completed([pool.submit(job,x) for x in enumerate(jobs)]):
  done.append(f.result());(out/'STATUS.json').write_text(json.dumps(dict(completed=len(done),planned=len(jobs),seconds=time.monotonic()-start))+'\n')
(out/'FINAL.json').write_text(json.dumps(dict(jobs=done,seconds=time.monotonic()-start,dependencies_unchanged=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())),indent=2)+'\n')
