import json,sys,time
from pathlib import Path
import numpy as np
import owalnuts
from move import EnsembleMove
d,start_kind,arm,seed,out=sys.argv[1:];d=int(d);seed=int(seed);out=Path(out)
x=np.zeros((4,d));x[:,0]=-8
if start_kind=='covered':x[3,0]=8
assert start_kind in ('cold','covered') and arm in ('local','ensemble')
calls=0;errors=0
def target(q):
 global calls,errors
 calls+=1
 a=np.log(.8)-np.log(2.)-.5*((q[0]+8)/2)**2
 b=np.log(.2)-np.log(.2)-.5*((q[0]-8)/.2)**2
 lp=np.logaddexp(a,b);wa=np.exp(a-lp);wb=np.exp(b-lp)
 g=-q.copy();g[0]=-wa*(q[0]+8)/4-wb*(q[0]-8)/.04
 lp=float(lp-.5*np.sum(q[1:]**2)-d*.5*np.log(2*np.pi))
 if not np.isfinite(lp) or not np.isfinite(g).all():errors+=1
 return lp,g
move=EnsembleMove(np.tile(np.eye(d),(4,1,1)));rng=np.random.default_rng(seed+1000000)
samples=[];local=[];accepted=np.zeros(4,int);invalid=0;div=0;depth=0;t=time.monotonic()
for chunk in range(100):
 state=owalnuts.WarmState(positions=x,step_sizes=np.full(4,.1),mass_diagonal=np.ones((4,d)))
 f=owalnuts.sample_warm(target,state,draws=10,seed=seed+1000*chunk,threads=1,tuning=owalnuts.Tuning(max_depth=10,max_error=1.))
 x=f.warm_state().positions.copy();local.append(f.samples.copy());div+=int(f.divergent.sum());depth+=int((f.depth>=10).sum())
 if arm=='ensemble':
  x,meta=move.sweep(x,lambda v:target(v)[0],rng);accepted+=meta['accepted'];invalid+=meta['invalid']
 samples.append(x.copy())
 if chunk%10==9:(out/'PROGRESS.json').write_text(json.dumps(dict(chunks=chunk+1,seconds=time.monotonic()-t,calls=calls))+'\n')
np.savez_compressed(out/'draws.npz',post_sweep=np.array(samples),local=np.concatenate(local,axis=1))
r=dict(d=d,start=start_kind,arm=arm,seed=seed,seconds=time.monotonic()-t,calls=calls,errors=errors,accepted=accepted.tolist(),invalid=invalid,divergences=div,depth_stops=depth)
(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
