import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import ndtr
p=Path(__file__).resolve().parent;root=p/'local_recovery/recycled_baseline_screen01'
s=json.loads((root/'SUMMARY.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
rng=np.random.default_rng(941620001);cost_rng=np.random.default_rng(941630101);results=[]
for ti,target in enumerate(['noncentered','analytic_rotated_gaussian']):
    d=10 if ti==0 else 2;var=np.array([9.]+[1.]*9 if ti==0 else [2.,2.]);truth=np.r_[np.zeros(d),var,np.full(d,.5),ndtr(-2/np.sqrt(var))];scale=np.r_[np.sqrt(var),var,np.ones(2*d)]
    arms=list(s['builds']);est={a:[] for a in arms};mcse={a:[] for a in arms};cost={a:[] for a in arms};div={a:0 for a in arms}
    for b in range(16):
        f=root/f'{target}-{b:02d}';timings=json.loads((f/'TIMINGS.json').read_text())
        for a in arms:
            cost[a].append(np.mean([t['seconds'] for t in timings if t['arm']==a]))
            data=json.loads((f/f'RAW-{a}.json').read_text())
            for c in data['chains']:
                sm=c['summary'] if a.startswith('wal') else c['conditional_summary' if a.endswith('recycled') else 'ordinary_summary'];assert sm['count']==1000 and sm['block_sizes']==[50]*20
                est[a].append(sm['mean']);mcse[a].append(np.std(sm['block_means'],axis=0,ddof=1)/np.sqrt(20));div[a]+=c['retained_divergences']
    est={a:np.array(v) for a,v in est.items()};mcse={a:np.array(v) for a,v in mcse.items()};cost={a:np.array(v) for a,v in cost.items()}
    idx=rng.integers(0,64,(10000,64));ci=cost_rng.integers(0,16,(10000,16));base='wal_recycled'
    diagnostics={a:dict(retained_divergences=div[a],mean_estimates=est[a].mean(0).tolist(),aggregate_error_z=((est[a].mean(0)-truth)/(est[a].std(0,ddof=1)/8)).tolist(),coverage95=np.mean(abs(est[a]-truth)<=1.96*mcse[a],axis=0).tolist(),mean_batch_seconds=float(cost[a].mean())) for a in arms}
    families=[]
    for j,family in enumerate(['mean','second_moment','below_zero','below_minus_two']):
        sl=slice(j*d,(j+1)*d);errors={a:np.mean(((est[a][:,sl]-truth[sl])/scale[sl])**2,axis=1) for a in arms};comparisons=[]
        for a in arms:
            if a==base:continue
            mr=float(errors[a].mean()/errors[base].mean());mb=errors[a][idx].mean(1)/errors[base][idx].mean(1);mi=np.quantile(mb,[.025,.975]);cr=float(cost[a].mean()/cost[base].mean());cb=cost[a][ci].mean(1)/cost[base][ci].mean(1);cc=np.quantile(cb,[.025,.975])
            comparisons.append(dict(control=a,mse_ratio=mr,mse_interval=mi.tolist(),cost_ratio=cr,cost_interval=cc.tolist(),cost_adjusted_ratio=mr*cr,descriptive_endpoint_range=[float(mi[0]*cc[0]),float(mi[1]*cc[1])]))
        families.append(dict(family=family,mse={a:float(errors[a].mean()) for a in arms},comparisons=comparisons))
    results.append(dict(target=target,diagnostics=diagnostics,families=families))
primary=results[0]['families'][1];checks={c['control']:c['descriptive_endpoint_range'][0]>1.2 for c in primary['comparisons'] if not c['control'].startswith('wal')}
z_ok=all(max(abs(z) for z in row['aggregate_error_z'][10:20])<=4.5 for row in results[0]['diagnostics'].values())
report=dict(primary_passed=all(checks.values()) and z_ok,primary_controls=checks,primary_z_gate=z_ok,results=results,scope='Optimistic WAL elimination screen; cost-adjusted endpoints are not joint confidence intervals; no application or cold-start superiority claim')
(p/'RECYCLED-BASELINE-SCREEN-ANALYSIS.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
lines=['# Independent recycled baseline elimination screen','',f'Primary gate passed: {report["primary_passed"]}. Ratios above one favor recycled WAL. WAL receives uncharged fixed geometry while native pays for 1,000 warmup draws; positive results require a fair cold-start study.','', '| Target | Family | Control | MSE ratio | Cost ratio | Adjusted ratio | Descriptive range |','|---|---|---|---:|---:|---:|---|']
for row in results:
    for fam in row['families']:
        for c in fam['comparisons']:lines.append(f'| {row["target"]} | {fam["family"]} | {c["control"]} | {c["mse_ratio"]:.3f} | {c["cost_ratio"]:.3f} | {c["cost_adjusted_ratio"]:.3f} | {c["descriptive_endpoint_range"][0]:.3f}-{c["descriptive_endpoint_range"][1]:.3f} |')
(p/'RECYCLED-BASELINE-SCREEN-REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(primary_passed=report['primary_passed'],primary=primary,primary_z_gate=z_ok),indent=2))
