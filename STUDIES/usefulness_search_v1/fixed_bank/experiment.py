import json,sys,time
from pathlib import Path
import numpy as np
from scipy.special import logsumexp
import owalnuts
from bank import FixedBank
d,arm,seed,out=sys.argv[1:];d=int(d);seed=int(seed);out=Path(out);calls=0;errors=0
def target(q):
 global calls,errors
 calls+=1;a=np.log(.8/2)-.5*((q[0]+8)/2)**2;b=np.log(.2/.2)-.5*((q[0]-8)/.2)**2;lp=np.logaddexp(a,b)
 g=-q.copy();g[0]=-np.exp(a-lp)*(q[0]+8)/4-np.exp(b-lp)*(q[0]-8)/.04
 lp=float(lp-.5*np.sum(q[1:]**2)-d*.5*np.log(2*np.pi))
 if not np.isfinite(lp) or not np.isfinite(g).all():errors+=1
 return lp,g
centers=np.zeros((2,d));centers[:,0]=[-8,8];bank=FixedBank(centers,np.tile(np.eye(d),(2,1,1)),[.5,.5]);rng=np.random.default_rng(seed+1000000);t=time.monotonic();accepted=0;invalid=0;div=0;depth=0
if arm=='is':
 q=np.array([bank.propose(rng) for _ in range(800)]);lw=np.array([target(v)[0]-bank.logq(v) for v in q]);w=np.exp(lw-logsumexp(lw));np.savez_compressed(out/'draws.npz',q=q,log_weight=lw,weight=w)
else:
 x=np.zeros((4,d));x[:,0]=-8;draws=[];local=[]
 for chunk in range(100):
  if arm!='bank':
   state=owalnuts.WarmState(positions=x,step_sizes=np.full(4,.1),mass_diagonal=np.ones((4,d)))
   f=owalnuts.sample_warm(target,state,draws=10,seed=seed+1000*chunk,threads=1,tuning=owalnuts.Tuning(max_depth=10,max_error=1.));x=f.warm_state().positions.copy();local.append(f.samples.copy());div+=int(f.divergent.sum());depth+=int((f.depth>=10).sum())
  if arm in ['augmented','bank']:
   x,meta=bank.sweep(x,lambda v:target(v)[0],rng);accepted+=sum(meta['accepted']);invalid+=meta['invalid']
  draws.append(x.copy())
 np.savez_compressed(out/'draws.npz',post_sweep=np.array(draws),local=np.concatenate(local,axis=1) if local else np.empty((0,)))
r=dict(d=d,arm=arm,seed=seed,seconds=time.monotonic()-t,calls=calls,errors=errors,accepted=accepted,invalid=invalid,divergences=div,depth_stops=depth,oracle_centers=True)
(out/'RESULT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
