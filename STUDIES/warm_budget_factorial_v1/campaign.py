import concurrent.futures,hashlib,importlib.metadata,json,os,shutil,sys,threading,time
from pathlib import Path
from resource_monitor import execute
from worker import settings
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
def main():
    base=Path(__file__).resolve().parent;root=base/'campaign01';root.mkdir(exist_ok=False)
    parent=base/'PARENT.json';spec=json.loads(parent.read_bytes())
    if shutil.disk_usage(base).free<10*1024**3:raise ValueError('Disk admission')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime drift')
    for name,want in spec['runtime']['packages'].items():
        if importlib.metadata.version(name)!=want:raise ValueError('Package drift')
    for name,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(name)!=want:raise ValueError('Inherited identity changed '+name)
    sources={str(p):sha(p) for p in base.glob('*.py')};sources.update({str(base/n):sha(base/n) for n in ('PLAN.md','SEED-AUDIT.json')})
    write(base/'MANIFEST.json',dict(parent_sha256=sha(parent),new_sources=sources,jobs=[dict(job=j,settings=settings(j)) for j in range(12)]))
    jobs=[dict(job=j,status='not_started') for j in range(12)];order=iter(list(range(1,12,2))+list(range(0,12,2)));lock=threading.Lock();stop=threading.Event();start=time.monotonic()
    def queue(q):
        while not stop.is_set():
            with lock:j=next(order,None)
            if j is None:break
            if time.monotonic()-start>9500 or shutil.disk_usage(base).free<4*1024**3:stop.set();break
            jobroot=root/f'job-{j:02d}';jobroot.mkdir()
            cmd=['taskset','-c',f'{4*q}-{4*q+3}',sys.executable,str(base/'worker.py'),str(parent),str(j),str(jobroot/'candidate'),'--manifest',str(base/'MANIFEST.json')]
            try:
                result=execute(cmd,str(base),min(3600,9990-(time.monotonic()-start)),str(jobroot),4*1024**3,512*1024**2,str(jobroot/'stdout.log'),output_scan_interval=5,utilization_path=str(jobroot/'utilization.jsonl'),phase_reserved_cores={'startup':4})
                jobs[j].update(result)
                if not result.get('group_drained') or result.get('reason') in ('rss_limit','output_limit','output_limit_final_scan'):stop.set()
            except Exception as e:jobs[j].update(status='monitor_failed',error=repr(e));stop.set()
            write(jobroot/'MONITOR.json',jobs[j]);print(json.dumps(dict(job=j,status=jobs[j].get('status'),exit_code=jobs[j].get('exit_code'))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for f in [ex.submit(queue,q) for q in range(4)]:f.result()
    write(root/'FINAL.json',dict(jobs=jobs,elapsed_seconds=time.monotonic()-start,stopped=stop.is_set(),source_hashes=sources))
    return 0 if all(j.get('exit_code')==0 and j.get('group_drained') for j in jobs) else 1
if __name__=='__main__':raise SystemExit(main())
