import argparse,hashlib,io,json,math
from pathlib import Path
import numpy as np
import arviz as az

def checked(root,name,seal):
    raw=(root/name).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=seal.get(name):raise ValueError('Artifact drift '+name)
    return raw
def manifest(root):
    out={}
    for line in (root/'ARTIFACTS.sha256').read_text().splitlines():
        h,n=line.split(maxsplit=1);out[n.removeprefix('./')]=h
    return out
def precision(logs,pits):
    if logs.shape!=(4,400) or pits.shape!=logs.shape or not np.isfinite(logs).all() or not np.isfinite(pits).all() or np.any((pits<0)|(pits>1)):raise ValueError('Invalid fixed candidate arrays')
    shift=float(logs.max());scaled=np.exp(logs-shift)
    mcse=lambda x:0. if np.ptp(x)==0 else float(np.asarray(az.mcse(x,method='mean')).item())
    return dict(logpdf=shift+math.log(float(scaled.mean())),pit=float(pits.mean()),logpdf_mcse=mcse(scaled)/float(scaled.mean()),pit_mcse=mcse(pits))

def run(original,extended):
    original=Path(original);extended=Path(extended);oldseal=manifest(original);newseal=manifest(extended)
    comparison=json.loads(checked(extended,'COMPARISON.json',newseal));rows=[]
    for r in comparison['rows']:
        m,t,j=r['month'],r['tick'],r['job'];prefix=f'campaign01/batch/inference/{m}/candidate/'
        record=json.loads(checked(original,prefix+f'records/{t:06d}.json',oldseal))
        if record['score_status']!='ok':raise ValueError('Candidate unavailable')
        raw=checked(original,prefix+record['arrays']['file'],oldseal)
        if hashlib.sha256(raw).hexdigest()!=record['arrays']['sha256']:raise ValueError('Record/array mismatch')
        with np.load(io.BytesIO(raw),allow_pickle=False) as a:metrics=precision(a['score__logpdf_by_chain_draw'],a['score__pit_by_chain_draw'])
        if abs(metrics['logpdf']-record['score']['logpdf'])>1e-12 or abs(metrics['pit']-record['score']['pit'])>1e-12:raise ValueError('Score reconstruction mismatch')
        ref=r['extended'];rows.append(dict(job=j,month=m,tick=t,reference_pass=ref['passed'],candidate=metrics,reference=ref,
            candidate_minus_reference=dict(logpdf=metrics['logpdf']-ref['logpdf'],pit=metrics['pit']-ref['pit'])))
    summaries={}
    for name,selected in [('all_24',rows),('passing_references_only',[r for r in rows if r['reference_pass']])]:
        summaries[name]=dict(count=len(selected),max_abs_logpdf_difference=max(abs(r['candidate_minus_reference']['logpdf']) for r in selected),
            max_abs_pit_difference=max(abs(r['candidate_minus_reference']['pit']) for r in selected),
            median_candidate_logpdf_mcse=float(np.median([r['candidate']['logpdf_mcse'] for r in selected])),
            median_reference_logpdf_mcse=float(np.median([r['reference']['logpdf_mcse'] for r in selected])))
    return dict(scope='Descriptive fixed-spot approximation audit; failed references retained; no new qualification',rows=rows,summaries=summaries,arviz=az.__version__,numpy=np.__version__)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('original');p.add_argument('extended');p.add_argument('out');a=p.parse_args();v=run(a.original,a.extended)
    with Path(a.out).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)
    print(json.dumps(v['summaries']))
