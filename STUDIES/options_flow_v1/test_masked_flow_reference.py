import copy
import unittest
import numpy as np
import jax
import jax.numpy as jnp
from jax.scipy.special import gammaln
from masked_flow import from_arrays,canonical,log_density
from flow_starts import canonical_starts,to_noncentered
from masked_flow_reference import target,names,screen
from reference_continuation import ContinuedReference
from masked_forecast import forecast

class MaskedReferenceTests(unittest.TestCase):
    def data(self):
        return from_arrays([[.2],[0.],[.1]],[[.1],[0.],[.3]],y_available=[[True],[False],[True]],x_available=[[True]]*3)
    def test_normalized_nc_and_gradient(self):
        data=self.data();q=to_noncentered(canonical_starts(data,1)[0],data);q[-3:]=[.2,-.1,.4]
        physical=canonical(q,data);jac=3*q[3]-.5*np.log(1-data['rho']**2)
        self.assertAlmostEqual(float(-target(data)(jnp.asarray(q))),log_density(physical,data)+jac,places=11)
        grad=np.asarray(jax.grad(target(data))(jnp.asarray(q)))
        numeric=np.array([(target(data)(jnp.asarray(q+np.eye(len(q))[i]*1e-5))-target(data)(jnp.asarray(q-np.eye(len(q))[i]*1e-5)))/2e-5 for i in range(len(q))])
        np.testing.assert_allclose(grad,numeric,rtol=1e-5,atol=1e-7)
        np.testing.assert_allclose(canonical(to_noncentered(physical,data),data),physical)
    def test_masked_target_prefix_identical(self):
        data=self.data();starts=to_noncentered(canonical_starts(data,2),data)
        split=ContinuedReference(target(data),starts,703,20,8,.9);full=ContinuedReference(target(data),starts,703,20,16,.9)
        split.adapt();split.append();split.append();full.adapt();full.append()
        np.testing.assert_array_equal(split.samples,full.samples)
        self.assertEqual(split.checkpoints[0]['adaptation_sha256'],split.checkpoints[1]['adaptation_sha256'])
    def test_gap_forecast_and_full_scope(self):
        data=self.data();draws=np.repeat(canonical_starts(data,4)[:,None,:],32,axis=1)
        future=dict(x=[[1.],[None],[2.]],y=[[None],[None],[.2]],x_available=[[True],[False],[True]],observation_mask=[[False],[False],[True]],grid_index=[0,1,2])
        a=forecast(draws,data,future,23);changed=copy.deepcopy(future);changed['y'][2]=[100.];b=forecast(draws,data,changed,23)
        self.assertEqual(a['rows'][2]['lower'],b['rows'][2]['lower']);self.assertEqual(a['scheduled_cells'],3);self.assertEqual(a['scored_cells'],1)
        report=dict(status='completed',healthy=True,evaluation=dict(functionals={n:dict(interval_90=[-1,1],endpoint_mcse=[.001,.001]) for n in names(1)},forecast=a))
        report['evaluation']['forecast']['rows'][0]['endpoint_mcse']=[.001,.001];report['evaluation']['forecast']['rows'][2]['endpoint_mcse']=[.001,.001]
        self.assertTrue(screen(report,1,[[1,0],[3,0]])['pass'])
        self.assertFalse(screen(report,1,[[3,0]])['pass'])
        del report['evaluation']['functionals']['h_mean'];self.assertFalse(screen(report,1,[[1,0],[3,0]])['pass'])
if __name__=='__main__':unittest.main()
