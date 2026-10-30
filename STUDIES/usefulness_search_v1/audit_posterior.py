"""Exploratory distribution audit; never changes the prior study's primary gates."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
old=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029')
sys.path.insert(0,str(old/'source'))
from features import summarize
start=time.monotonic();out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False)
refs=json.loads((old/'REFERENCES.json').read_text());inputs={};results={}
def read(p):inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
rows=[]
for p in sorted((old/'initial02').glob('*/result/RESULT.json')):
    r=read(p);r['folder']=p.parent;rows.append(r)
for case in refs:
    rr=[r for r in rows if r['case']==case and r['phase']=='reference'];lap=[r for r in rows if r['case']==case and r['phase']=='laplace'][0]
    prep=read(old/'prepared'/f'{case}.json');mode=np.array(prep['mode']);sd=np.sqrt(np.diag(prep['cov']));lo=mode-1.645*sd;hi=mode+1.645*sd
    def load(r):
        p=r['folder']/'draws.npz';inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return np.load(p)['q']
    def transform(q):return np.concatenate([q,q*q,(q<lo).astype(float),(q>hi).astype(float)],axis=-1)
    arrays=[transform(load(r)) for r in rr];pooled=summarize(np.concatenate(arrays),min_ess=2000)
    separate=[summarize(a) for a in arrays];approx=summarize(transform(load(lap)))
    mu=np.array(pooled['mean']);delta=np.array(separate[0]['mean'])-separate[1]['mean'];mc=np.array([float('nan') if x is None else x for x in pooled['mcse']]);dm=np.sqrt(np.array(separate[0]['mcse'],dtype=float)**2+np.array(separate[1]['mcse'],dtype=float)**2)
    p=len(mode);names=[f'{kind}[{i}]' for kind in ('log_parameter','squared_log_parameter','lower_tail','upper_tail') for i in range(p)]
    def finite(x):return float(x) if np.isfinite(x) else None
    results[case]=dict(original_reference_qualified=refs[case]['qualified'],new_functional_diagnostics=pooled,threshold_lower=lo.tolist(),threshold_upper=hi.tolist(),features=[dict(name=n,reference=finite(mu[i]),laplace=finite(approx['mean'][i]),reference_mcse=finite(mc[i]),independent_difference=finite(delta[i]),independent_difference_mcse=finite(dm[i]),difference_z=finite(delta[i]/dm[i]) if dm[i]>0 else None) for i,n in enumerate(names)])
read(old/'REFERENCES.json');inputs[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
(out/'INPUT-HASHES.json').write_text(json.dumps(inputs,indent=2)+'\n');(out/'AUDIT.json').write_text(json.dumps(results,indent=2,allow_nan=False)+'\n')
(out/'COMPLETE.json').write_text(json.dumps(dict(seconds=time.monotonic()-start,cases=len(results),purpose='Exploratory; original qualification unchanged'),indent=2)+'\n')
print(json.dumps({k:dict(original_reference_qualified=v['original_reference_qualified'],rhat=v['new_functional_diagnostics']['rhat_max'],ess=v['new_functional_diagnostics']['ess_min'],max_tail_probability_gap=max(abs(f['reference']-f['laplace']) for f in v['features'] if 'tail' in f['name'])) for k,v in results.items()},indent=2))
