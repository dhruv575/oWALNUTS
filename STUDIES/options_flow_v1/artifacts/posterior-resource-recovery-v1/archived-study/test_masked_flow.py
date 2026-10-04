import unittest
import copy
from importlib.util import find_spec
import numpy as np
from scipy.special import gammaln
from scipy.stats import norm
import masked_flow as masked
from model import log_density as original
from flow_starts import canonical_starts,to_noncentered


class MaskedFlowTests(unittest.TestCase):
    def data(self):
        rng=np.random.default_rng(187)
        return masked.from_arrays(rng.normal(size=(8,2)),rng.normal(size=(8,2)),y_available=np.ones((8,2),bool),x_available=np.ones((8,2),bool))

    def test_all_observed_and_prior_only(self):
        data=self.data();q=canonical_starts(data,1)[0]+np.random.default_rng(5).normal(0,.03,16)
        self.assertAlmostEqual(masked.log_density(q,data),original(q,data),places=11)
        u=to_noncentered(q,data);data['observation_mask']=np.zeros((8,2),bool).tolist()
        data['y']=np.full((8,2),np.nan).tolist();data['x']=np.full((8,2),np.inf).tolist()
        prior=norm.logpdf(u[:4],[0,-1,-1,-1.5],[.5,.5,1,.5]).sum()+norm.logpdf(u[4:]).sum()
        self.assertAlmostEqual(masked.log_density(u,data,noncentered=True),prior,places=11)

    def test_missing_covariates_and_grid_contract(self):
        y=np.array([[1.],[np.nan],[3.],[4.]]);x=np.array([[0.],[np.nan],[np.nan],[1.]])
        data=masked.from_arrays(y,x,y_available=[[True],[False],[True],[True]],x_available=[[True],[False],[False],[True]])
        self.assertEqual(data['observation_mask'],[[True],[False],[False],[True]])
        self.assertEqual(data['missingness']['excluded_x'],1)
        self.assertEqual(len(data['y']),4)
        data['grid_index']=[0,1,3,4]
        with self.assertRaises(ValueError):masked.validate(data)
        data['grid_index']=[0,1,2,3];data['observation_mask'][2][0]=True;data['x'][2][0]=np.nan
        with self.assertRaises(ValueError):masked.validate(data)

    @unittest.skipUnless(find_spec('jax') is not None,'JAX unavailable')
    def test_jax_gradient_and_placeholder_invariance(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from jax.scipy.special import gammaln as jgamma
        data=self.data();mask=np.ones((8,2),bool);mask[1:5]=False;data['observation_mask']=mask.tolist()
        data['y']=np.where(mask,data['y'],np.nan).tolist();data['x']=np.where(mask,data['x'],np.inf).tolist()
        u=to_noncentered(canonical_starts(data,1)[0],data)+np.random.default_rng(91).normal(0,.02,16)
        def vg(d):return jax.value_and_grad(lambda p:masked.log_density(p,d,jnp,jgamma,True))(jnp.asarray(u))
        value,gradient=vg(data);self.assertTrue(np.isfinite(gradient).all())
        changed=copy.deepcopy(data);changed['y']=np.where(mask,data['y'],1e200).tolist();changed['x']=np.where(mask,data['x'],-1e200).tolist()
        other,othergrad=vg(changed);np.testing.assert_array_equal(value,other);np.testing.assert_array_equal(gradient,othergrad)
        direction=np.random.default_rng(17).normal(size=len(u));direction/=np.linalg.norm(direction);eps=1e-5
        fd=(masked.log_density(u+eps*direction,data,noncentered=True)-masked.log_density(u-eps*direction,data,noncentered=True))/(2*eps)
        np.testing.assert_allclose(fd,np.asarray(gradient)@direction,rtol=1e-6,atol=1e-6)
        # A gap retains its latent innovation's influence on later observed times.
        self.assertGreater(abs(np.asarray(gradient)[8+2]+u[8+2]),1e-8)

    @unittest.skipUnless(all(find_spec(n) is not None for n in ['pymc','owalnuts','jax']),'Optional PyMC/JAX integration unavailable')
    def test_compiled_pymc_value_gradient_matches_independent_targets(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from jax.scipy.special import gammaln as jgamma
        from masked_flow_pymc import compile_target
        from pymc_workflow import evaluate_cfunc
        for kind in ['all','gap','none']:
            data=self.data()
            if kind=='gap':data['observation_mask'][2:6]=[[False,False]]*4
            if kind=='none':data['observation_mask']=np.zeros((8,2),bool).tolist()
            mask=np.asarray(data['observation_mask']);data['y']=np.where(mask,data['y'],np.nan).tolist();data['x']=np.where(mask,data['x'],np.nan).tolist()
            u=to_noncentered(canonical_starts(data,1)[0],data)
            target,_,_,_,_=compile_target(data)
            value,gradient=evaluate_cfunc(target,u)
            ref,grad=jax.value_and_grad(lambda p:masked.log_density(p,data,jnp,jgamma,True))(jnp.asarray(u))
            np.testing.assert_allclose(value,masked.log_density(u,data,noncentered=True),rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(gradient,grad,rtol=1e-9,atol=1e-8)


if __name__=='__main__':unittest.main()
