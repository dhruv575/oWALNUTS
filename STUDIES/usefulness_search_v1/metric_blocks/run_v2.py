import concurrent.futures,hashlib,json,queue,shutil,sys,time
from pathlib import Path
import psutil
root=Path(__file__).resolve().parent;old=Path('/dev/shm/reconsider-20261029');models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');binary=root/'source2/STUDIES/metric_autoselect_confirmation_v1/target/release/pdb';out=root/'run02';out.mkdir(exist_ok=False)
assert psutil.virtual_memory().available>=10*1024**3 and shutil.disk_usage('/').free>=1024**3 and shutil.disk_usage('/dev/shm').free>=4*1024**3
assert json.loads((root/'BUILD-v2.json').read_text())['exit_code']==0
original=json.loads((old/'run01/MANIFEST.json').read_text());jobs=[dict(original_index=i,model=m,arm=a,seed=s) for i,(m,a,s) in enumerate(original['jobs']) if a=='auto2'];assert len(jobs)==12
paths=[binary,root/'run_v2.py',root/'SNAPSHOT-PROTOCOL.md',root/'source2/src/walnutpie.rs']+[models/(j['model']+suffix) for j in jobs for suffix in ['_model.so','.data.json']]+[old/'run01'/f"{j['original_index']:03d}"/'RESULT.json' for j in jobs];inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(out/'MANIFEST.json').write_text(json.dumps(dict(jobs=jobs,inputs=inputs),indent=2)+'\n')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
cores=queue.Queue()
for core in ['0-3','4-7','8-11']:cores.put(core)
def run(item):
 i,j=item;p=out/f'{i:03d}';p.mkdir();core=cores.get()
 try:
  cmd=['env','STUDY_SELECT_WINDOW=2','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','taskset','-c',core,str(binary),str(models/(j['model']+'_model.so')),str(models/(j['model']+'.data.json')),'auto',str(j['seed']),str(p/'RESULT.json'),'4']
  r=execute(cmd,str(root),600,p,2*1024**3,64*1024**2,p/'worker.log',output_scan_interval=2);(p/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');return dict(index=i,**r)
 finally:cores.put(core)
t=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,enumerate(jobs)))
(out/'FINAL.json').write_text(json.dumps(dict(jobs=results,seconds=time.monotonic()-t,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items())),indent=2)+'\n')
