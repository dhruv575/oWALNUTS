import hashlib,json,sys
from pathlib import Path
import numpy as np,arviz as az,bridgestan as bs
base=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False);sys.path.insert(0,str(base))
from bounded_transport import fit
from gp_workflow_setup import target_data
runtime=Path(json.loads((base/'RUNTIME.json').read_text())['root']);so=runtime/'models/raw.so';references=json.loads((base/'REFERENCE.json').read_text());rows=[];inputs={}
for f in [Path(__file__),base/'REFERENCE.json',base/'bounded_transport.py',base/'gp_workflow_setup.py',so]:inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
for scenario in range(4):
 d=out/f'scenario-{scenario}';d.mkdir();source=base/f'results/{scenario}-bounded-walnuts_dense/PILOT-RAW.json';raw=json.loads(source.read_text());q=np.asarray(raw['draws']);assert q.shape==(4,2000,13) and np.isfinite(q).all();replay=[]
 for arm,mode in [('affine','walnuts_dense'),('affine','diag'),('bounded','walnuts_dense'),('bounded','diag')]:
  f=base/f'results/{scenario}-{arm}-{mode}/PILOT-RAW.json';inputs[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest();other=json.loads(f.read_text());replay.append(bool(np.array_equal(q,other['draws']) and raw['target_calls']==other['target_calls']))
 data=runtime/f'data/{scenario}.json';inputs[str(data)]=hashlib.sha256(data.read_bytes()).hexdigest();model=bs.StanModel(str(so),data=data.read_text(),seed=1);names=model.param_names(include_tp=True,include_gq=False);ix=[names.index(n) for n in ['rho','alpha']+[f'f.{j}' for j in range(1,12)]];v=np.asarray([model.param_constrain(x,include_tp=True,include_gq=False)[ix] for x in q.reshape(-1,13)]).reshape(4,2000,13);v=np.concatenate([v,np.exp(v[:,:,2:])],axis=2);assert np.isfinite(v).all();ds=az.convert_to_dataset({'p':v});ref=next(x['stats'] for x in references['references'] if x['scenario']==scenario)
 stats=dict(mean=v.mean((0,1)),sd=v.reshape(-1,24).std(0,ddof=1),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),rhat=np.asarray(az.rhat(ds,method='rank').p),mcse=np.asarray(az.mcse(ds,method='mean').p));z=abs(stats['mean']-ref['mean'])/np.sqrt(stats['mcse']**2+np.asarray(ref['mcse'])**2);me=abs(stats['mean']-ref['mean'])/ref['sd'];se=abs(stats['sd']/ref['sd']-1)
 checks=dict(within_aws_replay=all(replay),rhat=max(stats['rhat'])<=1.01,bulk=min(stats['bulk'])>=400,tail=min(stats['tail'])>=400,divergences=raw['retained_divergences']==0,mean_z=max(z)<=4,mean_sd=max(me)<=.1,sd_error=max(se)<=.1);checks={k:bool(v) for k,v in checks.items()};passed=all(checks.values());np.savez_compressed(d/'DRAWS-FUNCTIONALS.npz',q=q,values=v)
 row=dict(scenario=scenario,passed=passed,checks=checks,calls=dict(gradient=raw['target_calls']),divergences=raw['retained_divergences'],stats={k:x.tolist() for k,x in stats.items()},max_z=float(max(z)),max_mean_error=float(max(me)),max_sd_error=float(max(se)))
 if passed:
  m=fit(q[:,:100].reshape(-1,13));(d/'MAP.json').write_text(json.dumps(m,indent=2)+'\n')
  for affine in [True,False]:(d/('affine.json' if affine else 'bounded.json')).write_text(json.dumps(target_data(json.loads(data.read_text()),m,affine=affine))+'\n')
 (d/'SUMMARY.json').write_text(json.dumps(row,indent=2)+'\n');rows.append(row);print(json.dumps(dict(scenario=scenario,passed=passed,checks=checks)),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in inputs.items())
(out/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all(x['passed'] for x in rows),rows=rows,inputs=inputs),indent=2)+'\n')
