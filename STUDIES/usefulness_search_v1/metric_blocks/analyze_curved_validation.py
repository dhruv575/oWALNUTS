import hashlib,json
from pathlib import Path
import numpy as np
import arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'curved_cold_validation01';s=json.loads((r/'SUMMARY.json').read_text());assert s['passed']
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
truth=np.array(json.loads((l/'banana_recycling_test01/EXACT-CONTROL.json').read_text())['truth']);var=np.tile([1.,51.],12);scale=np.r_[np.sqrt(var),var,np.ones(48)];arms=list(s['builds']);est={a:[] for a in arms};mcse={a:[] for a in arms};cost={a:[] for a in arms};div={a:0 for a in arms};full_diag={}
def summary(c,a):return c['summary'] if a=='exact' or '_wal_' in a else c['conditional_summary' if a.endswith('_recycled') else 'ordinary_summary']
for batch in range(16):
    f=r/f'batch-{batch:02d}';ts=json.loads((f/'TIMINGS.json').read_text());assert len(ts)==27
    for arm in arms:
        data=json.loads((f/f'RAW-{arm}.json').read_text());cost[arm].append(float(np.mean([v['seconds'] for v in ts if v['arm']==arm])))
        for c in data['chains']:
            sm=summary(c,arm);assert sm['count']==2000 and sm['block_sizes']==[50]*40;est[arm].append(sm['mean']);mcse[arm].append(np.std(sm['block_means'],axis=0,ddof=1)/np.sqrt(40));div[arm]+=c['retained_divergences']
for arm in arms:
    full=json.loads((r/'full'/arm/'RAW.json').read_text());compact=json.loads((r/'batch-00'/f'RAW-{arm}.json').read_text());xs=[]
    for a,b in zip(full['chains'],compact['chains']):
        native='_native_' in arm;warmup=1000 if native else 0;q=np.array(a['all_draws' if native else 'draws'],dtype='<f8');assert hashlib.sha256(q.tobytes()).hexdigest()==b['draw_sha256'];x=q[warmup:];xs.append(x);physical=x.copy()
        if arm.startswith('latent'):physical[:,1::2]+=5*(physical[:,::2]**2-1)
        obs=np.concatenate([physical,physical*physical,(physical<0).astype(float),(physical< -2).astype(float)],axis=1)
        v=np.array(a['recycled'])[warmup:] if arm.endswith('_recycled') else obs;sm=summary(b,arm);assert v.shape==(2000,96);np.testing.assert_allclose(sm['mean'],v.mean(0),rtol=2e-13,atol=1e-10);np.testing.assert_allclose(sm['block_means'],v.reshape(40,50,96).mean(1),rtol=2e-13,atol=1e-10)
        for k in ['target_calls','retained_divergences']:assert a[k]==b[k]
    x=np.array(xs);full_diag[arm]=dict(max_rhat=max(float(az.rhat(x[:,:,i])) for i in range(24)),min_bulk=min(float(az.ess(x[:,:,i],method='bulk')) for i in range(24)),min_tail=min(float(az.ess(x[:,:,i],method='tail')) for i in range(24)),scope='First validation batch only; not full validation qualification')
est={a:np.array(v) for a,v in est.items()};mcse={a:np.array(v) for a,v in mcse.items()};cost={a:np.array(v) for a,v in cost.items()};calcost={a:0. for a in arms};eligibility={a:True for a in arms}
for choice in s['selection']['selected']:
    arm=choice['representation']+'_'+choice['engine']+'_'+choice['mode'];calcost[arm]=choice['all_candidate_calibration_seconds'];eligibility[arm]=choice['eligible']
