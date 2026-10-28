"""Six fixed paths on disjoint four-core groups, with bounded evidence."""
import argparse,concurrent.futures,json,os,shutil,sys,threading,time
from pathlib import Path
from rolling_market_worker import validate
from literal_reference import write
from resource_monitor import execute

def campaign(root):
    validate(root/'PLAN.json')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('Exact sixteen-core allocation')
    if shutil.disk_usage(root).free<8*1024**3:raise ValueError('Initial disk admission')
    out=root/'campaign01';out.mkdir(exist_ok=False);stop=threading.Event();started=time.monotonic()
    rows=[dict(index=i,status='not_started') for i in range(6)]
    def group(g):
        for i in range(g,6,4):
            if stop.is_set():break
            if shutil.disk_usage(root).free<3*1024**3 or time.monotonic()-started>7400:stop.set();break
            directory=out/f'job-{i:02d}';directory.mkdir()
            command=['taskset','-c',f'{g*4}-{g*4+3}',sys.executable,str(Path(__file__).with_name('rolling_market_worker.py')),str(root/'PLAN.json'),str(i),str(directory/'fit')]
            try:
                receipt=execute(command,str(root),3600,directory,4*1024**3,1024**3,directory/'worker.log',output_scan_interval=5,
                                utilization_path=directory/'utilization.jsonl',phase_reserved_cores={'startup':4})
                rows[i].update(receipt)
                if not receipt.get('group_drained') or receipt.get('reason') in ('rss_limit','output_limit','output_limit_final_scan'):stop.set()
            except Exception as exc:rows[i].update(status='monitor_failed',error=repr(exc));stop.set()
            write(directory/'SUPERVISION.json',rows[i]);print(json.dumps(dict(index=i,status=rows[i]['status'],exit_code=rows[i].get('exit_code'))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for f in [pool.submit(group,g) for g in range(4)]:f.result()
    write(out/'FINAL.json',dict(jobs=rows,resource_stop=stop.is_set(),elapsed_seconds=time.monotonic()-started))
    return 0 if all(r.get('exit_code')==0 and r.get('group_drained') for r in rows) else 1

def supervise(root):
    validate(root/'PLAN.json')
    receipt=execute([sys.executable,str(Path(__file__).resolve()),str(root),'--campaign'],str(root),11000,root,
                    22*1024**3,6*1024**3,root/'campaign.log',ownership_env='OWALNUTS_ROLLING_NUTPIE_OUTER',
                    output_scan_interval=5,utilization_path=root/'outer-utilization.jsonl',phase_reserved_cores={'startup':16})
    write(root/'SUPERVISION.json',receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--campaign',action='store_true');a=p.parse_args()
    raise SystemExit((campaign if a.campaign else supervise)(a.root.resolve()))
