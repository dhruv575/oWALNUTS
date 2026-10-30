import json,sys,time
from pathlib import Path
import numpy as np
import owalnuts,nutpie
from native import Native,ROOT
engine,seed,out=sys.argv[1:];seed=int(seed);out=Path(out);out.mkdir(exist_ok=False);p=json.loads((ROOT/'PREPARED.json').read_text());center=np.array(p['mode']);L=np.array(p['L']);x=np.linalg.solve(L,(np.array(p['starts'])-center).T).T;b=Native(center,L,x);start=time.monotonic()
if engine=='walnuts':
 f=owalnuts.sample(b.walnuts,dim=43,init=x,chains=4,threads=1,warmup=1000,draws=4000,seed=seed,tuning=owalnuts.Tuning(max_depth=12,max_error=1.),adaptation=owalnuts.Adaptation(target_accept=.99));q=f.samples@L.T+center;div=[int(f.divergent[:,:1000].sum()),int(f.divergent[:,1000:].sum())];depth=[int((f.depth[:,:1000]>=12).sum()),int((f.depth[:,1000:]>=12).sum())]
else:
 f=nutpie.sample(b.nuts,chains=4,cores=1,tune=1000,draws=4000,seed=seed,progress_bar=False,save_warmup=True,target_accept=.99,maxdepth=12,low_rank_modified_mass_matrix=False,transform_adapt=False);q=np.asarray(f.posterior.q.values)@L.T+center;div=[int(f.warmup_sample_stats.diverging.sum()),int(f.sample_stats.diverging.sum())];depth=[int(f.warmup_sample_stats.maxdepth_reached.sum()),int(f.sample_stats.maxdepth_reached.sum())];f.close()
assert q.shape==(4,4000,43);np.savez_compressed(out/'draws.npz',q=q);r=dict(engine=engine,seed=seed,seconds=time.monotonic()-start,calls_errors=b.counts(),divergences_by_phase=div,depth_hits_by_phase=depth,primary_fraction=(q[:,:,0]>q[:,:,1]).mean(axis=1).tolist());(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));b.close()
