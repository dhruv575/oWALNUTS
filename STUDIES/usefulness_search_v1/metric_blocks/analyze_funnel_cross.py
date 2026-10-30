import json
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import ndtr
study=Path(__file__).resolve().parent;root=study/'local_recovery/funnel_cross01'
# Reuse the frozen statistical functions verbatim, without executing its old batch.
source=(study/'analyze_funnel_error_guard.py').read_text();exec(source[source.index('def diagnostics'):source.index('rows=[]')])
rows=[]
for case in json.loads((root/'SUMMARY.json').read_text())['rows']:
    row=dict(case);rows.append(row)
    if not case['completed']:row.update(qualified=False,reason='bounded worker failed');continue
    raw=json.loads((root/case['folder']/'RAW.json').read_text());spec=json.loads((root/case['folder']/'INPUT.json').read_text())
    assert raw['target_calls']==sum(c['target_calls'] for c in raw['chains'])
    for c,s in zip(raw['chains'],spec['chains']):
        assert c['levels']==8 and c['max_error']==case['max_error'] and c['seed']==s['seed'] and c['work']['all_phase_calls']==c['target_calls']
        assert abs(c['step_size']-s['step_size'])<=abs(np.spacing(s['step_size']))
        assert np.all(np.abs(np.asarray(c['mass'])-s['mass'])<=np.abs(np.spacing(s['mass'])))
    x=np.asarray([c['draws'] for c in raw['chains']]).transpose(2,0,1);assert x.shape==(10,4,22000);x=x[:,:,2000:]
    q=x.copy();q[0]/=3;q[1:]*=np.exp(-x[0]/2);u=ndtr(q)
    coords=[dict(index=i,raw=diagnostics(x[i]),uniform=diagnostics(u[i])) for i in range(10)]
    features=[moment(f'U{i}_mean',u[i],.5,.015) for i in range(10)]
    for i in range(3):features.extend([moment(f'U{i}_lower',(u[i]<.05).astype(float),.05,.01),moment(f'U{i}_upper',(u[i]>.95).astype(float),.05,.01)])
    features.extend([moment('joint_lower_median',((u[0]<.5)&(u[1]<.5)).astype(float),.25,.02),moment('centered_product',(u[0]-.5)*(u[1]-.5),0.,.005)])
    for t in [5,6]:features.append(moment(f'omega_below_minus{t}',(x[0]<-t).astype(float),float(ndtr(-t/3)),.01,False))
    div=sum(c['retained_divergences'] for c in raw['chains']);depth=sum(c['work']['maximum_depth_stops'] for c in raw['chains'])
    passed=np.isfinite(x).all() and all(dg_pass(c[k]) for c in coords for k in ['raw','uniform']) and all(f['passed'] for f in features) and div==0 and depth==0
    row.update(qualified=bool(passed),coordinates=coords,features=features,divergences_including_discard=div,depth_caps_including_discard=depth,target_calls=raw['target_calls'],reverse_calls=sum(c['work']['target_calls_reverse'] for c in raw['chains']))
def safe(v):
    if isinstance(v,dict):return {k:safe(x) for k,x in v.items()}
    if isinstance(v,list):return [safe(x) for x in v]
    if isinstance(v,float) and not np.isfinite(v):return None
    return v
(study/'FUNNEL-CROSS-ANALYSIS.json').write_text(json.dumps(safe(dict(rows=rows)),indent=2,allow_nan=False)+'\n')
lines=['# Crossed funnel settings results','','| Pilot seed | Pilot threshold | Retained threshold | Qualified | P(omega<-5) | MCSE | Div incl discard | Depth incl discard | Calls |','|---|---|---|---|---|---|---|---|---|']
for r in rows:
    f=next((f for f in r.get('features',[]) if f['name']=='omega_below_minus5'),{})
    lines.append(f"| {r['pilot_seed']} | {r['pilot']} | {r['max_error']} | {r['qualified']} | {f.get('estimate','-')} | {f.get('mcse','-')} | {r.get('divergences_including_discard','-')} | {r.get('depth_caps_including_discard','-')} | {r.get('target_calls','-')} |")
lines+=['','Exploratory crossed continuation, with common starts and no adaptation. Original pilot costs are reported separately in the analysis JSON. No end-to-end speed or improvement claim.']
(study/'FUNNEL-CROSS-REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
