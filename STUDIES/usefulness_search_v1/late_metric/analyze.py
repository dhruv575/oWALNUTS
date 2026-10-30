import hashlib,json,statistics,zipfile
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
ROOT=Path('/dev/shm/late-metric-20261029');run=ROOT/'run01';out=ROOT/'analysis01';out.mkdir(exist_ok=False)
PDB=Path('/home/ubuntu/infra/posteriordb/posterior_database');MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
inputs={}
def read(p):
 raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def stats(a):
 ds=az.convert_to_dataset({'p':a})
 return dict(mean=a.mean(axis=(0,1)),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),rhat=np.asarray(az.rhat(ds,method='rank').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
def good(s):return bool(all(np.isfinite(x).all() for x in s.values()) and s['rhat'].max()<=1.01 and s['bulk'].min()>=400 and s['tail'].min()>=400)
def name(n):
 p=n.split('.');return p[0]+'['+','.join(p[1:])+']' if len(p)>1 and all(x.isdigit() for x in p[1:]) else n
manifest=read(run/'MANIFEST.json');final=read(run/'FINAL.json');assert final['dependencies_unchanged'] and all(j.get('group_drained') for j in final['jobs'])
cache={};rows=[]
for i,(m,arm,seed) in enumerate(manifest['jobs']):
 p=run/f'{i:03d}/RESULT.json';sup=read(p.parent/'SUPERVISION.json');r=read(p)
 assert r['status']=='ok'
 if m not in cache:
  info=read(PDB/'posteriors'/f'{m}.json');rp=PDB/'reference_posteriors/draws/draws'/f"{info['reference_posterior_name']}.json.zip"
  inputs[str(rp)]=hashlib.sha256(rp.read_bytes()).hexdigest()
  with zipfile.ZipFile(rp) as z:ref=json.loads(z.read(z.namelist()[0]))
  names=list(ref[0]);a=np.asarray([[c[n] for n in names] for c in ref]).transpose(0,2,1);rs=stats(a)
  model=bs.StanModel(str(MODELS/(m+'_model.so')),data=(MODELS/(m+'.data.json')).read_text(),seed=1)
  cn=[name(n) for n in model.param_names(include_tp=True,include_gq=False)];indices=[cn.index(n) for n in names]
  cache[m]=(model,indices,rs)
 model,indices,rs=cache[m];q=np.array([c['samples'] for c in r['chains_data']]);a=np.array([model.param_constrain(x,include_tp=True,include_gq=False)[indices] for x in q.reshape(-1,q.shape[-1])]).reshape(*q.shape[:2],-1);s=stats(a)
 div=sum(c['divergences'] for c in r['chains_data']);dec=r['chains_data'][0]['dense_auto_select']
 assert all(c['dense_auto_select']==dec for c in r['chains_data'])
 if arm!='diag':assert dec['window_index']==int(arm[-1])
 z=np.abs(s['mean']-rs['mean'])/np.sqrt(s['mcse']**2+rs['mcse']**2)
 rows.append(dict(model=m,arm=arm,seed=seed,passed=good(s) and div==0,bulk_min=float(s['bulk'].min()),tail_min=float(s['tail'].min()),rhat_max=float(s['rhat'].max()),divergences=div,calls=r['target_calls_total'],efficiency=float(s['bulk'].min()/r['target_calls_total']),reference_diagnostics_pass=good(rs),max_reference_z=float(z.max()),decision=dec,seconds=r['wall_seconds']))
summary={}
for m in cache:
 rr=[r for r in rows if r['model']==m];groups={a:[r for r in rr if r['arm']==a] for a in ('diag','auto2','auto3')}
 ratios={a:statistics.median(next(r['efficiency'] for r in groups['auto3'] if r['seed']==s)/next(r['efficiency'] for r in groups[a] if r['seed']==s) for s in range(926100001,926100004)) for a in ('diag','auto2')}
 summary[m]=dict(passes={a:sum(r['passed'] for r in rs) for a,rs in groups.items()},dense={a:sum(bool(r['decision'] and r['decision']['chose_dense']) for r in rs) for a,rs in groups.items()},candidate_efficiency_ratio=ratios)
inputs[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
for n,d in [('ROWS',rows),('SUMMARY',summary),('INPUT-HASHES',inputs)]: (out/(n+'.json')).write_text(json.dumps(d,indent=2,allow_nan=False)+'\n')
print(json.dumps(summary,indent=2))
