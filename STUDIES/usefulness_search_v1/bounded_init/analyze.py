import hashlib,json,statistics,zipfile
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
ROOT=Path('/dev/shm/bounded-init-20261030');RUN=ROOT/'run01';PDB=Path('/home/ubuntu/infra/posteriordb/posterior_database');MODELS=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');inputs={}
def read(p):
 raw=p.read_bytes();inputs[str(p)]=hashlib.sha256(raw).hexdigest();return json.loads(raw)
def stats(a):
 ds=az.convert_to_dataset({'q':a});return dict(mean=a.mean(axis=(0,1)),rhat=np.asarray(az.rhat(ds,method='rank').q),bulk=np.asarray(az.ess(ds,method='bulk').q),tail=np.asarray(az.ess(ds,method='tail').q),mcse=np.asarray(az.mcse(ds,method='mean').q))
def good(s):return bool(all(np.isfinite(v).all() for v in s.values()) and s['rhat'].max()<=1.01 and s['bulk'].min()>=400 and s['tail'].min()>=400)
def name(n):
 parts=n.split('.');return parts[0]+'['+','.join(parts[1:])+']' if len(parts)>1 and all(p.isdigit() for p in parts[1:]) else n
manifest=read(RUN/'MANIFEST.json');final=read(RUN/'FINAL.json');rule=read(ROOT/'SV-RULE.json');cache={};rows=[];bounds_valid=True;all_completed=len(final['jobs'])==78 and final['dependencies_unchanged']
for i,(kind,model,arm,seed) in enumerate(manifest['jobs']):
 folder=RUN/f'{i:03d}';sup=read(folder/'SUPERVISION.json') if (folder/'SUPERVISION.json').exists() else {};base=dict(index=i,kind=kind,model=model,arm=arm,seed=seed)
 if sup.get('exit_code')!=0 or not sup.get('group_drained') or not (folder/'RESULT.json').exists():rows.append(dict(**base,passed=False,failure=sup));all_completed=False;continue
 r=read(folder/'RESULT.json')
 if arm=='bounded':
  masses=np.concatenate([c['initial_mass_diagonal'] for c in r['chains_data']]);bounds_valid &= bool(np.isfinite(masses).all() and masses.min()>=.1 and masses.max()<=1000.)
 if kind=='pdb':
  if model not in cache:
   meta=read(PDB/'posteriors'/f'{model}.json');rp=PDB/'reference_posteriors/draws/draws'/f"{meta['reference_posterior_name']}.json.zip";inputs[str(rp)]=hashlib.sha256(rp.read_bytes()).hexdigest()
   with zipfile.ZipFile(rp) as z:ref=json.loads(z.read(z.namelist()[0]))
   names=list(ref[0]);refa=np.asarray([[c[n] for n in names] for c in ref]).transpose(0,2,1);rs=stats(refa);stan=bs.StanModel(str(MODELS/(model+'_model.so')),data=(MODELS/(model+'.data.json')).read_text(),seed=1);cn=[name(n) for n in stan.param_names(include_tp=True,include_gq=False)];indices=[cn.index(n) for n in names];cache[model]=(stan,indices,rs)
  stan,indices,rs=cache[model];q=np.asarray([c['samples'] for c in r['chains_data']]);a=np.asarray([stan.param_constrain(x,include_tp=True,include_gq=False)[indices] for x in q.reshape(-1,q.shape[-1])]).reshape(*q.shape[:2],-1);s=stats(a);div=sum(c['divergences'] for c in r['chains_data']);z=np.abs(s['mean']-rs['mean'])/np.sqrt(s['mcse']**2+rs['mcse']**2)
  rows.append(dict(**base,passed=good(s) and div==0,bulk_min=float(s['bulk'].min()),tail_min=float(s['tail'].min()),rhat_max=float(s['rhat'].max()),divergences=div,calls=r['target_calls_total'],warmup_calls=sum(c['warmup_target_calls'] for c in r['chains_data']),efficiency=float(s['bulk'].min()/r['target_calls_total']),max_reference_z=float(z.max()),reference_diagnostics_pass=good(rs),seconds=r['wall_seconds'],warnings=r['chain_warnings'],guard_firings=sum(any(ch['restarted'] for ch in c['trapped_chain_checks']) for c in r['chains_data'])))
 elif kind=='sv':
  a=np.asarray([c['draws_mu_logsigma_hlast'] for c in r['chains_data']]);trapped=[]
  for c in range(4):
   if abs(np.median(a[c,:,1])-rule['anchor_log_sigma'])>rule['log_sigma_tolerance'] or abs(np.median(a[c,:,2])-rule['anchor_h_last'])>rule['h_last_tolerance']:trapped.append(c)
  rows.append(dict(**base,passed=not trapped,trapped=trapped,warmup_calls=sum(c['warmup_target_calls'] for c in r['chains_data']),calls=r['target_calls_total'],guard_firings=sum(any(ch['restarted'] for ch in c['trapped_chain_checks']) for c in r['chains_data']),warnings=r['chain_warnings']))
 else:
  tm=r['tail_mass'];rows.append(dict(**base,passed=abs(tm['z'])<=3 and r['nonfinite_draws']==0,tail_mass=tm,calls=r['target_calls_total'],bulk_min=r['min_bulk_ess'],tail_min=r['min_tail_ess'],rhat_max=r['max_rhat']))
