"""Optimized equivalent NumPyro target: associative AR1 prefix and direct innovation priors."""
import os
os.environ.setdefault('JAX_ENABLE_X64','true')
import json,sys,time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
from jax.scipy.special import gammaln
import numpyro
from numpyro.infer import MCMC,NUTS
from model import log_density,validate


def canonical_noncentered(q,data):
    g=len(data['y'][0]);z=q[4+2*g:];mu=q[2];sig=jnp.exp(q[3]);rho=data['rho']
    a=jnp.full(z.shape,rho).at[0].set(0.)
    b=(mu*(1-rho)+sig*z).at[0].set(mu+sig*z[0]/jnp.sqrt(1-rho*rho))
    def compose(left,right):
        a0,b0=left;a1,b1=right
        return a1*a0,b1+a1*b0
    _,h=jax.lax.associative_scan(compose,(a,b))
    return jnp.concatenate((q[:4+2*g],h))

def noncentered_log_density(q,data):
    y,x=jnp.asarray(data['y']),jnp.asarray(data['x']);t,g=y.shape;nu=data['nu']
    c=canonical_noncentered(q,data);h=c[4+2*g:];b,lt,mu,ls=q[:4]
    def normal(v,m,s):return jnp.sum(-.5*((v-m)/s)**2-jnp.log(s)-.5*jnp.log(2*jnp.pi))
    lp=normal(q[:4],jnp.array([0.,-1.,-1.,-1.5]),jnp.array([.5,.5,1.,.5]))+normal(q[4:],0.,1.)
    location=.3*q[4:4+g]+(b+jnp.exp(lt)*q[4+g:4+2*g])*x
    residual=(y-location)*jnp.exp(-h[:,None]/2)
    return lp+jnp.sum(gammaln((nu+1)/2)-gammaln(nu/2)-.5*jnp.log(nu*jnp.pi)-h[:,None]/2-(nu+1)/2*jnp.log1p(residual**2/nu))


def run(data,seed,warmup,draws,chains,starts=None,noncentered=False):
    validate(data); g=len(data['y'][0]); t=len(data['y']); dim=4+2*g+t
    if starts is None:
        starts=np.tile(np.r_[0.,-1.,-1.,-1.5,np.zeros(2*g),np.full(t,-1.)],(chains,1))
    def canonical(q):
        return canonical_noncentered(q,data) if noncentered else q
    if noncentered:
        starts=starts.copy();starts[:,4+2*g:]=0.
    def potential(q):
        return -noncentered_log_density(q,data) if noncentered else -log_density(q,data,jnp,gammaln)
    kernel=NUTS(potential_fn=potential,target_accept_prob=.8,max_tree_depth=10)
    mcmc=MCMC(kernel,num_warmup=warmup,num_samples=draws,num_chains=chains,chain_method='sequential',progress_bar=False)
    start=time.perf_counter()
    ts=time.perf_counter(); mcmc.warmup(jax.random.PRNGKey(seed),init_params=jnp.asarray(starts),extra_fields=('num_steps','diverging'))
    jax.block_until_ready(mcmc.last_state.z); warm_seconds=time.perf_counter()-ts
    print(json.dumps({'phase':'warmup_complete','seconds':warm_seconds}),flush=True)
    ts=time.perf_counter(); mcmc.run(mcmc.post_warmup_state.rng_key,extra_fields=('num_steps','diverging'))
    samples=mcmc.get_samples(group_by_chain=True); jax.block_until_ready(samples)
    if noncentered:samples=jax.vmap(jax.vmap(canonical))(samples);jax.block_until_ready(samples)
    sample_seconds=time.perf_counter()-ts; extra=mcmc.get_extra_fields(group_by_chain=True)
    return {'arm':'numpyro-noncentered' if noncentered else 'numpyro','seed':seed,'chains':[{'draws':np.asarray(samples[c]).tolist(),
            'retained_divergences':int(np.asarray(extra['diverging'][c]).sum()),
            'retained_leapfrogs':int(np.asarray(extra['num_steps'][c]).sum()),'max_depth_rate':float(np.mean(np.asarray(extra['num_steps'][c]) >= 2**10-1))} for c in range(chains)],
            'wall_seconds':time.perf_counter()-start,'timing_seconds':{'density_compilation':None,
            'warmup_including_sampler_compilation':warm_seconds,'sampling_including_any_new_compilation':sample_seconds,
            'sampler_compilation_separate':None},
            'software':{'jax':jax.__version__,'numpyro':numpyro.__version__},
            'timing_limitation':'Public NumPyro API does not expose isolated sampler compilation; cold process total is comparison metric.'}

if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text())
    result=run(data,*map(int,sys.argv[3:7]),noncentered=(len(sys.argv)>7 and sys.argv[7]=='noncentered'))
    Path(sys.argv[2]).write_text(json.dumps(result,allow_nan=False))
