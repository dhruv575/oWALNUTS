import hashlib,json
from pathlib import Path
import numpy as np
from scipy.stats import norm
root=Path(__file__).resolve().parent;run=root/'mixing01';out=root/'mixing-analysis01';out.mkdir(exist_ok=False)
final=json.loads((run/'FINAL.json').read_text());assert final['unchanged']
rows=[];inputs={};failures=[]
for job in sorted(final['results'],key=lambda j:j['index']):
 folder=run/f"{job['index']:03d}"
 if job['exit_code']!=0 or not job['group_drained']:
  failures.append(job);continue
 for n in ['RESULT.json','draws.npz','SUPERVISION.json']:
  p=folder/n;inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 r=json.loads((folder/'RESULT.json').read_text());q=np.load(folder/'draws.npz')['post_sweep'][20:];assert q.shape==(80,4,r['d']) and np.isfinite(q).all()
 values=dict(positive_mass=float((q[:,:,0]>0).mean()),mean=float(q[:,:,0].mean()),second_moment=float((q[:,:,0]**2).mean()))
 if r['d']>1:values.update(other_mean=float(q[:,:,1:].mean()),other_second=float((q[:,:,1:]**2).mean()))
 rows.append(dict(**r,values=values))
truth=dict(positive_mass=.8*norm.sf(4)+.2*norm.sf(-40),mean=-4.8,second_moment=67.208,other_mean=0.,other_second=1.)
groups=[];gates=[]
for d in [1,8]:
 for start in ['cold','covered']:
  stats={}
  for arm in ['local','ensemble']:
   selected=sorted([r for r in rows if r['d']==d and r['start']==start and r['arm']==arm],key=lambda r:r['seed']);assert len(selected)==16
   st={}
   for k in selected[0]['values']:
    a=np.array([r['values'][k] for r in selected]);se=float(a.std(ddof=1)/4);mean=float(a.mean());rmse=float(np.sqrt(np.mean((a-truth[k])**2)))
    st[k]=dict(truth=truth[k],mean=mean,se=se,rmse=rmse,within_3se=bool(abs(mean-truth[k])<=3*se))
   stats[arm]=st;groups.append(dict(d=d,start=start,arm=arm,functionals=st,total_calls=sum(r['calls'] for r in selected),accepted=sum(sum(r['accepted']) for r in selected),errors=sum(r['errors'] for r in selected),divergences=sum(r['divergences'] for r in selected),depth_stops=sum(r['depth_stops'] for r in selected)))
  base=stats['local'];aug=stats['ensemble'];p=aug['positive_mass']
  checks=dict(probability_rmse=p['rmse']<=.05,probability_mean=p['within_3se'],twofold_rmse=p['rmse']<=base['positive_mass']['rmse']/2,no_other_regression=all(aug[k]['rmse']<=1.1*base[k]['rmse'] for k in aug if k!='positive_mass'),zero_errors=all(r['errors']==0 for r in rows if r['d']==d and r['start']==start))
  gates.append(dict(d=d,start=start,checks=checks,passed=all(checks.values())))
summary=dict(jobs=len(rows),failed_jobs=failures,batch_seconds=final['seconds'],groups=groups,gates=gates,passed=not failures and all(g['passed'] for g in gates),interpretation='Independent ensemble estimates; no within-ensemble walker independence assumed. Fixed-tuning mechanism screen, not NUTS comparison.')
for name,data in [('ROWS',rows),('SUMMARY',summary),('INPUTS',inputs)]: (out/(name+'.json')).write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps(summary,indent=2))
