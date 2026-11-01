"""Finite, resource-bounded campaign with frozen calibration selection."""
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

def write(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(path)

def main():
    assert shutil.disk_usage(ROOT).free>=1.3*1024**3
    pre=json.loads((ROOT/'PREFLIGHT.json').read_text());assert pre['passed']
    ps=json.loads((ROOT/'PREFLIGHT-SUPERVISION.json').read_text());assert ps['status']=='exited' and ps['exit_code']==0 and ps['group_drained']
    for n,h in pre['sources'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
    assert hashlib.sha256((ROOT/'pendulum.so').read_bytes()).hexdigest()==pre['library_sha256']
    paths=[p for p in ROOT.iterdir() if p.suffix in ['.py','.cpp','.md','.so']]+list((ROOT/'data').glob('*.json'))+list((ROOT/'prepared').glob('*.json'))
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write(ROOT/'CAMPAIGN-MANIFEST.json',dict(sources=hashes,pid=os.getpid(),started=time.time()))
    started=time.monotonic();stop=threading.Event();cores=queue.Queue();rows=[]
    for c in range(16):cores.put(c)
    def heartbeat():
        with (ROOT/'HEARTBEAT.jsonl').open('x') as f:
            while not stop.is_set():
                r=dict(unix_seconds=time.time(),cpu_percent=psutil.cpu_percent(interval=1),memory_available=psutil.virtual_memory().available,disk_free=shutil.disk_usage(ROOT).free,completed=len(rows))
                f.write(json.dumps(r)+'\n');f.flush();write(ROOT/'LIVE.json',r);stop.wait(14)
    watcher=threading.Thread(target=heartbeat,daemon=True);watcher.start()
    write(ROOT/'STATUS.json',dict(status='running',phase='initial',pid=os.getpid()))
    def job(item):
        phase,case,config,rep=item;folder=ROOT/'runs'/f'{phase}-{case}-{config}-{rep}';folder.mkdir(parents=True,exist_ok=False);core=cores.get()
        try:
            if shutil.disk_usage(ROOT).free<1024**3 or time.monotonic()-started>2400:return dict(job=item,status='not_started_resource_admission')
            command=['env',f'XDG_CACHE_HOME={folder}/cache','taskset','-c',str(core),sys.executable,str(ROOT/'worker.py'),phase,str(case),config,str(rep),str(folder/'result')]
            s=execute(command,str(ROOT),300,folder,1024**3,8*1024**2,folder/'worker.log',output_scan_interval=2)
            write(folder/'SUPERVISION.json',s)
            ok=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and (folder/'result/RESULT.json').exists()
            return dict(job=item,status='ok' if ok else 'failed',folder=str(folder.relative_to(ROOT)),supervision=s)
        finally:cores.put(core)
    def batch(jobs):
        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
            for future in concurrent.futures.as_completed([pool.submit(job,j) for j in jobs]):
                row=future.result();rows.append(row);write(ROOT/'ROWS.json',rows);print(json.dumps(dict(job=row['job'],status=row['status'])),flush=True)
    try:
        configs=[f'{e}_{s}_{a}' for e in ['walnuts','nuts'] for s in ['raw','white'] for a in ['90','99']]
        jobs=[('calibrate',c,k,0) for c in range(2) for k in configs]
        jobs += [(p,c,k,0) for c in range(2) for k in ['nonlinear','linear'] for p in ['grid','laplace','laplace_grid']]
        random.Random(953400001).shuffle(jobs);batch(jobs)
        selected={};reference={}
        for case in range(2):
            grid_row=next(r for r in rows if r['job']==('grid',case,'nonlinear',0))
            reference[str(case)]=grid_row['status']=='ok' and json.loads((ROOT/grid_row['folder']/'result/RESULT.json').read_text())['reference_pass']
            for engine in ['walnuts','nuts']:
                candidates=[]
                for row in rows:
                    phase,c,config,_=row['job']
                    if phase=='calibrate' and c==case and config.startswith(engine+'_') and row['status']=='ok':
                        r=json.loads((ROOT/row['folder']/'result/RESULT.json').read_text());candidates.append(r)
                if candidates:
                    passed=[r for r in candidates if r['summary']['diagnostic_pass']]
                    winner=min(passed,key=lambda r:(r['seconds'],r['config'])) if passed else min(candidates,key=lambda r:(r['summary']['max_mcse_sd'],r['config']))
                    selected[f'{case}-{engine}']=winner['config']
        write(ROOT/'SELECTION.json',dict(selected=selected,reference_qualified=reference,created=time.time(),rule='Frozen protocol; no future outcomes used'))
        write(ROOT/'STATUS.json',dict(status='running',phase='validation',pid=os.getpid()))
        jobs=[('validate',c,selected[f'{c}-{e}'],rep) for c in range(2) for e in ['walnuts','nuts'] for rep in range(4) if reference[str(c)] and f'{c}-{e}' in selected]
        random.Random(953400002).shuffle(jobs);batch(jobs)
        out=ROOT/'analysis';out.mkdir(exist_ok=False)
        s=execute(['env',f'XDG_CACHE_HOME={out}/cache',sys.executable,str(ROOT/'analyze.py')],str(ROOT),300,out,2*1024**3,16*1024**2,out/'worker.log',output_scan_interval=2)
        write(out/'SUPERVISION.json',s)
        intact=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items())
        ok=s['status']=='exited' and s['exit_code']==0 and s['group_drained'] and intact
        write(ROOT/'STATUS.json',dict(status='completed' if ok else 'analysis_failed',elapsed_seconds=time.monotonic()-started,jobs=len(rows),sources_intact=intact,analysis_completed=ok))
    except BaseException as exc:
        write(ROOT/'STATUS.json',dict(status='failed',error=repr(exc),elapsed_seconds=time.monotonic()-started));raise
    finally:stop.set();watcher.join(timeout=20)
if __name__=='__main__':main()
