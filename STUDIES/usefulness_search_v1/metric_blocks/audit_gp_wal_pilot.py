import hashlib,json
from pathlib import Path
import numpy as np,arviz as az
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_wal_pilot01';s=json.loads((r/'SUMMARY.json').read_text());refs=json.loads((l/'gp_fresh_reference01/SUMMARY.json').read_text());audit=[]
assert s['completed'] and len(s['rows'])==4
for item in s['rows']:
 row=item['result'];d=r/f"scenario-{item['scenario']}";ref=next(x['stats'] for x in refs['references'] if x['scenario']==item['scenario']);a=np.load(d/'FUNCTIONALS.npz')['values'];assert a.shape==(4,2000,24) and np.isfinite(a).all();ds=az.convert_to_dataset({'p':a})
 stats=dict(mean=a.mean((0,1)),sd=a.reshape(-1,24).std(0,ddof=1),bulk=np.asarray(az.ess(ds,method='bulk').p),tail=np.asarray(az.ess(ds,method='tail').p),rhat=np.asarray(az.rhat(ds,method='rank').p),mcse=np.asarray(az.mcse(ds,method='mean').p))
 for key,value in stats.items():assert np.allclose(value,row['functionals'][key],rtol=1e-12,atol=1e-12)
 raw=json.loads((d/'RAW.json').read_text());assert raw['target_calls']==row['calls']['gradient'];div=raw['retained_divergences'];assert div==row['divergences']
 z=abs(stats['mean']-ref['mean'])/np.sqrt(stats['mcse']**2+np.asarray(ref['mcse'])**2);mean=abs(stats['mean']-ref['mean'])/ref['sd'];sd=abs(stats['sd']/ref['sd']-1)
 passed=max(stats['rhat'])<=1.01 and min(stats['bulk'])>=400 and min(stats['tail'])>=400 and div==0 and max(z)<=4 and max(mean)<=.1 and max(sd)<=.1
 assert bool(passed)==row['passed'];audit.append(dict(scenario=item['scenario'],passed=bool(passed),gradient_calls=raw['target_calls']))
(r/'RAW-AUDIT.json').write_text(json.dumps(dict(passed=True,rows=audit),indent=2)+'\n');print(json.dumps(audit))
