import concurrent.futures,hashlib,importlib.metadata,json,os,shutil,sys,threading,time
from pathlib import Path
from resource_monitor import execute

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)

def main():
    base=Path(__file__).resolve().parent;root=base/'campaign01';root.mkdir(exist_ok=False)
    old=base/'PARENT.json';spec=json.loads(old.read_bytes())
    if shutil.disk_usage(base).free<8*1024**3:raise ValueError('Disk admission')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix drift')
    for name,v in spec['runtime']['packages'].items():
        if importlib.metadata.version(name)!=v:raise ValueError('Runtime package drift '+name)
    for name,want in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(name)!=want:raise ValueError('Inherited source/runtime drift '+name)
    sources={str(base/name):sha(base/name) for name in ('worker.py','extended_adapter.py','campaign.py','resource_monitor.py','PLAN.md','SEED-AUDIT.json')}
    manifest=dict(parent_manifest=str(old),parent_sha256=sha(old),new_sources=sources,retained=16000,warmup=2000,jobs=24)
    write(base/'MANIFEST.json',manifest)
    jobs=[dict(job=j,status='not_started') for j in range(24)];stop=threading.Event();start=time.monotonic()
    os.environ.update(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')
    def queue(q):
        for j in range(q,24,4):
            if stop.is_set() or time.monotonic()-start>2500:break
            if shutil.disk_usage(base).free<4*1024**3:stop.set();break
            jobroot=root/f'job-{j:02d}';jobroot.mkdir()
            cmd=['taskset','-c',f'{q*4}-{q*4+3}',sys.executable,str(base/'worker.py'),str(base/'MANIFEST.json'),str(j),str(jobroot/'results')]
            try:
                result=execute(cmd,str(base),min(480,2990-(time.monotonic()-start)),str(jobroot),4*1024**3,1024**3,str(jobroot/'stdout.log'),output_scan_interval=5,utilization_path=str(jobroot/'utilization.jsonl'),phase_reserved_cores=4)
                jobs[j].update(result)
                if not result.get('group_drained') or result.get('reason') in ('rss_limit','output_limit','output_limit_final_scan'):stop.set()
            except Exception as e:jobs[j].update(status='monitor_failed',error=repr(e));stop.set()
            write(jobroot/'MONITOR.json',jobs[j])
            print(json.dumps(dict(job=j,status=jobs[j].get('status'),exit_code=jobs[j].get('exit_code'))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for f in [ex.submit(queue,q) for q in range(4)]:f.result()
    total=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    write(root/'FINAL.json',dict(jobs=jobs,elapsed_seconds=time.monotonic()-start,output_bytes=total,resource_stop=stop.is_set(),source_hashes=sources))
    return 0 if all(j.get('exit_code')==0 and j.get('group_drained') for j in jobs) else 1
if __name__=='__main__':raise SystemExit(main())
