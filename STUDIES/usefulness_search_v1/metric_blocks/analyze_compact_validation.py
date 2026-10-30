import json
from pathlib import Path
import numpy as np
study=Path(__file__).resolve().parent;root=study/'local_recovery/compact_validation01';assert json.loads((root/'SUMMARY.json').read_text())['passed']
prior=json.loads((study/'RECYCLING-MSE-ANALYSIS.json').read_text());truths={t['target']:np.array(t['truth']) for t in prior['targets']}
idx=np.random.Generator(np.random.PCG64(941420001)).integers(0,64,size=(10000,64));ciidx=np.random.Generator(np.random.PCG64(941430101)).integers(0,16,size=(10000,16));rows=[]
lines=['# Fresh compact-recycling validation','','| Target | Family | MSE ratio (95% CI) | Direct cost ratio | Cost-adjusted ratio | Descriptive range |','|---|---|---|---|---|---|']
for target,truth in truths.items():
    d=len(truth)//4;est=[[],[]];mcse2=[[],[]];times=np.zeros((2,3,16));events=dict(divergences=0,depth_caps=0);output_bytes=[0,0]
    for batch in range(16):
        folder=root/f'{target}-{batch:02d}';a=json.loads((folder/'RAW-original.json').read_text());b=json.loads((folder/'RAW-observed.json').read_text())
        for x,y in zip(a['chains'],b['chains']):
            for k in x:
                if k not in ['seconds','summary']:assert x[k]==y[k]
        for arm,r in enumerate([a,b]):
            output_bytes[arm]+=(folder/('RAW-original.json' if arm==0 else 'RAW-observed.json')).stat().st_size
            for c in r['chains']:
                s=c['summary'];assert s['count']==1000 and s['block_sizes']==[50]*20
                est[arm].append(s['mean']);mcse2[arm].append(np.asarray(s['block_means']).var(axis=0,ddof=1)/20)
                if arm==0:events['divergences']+=c['retained_divergences'];events['depth_caps']+=c['work']['maximum_depth_stops']
        for r in json.loads((folder/'TIMINGS.json').read_text()):times[int(r['arm']=='observed'),r['repeat'],batch]=r['seconds']
    cost=float(times[1].sum()/times[0].sum());batchmeans=times.mean(axis=1);costboot=batchmeans[1,ciidx].sum(axis=1)/batchmeans[0,ciidx].sum(axis=1);costci=np.quantile(costboot,[.025,.975]).tolist()
    est=np.array(est);mcse2=np.array(mcse2);error=est-truth;scale=np.concatenate([np.sqrt(truth[d:2*d]),truth[d:2*d],np.ones(2*d)]);sq=(error/scale)**2;families=[];functionals=[]
    for j,name in enumerate(['mean','second_moment','below_zero','below_minus2']):
        section=slice(j*d,(j+1)*d);a=sq[0,:,section].mean(axis=1);b=sq[1,:,section].mean(axis=1);ratio=float(a.mean()/b.mean());ci=np.quantile(a[idx].mean(axis=1)/b[idx].mean(axis=1),[.025,.975]).tolist();flags=[]
        for i in range(d):
            k=j*d+i;z=error[:,:,k].mean(axis=1)/(error[:,:,k].std(axis=1,ddof=1)/8);flag=bool(np.any(abs(z)>4.5));flags.append(flag)
            av=sq[0,:,k];bv=sq[1,:,k];fci=np.quantile(av[idx].mean(axis=1)/bv[idx].mean(axis=1),[.025,.975]).tolist()
            functionals.append(dict(family=name,coordinate=i,mse_ratio=float(av.mean()/bv.mean()),ci95=fci,bias_z=z.tolist(),bias_flag=flag,coverage95=np.mean(np.abs(error[:,:,k])<=1.96*np.sqrt(mcse2[:,:,k]),axis=1).tolist(),estimated_variance_over_mse=(mcse2[:,:,k].mean(axis=1)/(error[:,:,k]**2).mean(axis=1)).tolist()))
        interval=[ci[0]/costci[1],ci[1]/costci[0]];families.append(dict(family=name,ratio=ratio,ci95=ci,cost_adjusted=ratio/cost,descriptive_range=interval,bias_flag=any(flags),primary_pass=target=='analytic_rotated_gaussian' and name=='below_minus2' and ci[0]>1.2 and interval[0]>1.1 and not any(flags)))
        lines.append(f'| {target} | {name} | {ratio:.3f} [{ci[0]:.3f}, {ci[1]:.3f}] | {cost:.3f} | {ratio/cost:.3f} | [{interval[0]:.3f}, {interval[1]:.3f}] |')
    rows.append(dict(target=target,cost_ratio=cost,cost_ci95=costci,repetition_cost_ratios=(times[1].sum(axis=1)/times[0].sum(axis=1)).tolist(),families=families,functionals=functionals,replicate_estimates=est.tolist(),batch_mcse_squared=mcse2.tolist(),truth=truth.tolist(),events=events,output_bytes=output_bytes))
passed=any(f['primary_pass'] for t in rows for f in t['families']);lines+=['',f'Predeclared scoped primary passed: {passed}.','No general improvement or application claim. Coverage diagnostics, all coordinate results, events and exact truths are in the JSON. Cost-adjusted endpoint ranges are descriptive, not joint 95% intervals. Native/recycled NUTS and cold-workflow validation remain outstanding.']
(study/'COMPACT-VALIDATION-ANALYSIS.json').write_text(json.dumps(dict(primary_passed=passed,rows=rows),indent=2,allow_nan=False)+'\n');(study/'COMPACT-VALIDATION-REPORT.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
