"""Independent PyMC NUTS fixed-kernel control using the same native target."""
import numpy as np
import pymc as pm
import pytensor.tensor as pt
from pytensor.graph.op import Op
class NativeLogp(Op):
 itypes=[pt.dvector];otypes=[pt.dscalar,pt.dvector]
 def __init__(self,backend):self.backend=backend
 def perform(self,node,inputs,outputs):
  try:lp,g=self.backend.value(inputs[0])
  except ValueError:lp,g=-np.inf,np.zeros_like(inputs[0])
  outputs[0][0]=np.asarray(lp);outputs[1][0]=np.asarray(g)
 def grad(self,inputs,grads):return [grads[0]*self(inputs[0])[1]]
class FixedNUTS:
 def __init__(self,backend,initial,step,seed):
  self.backend=backend
  with pm.Model() as model:
   q=pm.Flat('q',shape=backend.dim)
   pm.Potential('target',NativeLogp(backend)(q)[0])
   self.kernel=pm.NUTS(scaling=np.ones(backend.dim),is_cov=False,step_scale=step*backend.dim**.25,adapt_step_size=False,step_rand=None,max_treedepth=12,early_max_treedepth=12,Emax=1000,rng=np.random.default_rng(seed),initial_point={'q':initial},mode='FAST_COMPILE')
  self.kernel.tune=False;self.model=model
 def draw(self,x):
  point,stats=self.kernel.step({'q':np.asarray(x,dtype=float)})
  return point['q'],stats[0]
