import hashlib,json
from pathlib import Path
import numpy as np
from scipy.stats import norm
root=Path(__file__).resolve().parent;run=root/'run01';out=root/'analysis01';out.mkdir(exist_ok=False)
final=json.loads((run/'FINAL.json').read_text());assert final['unchanged'];rows=[];hashes={};failures=[]
def functionals(q):
 v=dict(positive_mass=(q[:,0]>0).astype(float),mean=q[:,0],second=q[:,0]**2)
 if q.shape[1]>1:v.update(other_mean=q[:,1:].mean(1),other_second=(q[:,1:]**2).mean(1))
 return v
for j in final['results']:
 if j['exit_code']!=0 or not j['group_drained']:failures.append(j);continue
 folder=run/f"{j['index']:03d}";r=json.loads((folder/'RESULT.json').read_text());a=np.load(folder/'draws.npz')
 if r['arm']=='is':
  q=a['q'];w=a['weight'];assert np.isfinite(w).all() and abs(w.sum()-1)<1e-12;ess=float(1/np.sum(w*w))
 else:q=a['post_sweep'][20:].reshape(-1,r['d']);w=np.full(len(q),1/len(q));ess=None
 assert np.isfinite(q).all();values={k:float(v@w) for k,v in functionals(q).items()};rows.append(dict(**r,values=values,importance_ess=ess))
 for n in ['RESULT.json','draws.npz','SUPERVISION.json']:
  p=folder/n;hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
truth=dict(positive_mass=.8*norm.sf(4)+.2*norm.sf(-40),mean=-4.8,second=67.208,other_mean=0.,other_second=1.)
groups=[];gates=[]
for d in [1,8]:
 for arm in ['local','augmented','bank','is']:
  selected=[r for r in rows if r['d']==d and r['arm']==arm];assert len(selected)==16;stats={}
  for k in selected[0]['values']:
   a=np.array([r['values'][k] for r in selected]);mean=float(a.mean());se=float(a.std(ddof=1)/4);rmse=float(np.sqrt(np.mean((a-truth[k])**2)));stats[k]=dict(truth=truth[k],mean=mean,se=se,rmse=rmse,within3se=bool(abs(mean-truth[k])<=3*se))
  g=dict(d=d,arm=arm,functionals=stats,mean_calls=float(np.mean([r['calls'] for r in selected])),mean_seconds=float(np.mean([r['seconds'] for r in selected])),accepted=sum(r['accepted'] for r in selected),errors=sum(r['errors'] for r in selected),divergences=sum(r['divergences'] for r in selected),depth_stops=sum(r['depth_stops'] for r in selected))
  if arm=='is':g['importance_ess_min_median_max']=[float(f([r['importance_ess'] for r in selected])) for f in [np.min,np.median,np.max]]
  groups.append(g)
  if arm=='augmented':gates.append(dict(d=d,passed=stats['positive_mass']['rmse']<=.05 and stats['positive_mass']['within3se'] and g['errors']==0))
r=dict(jobs=len(rows),failed_jobs=failures,seconds=final['seconds'],groups=groups,gates=gates,passed=not failures and all(g['passed'] for g in gates),oracle_centers=True,interpretation='Mechanism diagnostic only. Supplied centers bypass discovery. No competitive sampler claim.')
for name,data in [('SUMMARY',r),('ROWS',rows),('INPUTS',hashes)]: (out/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(r,indent=2))
