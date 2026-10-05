"""Matched, bounded, exploratory whole-fit comparison. No MCMC speed qualification."""
import argparse,time,json,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--arm',choices=['gibbs','numpyro','numpyro-nc','owalnuts'],required=True);p.add_argument('--out',required=True);a=p.parse_args();out=Path(a.out);out.mkdir();start=time.perf_counter()
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'STUDIES/options_flow_v1'))
from reference_bank_allocation import memory_limit
_memory_guard=memory_limit(8*1024**3)
import numpy as np
from blocked import simulate,chain
fixture,truth=simulate();y,x,mask,rho=(fixture[k] for k in ('y','x','mask','rho'));warmup=1000;draws=4000;seeds=[4101,4102,4103,4104]
compile_seconds=None;warmup_compile_seconds=None
if a.arm=='gibbs':
 tick=time.perf_counter();chain(y[:3],x[:3],mask[:3],rho,19,0,1);compile_seconds=time.perf_counter()-tick
 tick=time.perf_counter();samples=np.asarray([chain(y,x,mask,rho,s,warmup,draws) for s in seeds]);sampling_including_warmup=time.perf_counter()-tick;divergences=0
elif a.arm=='owalnuts':
 import pymc as pm,pytensor.tensor as pt,owalnuts
 tick=time.perf_counter();t=len(y);ix=np.where(mask)[0]
 with pm.Model() as graph:
  position=pm.Flat('position',shape=t+3,initval=np.r_[0.,np.log(.02),np.log(.09),np.zeros(t)])
  beta=position[0];q=pt.exp(position[1]);r=pt.exp(position[2]);h=position[3:]
  lp=pm.logp(pm.Normal.dist(0.,.5),beta)+pm.logp(pm.InverseGamma.dist(np.float64(3.),np.float64(.04)),q)+position[1]+pm.logp(pm.InverseGamma.dist(np.float64(3.),np.float64(.18)),r)+position[2]
  lp+=pm.logp(pm.Normal.dist(0.,pt.sqrt(q/(1-rho*rho))),h[0])+pm.logp(pm.Normal.dist(rho*h[:-1],pt.sqrt(q)),h[1:]).sum()
  lp+=pm.logp(pm.StudentT.dist(nu=np.float64(5.),mu=h[ix]+beta*x[ix],sigma=pt.sqrt(r)),y[ix]).sum();pm.Potential('normalized',lp)
 import hashlib,owalnuts._owalnuts
 (out/'actual-runtime.json').write_text(json.dumps({name:dict(path=module.__file__,sha256=hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()) for name,module in [('adapter',owalnuts),('extension',owalnuts._owalnuts)]},indent=2))
 target,dim,initial,names,unravel=owalnuts.from_pymc(graph,gil_free=True);compile_seconds=time.perf_counter()-tick
 # Independent normalized JAX gradient before sampling.
 import jax;jax.config.update('jax_enable_x64',True)
 import jax.numpy as jnp
 from jax.scipy.special import gammaln
 import ctypes
 def density(u):
  b,lq,lr=u[:3];h=u[3:];q=jnp.exp(lq);r=jnp.exp(lr)
  normal=lambda v,m,sd:jnp.sum(-.5*((v-m)/sd)**2-jnp.log(sd)-.5*jnp.log(2*jnp.pi))
  value=normal(b,0.,.5)+3*jnp.log(.04)-gammaln(3.)-3*lq-.04/q+3*jnp.log(.18)-gammaln(3.)-3*lr-.18/r
  value+=normal(h[0],0.,jnp.sqrt(q/(1-rho*rho)))+normal(h[1:],rho*h[:-1],jnp.sqrt(q))
  residual=jnp.asarray(y[ix])-h[ix]-b*jnp.asarray(x[ix]);value+=jnp.sum(gammaln(3.)-gammaln(2.5)-.5*jnp.log(5*jnp.pi)-.5*lr-3*jnp.log1p(residual**2/(5*r)))
  return value
 caller=ctypes.CFUNCTYPE(ctypes.c_double,ctypes.c_ssize_t,ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double),ctypes.c_void_p)(target.address);vg=jax.jit(jax.value_and_grad(density));parity=[]
 for offset in (0.,.01,-.03):
  u=np.ascontiguousarray(initial+offset);g=np.empty_like(u);v=caller(dim,u.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),g.ctypes.data_as(ctypes.POINTER(ctypes.c_double)),None);rv,rg=vg(u);parity.append(dict(value_error=abs(v-float(rv)),gradient_error=float(np.max(np.abs(g-np.asarray(rg))))))
 (out/'parity.json').write_text(json.dumps(parity,indent=2))
 if any(p['value_error']>1e-8 or p['gradient_error']>1e-8 for p in parity):raise ValueError('Normalized target parity failed')
 tick=time.perf_counter();posterior=owalnuts.sample(target,dim=dim,init=np.tile(initial,(4,1)),chains=4,warmup=warmup,draws=draws,seed=4101,threads=1);sampling_including_warmup=time.perf_counter()-tick;samples=np.asarray(posterior.samples).copy();samples[...,1:3]=np.exp(samples[...,1:3]/2);divergences=posterior.health()['divergences']
