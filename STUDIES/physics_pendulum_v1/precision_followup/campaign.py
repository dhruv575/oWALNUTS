import concurrent.futures
import hashlib
import json
import os
import queue
import random
import shutil
import sys
import threading
import time
from pathlib import Path
import psutil
from resource_monitor import execute
ROOT=Path(__file__).resolve().parent
OLD=ROOT.with_name('physics-pendulum-20261031')

def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n');temp.replace(path)

def main():
    assert shutil.disk_usage(ROOT).free>=1.25*1024**3
    assert json.loads((OLD/'STATUS.json').read_text())['status']=='completed'
    original=json.loads((OLD/'CAMPAIGN-MANIFEST.json').read_text())['sources']
    assert all(hashlib.sha256((OLD/n).read_bytes()).hexdigest()==h for n,h in original.items())
    shutil.copyfile(OLD/'pendulum.so',ROOT/'pendulum.so')
    for directory in ['data','prepared']:shutil.copytree(OLD/directory,ROOT/directory)
    shutil.copyfile(OLD/'SELECTION.json',ROOT/'SELECTION.json')
    oldrows=json.loads((OLD/'ROWS.json').read_text());prior=next(r for r in oldrows if r['job']==['laplace',1,'nonlinear',0])
    assert prior['status']=='ok';prior['folder']='../'+OLD.name+'/'+prior['folder']
    rows=[prior];paths=[p for p in ROOT.iterdir() if p.suffix in ['.py','.so','.md']]+list((ROOT/'data').glob('*.json'))+list((ROOT/'prepared').glob('*.json'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write(ROOT/'CAMPAIGN-MANIFEST.json',dict(sources=hashes,original_sources=original,started=time.time()))
    cores=queue.Queue()
    for c in range(12):cores.put(c)
    stop=threading.Event();started=time.monotonic()
    def heartbeat():
        with (ROOT/'HEARTBEAT.jsonl').open('x') as f:
            while not stop.is_set():
                r=dict(unix_seconds=time.time(),cpu_percent=psutil.cpu_percent(interval=1),memory_available=psutil.virtual_memory().available,disk_free=shutil.disk_usage(ROOT).free,completed_new_jobs=len(rows)-1)
                f.write(json.dumps(r)+'\n');f.flush();write(ROOT/'LIVE.json',r);stop.wait(14)
    watcher=threading.Thread(target=heartbeat,daemon=True);watcher.start()
    write(ROOT/'STATUS.json',dict(status='running',pid=os.getpid()))
    def run(item):
        phase,case,config,rep=item;folder=ROOT/'runs'/f'{phase}-{case}-{config}-{rep}';folder.mkdir(parents=True,exist_ok=False);core=cores.get()
        try:
            cmd=['env',f'XDG_CACHE_HOME={folder}/cache','taskset','-c',str(core),sys.executable,str(ROOT/'worker.py'),phase,str(case),config,str(rep),str(folder/'result')]
            s=execute(cmd,str(ROOT),300,folder,1024**3,8*1024**2,folder/'worker.log',ownership_env='OWALNUTS_PHYSICS_JOB_TOKEN',output_scan_interval=2)
            write(folder/'SUPERVISION.json',s)
            ok=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and (folder/'result/RESULT.json').exists()
            return dict(job=item,folder=str(folder.relative_to(ROOT)),status='ok' if ok else 'failed',supervision=s)
        finally:cores.put(core)
    try:
        jobs=[('validate',1,f'{engine}_raw_90',rep) for engine in ['walnuts','nuts'] for rep in range(4)]
        jobs += [('grid',1,'nonlinear',0),('grid',1,'linear',0),('laplace_grid',1,'nonlinear',0)]
        random.Random(953600001).shuffle(jobs)
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            for future in concurrent.futures.as_completed([pool.submit(run,j) for j in jobs]):
                row=future.result();rows.append(row);write(ROOT/'ROWS.json',rows);print(json.dumps(dict(job=row['job'],status=row['status'])),flush=True)
        out=ROOT/'analysis';out.mkdir()
        s=execute(['env',f'XDG_CACHE_HOME={out}/cache',sys.executable,str(ROOT/'analyze.py')],str(ROOT),300,out,2*1024**3,16*1024**2,out/'worker.log',ownership_env='OWALNUTS_PHYSICS_JOB_TOKEN',output_scan_interval=2)
        write(out/'SUPERVISION.json',s)
        intact=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items()) and all(hashlib.sha256((OLD/n).read_bytes()).hexdigest()==h for n,h in original.items())
        ok=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and intact
        write(ROOT/'STATUS.json',dict(status='completed' if ok else 'analysis_failed',new_jobs=len(rows)-1,sources_intact=intact,elapsed_seconds=time.monotonic()-started))
    finally:stop.set();watcher.join(timeout=20)
if __name__=='__main__':main()
