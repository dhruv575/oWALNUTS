import hashlib,itertools,json
from pathlib import Path
import numpy as np,arviz as az
from scipy.special import logsumexp
from exact_controls import fit_controls,predictive_logpmf
base=Path(__file__).resolve().parent;out=base/'scoring01';out.mkdir(exist_ok=False);summary=json.loads((base/'results/SUMMARY.json').read_text());repair=json.loads((base/'repair01/SUMMARY.json').read_text());jobs=json.loads((base/'JOBS.json').read_text());assert len(jobs)==36
original={x['name']:x for x in summary['rows']};repaired={x['name']:x for x in repair['rows']};loaded={}
for job in jobs:
    name=job['name'];folder=base/('results' if original[name]['completed'] else 'repair01')/name;row=original[name] if original[name]['completed'] else repaired[name];assert row['completed'];s=json.loads((folder/'SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained'];a=np.load(folder/'PREDICTIVE.npz');p=a['p256'];q=a['p128'];assert p.shape==q.shape and p.shape[1]==30 and np.isfinite(p).all() and (p>=0).all() and (p<=1).all();loaded[name]=(p,q)
    if (p==0).any():assert np.all(a['logp256'][p==0]<=np.log(np.finfo(float).tiny))
    assert hashlib.sha256(Path(job['draws']).read_bytes()).hexdigest()==job['draws_sha256']
labels=json.loads((base/'HELDOUT.json').read_text());observed=[x for x in labels if x['count'] is not None];years=np.array([x['year'] for x in observed]);y=np.array([x['count'] for x in observed]);assert len(y)==30
def mcmc(p,q):
    ds=az.convert_to_dataset({'p':p});mean=p.mean((0,1));mcse=np.asarray(az.mcse(ds,method='mean').p);assert np.min(mean)>0
    influence=np.mean(p/mean,axis=2);score_mcse=float(az.mcse(az.convert_to_dataset({'p':influence}),method='mean').p)
    return dict(mean=mean,mcse=mcse,rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),quadrature=np.mean(abs(p-q),axis=(0,1))/mean,log_mcse=mcse/mean,score_mcse=score_mcse)
def serial(st):return {k:v.tolist() if isinstance(v,np.ndarray) else v for k,v in st.items()}
groups=[];arrays=[];low=[]
for g in range(4):
    p=np.stack([loaded[f'reference-{g}-{c}'][0] for c in range(4)]);q=np.stack([loaded[f'reference-{g}-{c}'][1] for c in range(4)]);arrays.append(p);low.append(q);st=mcmc(p,q);checks=dict(finite=all(np.isfinite(x).all() for x in st.values()),rhat=max(st['rhat'])<=1.01,bulk=min(st['bulk'])>=1000,tail=min(st['tail'])>=1000,quadrature=max(st['quadrature'])<=1e-4);groups.append(dict(group=g,passed=bool(all(checks.values())),checks={k:bool(v) for k,v in checks.items()},stats=st))
reference=mcmc(np.concatenate(arrays),np.concatenate(low));pairs=[]
for a,b in itertools.combinations(groups,2):
    x,z=a['stats'],b['stats'];pairs.append(dict(groups=[a['group'],b['group']],max_z=float(max(abs(x['mean']-z['mean'])/np.sqrt(x['mcse']**2+z['mcse']**2))),max_log_difference=float(max(abs(np.log(x['mean'])-np.log(z['mean']))))))
