import json
import numpy as np
import nutpie,owalnuts
from native import Native,ROOT
prep=json.loads((ROOT/'PREPARED.json').read_text());modes=json.loads((ROOT/'MODES.json').read_text());mode=np.array(prep['mode']);L=np.array(prep['L']);initial=np.linalg.solve(L,(np.array(modes['starts'])-mode).T).T
b=Native(mode,L,initial);step=.05
f=nutpie.sample(b.nuts,chains=4,cores=1,tune=0,draws=4,seed=931100001,progress_bar=False,save_warmup=False,initial_step=step,maxdepth=12,store_mass_matrix=True,low_rank_modified_mass_matrix=False,transform_adapt=False)
print('sample stats:',list(f.sample_stats),flush=True)
for name in f.sample_stats:
 if 'step' in name or 'mass' in name:
  a=np.asarray(f.sample_stats[name]);print(name,a.shape,np.min(a),np.max(a),flush=True)
f.close()
w=owalnuts.sample(b.walnuts,dim=43,init=initial,chains=4,threads=1,warmup=0,draws=4,seed=931100002,tuning=owalnuts.Tuning(step_size=step,max_depth=12,max_error=1.),adaptation=None)
print('walnuts final steps',w.final_step_size.tolist(),flush=True);b.close()
