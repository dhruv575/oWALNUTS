"""Exploratory common-functional audit of preserved validation draws."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
old=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029')
sys.path.insert(0,str(old/'source'))
from features import summarize
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
inputs={};start=time.monotonic()
def read(p):
    raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest()
    return json.loads(raw)
audit=read(Path('/home/ubuntu/lanes/usefulness-search-20261029/audit01/AUDIT.json'))['stan_public']
ref=audit['new_functional_diagnostics'];assert audit['original_reference_qualified'] and ref['diagnostic_pass']
lo=np.array(audit['threshold_lower']);hi=np.array(audit['threshold_upper']);d=len(lo)
tol=np.r_[.1*np.array(ref['sd'][:2*d]),np.full(2*d,.02)]
bound=tol+3*np.array(ref['mcse']);rows=[]
for p in sorted((old/'validation01').glob('*/result/RESULT.json')):
    r=read(p)
    if r['case']!='stan_public':continue
    assert r['status']=='ok'
    draws=p.parent/'draws.npz';inputs[str(draws)]=hashlib.sha256(draws.read_bytes()).hexdigest()
    q=np.load(draws)['q'];f=np.concatenate([q,q*q,(q<lo).astype(float),(q>hi).astype(float)],axis=-1)
    s=summarize(f,r['divergences'],r['depth_hits'])
    err=float(np.max(np.abs(np.array(s['mean'])-ref['mean'])/bound))
    mc=np.array([float('inf') if x is None else x for x in s['mcse']]);precision=float(np.max(mc/(tol/2)))
    rows.append(dict(config=r['config'],rep=r['rep'],summary=s,max_error_ratio=err,max_mcse_ratio=precision if np.isfinite(precision) else None,passes=bool(s['diagnostic_pass'] and err<=1 and precision<=1)))
assert len(rows)==16
inputs[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
inputs[str(old/'source/features.py')]=hashlib.sha256((old/'source/features.py').read_bytes()).hexdigest()
summary={arm:dict(attempts=len(rr),passes=sum(r['passes'] for r in rr),diagnostic_passes=sum(r['summary']['diagnostic_pass'] for r in rr),error_passes=sum(r['max_error_ratio']<=1 for r in rr),precision_passes=sum(r['max_mcse_ratio'] is not None and r['max_mcse_ratio']<=1 for r in rr)) for arm in ('walnuts','nuts') for rr in [[r for r in rows if r['config'].startswith(arm+'_')]]}
for name,data in [('ROWS',rows),('SUMMARY',summary),('INPUT-HASHES',inputs),('COMPLETE',dict(seconds=time.monotonic()-start,exploratory=True))]:
    (out/(name+'.json')).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,indent=2))
