"""Fixed 24-fit reference queue with four disjoint four-core groups."""
import argparse,concurrent.futures,json,os,shutil,sys,threading,time
from pathlib import Path
from literal_reference import validate,write,sha
from resource_monitor import execute

def validate_panel(root):
    plan=json.loads((root/'PANEL.json').read_bytes())
    if plan['status']!='frozen_authorized' or len(plan['manifests'])!=24:raise ValueError('Fixed panel required')
    for path,digest in plan['sources'].items():
        if sha(path)!=digest:raise ValueError('Panel source drift')
    if set(os.sched_getaffinity(0))!=set(range(16)):raise ValueError('Exact sixteen-core allocation')
    seeds=[]
    for i,item in enumerate(plan['manifests']):
        if sha(item['path'])!=item['sha256']:raise ValueError('Manifest drift')
        spec=validate(json.loads(Path(item['path']).read_bytes()))
        if spec['scope']!='fixed_market_reference' or spec['spot']!=i:raise ValueError('Ordered fixed windows')
        seeds.extend([spec['seed'],spec['seed']+1])
    if len(set(seeds))!=48:raise ValueError('Unique external seeds required')
    return plan

def campaign(root):
    plan=validate_panel(root)
    if shutil.disk_usage(root).free<8*1024**3:raise ValueError('Initial disk admission')
    out=root/'campaign01';out.mkdir(exist_ok=False)
    rows=[dict(index=i,status='not_started') for i in range(24)]
    stop=threading.Event();started=time.monotonic()
    def group(g):
        for i in range(g,24,4):
            if stop.is_set():break
            if shutil.disk_usage(root).free<4*1024**3 or time.monotonic()-started>11000:
                stop.set();break
            directory=out/f'job-{i:02d}';directory.mkdir()
            command=['taskset','-c',f'{4*g}-{4*g+3}',sys.executable,str(Path(__file__).with_name('literal_reference.py')),
                     plan['manifests'][i]['path'],str(directory/'fit'),'--worker']
            try:
                receipt=execute(command,str(root),1800,directory,4*1024**3,1024**3,directory/'worker.log',
                                output_scan_interval=5,utilization_path=directory/'utilization.jsonl',phase_reserved_cores={'startup':4})
                rows[i].update(receipt)
                if not receipt.get('group_drained') or receipt.get('reason') in ('rss_limit','output_limit','output_limit_final_scan'):stop.set()
            except Exception as exc:rows[i].update(status='monitor_failed',error=repr(exc));stop.set()
            write(directory/'SUPERVISION.json',rows[i])
            print(json.dumps(dict(index=i,status=rows[i]['status'],exit_code=rows[i].get('exit_code'))),flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for future in [pool.submit(group,g) for g in range(4)]:future.result()
    write(out/'FINAL.json',dict(jobs=rows,resource_stop=stop.is_set(),elapsed_seconds=time.monotonic()-started))
    return 0 if all(r.get('exit_code')==0 and r.get('group_drained') for r in rows) else 1

def supervise(root):
    validate_panel(root)
    receipt=execute([sys.executable,str(Path(__file__).resolve()),str(root),'--campaign'],str(root),13000,root,
                    22*1024**3,8*1024**3,root/'campaign.log',ownership_env='OWALNUTS_MARKET_REFERENCE_OUTER',
                    output_scan_interval=5,utilization_path=root/'outer-utilization.jsonl',phase_reserved_cores={'startup':16})
    write(root/'SUPERVISION.json',receipt)
    return 0 if receipt.get('exit_code')==0 and receipt.get('group_drained') else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--campaign',action='store_true');a=p.parse_args()
    raise SystemExit((campaign if a.campaign else supervise)(a.root.resolve()))
