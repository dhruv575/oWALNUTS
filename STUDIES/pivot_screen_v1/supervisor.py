"""Detached bounded campaign; CPU affinity and per-job process ownership."""
import concurrent.futures,hashlib,json,os,shutil,sys,time,queue
import importlib.metadata as md
from pathlib import Path
from models import CANDIDATES,SCENARIOS
from resource_monitor import execute

HERE=Path(__file__).resolve().parent


def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2)+'\n');temp.replace(path)


def run(root,mode):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ['.py','.md']}
    jobs=[(c,s,r) for r in range(20) for s in SCENARIOS for c in CANDIDATES] if mode=='main' else [(c,'sparse',0) for c in CANDIDATES]
    manifest=dict(mode=mode,jobs=jobs,warmup=500,draws=750,chains=4,concurrency=12 if mode=='main' else 4,job_cap_seconds=900,campaign_admission_seconds=7200,sources=sources,pid=os.getpid(),created_unix=time.time())
    manifest['versions']={name:md.version(name) for name in ['numpy','scipy','owalnuts','nutpie','arviz','psutil']}
    manifest['python']=sys.version
    write(root/'MANIFEST.json',manifest);started=time.monotonic();completed=[]
    cores=queue.Queue()
    for core in range(manifest['concurrency']):cores.put(core)
    def job(item):
        index,(c,s,r)=item;folder=root/f'{index:03d}-{c}-{s}-{r:02d}';folder.mkdir()
        if time.monotonic()-started>7200 or shutil.disk_usage(root).free<1024**3:
            return dict(index=index,candidate=c,scenario=s,replicate=r,status='not_started_resource_admission')
        for name,digest in sources.items():
            if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:raise ValueError('Frozen source drift')
        cache=folder/'cache';cache.mkdir()
        core=cores.get()
        cmd=['env',f'XDG_CACHE_HOME={cache}','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','taskset','-c',str(core),sys.executable,str(HERE/'worker.py'),c,s,str(r),str(folder/'result'),'500','750']
        if mode=='pilot':cmd.append('pilot')
        receipt=execute(cmd,str(HERE),900,folder,1024**3,32*1024**2,folder/'worker.log',output_scan_interval=2)
        if not receipt['group_drained']:raise RuntimeError('Undrained group; core cannot be reused')
        cores.put(core)
        write(folder/'SUPERVISION.json',receipt)
        return dict(index=index,candidate=c,scenario=s,replicate=r,**receipt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=manifest['concurrency']) as pool:
        futures=[pool.submit(job,item) for item in enumerate(jobs)]
        for f in concurrent.futures.as_completed(futures):
            completed.append(f.result());write(root/'STATUS.json',dict(completed=len(completed),planned=len(jobs),elapsed_seconds=time.monotonic()-started,last=completed[-1],pid=os.getpid(),free_disk_bytes=shutil.disk_usage(root).free))
    write(root/'FINAL.json',dict(jobs=sorted(completed,key=lambda r:r['index']),elapsed_seconds=time.monotonic()-started,sources_unchanged=all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in sources.items())))


if __name__=='__main__':run(*sys.argv[1:])