else:
 import jax;jax.config.update('jax_enable_x64',True)
 import jax.numpy as jnp
 import numpyro,numpyro.distributions as dist
 from numpyro.infer import MCMC,NUTS,init_to_value
 ix=np.where(mask)[0];jy=jnp.asarray(y[ix]);jx=jnp.asarray(x[ix]);t=len(y)
 def model():
  q=numpyro.sample('q',dist.InverseGamma(3.,.04));r=numpyro.sample('r',dist.InverseGamma(3.,.18));beta=numpyro.sample('beta',dist.Normal(0.,.5))
  if a.arm=='numpyro-nc':
   z=numpyro.sample('z',dist.Normal(0.,1.).expand([t]).to_event(1));innovation=jnp.sqrt(q)*z;innovation=innovation.at[0].divide(jnp.sqrt(1-rho*rho));coef=jnp.full(t,rho).at[0].set(0.)
   def compose(left,right):return right[0]*left[0],right[1]+right[0]*left[1]
   h=numpyro.deterministic('h',jax.lax.associative_scan(compose,(coef,innovation))[1])
  else:h=numpyro.sample('h',dist.Normal(0.,1.).expand([t]).to_event(1))
  lp=dist.Normal(0.,jnp.sqrt(q/(1-rho*rho))).log_prob(h[0])+dist.Normal(rho*h[:-1],jnp.sqrt(q)).log_prob(h[1:]).sum()-dist.Normal(0.,1.).log_prob(h).sum()
  
  if a.arm!='numpyro-nc':numpyro.factor('ar_prior',lp)
  numpyro.sample('y',dist.StudentT(5.,h[ix]+beta*jx,jnp.sqrt(r)),obs=jy)
 kernel=NUTS(model,target_accept_prob=.9,init_strategy=init_to_value(values=dict(q=.02,r=.09,beta=0.,h=jnp.zeros(t),z=jnp.zeros(t))))
 engine=MCMC(kernel,num_warmup=warmup,num_samples=draws,num_chains=4,chain_method='sequential',progress_bar=False)
 tick=time.perf_counter();engine.warmup(jax.random.PRNGKey(4101),extra_fields=('diverging','num_steps'));warmup_compile_seconds=time.perf_counter()-tick
 tick=time.perf_counter();engine.run(jax.random.PRNGKey(4111),extra_fields=('diverging','num_steps'));raw=engine.get_samples(group_by_chain=True);jax.block_until_ready(raw);sampling_including_warmup=warmup_compile_seconds+time.perf_counter()-tick
 samples=np.concatenate((np.asarray(raw['beta'])[...,None],np.sqrt(np.asarray(raw['q']))[...,None],np.sqrt(np.asarray(raw['r']))[...,None],np.asarray(raw['h'])),axis=-1);divergences=int(np.asarray(engine.get_extra_fields()['diverging']).sum())
np.save(out/'draws.npy',samples,allow_pickle=False)
fit_seconds=time.perf_counter()-start
import arviz as az
rhat=np.asarray(az.rhat({'q':samples})['q']);bulk=np.asarray(az.ess({'q':samples},method='bulk')['q']);tail=np.asarray(az.ess({'q':samples},method='tail')['q'])
rng=np.random.default_rng(131111);future=rho*samples[...,-1]+samples[...,1]*rng.normal(size=samples.shape[:2])+samples[...,2]*rng.standard_t(5,size=samples.shape[:2]);functionals=dict(beta=samples[...,0],sigma_state=samples[...,1],sigma_obs=samples[...,2],h_terminal=samples[...,-1],next_observed=future)
rows={}
for name,values in functionals.items():
 interval=np.quantile(values,[.05,.95]);mcse=[float(az.mcse({'v':values},method='quantile',prob=p)['v']) for p in (.05,.95)]
 rows[name]=dict(mean=float(values.mean()),mean_mcse=float(az.mcse({'v':values},method='mean')['v']),interval=interval.tolist(),endpoint_mcse=mcse,bulk_ess=float(az.ess({'v':values},method='bulk')['v']),tail_ess=float(az.ess({'v':values},method='tail')['v']),rhat=float(az.rhat({'v':values})['v']),endpoint_mcse_width=max(mcse)/(interval[1]-interval[0]))
result=dict(arm=a.arm,status='completed',scope='Specialized alternative Gibbs algorithm vs centered NumPyro on exactly matched new model; exploratory synthetic, no oWALNUTS improvement claim',T=len(y),observed=int(mask.sum()),chains=4,warmup=warmup,draws=draws,truth=truth,prediction=dict(horizon=1,x_future=0.,type='observed return with latent persistent conditional mean'),divergence_scope='HMC divergences not applicable to Gibbs; convergence assessed independently',compile_seconds=compile_seconds,warmup_compile_seconds=warmup_compile_seconds,sampling_including_warmup_seconds=sampling_including_warmup,fit_seconds=fit_seconds,end_to_end_seconds=time.perf_counter()-start,all_canonical=dict(max_rhat=float(np.max(rhat)),min_bulk_ess=float(np.min(bulk)),min_tail_ess=float(np.min(tail)),retained_divergences=divergences),functionals=rows)
result['health_pass']=result['all_canonical']['max_rhat']<=1.01 and result['all_canonical']['min_bulk_ess']>=400 and result['all_canonical']['min_tail_ess']>=400 and divergences==0
result['endpoint_precision_pass']=all(r['endpoint_mcse_width']<=.02 for r in rows.values())
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
