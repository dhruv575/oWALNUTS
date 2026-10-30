import json
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import ndtr
study=Path(__file__).resolve().parent;root=study/'local_recovery/funnel_error_guard01'

def diagnostics(x):
    return dict(rhat=float(az.rhat(x)),bulk=float(az.ess(x,method='bulk')),tail=float(az.ess(x,method='tail')),mcse=float(az.mcse(x,method='mean')))

def dg_pass(d):
    return all(np.isfinite(v) for v in d.values()) and d['rhat']<=1.01 and d['bulk']>=400 and d['tail']>=400

def moment(name,x,exact,tolerance,require_diagnostics=True):
    d=diagnostics(x);estimate=float(x.mean());error=estimate-exact
    z=error/d['mcse'] if d['mcse']>0 else None
    passed=np.isfinite(estimate) and z is not None and abs(error)<=tolerance and d['mcse']<=tolerance/2 and abs(z)<=4.5
    if require_diagnostics:passed=passed and dg_pass(d)
    return dict(name=name,estimate=estimate,exact=exact,error=error,z=z,tolerance=tolerance,**d,passed=bool(passed))

rows=[]
for case in json.loads((root/'SUMMARY.json').read_text())['rows']:
    row=dict(case);rows.append(row)
    if not case['completed']:row.update(qualified=False,reason='bounded worker failed');continue
    raw=json.loads((root/case['folder']/'RAW.json').read_text());x=np.asarray(raw.pop('columns'),dtype=float)
    assert x.shape==(10,4,20000) and raw['kernel_tuning']['max_refinement_levels']==8
    assert raw['kernel_tuning']['max_error']==(1 if case['arm']=='default' else 1000)
    assert raw['target']==case['target'] and raw['seed']==case['seed']
    q=x.copy();q[0]/=3
    if case['target']=='centered':q[1:]*=np.exp(-x[0]/2)
    u=ndtr(q)
    coords=[dict(index=i,raw=diagnostics(x[i]),uniform=diagnostics(u[i])) for i in range(10)]
    features=[moment(f'U{i}_mean',u[i],.5,.015) for i in range(10)]
    for i in range(3):
        features.extend([moment(f'U{i}_lower',(u[i]<.05).astype(float),.05,.01),moment(f'U{i}_upper',(u[i]>.95).astype(float),.05,.01)])
    features.extend([moment('joint_lower_median',((u[0]<.5)&(u[1]<.5)).astype(float),.25,.02),moment('centered_product',(u[0]-.5)*(u[1]-.5),0.,.005)])
    for t in [5,6]:features.append(moment(f'omega_below_minus{t}',(x[0]<-t).astype(float),float(ndtr(-t/3)),.01,False))
    divergences=sum(c['divergences'] for c in raw['chains_data']);depth=sum(c['depth_caps'] for c in raw['chains_data'])
    qualified=bool(np.isfinite(x).all() and all(dg_pass(c[k]) for c in coords for k in ['raw','uniform']) and all(f['passed'] for f in features) and divergences==0 and depth==0)
    row.update(qualified=qualified,coordinates=coords,features=features,divergences=divergences,depth_caps=depth,target_calls=raw['target_calls_total'],min_bulk=min(c['raw']['bulk'] for c in coords),reported_tail=raw['tail_mass'],exhaustions=sum(c['refinement_exhaustions'] for c in raw['chains_data']))
report={'rows':rows,'all_permissive_qualified':all(r['qualified'] for r in rows if r['arm']=='permissive'),'all_easy_controls_qualified':all(r['qualified'] for r in rows if r['target']=='noncentered')}
def json_safe(value):
    if isinstance(value,dict):return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,list):return [json_safe(v) for v in value]
    if isinstance(value,float) and not np.isfinite(value):return None
    return value
(study/'FUNNEL-ERROR-GUARD-ANALYSIS.json').write_text(json.dumps(json_safe(report),indent=2,allow_nan=False)+'\n')
lines=['# Fresh funnel error guard','', '| Target | Arm | Seed | Qualified | Divergences | Depth caps | Failed moments | Calls |','|---|---|---|---|---|---|---|---|']
for r in rows:lines.append(f"| {r['target']} | {r['arm']} | {r['seed']} | {r['qualified']} | {r.get('divergences','-')} | {r.get('depth_caps','-')} | {','.join(f['name'] for f in r.get('features',[]) if not f['passed']) or '-'} | {r.get('target_calls','-')} |")
lines.extend(['','Permissive promotion guard passed: '+str(report['all_permissive_qualified']), 'All easy controls qualified: '+str(report['all_easy_controls_qualified']), '', 'All raw evidence is preserved. This guard cannot establish general correctness, novelty, or application value.'])
(study/'FUNNEL-ERROR-GUARD-REPORT.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
