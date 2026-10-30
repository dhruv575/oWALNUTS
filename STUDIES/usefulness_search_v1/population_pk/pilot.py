import json,sys,time
from pathlib import Path
import numpy as np
import owalnuts,nutpie
from native import Native,ROOT
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from features import summarize
engine,out=sys.argv[1:];out=Path(out);out.mkdir(exist_ok=False);prep=json.loads((ROOT/'PREPARED.json').read_text());modes=json.loads((ROOT/'MODES.json').read_text());mode=np.array(prep['mode']);L=np.array(prep['L']);starts=np.linalg.solve(L,(np.array(modes['starts'])-mode).T).T
b=Native(mode,L,starts);seed=930100001 if engine=='walnuts' else 930100002;b.reset();start=time.monotonic()
if engine=='walnuts':
 f=owalnuts.sample(b.walnuts,dim=43,init=starts,chains=4,threads=1,warmup=1000,draws=1000,seed=seed,tuning=owalnuts.Tuning(max_depth=12,max_error=1.),adaptation=owalnuts.Adaptation(target_accept=.99))
 q=f.samples;div=int(f.divergent[:,1000:].sum());depth=int((f.depth[:,1000:]>=12).sum())
else:
 f=nutpie.sample(b.nuts,chains=4,cores=1,tune=1000,draws=1000,seed=seed,progress_bar=False,save_warmup=False,target_accept=.99,maxdepth=12,low_rank_modified_mass_matrix=False,transform_adapt=False)
 q=np.asarray(f.posterior.q.values);div=int(f.sample_stats.diverging.sum());depth=int(f.sample_stats.maxdepth_reached.sum());f.close();assert b.initial_calls==4
elapsed=time.monotonic()-start;calls,errors=b.counts();q=q@L.T+mode;s=summarize(q,div,depth);np.savez_compressed(out/'draws.npz',q=q)
r=dict(engine=engine,seed=seed,seconds=elapsed,calls=calls,errors=errors,divergences=div,depth_hits=depth,summary=s,primary_rate_order_fraction_by_chain=(q[:,:,0]>q[:,:,1]).mean(axis=1).tolist(),not_reference=True)
(out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n');b.close();print(json.dumps({k:v for k,v in r.items() if k!='summary'}))
