import hashlib,json
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'recycling_mse01'
summary=json.loads((root/'SUMMARY.json').read_text());assert summary['unchanged']
for p,h in summary['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
analysis=json.loads((study/'RECYCLING-MSE-ANALYSIS.json').read_text());checks=[]
for t in analysis['targets']:
    target=t['target'];d=len(t['truth'])//4;ordinary=[];observed=[]
    for batch in range(16):
        a=json.loads((root/f'{target}-{batch:02d}-original/RAW.json').read_text());b=json.loads((root/f'{target}-{batch:02d}-observed/RAW.json').read_text())
        for arm in ['original','observed']:
            s=json.loads((root/f'{target}-{batch:02d}-{arm}/SUPERVISION.json').read_text());assert s['group_drained'] and s['exit_code']==0
        for old,new in zip(a['chains'],b['chains']):
            for k in old:
                if k!='seconds':assert old[k]==new[k]
            x=np.array(old['draws']);v=np.array(new['recycled']);ordinary.append([float(np.mean(x[:,i] if j==0 else x[:,i]**2 if j==1 else x[:,i]<(0 if j==2 else -2))) for j in range(4) for i in range(d)]);observed.append([float(np.mean(v[:,i])) for i in range(4*d)])
    a=np.array(ordinary);b=np.array(observed);expected=np.array(t['replicate_estimates']);assert np.allclose(a,expected[0],atol=1e-9,rtol=1e-13) and np.allclose(b,expected[1],atol=1e-9,rtol=1e-13)
    truth=np.array(t['truth']);ea=(a-truth)**2;eb=(b-truth)**2
    for j,f in enumerate(t['functionals']):assert abs(ea[:,j].mean()/eb[:,j].mean()-f['ratio'])<1e-9
    scale=np.ones(4*d);scale[:d]=np.sqrt(truth[d:2*d]);scale[d:2*d]=truth[d:2*d]
    for j,f in enumerate(t['families']):
        ix=slice(j*d,(j+1)*d);r=np.sum(ea[:,ix]/scale[ix]**2)/np.sum(eb[:,ix]/scale[ix]**2);assert abs(r-f['ratio'])<1e-9
    checks.append(dict(target=target,replicates=64,functionals=4*d,raw_estimates_and_mse_ratios_verified=True))
timing=local/'recycling_mse_timing01';s=json.loads((timing/'SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
for target in s['targets']:
    r=json.loads((timing/target/'TIMINGS.json').read_text());assert len(r)==96 and all(x['seconds']>0 for x in r)
    sup=json.loads((timing/target/'SUPERVISION.json').read_text());assert sup['exit_code']==0 and sup['group_drained']
(study/'RECYCLING-MSE-REPLAY.json').write_text(json.dumps(dict(passed=True,checks=checks,timing_replays=288,source_hashes_unchanged=True),indent=2)+'\n');print('Verified all 192 paired replicate estimates, 88 functional ratios, 12 family ratios and 288 timing replay records')
