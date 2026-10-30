import concurrent.futures,hashlib,json,os,queue,sys,time,shutil,random
from pathlib import Path
from resource_monitor import execute
from worker import CASES
from sampling import CONFIGS
from backend import ROOT

def run(phase,root,selection=None):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);here=Path(__file__).resolve().parent
    if phase=='initial':
        jobs=[('calibrate',case,c,0) for case in CASES[:4] for c in CONFIGS]
        jobs += [('reference',case,c,i) for case in CASES for i,c in enumerate(['nuts_raw_99','nuts_white_99'])]
        jobs += [('laplace',case,'laplace',0) for case in CASES]
    else:
        chosen=json.loads(Path(selection).read_text())['selected'];jobs=[('validate',case,chosen[case][engine],rep) for case in CASES[:4] for engine in ('walnuts','nuts') for rep in range(8)]
    random.Random(895100000 if phase=='initial' else 895200000).shuffle(jobs)
    files=list(here.glob('*.py'))+list(here.glob('*.stan'))+list(here.glob('*.cpp'))+list(here.glob('*.md'))+list((ROOT/'build').glob('*.so'))+list((ROOT/'data').glob('*.json'))+list((ROOT/'prepared').glob('*.json'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    manifest=dict(phase=phase,jobs=jobs,sources=hashes,pid=os.getpid(),created_unix=time.time(),selection_sha256=hashlib.sha256(Path(selection).read_bytes()).hexdigest() if selection else None)
    (root/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');cores=queue.Queue()
    for c in range(12):cores.put(c)
    started=time.monotonic()
    def job(item):
        index,(p,case,c,rep)=item;folder=root/f'{index:03d}';folder.mkdir();core=cores.get()
        try:
            if shutil.disk_usage(root).free<1024**3 or time.monotonic()-started>3600:return dict(index=index,status='not_started_resource_admission')
            if any(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()!=h for n,h in hashes.items()):raise ValueError('Source drift')
            cache=folder/'cache';cache.mkdir()
            cmd=['env',f'XDG_CACHE_HOME={cache}','OPENBLAS_NUM_THREADS=1','OMP_NUM_THREADS=1','MKL_NUM_THREADS=1','taskset','-c',str(core),sys.executable,str(here/'worker.py'),p,case,c,str(rep),str(folder/'result')]
            receipt=execute(cmd,str(here),900,folder,1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
            (folder/'SUPERVISION.json').write_text(json.dumps(receipt,indent=2)+'\n')
            if not receipt['group_drained']:raise ValueError('Undrained process')
            return dict(index=index,**receipt)
        finally:cores.put(core)
    completed=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for f in concurrent.futures.as_completed([pool.submit(job,i) for i in enumerate(jobs)]):
            completed.append(f.result());(root/'STATUS.json').write_text(json.dumps(dict(completed=len(completed),planned=len(jobs),elapsed_seconds=time.monotonic()-started))+'\n')
    (root/'FINAL.json').write_text(json.dumps(dict(jobs=sorted(completed,key=lambda r:r['index']),elapsed_seconds=time.monotonic()-started,sources_unchanged=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())),indent=2)+'\n')

if __name__=='__main__':run(*sys.argv[1:])
