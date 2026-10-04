"""Pending quiet-window checks; no sampler or timing comparison."""
import unittest
import numpy as np
import jax
jax.config.update('jax_enable_x64',True)
import jax.numpy as jnp
from jax.scipy.special import gammaln
from flow_mixed_coordinates import jax_log_density as sequential, jax_to_canonical as sequential_canonical, log_jacobian, to_mixed
from flow_mixed_associative import jax_log_density,jax_to_canonical
from flow_starts import canonical_starts
from model import log_density

class MixedAssociativeTests(unittest.TestCase):
    def test_normalized_density_gradients_and_canonical_paths(self):
        for t in [1,32,128,1000]:
            for rho in [0.,1e-10,-.95,.95,.9999]:
                with self.subTest(t=t,rho=rho):
                    rng=np.random.default_rng(823+t)
                    data=dict(y=rng.normal(size=(t,2)).tolist(),x=rng.normal(size=(t,2)).tolist(),rho=rho,nu=5.)
                    q=canonical_starts(data,1)[0];u=to_mixed(q,data)
                    u[0]=.17;u[1]=-.7;u[4:8]=[.3,-.2,.4,-.1];u[8:]=rng.normal(size=t)*.2
                    value,grad=jax.jit(jax.value_and_grad(lambda v:jax_log_density(v,data)))(jnp.asarray(u))
                    other,other_grad=jax.jit(jax.value_and_grad(lambda v:sequential(v,data)))(jnp.asarray(u))
                    # Independent sequential canonical transform and normalized
                    # centered density + full Jacobian checks beta centering too.
                    exact,exact_grad=jax.jit(jax.value_and_grad(lambda v:log_density(sequential_canonical(v,data),data,jnp,gammaln)+log_jacobian(v,data,jnp)))(jnp.asarray(u))
                    np.testing.assert_allclose(value,other,rtol=1e-10,atol=1e-8)
                    np.testing.assert_allclose(grad,other_grad,rtol=1e-9,atol=1e-7)
                    np.testing.assert_allclose(value,exact,rtol=1e-10,atol=1e-8)
                    np.testing.assert_allclose(grad,exact_grad,rtol=1e-8,atol=1e-6)
                    np.testing.assert_allclose(jax_to_canonical(jnp.asarray(u),data),sequential_canonical(jnp.asarray(u),data),rtol=1e-10,atol=1e-10)
                    self.assertTrue(np.isfinite(grad).all())
    def test_masks_cannot_be_silently_ignored(self):
        data=dict(y=[[0.]],x=[[0.]],rho=.95,nu=5.,observation_mask=[[False]])
        with self.assertRaises(ValueError):jax_log_density(jnp.zeros(7),data)
    def test_small_varied_scales_dimensions_and_finite_difference(self):
        for g in [1,4]:
            data=dict(y=[[.2]*g,[.1]*g],x=[[.3]*g,[-.2]*g],rho=-.9999,nu=5.)
            for lt,ls in [(-2.,-3.),(.7,-.5)]:
                u=to_mixed(canonical_starts(data,1)[0],data);u[1]=lt;u[3]=ls;u[-2:]=[.03,-.02]
                actual=lambda v:jax_log_density(v,data)
                value,gradient=jax.value_and_grad(actual)(jnp.asarray(u))
                other,other_gradient=jax.value_and_grad(lambda v:sequential(v,data))(jnp.asarray(u))
                np.testing.assert_allclose(value,other,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(gradient,other_gradient,rtol=1e-8,atol=1e-6)
                numerical=[]
                for i in range(len(u)):
                    delta=np.zeros_like(u);delta[i]=1e-5
                    numerical.append(float((actual(jnp.asarray(u+delta))-actual(jnp.asarray(u-delta)))/2e-5))
                np.testing.assert_allclose(gradient,numerical,rtol=2e-5,atol=2e-5)
            for wrong in [jnp.zeros((2,len(u))),jnp.zeros(len(u)+1),jnp.zeros(len(u)-1)]:
                with self.assertRaises(ValueError):jax.jit(lambda v:jax_log_density(v,data))(wrong)
    def test_actual_associative_worker_invocation(self):
        import json,tempfile
        from pathlib import Path
        from mixed_flow_reference import execute
        data=dict(y=[[.2],[.1]],x=[[.3],[-.2]],rho=.95,nu=5.)
        fixture=dict(data=data,holdout=dict(x=[[.2]],y=[[.1]]))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.json';path.write_text(json.dumps(fixture));out=Path(directory)/'out'
            report=execute(path,out,873,warmup=12,chains=4,tiers=(8,),batch=8,implementation='associative')
            self.assertEqual(report['status'],'completed',report.get('traceback'))
            self.assertEqual(report['implementation'],'associative');self.assertEqual(report['settings']['implementation'],'associative')
            self.assertEqual(report['parity']['implementation'],'associative');self.assertTrue(report['parity']['passed'])
            self.assertEqual(report['arm'],'numpyro-mixed-slopes-continuation')
            self.assertEqual(report['checkpoints'][-1]['draws_per_chain'],8)
if __name__=='__main__':unittest.main()

