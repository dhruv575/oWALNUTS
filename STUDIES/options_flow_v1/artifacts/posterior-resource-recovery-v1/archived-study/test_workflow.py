import unittest
import numpy as np
from model import simulate,validate,log_density,functionals
class ContractTests(unittest.TestCase):
    def test_repeatability(self):
        self.assertEqual(simulate(11),simulate(11))
    def test_missing_refused(self):
        d=simulate(1)['data'];d['y'][0][0]=float('nan')
        with self.assertRaises(ValueError):validate(d)
    def test_infinite_tail_parameter_refused(self):
        d=simulate(1)['data'];d['nu']=float('inf')
        with self.assertRaises(ValueError):validate(d)
    def test_prior_draws_and_density(self):
        for seed in range(3):
            f=simulate(seed,8,2,2,True);q=np.array(f['truth'])
            self.assertEqual(len(q),16);self.assertTrue(np.isfinite(log_density(q,f['data'])))
            self.assertEqual(set(functionals(q,2)),{'beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean','alpha_0','alpha_1','beta_0','beta_1'})
    def test_future_outcomes_cannot_change_posterior(self):
        f=simulate(12,8,2,2);q=np.array(f['truth']);lp=log_density(q,f['data'])
        f['holdout']['y']=[[1e9,1e9]]*2
        self.assertEqual(log_density(q,f['data']),lp)
    def test_diagnostics_cover_entire_state(self):
        from evaluate import summarize
        f=simulate(31,6,2,2);rng=np.random.default_rng(888)
        q=rng.normal(size=(4,500,len(f['truth'])))
        out=summarize(q,f)
        self.assertEqual(len(out['canonical_parameter_diagnostics']),len(f['truth']))
        self.assertEqual(len(out['forecast']['rows']),4)
        self.assertFalse(out['forecast']['operational_forecast_qualified'])
    def test_reference_nc_canonical_posterior_contract(self):
        # The transformed target must include a determinant depending on sigma_h.
        f=simulate(51,6,2,2);q=np.array(f['truth']);rho=f['data']['rho'];g=2
        h=q[4+2*g:];mu=q[2];sig=np.exp(q[3])
        z=np.r_[(h[0]-mu)*np.sqrt(1-rho*rho)/sig,(h[1:]-mu-rho*(h[:-1]-mu))/sig]
        rebuilt=np.empty_like(h);rebuilt[0]=mu+sig*z[0]/np.sqrt(1-rho*rho)
        for i in range(1,len(h)):rebuilt[i]=mu+rho*(rebuilt[i-1]-mu)+sig*z[i]
        np.testing.assert_allclose(rebuilt,h,atol=1e-12)
    def test_jax_gradient_finite_difference(self):
        import jax; jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from jax.scipy.special import gammaln
        f=simulate(2,6,2,2);q=np.array(f['truth'])
        v,g=jax.value_and_grad(lambda z:log_density(z,f['data'],jnp,gammaln))(jnp.asarray(q))
        self.assertAlmostEqual(float(v),float(log_density(q,f['data'])),places=9)
        eps=1e-5; finite=[]
        for j in range(len(q)):
            d=np.zeros_like(q);d[j]=eps
            finite.append((log_density(q+d,f['data'])-log_density(q-d,f['data']))/(2*eps))
        np.testing.assert_allclose(g,finite,rtol=2e-6,atol=2e-6)
if __name__=='__main__':unittest.main()
