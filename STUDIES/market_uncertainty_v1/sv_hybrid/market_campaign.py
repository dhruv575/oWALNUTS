"""Fixed 16-core queue with per-chain and whole-campaign containment."""
import argparse
import concurrent.futures
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from development import sha,write
from resource_monitor import execute


def validate(root):
    spec=json.loads((root/'MANIFEST.json').read_bytes())
    methods=spec.get('methods',[0,1])
    if methods not in ([0,1],[2]) or spec.get('status')!='frozen_authorized' or spec['chains']!=96*len(methods) or spec['warmup']!=1000 or spec['retained']!=2000:
        raise ValueError('Fixed campaign required')
    if sys.prefix!=spec['runtime']['prefix']:raise ValueError('Runtime prefix drift')
    for package,version in spec['runtime']['packages'].items():
        if importlib.metadata.version(package)!=version:raise ValueError('Runtime package drift')
    for path,digest in {**spec['sources'],**spec['runtime']['binaries']}.items():
        if sha(path)!=digest:raise ValueError('Source/runtime binary drift')
    if sha(root/'PARENT.json')!=spec['parent_sha256'] or sha(root/'SEED-AUDIT.json')!=spec['audit_sha256']:
        raise ValueError('Frozen parent/audit drift')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('Exact 16-core allocation required')
    return spec


def campaign(root):
    spec=validate(root)
    if shutil.disk_usage(root).free<10*1024**3:raise ValueError('Initial disk admission')
    out=root/'campaign01';out.mkdir(exist_ok=False)
    count=spec['chains'];jobs=[dict(index=i,status='not_started') for i in range(count)]
    order=iter(range(count));lock=threading.Lock();stop=threading.Event();started=time.monotonic()
    def queue(core):
        while not stop.is_set():
            with lock:index=next(order,None)
            if index is None:break
            if time.monotonic()-started>4450 or shutil.disk_usage(root).free<4*1024**3:
                stop.set();break
            directory=out/f'chain-{index:03d}';directory.mkdir()
            command=['taskset','-c',str(core),sys.executable,str(Path(__file__).with_name('market_worker.py')),str(root/'MANIFEST.json'),str(index),str(directory/'fit')]
            try:
                receipt=execute(command,str(root),300,directory,1024**3,64*1024**2,directory/'worker.log',
                                output_scan_interval=5,utilization_path=directory/'utilization.jsonl',phase_reserved_cores={'startup':1})
                jobs[index].update(receipt)
                if not receipt.get('group_drained') or receipt.get('reason') in ('rss_limit','output_limit','output_limit_final_scan'):stop.set()
            except Exception as exc:jobs[index].update(status='monitor_failed',error=repr(exc));stop.set()
            write(directory/'MONITOR.json',jobs[index])
            print(json.dumps(dict(index=index,status=jobs[index]['status'],exit_code=jobs[index].get('exit_code'))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        for future in [pool.submit(queue,core) for core in range(16)]:future.result()
    write(out/'FINAL.json',dict(jobs=jobs,elapsed_seconds=time.monotonic()-started,resource_stop=stop.is_set()))
    return 0 if all(j.get('exit_code')==0 and j.get('group_drained') for j in jobs) else 1


def supervise(root):
    validate(root)
    result=execute([sys.executable,str(Path(__file__).resolve()),str(root),'--campaign'],str(root),4800,root,
                   22*1024**3,8*1024**3,root/'campaign.log',ownership_env='OWALNUTS_SPECIALIST_MARKET_OUTER',
                   output_scan_interval=5,utilization_path=root/'outer-utilization.jsonl',phase_reserved_cores={'startup':16})
    write(root/'SUPERVISION.json',result)
    print(json.dumps(result))
    return 0 if result.get('exit_code')==0 and result.get('group_drained') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--campaign',action='store_true');a=p.parse_args()
    raise SystemExit((campaign if a.campaign else supervise)(a.root.resolve()))