diagnostics={a:dict(retained_divergences=div[a],aggregate_error_z=((est[a].mean(0)-truth)/(est[a].std(0,ddof=1)/8)).tolist(),coverage95=np.mean(abs(est[a]-truth)<=1.96*mcse[a],axis=0).tolist(),first_batch=full_diag[a],mean_batch_seconds=float(cost[a].mean()),calibration_one_pass_seconds=calcost[a],amortized_mean_batch_seconds=float(cost[a].mean()+calcost[a]/16),selected_eligible=eligibility[a]) for a in arms}
idx=np.random.default_rng(942040001).integers(0,64,(10000,64));ci=np.random.default_rng(942050001).integers(0,16,(10000,16));base='direct_wal_recycled';families=[]
for j,family in enumerate(['mean','second_moment','below_zero','below_minus_two']):
    sl=slice(j*24,(j+1)*24);errors={a:np.mean(((est[a][:,sl]-truth[sl])/scale[sl])**2,axis=1) for a in arms};comparisons=[]
    for arm in arms:
        if arm==base:continue
        mr=float(errors[arm].mean()/errors[base].mean());mi=np.quantile(errors[arm][idx].mean(1)/errors[base][idx].mean(1),[.025,.975]);cost_rows={}
        for label,amortized in [('single_fit',False),('calibration_amortized',True)]:
            aa=calcost[arm]/16 if amortized else 0;bb=calcost[base]/16 if amortized else 0;cr=float((cost[arm].mean()+aa)/(cost[base].mean()+bb));cc=np.quantile((cost[arm][ci].mean(1)+aa)/(cost[base][ci].mean(1)+bb),[.025,.975]);cost_rows[label]=dict(cost_ratio=cr,cost_interval=cc.tolist(),adjusted_ratio=mr*cr,descriptive_endpoint_range=[float(mi[0]*cc[0]),float(mi[1]*cc[1])])
        comparisons.append(dict(control=arm,mse_ratio=mr,mse_interval=mi.tolist(),costs=cost_rows))
    families.append(dict(family=family,mse={a:float(errors[a].mean()) for a in arms},comparisons=comparisons))
checks={c['control']:all(v['descriptive_endpoint_range'][0]>1.2 for v in c['costs'].values()) for c in families[1]['comparisons'] if c['control']!='direct_wal_ordinary'};z_ok=all(max(abs(z) for z in v['aggregate_error_z'][24:48])<=4.5 for v in diagnostics.values());zero_div=all(v==0 for v in div.values());eligible=all(eligibility.values());efficiency_gate=all(checks.values()) and z_ok and zero_div and eligible
out=dict(efficiency_gate_passed=efficiency_gate,promotion_established=False,checks=checks,z_gate=z_ok,zero_divergence_gate=zero_div,eligible_gate=eligible,diagnostics=diagnostics,families=families,full_replays_verified=9,scope='Known-truth selected synthetic target. Product endpoints are descriptive, not joint confidence intervals. A positive efficiency gate requires further all-batch diagnostic audit; no application or novelty claim.')
(p/'CURVED-COLD-VALIDATION-ANALYSIS.json').write_text(json.dumps(out,indent=2,allow_nan=False)+'\n');lines=['# Tuned curved cold validation','',f'Competitive efficiency gate passed: {efficiency_gate}. Promotion established: False. Ratios above one favor direct recycled WAL.','', '| Family | Control | MSE ratio | Single-fit adjusted ratio (range) | Calibration-amortized ratio (range) |','|---|---|---:|---|---|']
for f in families:
    for c in f['comparisons']:
        a=c['costs']['single_fit'];b=c['costs']['calibration_amortized'];lines.append(f'| {f["family"]} | {c["control"]} | {c["mse_ratio"]:.3f} | {a["adjusted_ratio"]:.3f} ({a["descriptive_endpoint_range"][0]:.3f}-{a["descriptive_endpoint_range"][1]:.3f}) | {b["adjusted_ratio"]:.3f} ({b["descriptive_endpoint_range"][0]:.3f}-{b["descriptive_endpoint_range"][1]:.3f}) |')
(p/'CURVED-COLD-VALIDATION-REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(dict(efficiency_gate_passed=efficiency_gate,z_gate=z_ok,zero_divergence_gate=zero_div,eligible_gate=eligible,primary=families[1]),indent=2))
