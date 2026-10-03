import unittest
from unittest.mock import patch

import numpy as np
from scipy.stats import t

from predictive_cdf import PredictiveMixture,equal_fit_weights


class PredictiveCdfTests(unittest.TestCase):
    def flow(self):
        data={'y':np.zeros((3,2)).tolist(),'rho':.6,'nu':5.}
        # beta_bar,log_tau,mu,log_sigma,za[2],zb[2],h[3].
        q=np.array([.4,np.log(.7),-.2,np.log(.3),.1,-.3,.2,.5,-.5,.4,1.2])
        return data,q

    def test_flow_zero_future_innovation_matches_analytic_student_t(self):
        data,q=self.flow()
        mixture=PredictiveMixture.from_flow(q,data,group=1,x_next=2.,future_innovation_multiplier=0.)
        location=.3*(-.3)+(.4+.7*.5)*2.
        scale=np.exp((-.2+.6*(1.2+.2))/2)
        grid=np.linspace(-3,5,17)
        np.testing.assert_allclose(mixture.cdf(grid),t.cdf(grid,5,loc=location,scale=scale),rtol=1e-13,atol=1e-14)
        result=mixture.quantiles()
        self.assertTrue(result['numerical_reference_ready'])
        np.testing.assert_allclose(result['quantiles'],t.ppf([.05,.95],5,loc=location,scale=scale),rtol=1e-10,atol=1e-9)
        self.assertEqual([r['order'] for r in result['ladder']],[16,32,64,128])
        self.assertFalse(result['posterior_reference_qualified'])

    def test_local_layout_and_zero_innovation_are_observed_log_price(self):
        data={'y':[99.,-5.,8.],'nu':5.}
        q=np.array([100.,-200.,1.3,np.log(.4),np.log(.3)])
        mixture=PredictiveMixture.from_local_level(q,data,future_innovation_multiplier=0.)
        grid=np.linspace(-1,3,11)
        np.testing.assert_allclose(mixture.cdf(grid),t.cdf(grid,5,loc=1.3,scale=.4),atol=1e-14)
        result=mixture.quantiles()
        self.assertTrue(result['numerical_reference_ready'])
        np.testing.assert_allclose(result['quantiles'],t.ppf([.05,.95],5,loc=1.3,scale=.4),atol=1e-9)
        self.assertEqual(result['metadata']['scale'],'observed log price')

    def test_real_innovation_mixture_is_monotone_and_chunk_invariant(self):
        data,q=self.flow();draws=np.tile(q,(2,4,1))
        draws[...,0]+=np.linspace(-.3,.3,8).reshape(2,4)
        a=PredictiveMixture.from_flow(draws,data,group=0,x_next=.7,chunk_size=1)
        b=PredictiveMixture.from_flow(draws,data,group=0,x_next=.7,chunk_size=100)
        grid=np.linspace(-8,8,49);cdf=a.cdf(grid)
        self.assertTrue(np.all(np.diff(cdf)>0));self.assertTrue(np.all((cdf>=0)&(cdf<=1)))
        np.testing.assert_allclose(cdf,b.cdf(grid),atol=3e-15,rtol=0.)
        self.assertEqual(a.cdf(-np.inf),0.);self.assertEqual(a.cdf(np.inf),1.)
        self.assertTrue(a.quantiles()['numerical_reference_ready'])

    def test_local_innovation_is_integrated_not_omitted(self):
        data={'y':[0.]};q=[0.,np.log(.2),np.log(.1)]
        noiseless=PredictiveMixture.from_local_level(q,data,future_innovation_multiplier=0.)
        full=PredictiveMixture.from_local_level(q,data)
        self.assertAlmostEqual(full.cdf(0.),.5,places=14)
        self.assertLess(full.cdf(.5),noiseless.cdf(.5))
        result=full.quantiles()
        self.assertTrue(result['numerical_reference_ready'])
        self.assertGreater(result['quantiles'][1],noiseless.quantiles()['quantiles'][1])

    def test_equal_fit_weighting_does_not_weight_longer_fit_more(self):
        data={'y':[0.]}
        a=np.array([-2.,np.log(.3),np.log(.2)]);b=np.array([2.,np.log(.3),np.log(.2)])
        pooled=np.vstack([a,np.tile(b,(9,1))]);weights=equal_fit_weights([1,9])
        mixture=PredictiveMixture.from_local_level(pooled,data,weights=weights,future_innovation_multiplier=0.)
        self.assertAlmostEqual(mixture.cdf(0.),.5,places=14)
        self.assertLess(PredictiveMixture.from_local_level(pooled,data,future_innovation_multiplier=0.).cdf(0.),.2)

    def test_unconverged_ladder_and_root_failure_do_not_return_accepted_quantiles(self):
        mixture=PredictiveMixture.from_local_level([0.,-1.,-2.],{'y':[0.]})
        def varying(probabilities,order,*args):
            return {'order':order,'quantiles':[-1.,1.+order*.01],'roots':[],'bracket':[-10.,10.]}
        with patch.object(mixture,'_quantiles_at_order',side_effect=varying):
            result=mixture.quantiles()
        self.assertFalse(result['numerical_reference_ready']);self.assertIsNone(result['quantiles'])
        self.assertIsNotNone(result['provisional_quantiles'])
        self.assertEqual(result['failure_reason'],'quadrature_ladder_not_converged_at_cap')
        with patch.object(mixture,'_quantiles_at_order',side_effect=RuntimeError('bracket failed')):
            result=mixture.quantiles()
        self.assertEqual(result['status'],'quadrature_unresolved');self.assertIsNone(result['quantiles'])
        self.assertIn('bracket failed',result['ladder'][0]['error'])

    def test_invalid_shapes_weights_and_probabilities_fail_closed(self):
        data,q=self.flow()
        with self.assertRaises(ValueError):PredictiveMixture.from_flow(q[:-1],data)
        with self.assertRaises(ValueError):PredictiveMixture.from_flow(q,data,group=2)
        with self.assertRaises(ValueError):PredictiveMixture.from_flow(q,data,weights=[0.])
        with self.assertRaises(ValueError):PredictiveMixture.from_local_level([0.,-1.,float('nan')],{'y':[0.]})
        mixture=PredictiveMixture.from_flow(q,data)
        with self.assertRaises(ValueError):mixture.quantiles([.95,.05])
        with self.assertRaises(ValueError):mixture.cdf(float('nan'))


if __name__=='__main__':unittest.main()
