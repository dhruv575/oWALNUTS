import concurrent.futures,hashlib,importlib.metadata as md,json,os,queue,shutil,sys,time
from pathlib import Path
from targets import NAMES
from sampling import CONFIGS
from resource_monitor import execute

HERE=Path(__file__).resolve().parent


def write(path,v):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(v,indent=2)+'\n');temp.replace(path)


def run(root,phase,selection=''):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    if phase=='calibrate':jobs=[(n,c,r,1000) for r in range(2) for n in NAMES for c in CONFIGS]
    elif phase=='test':
        selected=json.loads(Path(selection).read_text())['selected']
        jobs=[(n,selected[n][e],r,d) for r in range(8) for d in [250,1000,3000] for n in NAMES for e in ['nuts','walnuts']]
    else:jobs=[(n,c,0,250) for n in ['isotropic','funnel_severe'] for c in ['nuts_90','nuts_lowrank90','walnuts_90']]
    sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ['.py','.md']}
    manifest=dict(phase=phase,jobs=jobs,sources=sources,concurrency=12,job_cap_seconds=120,versions={n:md.version(n) for n in ['numpy','scipy','numba','owalnuts','nutpie']},pid=os.getpid(),created_unix=time.time())
    if phase=='test':manifest['selection_sha256']=hashlib.sha256(Path(selection).read_bytes()).hexdigest()
    write(root/'MANIFEST.json',manifest);started=time.monotonic();cores=queue.Queue()
    for core in range(12):cores.put(core)
    def job(item):
        index,(name,config,rep,draws)=item;folder=root/f'{index:03d}-{name}-{config}-{rep}-{draws}';folder.mkdir()
        identity=dict(index=index,name=name,config=config,rep=rep,draws=draws)
        if time.monotonic()-started>3600 or shutil.disk_usage(root).free<1024**3:return dict(**identity,status='not_started_resource_admission')
        if any(hashlib.sha256((HERE/n).read_bytes()).hexdigest()!=h for n,h in sources.items()):raise ValueError('Frozen source drift')
        core=cores.get();cache=folder/'cache';cache.mkdir()
        command=['env',f'XDG_CACHE_HOME={cache}','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','taskset','-c',str(core),sys.executable,str(HERE/'worker.py'),name,config,str(rep),str(draws),phase,str(folder/'result')]
        receipt=execute(command,str(HERE),120,folder,1024**3,20*1024**2,folder/'worker.log',output_scan_interval=2)
        write(folder/'SUPERVISION.json',receipt)
        if not receipt['group_drained']:raise RuntimeError('Undrained job')
        cores.put(core);return dict(**identity,**receipt)
    completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for f in concurrent.futures.as_completed([pool.submit(job,item) for item in enumerate(jobs)]):
            completed.append(f.result());write(root/'STATUS.json',dict(completed=len(completed),planned=len(jobs),elapsed_seconds=time.monotonic()-started,last=completed[-1],pid=os.getpid(),free_disk_bytes=shutil.disk_usage(root).free))
    write(root/'FINAL.json',dict(jobs=sorted(completed,key=lambda r:r['index']),elapsed_seconds=time.monotonic()-started,sources_unchanged=all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in sources.items())))


if __name__=='__main__':run(*sys.argv[1:])
