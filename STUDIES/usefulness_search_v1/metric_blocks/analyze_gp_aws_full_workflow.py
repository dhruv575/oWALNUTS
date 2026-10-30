"""Audit frozen gates and report fixed-budget cost/precision without speed claims."""
import hashlib,json
from pathlib import Path
import numpy as np
import arviz as az
from scipy.special import logsumexp
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_aws_full_remote01/results';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==28
configs=[('raw','walnuts_dense'),('raw','diag'),('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','diag'),('importance','importance')]
assert {(x['fold'],x['transform'],x['mode']) for x in s['rows']}=={(f,t,m) for f in range(4) for t,m in configs}
for name,h in s['inputs'].items():assert hashlib.sha256((r.parent/name).read_bytes()).hexdigest()==h
reference=json.loads((r.parent/'REFERENCE.json').read_text());assert all(x['passed'] for x in reference['references']);rows=[]
for item in s['rows']:
    ref=next(x['stats'] for x in reference['references'] if x['scenario']==item['fold'])
    row={k:item[k] for k in ['fold','transform','mode','seed','completed','passed']};d=r/f"{item['fold']}-{item['transform']}-{item['mode']}"
    if item['completed']:
        result=item['result'];f=result if item['transform']=='importance' else result['functionals']
        mean=np.asarray(f['mean']);sd=np.asarray(f['sd']);mcse=np.asarray(f['mcse']);assert mean.shape==sd.shape==mcse.shape==(24,)
        if item['transform']=='importance':
            raw=np.load(d/'draws.npz');weights=raw['weight'];values=raw['values'];active=weights>0
            assert np.allclose(weights,np.exp(raw['log_weight']-logsumexp(raw['log_weight'])),rtol=1e-12,atol=1e-15)
            assert np.allclose(raw['log_weight'],raw['log_target']-raw['log_proposal'],rtol=1e-12,atol=1e-12)
            v=values[active];w=weights[active];raw_mean=w@v;raw_sd=np.sqrt(w@((v-raw_mean)**2));raw_mcse=np.sqrt(np.sum((w[:,None]*(v-raw_mean))**2,axis=0))
            _,pk=az.psislw(raw['log_weight']);assert np.isclose(result['pareto_k'],float(pk),rtol=1e-12,atol=1e-12)
            assert np.isclose(result['ess'],1/np.sum(weights**2),rtol=1e-12)
        else:
            values=np.load(d/'FUNCTIONALS.npz')['values'];assert values.shape==(4,8000,24)
            raw_mean=values.mean((0,1));raw_sd=values.reshape(-1,24).std(0,ddof=1);ds=az.convert_to_dataset({'p':values});raw_mcse=np.asarray(az.mcse(ds,method='mean').p)
            for key,actual in [('bulk',np.asarray(az.ess(ds,method='bulk').p)),('tail',np.asarray(az.ess(ds,method='tail').p)),('rhat',np.asarray(az.rhat(ds,method='rank').p))]:assert np.allclose(f[key],actual,rtol=1e-12,atol=1e-12)
            draws=np.load(d/'DRAWS-STATS.npz');assert int(draws['sample_stats__diverging'].sum())==result['divergences']
        for stored,actual in [(mean,raw_mean),(sd,raw_sd),(mcse,raw_mcse)]:assert np.allclose(stored,actual,rtol=1e-12,atol=1e-12)
        finite=all(np.isfinite(a).all() for a in [mean,sd,mcse]);error=abs(mean-ref['mean'])/ref['sd'];sderr=abs(sd/ref['sd']-1);z=abs(mean-ref['mean'])/np.sqrt(mcse**2+np.asarray(ref['mcse'])**2)
        gates=dict(finite=finite,mean_error=max(error)<=.1,sd_error=max(sderr)<=.1,combined_z=max(z)<=4)
        if item['transform']=='importance':gates.update(ess=result['ess']>=400,pareto_k=result['pareto_k']<.7)
        else:gates.update(rhat=result['rhat']<=1.01,bulk=result['bulk']>=400,tail=result['tail']>=400,divergences=result['divergences']==0)
        assert all(gates.values())==item['passed'];timing=json.loads((d/'PROCESS-TIME.json').read_text());assert timing['returncode']==0 and timing['seconds']>0
        row.update(seconds=timing['seconds'],worst_standardized_mcse=float(max(mcse/ref['sd'])),max_mean_error=float(max(error)),max_sd_error=float(max(sderr)),failed_gates=[k for k,v in gates.items() if not v])
        if (d/'SETUP.json').exists():row['setup']=json.loads((d/'SETUP.json').read_text())
    rows.append(row)
all_qualified=all(x['passed'] for x in rows);assert all_qualified==s['all_qualified']
lines=['# Serial complete-workflow results','','Fixed budgets, four exposed-map scenarios, precompiled libraries. Process time includes child imports, setup, sampling, diagnostics and writes. This is not a precision-matched speed ranking.','','| Scenario | Workflow | Qualified | Process seconds | Worst mean MCSE/reference SD | Max mean error/reference SD |','|---|---|---|---|---|---|']
for row in rows:
    lines.append(f"| {row['fold']} | {row['transform']}/{row['mode']} | {row['passed']} | {row.get('seconds','unavailable')} | {row.get('worst_standardized_mcse','unavailable')} | {row.get('max_mean_error','unavailable')} |")
lines+=['',f'All28 qualified: {all_qualified}.','', 'No method or scenario is removed. If any fails, competitive summaries are withheld. Even if all pass, these four conditional scenarios and fixed budgets do not prove a practical advantage or optimal implementation. Setup is regenerated per workflow; map training, proposal construction and achieved precision must remain visible. Native and importance ESS are not treated as equivalent.']
(p/'GP-AWS-FULL-WORKFLOW-RESULT.md').write_text('\n'.join(lines)+'\n')
(r/'AUDIT.json').write_text(json.dumps(dict(passed=True,all_qualified=all_qualified,rows=rows),indent=2,allow_nan=False)+'\n');print(json.dumps(dict(audited=len(rows),all_qualified=all_qualified)))
