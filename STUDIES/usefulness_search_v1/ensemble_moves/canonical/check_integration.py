import json
from pathlib import Path
import numpy as np
import owalnuts
from move import EnsembleMove
root=Path(__file__).resolve().parent;precision=np.array([.25,1.,4.]);seen=[]
def target(q):
 seen.append(q.copy());return float(-.5*np.sum(q*q*precision)),-precision*q
state=owalnuts.WarmState(positions=np.array([[2.,0.,-.5],[-2.,1.,.5],[0.,-1.,0.],[1.,.5,-.2]]),step_sizes=np.full(4,.15),mass_diagonal=np.tile(precision,(4,1)))
f=owalnuts.sample_warm(target,state,draws=8,seed=940100001,threads=1,tuning=owalnuts.Tuning(max_depth=8,max_error=1.));carried=f.warm_state();before=carried.positions.copy();move=EnsembleMove(np.array([np.diag(1/np.sqrt(v)) for v in carried.mass_diagonal]));changed,meta=move.sweep(before,lambda q:float(-.5*np.sum(q*q*precision)),np.random.default_rng(940100002));assert any(meta['accepted']);assert np.array_equal(before,carried.positions)
state2=owalnuts.WarmState(positions=changed,step_sizes=carried.step_sizes.copy(),mass_diagonal=carried.mass_diagonal.copy());seen.clear();out=owalnuts.sample_warm(target,state2,draws=8,seed=940100003,threads=1,tuning=owalnuts.Tuning(max_depth=8,max_error=1.));assert all(any(np.array_equal(x,y) for y in seen) for x in changed)
for c in range(4):
 direct=owalnuts.sample(target,dim=3,init=changed[c:c+1],chains=1,warmup=0,draws=8,seed=940100003+c,threads=1,tuning=owalnuts.Tuning(step_size=state2.step_sizes[c],max_depth=8,max_error=1.),adaptation=None,mass=state2.mass_diagonal[c]);assert np.array_equal(out.samples[c],direct.samples[0])
assert np.array_equal(out.final_step_size,state2.step_sizes);assert np.array_equal(out.warm_state().mass_diagonal,state2.mass_diagonal)
r=dict(passed=True,accepted=meta['accepted'],changed_state_evaluated=True,stateless_draws_exact=True,step_and_mass_unchanged=True);(root/'INTEGRATION-CHECK.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
