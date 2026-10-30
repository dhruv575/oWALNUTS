import concurrent.futures,hashlib,json,os,queue,random,shutil,sys,time
from pathlib import Path
ROOT=Path('/dev/shm/bounded-init-20261030');MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');SV=Path('/home/ubuntu/lanes/grad_init_metric_v1/repo/STUDIES/grad_init_metric_v1/models/data.json');MONITOR=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py');sys.path.insert(0,str(MONITOR.parent));from resource_monitor import execute
assert json.loads((ROOT/'PREFLIGHT.json').read_text())['passed']
models=['hudson_lynx_hare-lotka_volterra','bball_drive_event_0-hmm_drive_0','mcycle_gp-accel_gp','radon_all-radon_hierarchical_intercept_centered'];arms=['defaults','gradinit','bounded'];jobs=[('pdb',m,a,s) for m in models for a in arms for s in range(939100001,939100005)]+[('sv','sv250',a,s) for a in arms for s in range(939200001,939200009)]+[('funnel','funnel10',a,s) for a in arms for s in range(939300001,939300003)];random.Random(939999000).shuffle(jobs);assert len(jobs)==78
out=ROOT/'run01';out.mkdir(exist_ok=False)
files=[ROOT/'PROTOCOL.md',ROOT/'SV-RULE.json',ROOT/'PREFLIGHT.json',ROOT/'prepare.py',ROOT/'prepare_v2.py',ROOT/'audit_preflight.py',Path(__file__),ROOT/'src/walnutpie.rs',ROOT/'src/kernel.rs',ROOT/'source.tar',MONITOR,SV]+[ROOT/'target/release'/n for n in ['pdb-cell','sv-cell','funnel']]+list((ROOT/'STUDIES/grad_init_metric_v1/src/bin').glob('*.rs'))+[MODELS/(m+s) for m in models for s in ['.data.json','_model.so']]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(out/'MANIFEST.json').write_text(json.dumps(dict(jobs=jobs,dependencies=hashes,pid=os.getpid()),indent=2)+'\n')
cores=queue.Queue()
for c in ['0-3','4-7','8-11']:cores.put(c)
def job(item):
 i,(kind,model,arm,seed)=item;folder=out/f'{i:03d}';folder.mkdir();core=cores.get()
 try:
  if shutil.disk_usage('/').free<1024**3 or shutil.disk_usage(ROOT).free<4*1024**3:return dict(index=i,status='not_started_disk_floor')
  result=str(folder/'RESULT.json')
  if kind=='pdb':cmd=[str(ROOT/'target/release/pdb-cell'),str(MODELS/(model+'_model.so')),str(MODELS/(model+'.data.json')),arm,str(seed),result,'4']
  elif kind=='sv':cmd=[str(ROOT/'target/release/sv-cell'),str(SV),'250',arm,str(seed),result,str(folder/'TELEMETRY.json'),'4']
  else:cmd=[str(ROOT/'target/release/funnel'),'diag' if arm=='defaults' else arm,'2000','20000',str(seed),result]
  r=execute(['env','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','taskset','-c',core,*cmd],str(ROOT),600,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['group_drained'];return dict(index=i,kind=kind,model=model,arm=arm,seed=seed,**r)
 finally:cores.put(core)
done=[];start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for f in concurrent.futures.as_completed([pool.submit(job,x) for x in enumerate(jobs)]):
  done.append(f.result());(out/'STATUS.json').write_text(json.dumps(dict(completed=len(done),planned=len(jobs),seconds=time.monotonic()-start))+'\n')
(out/'FINAL.json').write_text(json.dumps(dict(jobs=done,seconds=time.monotonic()-start,dependencies_unchanged=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())),indent=2)+'\n')
