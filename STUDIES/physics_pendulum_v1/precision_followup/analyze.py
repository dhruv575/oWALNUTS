"""Raw numerical audit and frozen pilot evaluation; opens future data only here."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.special import expit,logsumexp,ndtr,roots_legendre
from prepare import solve
from backend import Backend,unconstrained
ROOT=Path(__file__).resolve().parent
out=ROOT/'analysis'

def main():
    selection=json.loads((ROOT/'SELECTION.json').read_text())
    frozen=json.loads((ROOT/'CAMPAIGN-MANIFEST.json').read_text())['sources']
    assert all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items())
    rows=json.loads((ROOT/'ROWS.json').read_text());results=[];audit=[]
    for row in rows:
        if row['status']!='ok':continue
        folder=ROOT/row['folder'];r=json.loads((folder/'result/RESULT.json').read_text());s=json.loads((folder/'SUPERVISION.json').read_text())
        assert s['status']=='exited' and s['exit_code']==0 and s['group_drained']
        a=np.load(folder/'result/draws.npz');q=a['q'].reshape(-1,2);pred=a['pred'].reshape(-1,5)
        assert np.isfinite(q).all() and np.isfinite(pred).all()
        if 'z' in a:assert np.allclose(q,np.array([-5.,-2.])+np.array([6.,4.])*expit(a['z'].reshape(-1,2)),rtol=1e-12,atol=1e-12)
        f=np.column_stack([q,np.exp(q),pred])
        lw=a['logweights'] if 'logweights' in a else np.zeros(len(q));weights=np.exp(lw-logsumexp(lw))
        mean=weights@f
        sd=np.sqrt(weights@((f-mean)**2)) if 'logweights' in a else f.std(0,ddof=1)
        p=float(weights@ndtr(pred[:,2]/.05))
        assert np.allclose(mean,r['summary']['mean'],rtol=1e-9,atol=1e-10)
        assert np.allclose(sd,r['summary']['sd'],rtol=1e-9,atol=1e-10)
        assert abs(p-r['summary']['probability'])<1e-10
        d=json.loads((ROOT/'data'/f"case{r['case']}.json").read_text());d['linear']=r['config']=='linear'
        # Posterior-mass-spaced deterministic points; independent DOP853.
        indices=np.unique(np.minimum(np.searchsorted(np.cumsum(weights),np.linspace(.001,.999,32)),len(q)-1))
        error=0.;density_error=0.
        if r['phase']=='grid':
            nodes,w=roots_legendre(256);expected=np.stack(np.meshgrid(-2+3*nodes,2*nodes,indexing='ij'),axis=-1).reshape(-1,2)
            assert np.array_equal(q,expected)
            qw=(np.log(w)[:,None]+np.log(w)[None,:]+np.log(6)).ravel()
        for i in indices:
            exact=solve(q[i],np.array(d['future_times']),d['theta'],d['linear'])
            error=max(error,float(max(abs(exact-pred[i]))))
            if r['phase']=='grid':
                train=solve(q[i],np.array(d['times']),d['theta'],d['linear'])
                lp=-.5*np.sum(((train-d['observed'])/.05)**2)-.5*np.sum(((q[i]-np.log([.2,2.]))/[.8,.5])**2)
                density_error=max(density_error,abs(lp+qw[i]-lw[i]))
        assert error<=2e-6 and density_error<=2e-4,(row['job'],error,density_error)
        audit.append(dict(job=row['job'],raw_draws=len(q),ode_points=len(indices),max_angle_error=error,max_logweight_error=density_error))
        evaluation=json.loads((ROOT/'data'/f"case{r['case']}-evaluation.json").read_text())
        y=np.asarray(evaluation['future_observations']);lp=-.5*((pred-y)/.05)**2-np.log(.05)-.5*np.log(2*np.pi)
        scores=logsumexp(lp+lw[:,None],axis=0)-logsumexp(lw)
        r.update(future_log_scores=scores.tolist(),mean_future_log_score=float(scores.mean()),
                 latent_forecast_rmse=float(np.sqrt(np.mean((mean[4:]-evaluation['latent_future'])**2))),folder=row['folder'])
        results.append(r)
    cases=[]
    for case in range(2):
        records=[r for r in results if r['case']==case]
        references=[r for r in records if r['phase']=='grid' and r['config']=='nonlinear']
        ref=references[0] if references else None
        qualified=bool(ref and ref['reference_pass'])
        summary=dict(case=case,reference_qualified=qualified,advance_to_replication=False,comparisons=[])
        if not qualified:cases.append(summary);continue
        rm=np.array(ref['summary']['mean']);rs=np.array(ref['summary']['sd']);tolerance=np.r_[.1*rs[:4],np.full(5,.02)]
        for r in records:
            means=np.array(r['summary']['mean']);p_error=abs(r['summary']['probability']-ref['summary']['probability'])
            errors=abs(means-rm)
            forecast=bool(max(errors[4:])<=.02 and p_error<=.02)
            full=bool(np.all(errors<=tolerance) and p_error<=.02)
            if r['phase'] in ['validate','calibrate','laplace']:
                precision=bool(np.all(np.array(r['summary']['mcse'])<=tolerance/2) and r['summary']['probability_mcse']<=.01)
                valid=full and precision and r['summary']['diagnostic_pass']
            elif r['phase']=='grid':valid=full and r['reference_pass']
            else:valid=full and r['approximation_quadrature_pass']
            r.update(accuracy_pass=bool(valid),forecast_tolerance_pass=forecast,parameter_error_sd=float(max(errors[:4]/rs[:4])),max_angle_mean_error=float(max(errors[4:])),probability_error=p_error)
            if r['phase']!='calibrate':summary['comparisons'].append({k:r[k] for k in ['phase','config','rep','accuracy_pass','forecast_tolerance_pass','parameter_error_sd','max_angle_mean_error','probability_error','total_seconds','mean_future_log_score','latent_forecast_rmse']})
        wal=[r for r in records if r['phase']=='validate' and r['config'].startswith('walnuts_')]
        nuts=[r for r in records if r['phase']=='validate' and r['config'].startswith('nuts_')]
        pairs=[]
        for w in wal:
            ns=[n for n in nuts if n['rep']==w['rep']]
            if ns and w['accuracy_pass'] and ns[0]['accuracy_pass']:
                n=ns[0];pairs.append(dict(rep=w['rep'],full_cost_ratio=n['total_seconds']/w['total_seconds'],kernel_ratio=n['seconds']/w['seconds']))
        cheap=[r for r in records if (r['phase'] in ['laplace','laplace_grid'] and r['config']=='nonlinear') or (r['phase']=='grid' and r['config']=='linear')]
        # Missing or numerically unqualified controls cannot be treated as defeated.
        controls_complete=len(cheap)==3 and all(r.get('reference_pass',r.get('approximation_quadrature_pass',True)) for r in cheap)
        cheap_misses=controls_complete and all(not r['forecast_tolerance_pass'] for r in cheap)
        w_pass=sum(r['accuracy_pass'] for r in wal);n_pass=sum(r['accuracy_pass'] for r in nuts)
        cost_ratio=float(np.median([p['full_cost_ratio'] for p in pairs])) if pairs else None
        grid_ratio=ref['total_seconds']/float(np.median([w['total_seconds'] for w in wal])) if wal else None
        advance=bool(w_pass==4 and w_pass>=n_pass and len(pairs)==4 and cost_ratio>=1.5 and all(p['full_cost_ratio']>1 for p in pairs) and cheap_misses and grid_ratio>=1.5)
        summary.update(wal_pass=w_pass,nuts_pass=n_pass,pairs=pairs,median_full_cost_ratio=cost_ratio,quadrature_to_wal_full_cost_ratio=grid_ratio,cheap_controls_complete=controls_complete,cheap_controls_miss_forecast=cheap_misses,advance_to_replication=advance)
        cases.append(summary)
    intact=all(hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h for n,h in frozen.items());assert intact
    result=dict(raw_audit_passed=True,cases=cases,failed_jobs=[r for r in rows if r['status']!='ok'],source_hashes_intact=intact,
                scope='Two synthetic pendulum cases, four validation seeds; exploratory, no deployment or neural-world-model claim')
    (out/'RAW-AUDIT.json').write_text(json.dumps(dict(passed=True,rows=audit),indent=2)+'\n')
    (out/'RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
    (out/'ALL-RESULTS.json').write_text(json.dumps(results,indent=2)+'\n')
    lines=['# Pendulum physics pilot','',result['scope'],'','Independent raw/numerical audit passed.','']
    for c in cases:
        lines+=['## Case '+str(c['case']),json.dumps({k:v for k,v in c.items() if k!='comparisons'},indent=2),'']
        for r in c['comparisons']:lines.append('- '+json.dumps(r))
    lines+=['','Quadrature, Laplace and the linear model are explicit competitors. Future scores are descriptive; no population calibration claim.']
    (out/'REPORT.md').write_text('\n'.join(lines)+'\n');print(json.dumps(result),flush=True)
if __name__=='__main__':main()
