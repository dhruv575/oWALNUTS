import concurrent.futures,hashlib,json,os,queue,sys,time,shutil
from pathlib import Path
source=Path(__file__).resolve().parent.parent/'source'
if source.is_dir():sys.path.insert(0,str(source))
from resource_monitor import execute
from native_check import CONFIGS,BUDGETS


def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);here=Path(__file__).resolve().parent
    jobs=[(c,r,d) for r in range(8) for d in BUDGETS for c in CONFIGS]
    files=list(here.glob('*.py'))+list(here.glob('*.md'))+list(source.glob('*.py'))
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest=dict(jobs=jobs,sources=hashes,pid=os.getpid(),created_unix=time.time())
    (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    cores=queue.Queue()
    for core in range(12):cores.put(core)
    started=time.monotonic()
    def job(item):
        index,(config,rep,draws)=item;folder=root/f'{index:03d}-{config}-{rep}-{draws}';folder.mkdir()
        if shutil.disk_usage(root).free<1024**3 or time.monotonic()-started>3600:return dict(index=index,status='not_started_resource_admission')
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise ValueError('Source drift')
        core=cores.get();cache=folder/'cache';cache.mkdir()
        cmd=['env',f'XDG_CACHE_HOME={cache}','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','taskset','-c',str(core),sys.executable,str(here/'native_check.py'),config,str(rep),str(draws),str(folder/'result')]
        receipt=execute(cmd,str(here),120,folder,1024**3,20*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if not receipt['group_drained']:raise ValueError('Undrained native process')
        cores.put(core);return dict(index=index,**receipt)
    completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for f in concurrent.futures.as_completed([pool.submit(job,item) for item in enumerate(jobs)]):
            completed.append(f.result());(root/'STATUS.json').write_text(json.dumps(dict(completed=len(completed),planned=len(jobs),elapsed_seconds=time.monotonic()-started))+'\n')
    (root/'FINAL.json').write_text(json.dumps(dict(jobs=sorted(completed,key=lambda r:r['index']),elapsed_seconds=time.monotonic()-started,sources_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())),indent=2)+'\n')


if __name__=='__main__':run(sys.argv[1])
