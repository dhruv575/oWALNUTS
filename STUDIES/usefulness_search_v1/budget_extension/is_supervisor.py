import concurrent.futures,hashlib,json,os,queue,random,shutil,sys,time
from pathlib import Path
OLD=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029');ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(OLD/'source'))
from resource_monitor import execute
root=ROOT/'importance01';root.mkdir(exist_ok=False);jobs=[(a,n,r) for a in ('mixture',) for n in (65536,262144) for r in range(8)];random.Random(915900000).shuffle(jobs)
files=list((ROOT/'source').glob('*'))+[OLD/'build/model_model.so',OLD/'build/adapter.so',OLD/'data/stan_public.json',OLD/'prepared/stan_public.json',OLD/'source/backend.py',OLD/'source/resource_monitor.py',ROOT/'audit01/AUDIT.json']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files if p.is_file()};(root/'MANIFEST.json').write_text(json.dumps(dict(jobs=jobs,dependencies=hashes,pid=os.getpid()),indent=2)+'\n')
cores=queue.Queue()
for c in range(12):cores.put(c)
def job(item):
    i,(a,n,r)=item;folder=root/f'{i:03d}';folder.mkdir();core=cores.get()
    try:
        if shutil.disk_usage(root).free<1024**3:return dict(index=i,status='not_started_disk_floor')
        cmd=['taskset','-c',str(core),sys.executable,str(ROOT/'source/is_worker.py'),a,str(n),str(r),str(folder/'result')]
        result=execute(cmd,str(ROOT),300,folder,1024**3,24*1024**2,folder/'worker.log',output_scan_interval=2);(folder/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');assert result['group_drained'];return dict(index=i,**result)
    finally:cores.put(core)
done=[];start=time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
    for f in concurrent.futures.as_completed([pool.submit(job,x) for x in enumerate(jobs)]):
        done.append(f.result());(root/'STATUS.json').write_text(json.dumps(dict(completed=len(done),planned=len(jobs),seconds=time.monotonic()-start))+'\n')
(root/'FINAL.json').write_text(json.dumps(dict(jobs=done,seconds=time.monotonic()-start,dependencies_unchanged=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())),indent=2)+'\n')
