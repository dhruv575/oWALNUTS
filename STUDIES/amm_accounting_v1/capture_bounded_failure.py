"""Diagnostic replay only: capture first nonfinite callback input on one thread."""
import json,time
from pathlib import Path
import numpy as np
import numba,owalnuts
from bounded_rescaled_native import compile_target

root=Path(__file__).resolve().parent;n=250;cap=.5
y=.003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n));y[[0,125]]=0.
owner=compile_target(y,cap);evaluate=owner.evaluator;dim=n+3
capture=np.zeros(dim+1)
@numba.cfunc(owalnuts.numba_raw_signature(),nopython=True)
def callback(d,qp,gp,user):
 q=numba.carray(qp,dim);g=numba.carray(gp,dim);saved=numba.carray(user,dim+1,dtype=numba.float64)
 value=evaluate(q,g)
 if not np.isfinite(value) and saved[0]==0:
  saved[0]=1
  for j in range(dim):saved[j+1]=q[j]
 return value
target=owalnuts.from_cfunc(callback,dim,user_data=capture.ctypes.data)
tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
adaptation=owalnuts.Adaptation(target_accept=.9,adapt_step_size=True,adapt_mass=True,metric_regularization='stan',trapped_chain_restart=True)
gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap));initial=np.tile(np.r_[2*np.log(.005),eta,0.,np.zeros(n)],(4,1))
error=None;start=time.monotonic()
try:
 owalnuts.sample(target,dim,init=initial,chains=4,warmup=2000,draws=1,seed=398139016,threads=1,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
except RuntimeError as exc:error=str(exc)
np.savez_compressed(root/'CAPTURE.npz',capture=capture,y=y)
q=capture[1:];l=np.log(cap)-np.logaddexp(0.,q[1]);weights=np.ones(n)/n
for i in range(n-1,0,-1):weights[i-1]+=.95*weights[i]
weights[0]/=np.sqrt(1-.95**2)
log_scale=.5*(q[0]+np.exp(l)*(q[3:]@weights))
r=dict(error=error,captured=bool(capture[0]),finite_input=bool(np.isfinite(q).all()),mu=float(q[0]),eta=float(q[1]),b=float(q[2]),log_sigma=float(l),log_beta_scale=float(log_scale),max_abs_z=float(abs(q[3:]).max()),elapsed_seconds=time.monotonic()-start,scope='Diagnostic replay of fit1 seed, threads1 and draws1; not a replacement or reference sample')
(root/'CAPTURE.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
