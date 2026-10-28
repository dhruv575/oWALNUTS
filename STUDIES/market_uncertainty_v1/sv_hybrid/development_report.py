"""Describe all eight fixed development chains, including incomplete ones."""
import argparse
import hashlib
import json
from pathlib import Path
import arviz as az
import numpy as np


def run(root):
    root=Path(root)
    final=json.loads((root/'FINAL.json').read_bytes())
    if len(final['receipts']) != 8:
        raise ValueError('Incomplete development ledger')
    summaries=[]
    for method in range(2):
        chains=[]; arrays=[]
        for chain in range(4):
            path=root/f'm{method}-c{chain}.json'
            row=json.loads(path.read_bytes()) if path.exists() else dict(status='missing',chain=chain,method=method)
            chains.append(row)
            if row['status']=='complete':
                data=root/f'm{method}-c{chain}.npz'
                if hashlib.sha256(data.read_bytes()).hexdigest()!=row['arrays_sha256']:
                    raise ValueError('Development array changed')
                with np.load(data,allow_pickle=False) as stored:
                    full,compact=stored['full'],stored['compact']
                    if full.shape!=(2000,35) or compact.shape!=(2000,4) or not np.isfinite(full).all() or not np.isfinite(compact).all():
                        raise ValueError('Invalid development arrays')
                    arrays.append((full.copy(),compact.copy()))
        summary=dict(method=method,planned=4,completed=len(arrays),chains=chains)
        if len(arrays)==4:
            full=np.stack([a[0] for a in arrays]);compact=np.stack([a[1] for a in arrays])
            def metrics(a):
                return dict(mean=float(a.mean()),rhat=float(np.asarray(az.rhat(a)).item()),
                            bulk_ess=float(np.asarray(az.ess(a,method='bulk')).item()),
                            tail_ess=float(np.asarray(az.ess(a,method='tail',prob=(.05,.95))).item()),
                            mean_mcse=float(np.asarray(az.mcse(a,method='mean')).item()))
            summary['compact']={name:metrics(compact[:,:,i]) for i,name in enumerate(('mu','log_sigma','beta','h_last'))}
            latent=[metrics(full[:,:,i]) for i in range(3,35)]
            summary['innovations']=dict(max_rhat=max(v['rhat'] for v in latent),min_bulk_ess=min(v['bulk_ess'] for v in latent),min_tail_ess=min(v['tail_ess'] for v in latent))
        summaries.append(summary)
    return dict(scope='Local literal development only; no independent posterior reference, predictive accuracy or market-performance claim',
                plan_sha256=hashlib.sha256((root/'PLAN.json').read_bytes()).hexdigest(),numpy=np.__version__,arviz=az.__version__,summaries=summaries)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');parser.add_argument('out');args=parser.parse_args()
    result=run(args.root)
    with Path(args.out).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(result))
