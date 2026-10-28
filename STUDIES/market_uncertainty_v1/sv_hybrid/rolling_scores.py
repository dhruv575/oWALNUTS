"""Reconstruct saved rolling scores; no independent-reference error assumption."""
import argparse
import io
import json
from pathlib import Path
import numpy as np
from rolling_inventory import inventory, read
from rolling_record_audit import sha


def precision(logs,pits):
    import arviz as az
    logs,pits=np.asarray(logs),np.asarray(pits)
    if logs.shape!=(4,400) or pits.shape!=logs.shape:
        raise ValueError('Four chains by 400 retained draws required')
    if not np.isfinite(logs).all() or not np.isfinite(pits).all() or np.any((pits<0)|(pits>1)):
        raise ValueError('Invalid score arrays')
    shift=float(logs.max());scaled=np.exp(logs-shift)
    def mcse(a):return 0. if np.ptp(a)==0 else float(np.asarray(az.mcse(a,method='mean')).item())
    result=dict(logpdf=shift+float(np.log(scaled.mean())),pit=float(pits.mean()),
                logpdf_mcse=mcse(scaled)/float(scaled.mean()),pit_mcse=mcse(pits))
    if not all(np.isfinite(v) for v in result.values()):raise ValueError('Unavailable MCSE')
    return result


def run(root,reference,reference_sha256):
    root=Path(root);audit=inventory(root,reference,reference_sha256)
    refs={(r['month'],r['tick']):r['extended'] for r in read(reference)['rows']}
    rows=[]
    for slot in audit['spots']:
        row=dict(slot,metrics_status='unavailable',reference=refs[slot['month'],slot['tick']])
        if slot['available']:
            lane=root/'campaign01'/f"job-{slot['job']:02d}"/'fit/lane'
            record=lane/'records'/f"{slot['tick']:06d}.json"
            if sha(record)!=slot['record_sha256']:raise ValueError('Record changed during analysis')
            payload=read(record);array=lane/payload['arrays']['file'];raw=array.read_bytes()
            import hashlib
            if hashlib.sha256(raw).hexdigest()!=payload['arrays']['sha256']:raise ValueError('Array changed during analysis')
            try:
                with np.load(io.BytesIO(raw),allow_pickle=False) as data:
                    metrics=precision(data['score__logpdf_by_chain_draw'],data['score__pit_by_chain_draw'])
            except (ValueError,KeyError) as exc:row['metrics_error']=repr(exc)
            else:
                if any(abs(metrics[k]-payload['score'][k])>1e-12 for k in ('logpdf','pit')):
                    raise ValueError('Saved score reconstruction mismatch')
                row.update(metrics_status='available',candidate=metrics,
                           difference={k:metrics[k]-row['reference'][k] for k in ('logpdf','pit')})
        rows.append(row)
    summaries=[]
    for j in range(6):
        for passing in (False,True):
            planned=[r for r in rows if r['job']==j and (not passing or r['reference_pass'])]
            valid=[r for r in planned if r['metrics_status']=='available']
            summary=dict(job=j,subset='passing_references' if passing else 'all_references',planned=len(planned),available=len(valid))
            for k in ('logpdf','pit'):
                summary['available_max_abs_'+k+'_difference']=max((abs(r['difference'][k]) for r in valid),default=None)
                summary['available_median_'+k+'_mcse']=float(np.median([r['candidate'][k+'_mcse'] for r in valid])) if valid else None
            summaries.append(summary)
    import arviz as az
    return dict(scope='Descriptive saved-score reconstruction; not fidelity qualification or untouched predictive evidence',
                inventory=audit,rows=rows,summaries=summaries,numpy=np.__version__,arviz=az.__version__,
                uncertainty='Shared references and chronological windows induce dependence; no combined independent-error interval is reported.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('reference');p.add_argument('reference_sha256');p.add_argument('out');a=p.parse_args()
    result=run(a.root,a.reference,a.reference_sha256)
    with Path(a.out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
