"""Independent NumPyro worker for the audited optionsWALNUTS local-level model."""
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
from local_level import validate,log_density,canonicalize,noncenter

def run(data,seed,warmup,draws,chains,noncentered=False):
    validate(data);kind='noncentered' if noncentered else 'centered'
    starts=[]
    for c in range(chains):
        offset=(c-(chains-1)/2)*.02
        starts.append(np.r_[np.asarray(data['y'])+offset,np.log(.08)+offset,np.log(.12)-offset])
    starts=np.array(starts);initial=starts.copy()
    if noncentered:starts=noncenter(starts,data)
    kernel=NUTS(potential_fn=lambda q:-log_density(q,data,jnp,gammaln,kind),target_accept_prob=.8,max_tree_depth=10)
    m=MCMC(kernel,num_warmup=warmup,num_samples=draws,num_chains=chains,chain_method='sequential',progress_bar=False)
    start=time.perf_counter();m.warmup(jax.random.PRNGKey(seed),init_params=jnp.asarray(starts),extra_fields=('num_steps','diverging'))
    jax.block_until_ready(m.last_state.z);warm_seconds=time.perf_counter()-start
    print(json.dumps({'phase':'warmup_complete','seconds':warm_seconds}),flush=True)
    ts=time.perf_counter();m.run(m.post_warmup_state.rng_key,extra_fields=('num_steps','diverging'))
    samples=canonicalize(m.get_samples(group_by_chain=True),data,kind,jnp);jax.block_until_ready(samples)
    sample_seconds=time.perf_counter()-ts;extra=m.get_extra_fields(group_by_chain=True)
    return {'arm':'numpyro-noncentered' if noncentered else 'numpyro','seed':seed,'initial_positions':initial.tolist(),
      'chains':[{'draws':np.asarray(samples[c]).tolist(),'retained_divergences':int(np.asarray(extra['diverging'][c]).sum()),
                 'retained_leapfrogs':int(np.asarray(extra['num_steps'][c]).sum()),'max_depth_rate':float(np.mean(np.asarray(extra['num_steps'][c]) >= 2**10-1))} for c in range(chains)],
      'wall_seconds':time.perf_counter()-start,'timing_seconds':{'warmup_including_sampler_compilation':warm_seconds,
      'sampling_including_any_compilation':sample_seconds,'isolated_compilation':None},
      'software':{'jax':jax.__version__,'numpyro':numpyro.__version__}}
if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text());r=run(data,*map(int,sys.argv[3:7]),noncentered=(len(sys.argv)>7 and sys.argv[7]=='noncentered'))
    Path(sys.argv[2]).write_text(json.dumps(r,allow_nan=False))
