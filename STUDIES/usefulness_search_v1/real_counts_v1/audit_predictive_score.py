import hashlib,json
from pathlib import Path
import numpy as np,arviz as az
from scipy.special import gammaln,logsumexp
from scipy.stats import nbinom
base=Path(__file__).resolve().parent;rawaudit=json.loads((base/'audit01/SUMMARY.json').read_text());assert rawaudit['passed'] and len(rawaudit['rows'])==36
s=json.loads((base/'scoring01/SUMMARY.json').read_text());assert s['completed'];v=[];low=[]
for g in range(4):
    chains=[];lo=[]
    for c in range(4):
        a=np.load(base/f'results/reference-{g}-{c}/PREDICTIVE.npz');chains.append(a['p256']);lo.append(a['p128'])
    v.extend(chains);low.extend(lo)
v=np.stack(v);low=np.stack(low);mean=v.mean((0,1));ds=az.convert_to_dataset({'p':v});mcse=np.asarray(az.mcse(ds,method='mean').p)
for k,actual in dict(mean=mean,mcse=mcse,rhat=np.asarray(az.rhat(ds,method='rank').p),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),log_mcse=mcse/mean,quadrature=np.mean(abs(v-low),axis=(0,1))/mean).items():assert np.allclose(actual,s['reference'][k],rtol=1e-10,atol=1e-10),k
score_mcse=float(az.mcse(az.convert_to_dataset({'score':np.mean(v/mean,axis=2)}),method='mean').score);assert np.isclose(score_mcse,s['reference']['score_mcse'],rtol=1e-10)
train=json.loads((base/'TRAIN.json').read_text());held=json.loads((base/'HELDOUT.json').read_text());observed=[x for x in held if x['count'] is not None];counts=np.array([x['count'] for x in observed]);years=np.array([x['year'] for x in observed]);ty=np.array([x['count'] for x in train if x['count'] is not None]);year=np.array([x['year'] for x in train if x['count'] is not None]);shape=1+ty.sum();rate=1+len(ty);constant=nbinom.logpmf(counts,shape,rate/(rate+1));terms=[];prior=[]
for switch in range(1851,1931):
    a,b=ty[year<=switch],ty[year>switch];prior.append(sum(gammaln(1+z.sum())-(1+z.sum())*np.log(1+len(z))-gammaln(z+1).sum() for z in [a,b]));r=1+len(b);terms.append(nbinom.logpmf(counts,1+b.sum(),r/(r+1)))
logweights=np.array(prior)-logsumexp(prior);change=logsumexp(np.array(terms)+logweights[:,None],axis=0)
assert np.allclose(constant,s['exact_scores']['constant'],rtol=1e-12,atol=1e-12) and np.allclose(change,s['exact_scores']['changepoint'],rtol=1e-12,atol=1e-12)
for key,value in dict(gp=np.log(mean).mean(),constant=constant.mean(),changepoint=change.mean()).items():assert np.isclose(value,s['mean_scores'][key],rtol=1e-12,atol=1e-12)
rng=np.random.default_rng(951800001);starts=rng.integers(0,31,size=(20000,7));checks=[]
for item in s['comparisons']:
    control=constant if item['control']=='constant' else change;delta=np.log(mean)-control;calendar=np.full(31,np.nan);calendar[years-1931]=delta;replicates=[]
    for row in starts:
        indices=np.concatenate([np.arange(i,i+5)%31 for i in row])[:31];replicates.append(float(np.nanmean(calendar[indices])))
    interval=np.quantile(replicates,[.025,.975]);assert np.allclose(interval,item['calendar_block95'],rtol=1e-12,atol=1e-12) and np.allclose(delta,item['yearly_differences'],rtol=1e-12,atol=1e-12);checks.append(dict(control=item['control'],mean_difference=float(delta.mean()),calendar_block95=interval.tolist()))
result=dict(passed=True,raw_prediction_jobs=36,reference_draws=v.shape[0]*v.shape[1],mean_scores=s['mean_scores'],comparisons=checks,predictive_advantage=s['predictive_advantage'],scope='All predictive raw outputs replayed; combined diagnostics and scores independently recomputed, SciPy negative-binomial exact controls and independent block-index bootstrap checked',scoring_sha256=hashlib.sha256((base/'scoring01/SUMMARY.json').read_bytes()).hexdigest(),auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'PREDICTIVE-SCORE-AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