checks=dict(groups=all(x['passed'] for x in groups),finite=all(np.isfinite(x).all() for x in reference.values()),rhat=max(reference['rhat'])<=1.01,bulk=min(reference['bulk'])>=4000,tail=min(reference['tail'])>=2000,log_mcse=max(reference['log_mcse'])<=.02,quadrature=max(reference['quadrature'])<=1e-4,pairs=all(x['max_z']<=4 and x['max_log_difference']<=.05 for x in pairs));reference_passed=bool(all(checks.values()))
training=json.loads((base/'FRESH-WORKFLOW-AUDIT.json').read_text());screen=json.loads((base/'IMPORTANCE-AUDIT.json').read_text());methods=[]
for rep in range(2):
    for method in ['native','wal','importance-screen','importance-fresh']:
        if method.startswith('importance'):
            stage=method.split('-')[1];name=f'{stage}-{rep}-importance';p,q=loaded[name];job=next(x for x in jobs if x['name']==name);w=np.load(job['draws'])['weight'];assert abs(w.sum()-1)<1e-12;mean=w@p;assert min(mean)>0;mcse=np.sqrt(np.sum((w[:,None]*(p-mean))**2,axis=0));influence=np.mean(p/mean,axis=1);st=dict(mean=mean,mcse=mcse,log_mcse=mcse/mean,quadrature=w@abs(p-q)/mean,score_mcse=float(np.sqrt(np.sum((w*(influence-w@influence))**2))));mc=True;train=next(x['qualified'] for x in (screen['rows'] if stage=='screen' else training['rows']) if x['rep']==rep and (stage=='screen' or x['method']=='importance'))
        else:
            p=np.stack([loaded[f'fresh-{rep}-{method}-{c}'][0] for c in range(4)]);q=np.stack([loaded[f'fresh-{rep}-{method}-{c}'][1] for c in range(4)]);st=mcmc(p,q);mc=max(st['rhat'])<=1.01 and min(st['bulk'])>=400 and min(st['tail'])>=400;train=next(x['qualified'] for x in training['rows'] if x['rep']==rep and x['method']==method)
        z=abs(st['mean']-reference['mean'])/np.sqrt(st['mcse']**2+reference['mcse']**2);err=abs(np.log(st['mean'])-np.log(reference['mean']));gate=dict(reference=reference_passed,training=train,finite=all(np.isfinite(x).all() for x in st.values()),mixing=bool(mc),quadrature=max(st['quadrature'])<=1e-4,log_error=max(err)<=.05,z=max(z)<=4,log_mcse=max(st['log_mcse'])<=.025)
        methods.append(dict(rep=rep,method=method,qualified=bool(all(gate.values())),checks={k:bool(v) for k,v in gate.items()},max_z=float(max(z)),max_log_error=float(max(err)),mean_log_score=float(np.log(st['mean']).mean()),stats=serial(st)))
controls=fit_controls(json.loads((base/'TRAIN.json').read_text()));constant=controls['constant'];lpconstant=predictive_logpmf(y,constant['shape'],constant['rate']);components=controls['changepoint']['components'];lpchange=logsumexp(np.array([np.log(c['probability'])+predictive_logpmf(y,c['late_shape'],c['late_rate']) for c in components]),axis=0)
comparisons=[]
if reference_passed:
    rng=np.random.default_rng(951800001);starts=rng.integers(0,31,size=(20000,7));indices=((starts[:,:,None]+np.arange(5))%31).reshape(20000,-1)[:,:31]
    for name,control in [('constant',lpconstant),('changepoint',lpchange)]:
        delta=np.log(reference['mean'])-control;calendar=np.full(31,np.nan);calendar[years-1931]=delta;boot=np.nanmean(calendar[indices],axis=1);ci=np.quantile(boot,[.025,.975]);comparisons.append(dict(control=name,mean_difference=float(delta.mean()),calendar_block95=ci.tolist(),yearly_differences=delta.tolist(),reference_score_mcse=reference['score_mcse']))
result=dict(completed=True,independent_audit_pending=True,reference_qualified=reference_passed,reference_checks={k:bool(v) for k,v in checks.items()},reference_groups=[dict(x,stats=serial(x['stats'])) for x in groups],reference_pairs=pairs,reference=serial(reference),methods=methods,years=years.tolist(),observed_counts=y.tolist(),exact_scores=dict(constant=lpconstant.tolist(),changepoint=lpchange.tolist()),mean_scores=dict(gp=float(np.log(reference['mean']).mean()),constant=float(lpconstant.mean()),changepoint=float(lpchange.mean())),comparisons=comparisons,predictive_advantage=bool(reference_passed and all(x['calendar_block95'][0]>0 for x in comparisons)),scope='Single exposed historical series; no algorithm-specific value or operational claim',inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [Path(__file__),base/'PREDICTIVE-SCORING-PROTOCOL.md',base/'HELDOUT.json',base/'TRAIN.json',base/'exact_controls.py']})
(out/'SUMMARY.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');print(json.dumps(dict(reference_qualified=reference_passed,mean_scores=result['mean_scores'],comparisons=comparisons,predictive_advantage=result['predictive_advantage'],method_passed=[dict(rep=x['rep'],method=x['method'],qualified=x['qualified']) for x in methods])),flush=True)
