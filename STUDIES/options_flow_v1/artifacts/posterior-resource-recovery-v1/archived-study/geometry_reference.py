"""Matched NumPyro fixed prior-Fisher geometry, with optional fixed mean shear."""
import os
os.environ.setdefault('JAX_ENABLE_X64','true')
import json,sys,time
from pathlib import Path
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
import numpyro
from numpyro.infer import MCMC,NUTS
from model import validate
from flow_starts import canonical_starts
from geometry import FixedGeometry,transformed_log_density

def run(data,seed,warmup,draws,chains,kind='fisher',starts=None):
    if kind not in ('fisher','fisher-shear'):raise ValueError('Unknown Fisher arm')
    validate(data);setup_start=time.perf_counter();geom=FixedGeometry.from_data(data,mean_shear=kind=='fisher-shear')
    if starts is None:starts=canonical_starts(data,chains)
    starts=np.asarray(starts,float)
    if starts.shape!=(chains,geom.dimension):raise ValueError('Initial shape mismatch')
    initial=starts.copy();transformed=geom.to_transformed(starts)
    setup_seconds=time.perf_counter()-setup_start
    kernel=NUTS(potential_fn=lambda u:-transformed_log_density(u,data,geom,jnp),target_accept_prob=.8,max_tree_depth=10)
    m=MCMC(kernel,num_warmup=warmup,num_samples=draws,num_chains=chains,chain_method='sequential',progress_bar=False)
    ts=time.perf_counter();m.warmup(jax.random.PRNGKey(seed),init_params=jnp.asarray(transformed),extra_fields=('num_steps','diverging'))
    jax.block_until_ready(m.last_state.z);warm=time.perf_counter()-ts
    print(json.dumps(dict(phase='warmup_complete',seconds=warm)),flush=True)
    ts=time.perf_counter();m.run(m.post_warmup_state.rng_key,extra_fields=('num_steps','diverging'))
    q=geom.to_canonical(m.get_samples(group_by_chain=True),jnp);jax.block_until_ready(q)
    retained=time.perf_counter()-ts;extra=m.get_extra_fields(group_by_chain=True)
    return dict(arm='numpyro-'+kind,seed=seed,initial_positions=initial.tolist(),transformed_initial_positions=transformed.tolist(),
      geometry=geom.metadata(),geometry_setup_seconds=setup_seconds,coordinates='centered',wall_seconds=setup_seconds+warm+retained,
      timing_seconds=dict(warmup_including_any_compilation=warm,sampling_including_any_compilation=retained,isolated_compilation=None),
      software=dict(jax=jax.__version__,numpyro=numpyro.__version__),
      chains=[dict(draws=np.asarray(q[c]).tolist(),retained_divergences=int(np.asarray(extra['diverging'][c]).sum()),
        retained_leapfrogs=int(np.asarray(extra['num_steps'][c]).sum()),
        max_depth_rate=float(np.mean(np.asarray(extra['num_steps'][c])>=2**10-1))) for c in range(chains)])
if __name__=='__main__':
    data=json.loads(Path(sys.argv[1]).read_text());r=run(data,*map(int,sys.argv[3:7]),kind=sys.argv[7] if len(sys.argv)>7 else 'fisher')
    Path(sys.argv[2]).write_text(json.dumps(r,allow_nan=False))
