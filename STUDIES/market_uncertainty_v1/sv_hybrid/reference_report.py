"""All-coordinate descriptive comparison; diagnostic flags never remove methods."""
import argparse
import json
from pathlib import Path
import numpy as np
import arviz as az
from literal_reference import sha, write


def metrics(a):
    a=np.asarray(a)
    if a.ndim!=2 or a.shape[0]!=4 or a.shape[1]<4 or not np.isfinite(a).all():
        raise ValueError('Finite four-chain data required')
    def scalar(value):
        value=float(np.asarray(value).item())
        return value if np.isfinite(value) else None
    return dict(mean=float(a.mean()),sd=float(a.std(ddof=1)),
                quantiles=dict(zip(('q05','q50','q95'),np.quantile(a,[.05,.5,.95]).tolist())),
                rhat=scalar(az.rhat(a)),bulk_ess=scalar(az.ess(a,method='bulk')),
                tail_ess=scalar(az.ess(a,method='tail',prob=(.05,.95))),
                mean_mcse=scalar(az.mcse(a,method='mean')))


def summarize(full,compact):
    full=np.asarray(full);compact=np.asarray(compact)
    if full.ndim!=3 or full.shape[0]!=4 or full.shape[2]!=253 or compact.shape!=(*full.shape[:2],4):
        raise ValueError('Exact T250 full/compact axes required')
    if not np.array_equal(full[:,:,:3],compact[:,:,:3]):
        raise ValueError('Full/compact parameter mismatch')
    # Reconstruct h_last from independent innovations, rather than trusting labels.
    mu,ls=full[:,:,0],full[:,:,1]
    h=mu+np.exp(ls)*full[:,:,3]/np.sqrt(1-.95**2)
    for i in range(4,253):h=mu+.95*(h-mu)+np.exp(ls)*full[:,:,i]
    if not np.allclose(h,compact[:,:,3],rtol=1e-11,atol=1e-11):
        raise ValueError('Terminal path reconstruction mismatch')
    result={name:metrics(compact[:,:,i]) for i,name in enumerate(('mu','log_sigma','beta','h_last'))}
    result.update({f'z[{i}]':metrics(full[:,:,i+3]) for i in range(250)})
    flagged=[name for name,m in result.items() if m['rhat'] is None or m['rhat']>1.01
             or m['bulk_ess'] is None or m['bulk_ess']<400 or m['tail_ess'] is None or m['tail_ess']<400]
    return dict(coordinates=result,flagged_coordinates=flagged,draws_per_chain=full.shape[1])


def run(reference,development):
    reference=Path(reference);development=Path(development)
    supervision=json.loads((reference/'SUPERVISION.json').read_bytes())
    if supervision.get('group_drained') is not True:
        raise ValueError('Reference ownership must be drained')
    result=dict(scope='Literal target corroboration; no market, speed or economic superiority claim',
                methods=[],mean_contrasts=[],arviz=az.__version__,source_sha256=sha(__file__))
    final_path=reference/'fit/FINAL.json'
    final=json.loads(final_path.read_bytes()) if final_path.exists() else dict(status='missing')
    row=dict(method='reference',status=final['status'],receipt=final);result['methods'].append(row)
    if supervision.get('exit_code')!=0:
        row['status']='unavailable'
    if final['status']=='complete' and supervision.get('exit_code')==0:
        path=reference/'fit/draws.npz'
        if sha(path)!=final['arrays_sha256']:raise ValueError('Reference array drift')
        with np.load(path,allow_pickle=False) as data:row.update(summarize(data['full'],data['compact']))
        row['divergences']=final['metadata']['divergences']
        row['reference_unresolved']=bool(row['flagged_coordinates'] or sum(row['divergences']))
    plan=json.loads((development/'PLAN.json').read_bytes())
    if plan.get('periods')!=250:raise ValueError('T250 specialist fixture required')
    for method in range(2):
        item=dict(method=('original','interwoven')[method],status='unavailable',chains=[])
        result['methods'].append(item);arrays=[]
        for chain in range(4):
            p=development/f'm{method}-c{chain}.json'
            receipt=json.loads(p.read_bytes()) if p.exists() else dict(status='missing')
            item['chains'].append(receipt)
            if receipt['status']!='complete':continue
            path=development/f'm{method}-c{chain}.npz'
            if sha(path)!=receipt['arrays_sha256']:raise ValueError('Specialist array drift')
            with np.load(path,allow_pickle=False) as data:
                if data['full'].shape!=(2000,253) or data['compact'].shape!=(2000,4):raise ValueError('Specialist shape')
                arrays.append((data['full'].copy(),data['compact'].copy()))
        if len(arrays)==4:
            item.update(summarize(np.stack([v[0] for v in arrays]),np.stack([v[1] for v in arrays])))
            item['status']='complete'
        for name in ('mu','log_sigma','beta','h_last'):
            contrast=dict(method=item['method'],coordinate=name,status='unavailable')
            result['mean_contrasts'].append(contrast)
            if 'coordinates' in item and 'coordinates' in row:
                a,b=item['coordinates'][name],row['coordinates'][name]
                contrast.update(status='available',difference=a['mean']-b['mean'],specialist_mcse=a['mean_mcse'],reference_mcse=b['mean_mcse'],reference_unresolved=row['reference_unresolved'])
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('reference');p.add_argument('development');p.add_argument('out');a=p.parse_args()
    write(a.out,run(a.reference,a.development))
