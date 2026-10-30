import json,sys,time
from pathlib import Path
import numpy as np
from pymc_control import FixedNUTS
from native import Native,ROOT
from involutions import global_exchange,local_exchange,move
engine,out=sys.argv[1:];out=Path(out);out.mkdir(exist_ok=False)
p=json.loads((ROOT/'PREPARED.json').read_text());m=json.loads((ROOT/'MODES.json').read_text());center=np.array(p['mode']);L=np.array(p['L']);inv=np.linalg.inv(L)
x=(np.array(m['starts'])-center)@inv.T
b=Native(center,L,x);raw=Native();seed=934100001 if engine=='plain' else 934100002;rng=np.random.default_rng(seed+100)
accepted=np.zeros((4,2),int);crossings=np.zeros(4,int);draws=[];history=[];div=depth=0;start=time.monotonic();jump_evaluations=0
kernels=[FixedNUTS(b,x[c],.05,seed+c*10000) for c in range(4)]
for chunk in range(60):
 before=x@L.T+center
 for c in range(4):
  for iteration in range(25):
   x[c],s=kernels[c].draw(x[c]);assert abs(s['step_size']-.05)<1e-14
   div+=int(s['diverging']);depth+=int(s['reached_max_treedepth'])
 q=x@L.T+center
 if engine=='jump':
  for c in range(4):
   q[c],a,_=move(q[c],raw.density,global_exchange,rng);accepted[c,0]+=a
   subject=int(rng.integers(12));q[c],a,_=move(q[c],raw.density,lambda v:local_exchange(v,subject),rng);accepted[c,1]+=a;jump_evaluations+=4
 crossings+=(q[:,0]>q[:,1])!=(before[:,0]>before[:,1]);x=(q-center)@inv.T
 history.append((q[:,0]>q[:,1]).tolist())
 if chunk>=20:draws.append(q.copy())
 (out/'PROGRESS.json').write_text(json.dumps(dict(chunks=chunk+1,seconds=time.monotonic()-start,accepted=accepted.tolist(),crossings=crossings.tolist()))+'\n')
q=np.stack(draws,axis=1);np.savez_compressed(out/'draws.npz',q=q)
r=dict(engine=engine,seconds=time.monotonic()-start,calls_errors=b.counts(),jump_density_evaluations=jump_evaluations,accepted=accepted.tolist(),crossings=crossings.tolist(),primary_fraction=(q[:,:,0]>q[:,:,1]).mean(axis=1).tolist(),mode_history=history,divergences=div,depth_hits=depth,not_reference=True)
(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');b.close();raw.close();print(json.dumps(r))
