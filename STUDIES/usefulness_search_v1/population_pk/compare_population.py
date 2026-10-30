import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import logsumexp
import arviz as az
from predictive import features,prediction,data
ROOT=Path(__file__).resolve().parent;REF=Path('/dev/shm/population-analytic-reference-20261029');IMP=Path('/dev/shm/population-importance-repaired-20261029')
assert json.loads((REF/'REFERENCE-AUDIT.json').read_text())['practical_reference_qualified'];assert json.loads((ROOT/'run01/FINAL.json').read_text())['dependencies_unchanged']
refq=[];inputs=[]
for folder in (REF/'run01').glob('*/result'):
 r=json.loads((folder/'RESULT.json').read_text())
 if r['engine']=='pymc_jump':refq.append(np.load(folder/'draws.npz')['q']);inputs.extend([folder/'RESULT.json',folder/'draws.npz'])
refq=np.concatenate(refq,axis=0);rf=features(refq);rs=az.summary(az.from_dict(posterior={'f':rf}),round_to='none');means=np.asarray(rs['mean']);mcse=np.asarray(rs.mcse_mean);sd=np.asarray(rs.sd)
def scores(q):
 logmu=prediction(q);obs=data()[-1].ravel();sigma=np.exp(q[...,-1:]);ll=-np.log(obs)-np.log(sigma)-.5*np.log(2*np.pi)-.5*((np.log(obs)-logmu)/sigma)**2
 return logsumexp(ll.reshape(-1,24),axis=0).reshape(12,2).sum(1)-2*np.log(np.prod(q.shape[:-1]))
refscores=scores(refq);rng=np.random.default_rng(938999001);indices=rng.integers(12,size=(20000,12));rows=[]
for folder in sorted((ROOT/'run01').glob('*/result')):
 r=json.loads((folder/'RESULT.json').read_text());q=np.load(folder/'draws.npz')['q'];s=az.summary(az.from_dict(posterior={'f':features(q)}),round_to='none');s.to_json(folder/'DIAGNOSTICS.json',orient='split',indent=2)
 z=np.abs(np.asarray(s['mean'])-means)/np.sqrt(np.asarray(s.mcse_mean)**2+mcse**2);scaled=np.abs(np.asarray(s['mean'])-means)/sd
 numerical=r['divergences_by_phase'][1]==0 and r['depth_hits_by_phase'][1]==0
 passed=numerical and s.r_hat.max()<=1.01 and s.ess_bulk.min()>=400 and s.ess_tail.min()>=200 and z.max()<=4.5 and scaled.max()<=.1
 rows.append(dict(**r,rhat_max=float(s.r_hat.max()),ess_bulk_min=float(s.ess_bulk.min()),ess_tail_min=float(s.ess_tail.min()),maximum_mean_z=float(z.max()),maximum_mean_scaled_error=float(scaled.max()),minimum_bulk_ess_per_second=float(s.ess_bulk.min()/r['seconds']),passed=bool(passed),callback_phase_unresolved=r['calls_errors'][1]>0,subject_log_scores=scores(q).tolist()))
 inputs.extend([folder/'RESULT.json',folder/'draws.npz'])
baselines=[]
for folder in sorted((IMP/'run01').glob('*/result')):
 r=json.loads((folder/'RESULT.json').read_text());inputs.append(folder/'RESULT.json')
 for label in ['importance','laplace']:
  v=r[label];mm=np.array([np.nan if x is None else x for x in v['mean']]);diff=np.abs(mm-means);dd=refscores-np.array(v['subject_log_scores']);bootstrap=dd[indices].mean(axis=1)
  baselines.append(dict(seed=r['seed'],method=label,weight_gate=v.get('weight_gate'),ess=v.get('ess'),pareto_k=v.get('pareto_k'),max_parameter_mean_scaled_error=float(np.nanmax((diff/sd)[:43])),max_forecast_mean_scaled_error=float(np.nanmax((diff/sd)[43:67])),reference_minus_baseline_mean_subject_log_score=float(dd.mean()),subject_bootstrap_95_percent=np.quantile(bootstrap,[.025,.975]).tolist(),subject_log_score_differences=dd.tolist(),not_independent_validation=True))
p=json.loads((ROOT/'PREPARED.json').read_text());mapq=np.array(p['mode'])[None,None,:];mapdiff=refscores-scores(mapq);mapboot=mapdiff[indices].mean(axis=1)
result=dict(native=rows,baselines=baselines,reference_subject_log_scores=refscores.tolist(),reference_minus_map_subject_score_mean=float(mapdiff.mean()),map_subject_bootstrap_95_percent=np.quantile(mapboot,[.025,.975]).tolist(),heldout_data_previously_exposed=True,unvisited_mode_mass_unbounded=True,goal_achieved=False)
(ROOT/'COMPARISON.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n');(ROOT/'COMPARISON-INPUTS.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2)+'\n');print(json.dumps(result,indent=2))
