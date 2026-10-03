"""Validated NumPyro continuation with frozen adaptation and fixed-size batches.

This mechanism avoids charging a capable reference for unnecessary re-warmup.
It does not yet provide a qualified cross-sampler timing comparison.
"""
import hashlib
import time
import numpy as np
import jax
import jax.numpy as jnp
from numpyro.infer import MCMC, NUTS
jax.config.update('jax_enable_x64', True)


def adaptation_digest(state):
    digest = hashlib.sha256()
    for leaf in jax.tree.leaves((state.adapt_state.step_size,
                                 state.adapt_state.inverse_mass_matrix)):
        value = np.asarray(leaf)
        digest.update(str((value.shape, value.dtype)).encode())
        digest.update(value.tobytes())
    return digest.hexdigest()


class ContinuedReference:
    def __init__(self, potential, starts, seed, warmup=1000, batch_size=1000):
        starts = np.asarray(starts, float)
        if starts.ndim != 2 or not np.isfinite(starts).all() or min(warmup, batch_size) < 1:
            raise ValueError('Require finite chain starts and positive warmup/batch size')
        self.mcmc = MCMC(NUTS(potential_fn=potential, target_accept_prob=.8,
                            max_tree_depth=10), num_warmup=warmup,
                         num_samples=batch_size, num_chains=len(starts),
                         chain_method='sequential', progress_bar=False)
        self.warmup = warmup
        self.batch_size = batch_size
        self.seed = seed
        self.starts = starts.copy()
        self.chunks = []
        self.checkpoints = []
        self.divergences = 0
        self.ready = False

    def adapt(self):
        if self.ready:
            raise RuntimeError('Adaptation already completed; create a new object for a new fit')
        ts = time.perf_counter(); cpu = time.process_time()
        self.mcmc.warmup(jax.random.PRNGKey(self.seed), init_params=jnp.asarray(self.starts),
                         extra_fields=('diverging', 'num_steps'))
        jax.block_until_ready(self.mcmc.last_state.z)
        self.adaptation_sha256 = adaptation_digest(self.mcmc.last_state)
        self.warmup_seconds = time.perf_counter()-ts
        self.warmup_cpu_seconds = time.process_time()-cpu
        self.ready = True

    def append(self):
        if not self.ready:
            raise RuntimeError('Warmup must complete before retained sampling')
        if self.chunks:
            self.mcmc.post_warmup_state = self.mcmc.last_state
        before = self.mcmc.post_warmup_state
        ts = time.perf_counter(); cpu = time.process_time()
        self.mcmc.run(before.rng_key, extra_fields=('diverging', 'num_steps'))
        q = np.asarray(self.mcmc.get_samples(group_by_chain=True))
        if not np.isfinite(q).all() or q.shape != (len(self.starts), self.batch_size, self.starts.shape[1]):
            raise RuntimeError('Invalid retained continuation output')
        if not np.all(np.asarray(self.mcmc.last_state.i) == np.asarray(before.i)+self.batch_size):
            raise RuntimeError('Continuation iteration counters did not advance by one batch')
        if adaptation_digest(self.mcmc.last_state) != self.adaptation_sha256:
            raise RuntimeError('Step size or metric changed during retained continuation')
        extra = self.mcmc.get_extra_fields()
        self.divergences += int(np.asarray(extra['diverging']).sum())
        self.chunks.append(q)
        self.checkpoints.append(dict(draws_per_chain=len(self.chunks)*self.batch_size,
            seconds=time.perf_counter()-ts,
            cpu_seconds=time.process_time()-cpu,
            retained_leapfrogs=int(np.asarray(extra['num_steps']).sum()),
            start_iterations=np.asarray(before.i).tolist(),
            end_iterations=np.asarray(self.mcmc.last_state.i).tolist(),
            adaptation_sha256=self.adaptation_sha256,
            retained_divergences_total=self.divergences))
        return q

    @property
    def samples(self):
        if not self.chunks:
            raise RuntimeError('No retained draws')
        return np.concatenate(self.chunks, axis=1)
