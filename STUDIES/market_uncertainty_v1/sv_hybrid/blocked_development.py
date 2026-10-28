"""Fixed four-chain T250 development check; no market data or retry."""
import argparse,concurrent.futures,importlib.metadata,json,sys
from pathlib import Path
import numpy as np
from development import sha,write
from market_worker import sample
from blocked_path import sweep_blocked
from resource_monitor import execute


def verify(root):
    spec=json.loads((root/'PLAN.json').read_bytes())
    if spec['status']!='frozen_authorized' or spec['seeds']!=list(range(2026102814000000,2026102814000004)):
        raise ValueError('Fixed development plan required')
    for name,h in spec['sources'].items():
        if sha(name)!=h:raise ValueError('Source drift')
    runtime=spec['runtime']
    if sys.prefix!=runtime['prefix']:raise ValueError('Runtime prefix')
    for name,v in runtime['packages'].items():
        if importlib.metadata.version(name)!=v:raise ValueError('Runtime package drift')
    return spec


def worker(root,chain):
    spec=verify(root)
    if not 0<=chain<4:raise ValueError('Chain')
    y=np.resize(np.array([.001,-.002,.0005,0.,.003]),250)
    result,full,compact=sample(y,1,spec['seeds'][chain],function=sweep_blocked)
    out=root/f'chain-{chain}';out.mkdir(exist_ok=False)
    np.savez_compressed(out/'draws.npz',full=full,compact=compact)
    result.update(chain=chain,seed=spec['seeds'][chain],arrays_sha256=sha(out/'draws.npz'),plan_sha256=sha(root/'PLAN.json'))
    write(out/'FINAL.json',result)
    return 0 if result['status']=='complete' else 1


def campaign(root):
    verify(root)
    def one(chain):
        monitoring=root/f'monitor-{chain}';monitoring.mkdir()
        command=['taskset','-c',str(chain),sys.executable,str(Path(__file__).resolve()),str(root),'--worker',str(chain)]
        r=execute(command,str(root),300,root,1024**3,512*1024**2,monitoring/'worker.log',output_scan_interval=5,
                  utilization_path=monitoring/'utilization.jsonl',phase_reserved_cores={'startup':1})
        write(monitoring/'FINAL.json',r);return r
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:receipts=list(pool.map(one,range(4)))
    write(root/'FINAL.json',dict(receipts=receipts,planned=4))
    return 0 if all(r.get('exit_code')==0 and r.get('group_drained') for r in receipts) else 1


def supervise(root):
    verify(root)
    r=execute([sys.executable,str(Path(__file__).resolve()),str(root),'--campaign'],str(root),360,root,6*1024**3,512*1024**2,
              root/'campaign.log',ownership_env='OWALNUTS_BLOCK_DEVELOPMENT_OUTER',output_scan_interval=5,
              utilization_path=root/'outer-utilization.jsonl',phase_reserved_cores={'startup':4})
    write(root/'SUPERVISION.json',r)
    return 0 if r.get('exit_code')==0 and r.get('group_drained') else 1


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--worker',type=int);p.add_argument('--campaign',action='store_true');a=p.parse_args()
    root=a.root.resolve();raise SystemExit(worker(root,a.worker) if a.worker is not None else campaign(root) if a.campaign else supervise(root))
