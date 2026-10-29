import concurrent.futures,hashlib,json,os,queue,sys,time
from pathlib import Path
source=Path(__file__).resolve().parent.parent/'source'
if source.is_dir():sys.path.insert(0,str(source))
from resource_monitor import execute
from targets import NAMES


def run(root,mode,selection=''):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);here=Path(__file__).resolve().parent
    jobs=[(n,) for n in NAMES] if mode=='controls' else [(n,path,str(r),selection) for r in range(4) for n in ['correlated','banana'] for path in ['smooth','abrupt']]
    files=list(here.glob('*.py'))+list(source.glob('*.py'));hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest=dict(mode=mode,jobs=jobs,sources=hashes,pid=os.getpid(),selection_sha256=hashlib.sha256(Path(selection).read_bytes()).hexdigest() if selection else None)
    (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    cores=queue.Queue()
    for c in range(12,16):cores.put(c)
    def job(item):
        i,args=item;folder=root/f'{i:02d}';folder.mkdir();core=cores.get();cache=folder/'cache';cache.mkdir()
        if any(hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h for p,h in hashes.items()):raise ValueError('Source drift')
        command=['env',f'XDG_CACHE_HOME={cache}','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','taskset','-c',str(core),sys.executable,str(here/f'{"controls" if mode=="controls" else "warm"}.py'),*args,str(folder/'result')]
        receipt=execute(command,str(here),300,folder,1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
        if not receipt['group_drained']:raise ValueError('Undrained process')
        cores.put(core);return dict(index=i,args=args,**receipt)
    start=time.monotonic();done=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for f in concurrent.futures.as_completed([pool.submit(job,x) for x in enumerate(jobs)]):
            done.append(f.result());(root/'STATUS.json').write_text(json.dumps(dict(completed=len(done),planned=len(jobs),elapsed=time.monotonic()-start))+'\n')
    (root/'FINAL.json').write_text(json.dumps(dict(jobs=done,elapsed_seconds=time.monotonic()-start,sources_unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())),indent=2)+'\n')


if __name__=='__main__':run(*sys.argv[1:])