summary={};quality=True;ratios=[]
for model in sorted(cache):
 group=[r for r in rows if r['model']==model];passes={a:sum(r['passed'] for r in group if r['arm']==a) for a in ['defaults','gradinit','bounded']};quality &= passes['bounded']>=passes['defaults'];rr=[]
 for seed in range(939100001,939100005):
  pair={r['arm']:r for r in group if r['seed']==seed}
  if all('efficiency' in pair.get(a,{}) for a in ['defaults','bounded']):rr.append(pair['bounded']['efficiency']/pair['defaults']['efficiency'])
 median=statistics.median(rr) if len(rr)==4 else 0.;ratios.append(median);summary[model]=dict(passes=passes,candidate_default_ratios=rr,median_ratio=median)
sv=[r for r in rows if r['kind']=='sv'];svwarm={a:statistics.median([r['warmup_calls'] for r in sv if r['arm']==a and 'warmup_calls' in r]) if any(r['arm']==a and 'warmup_calls' in r for r in sv) else float('inf') for a in ['defaults','gradinit','bounded']};traps={a:sum(len(r.get('trapped',list(range(4)))) for r in sv if r['arm']==a) for a in ['defaults','gradinit','bounded']};geomean=float(np.exp(np.mean(np.log(ratios)))) if len(ratios)==4 and min(ratios)>0 else 0.;funnel=all(r['passed'] for r in rows if r['kind']=='funnel' and r['arm']=='bounded');svratio=svwarm['bounded']/svwarm['defaults'] if np.isfinite(list(svwarm.values())).all() else float('inf')
verdict=dict(all_completed=all_completed,initial_mass_bounds_valid=bounds_valid,no_pdb_pass_loss=quality,pdb_geomean=geomean,no_model_below_point9=bool(ratios and min(ratios)>=.9),sv_warmup_ratio=svratio,sv_trapped=traps,funnel_pass=funnel);verdict['passed']=bool(all_completed and bounds_valid and quality and geomean>=1.1 and min(ratios)>=.9 and svratio<=.9 and traps['bounded']<=traps['defaults'] and funnel)
out=ROOT/'analysis01';out.mkdir(exist_ok=False)
def clean(v):
 if isinstance(v,float) and not np.isfinite(v):return None
 if isinstance(v,dict):return {k:clean(x) for k,x in v.items()}
 if isinstance(v,list):return [clean(x) for x in v]
 return v
for name,obj in [('ROWS',rows),('SUMMARY',summary),('VERDICT',verdict),('INPUTS',inputs)]: (out/(name+'.json')).write_text(json.dumps(clean(obj),indent=2,allow_nan=False)+'\n')
print(json.dumps(verdict,indent=2))
