"""Descriptive localization of fixed accuracy failures; never changes primary gates."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(sys.argv[1]);rows=json.loads((root/'ROWS.json').read_text());refs=json.loads((root/'REFERENCES.json').read_text());out={}
for case,ref in refs.items():
    if case.startswith('linear'):continue
    if not ref['qualified']:out[case]=dict(reason='Unqualified reference; no accuracy breakdown');continue
    d=json.loads((root/'data'/f'{case}.json').read_text());p=d['P'];n=d['Npred'];s=ref['summary'];tol=np.r_[.1*np.array(s['sd'][:p]),np.full(n,.03),.02,.02];bound=tol+3*np.array(s['mcse']);out[case]={}
    for engine in ('walnuts','nuts'):
        runs=[r for r in rows if r['case']==case and r['config'].startswith(engine+'_')];groups={}
        for name,ix in dict(log_parameters=slice(0,p),log_concentrations=slice(p,p+n),exceedance_probabilities=slice(p+n,p+n+2)).items():
            errors=[];precision=[]
            for r in runs:
                if r['status']!='ok':errors.append(False);precision.append(False);continue
                ss=r['summary'];err=np.abs(np.array(ss['mean'])-s['mean']);mc=np.array([float('inf') if x is None else x for x in ss['mcse']])
                errors.append(bool(np.all(err[ix]<=bound[ix])));precision.append(bool(np.all(mc[ix]<=tol[ix]/2)))
            groups[name]=dict(mean_pass=sum(errors),mcse_pass=sum(precision),attempts=len(runs))
        out[case][engine]=groups
(root/'ACCURACY-BREAKDOWN.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
