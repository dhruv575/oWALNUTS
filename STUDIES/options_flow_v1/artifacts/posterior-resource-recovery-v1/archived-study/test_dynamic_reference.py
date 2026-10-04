import unittest
import numpy as np
from model import simulate
class DynamicReferenceTests(unittest.TestCase):
    def test_factor_matches_normalized_density(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from numpyro.infer.util import log_density
        from dynamic_reference import dynamic_model
        from optimized_reference import noncentered_log_density
        f=simulate(91,8,2,2);d=f['data'];q=jnp.array(np.r_[0,-1,-1,-1.5,np.zeros(12)])
        args=(jnp.array(d['y']),jnp.array(d['x']),jnp.array(d['rho']),jnp.array(d['nu']))
        lp,_=log_density(dynamic_model,args,{},dict(q=q))
        self.assertAlmostEqual(float(lp),float(noncentered_log_density(q,d)),places=10)
    def test_refits_reset_warmup(self):
        from dynamic_reference import DynamicReference
        model=DynamicReference(warmup=8,draws=8,chains=2)
        for seed in [81,82]:
            result=model.fit(simulate(seed,4,2,1)['data'],seed+100)
            self.assertEqual(np.asarray(result['warmup_state_iterations']).tolist(),[8,8])
            self.assertEqual(np.array([c['draws'] for c in result['chains']]).shape,(2,8,12))
            self.assertTrue(result['fresh_adaptation'])
        fresh=DynamicReference(warmup=8,draws=8,chains=2).fit(simulate(82,4,2,1)['data'],182)
        np.testing.assert_allclose(np.array([c['draws'] for c in result['chains']]),np.array([c['draws'] for c in fresh['chains']]),rtol=0,atol=0)
if __name__=='__main__':unittest.main()
