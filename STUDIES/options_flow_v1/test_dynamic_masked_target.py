"""Queued correctness tests only; no persistent sampler benchmark."""
import copy
import unittest
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
from jax.scipy.special import gammaln
from dynamic_masked_target import snapshot,log_density,canonical
from masked_flow import log_density as independent,canonical as sequential
from flow_starts import canonical_starts,to_noncentered

class DynamicMaskedTargetTests(unittest.TestCase):
    def fixture(self,t=8,g=2):
        rng=np.random.default_rng(771+t)
        return dict(y=rng.normal(size=(t,g)).tolist(),x=rng.normal(size=(t,g)).tolist(),observation_mask=np.ones((t,g),bool).tolist(),grid_index=list(range(t)),rho=.95,nu=5.)
    def test_same_trace_changed_count_and_a_return(self):
        a=self.fixture();b=copy.deepcopy(a);b['observation_mask'][2:]=[[False,False]]*6;b['y'][2:]=[[None,float('nan')]]*6;b['x'][2:]=[[float('inf'),None]]*6
        q=to_noncentered(canonical_starts(a,1)[0],a);q[-8:]=np.linspace(-.2,.3,8)
        traces=[]
        def density(q,*args):traces.append(1);return log_density(q,*args)
        compiled=jax.jit(jax.value_and_grad(density));results=[]
        for data in [a,b,a]:
            args=tuple(jnp.asarray(v) for v in snapshot(data));value,gradient=compiled(jnp.asarray(q),*args)
            ref,refgrad=jax.value_and_grad(lambda z:independent(z,data,jnp,gammaln,noncentered=True))(jnp.asarray(q))
            np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-9);np.testing.assert_allclose(gradient,refgrad,rtol=1e-9,atol=1e-8)
            results.append((np.asarray(value),np.asarray(gradient)))
        raw=(jnp.asarray(np.asarray(b['y'],float)),jnp.asarray(np.asarray(b['x'],float)),jnp.asarray(b['observation_mask']),jnp.asarray(b['rho'],dtype=jnp.float64),jnp.asarray(b['nu'],dtype=jnp.float64))
        raw_value,raw_gradient=compiled(jnp.asarray(q),*raw)
        np.testing.assert_allclose(raw_value,results[1][0]);np.testing.assert_allclose(raw_gradient,results[1][1]);self.assertTrue(np.isfinite(raw_gradient).all())
        self.assertEqual(len(traces),1);np.testing.assert_array_equal(results[0][0],results[2][0]);np.testing.assert_array_equal(results[0][1],results[2][1]);self.assertNotEqual(float(results[0][0]),float(results[1][0]))
    def test_normalized_jacobian_extremes_and_no_observations(self):
        for t in [1,2,32]:
            for rho in [0.,-.9999,.95]:
                for observed in [False,True]:
                    with self.subTest(t=t,rho=rho,observed=observed):
                        data=self.fixture(t,1);data['rho']=rho;data['observation_mask']=[[observed]]*t
                        if not observed:data['y']=[[float('nan')]]*t;data['x']=[[float('inf')]]*t
                        q=to_noncentered(canonical_starts(data,1)[0],data);q[-t:]=.03
                        args=tuple(jnp.asarray(v) for v in snapshot(data))
                        actual=jax.value_and_grad(lambda z:log_density(z,*args))(jnp.asarray(q))
                        def reference(z):return independent(sequential(z,data,jnp),data,jnp,gammaln)+t*z[3]-.5*jnp.log1p(-rho*rho)
                        expected=jax.value_and_grad(reference)(jnp.asarray(q))
                        np.testing.assert_allclose(actual[0],expected[0],rtol=1e-9,atol=1e-8);np.testing.assert_allclose(actual[1],expected[1],rtol=1e-8,atol=1e-7)
                        self.assertTrue(np.isfinite(actual[1]).all())
                        np.testing.assert_allclose(canonical(jnp.asarray(q),*args),sequential(jnp.asarray(q),data,jnp),rtol=1e-10,atol=1e-10)
    def test_snapshot_owns_immutable_inputs_and_observed_nan_rejected(self):
        data=self.fixture();saved=snapshot(data);old=saved[0].copy();data['y'][0][0]=1234.
        np.testing.assert_array_equal(saved[0],old)
        with self.assertRaises(ValueError):saved[0][0,0]=1234.
        data['y'][0][0]=float('nan')
        with self.assertRaises(ValueError):snapshot(data)
if __name__=='__main__':unittest.main()


