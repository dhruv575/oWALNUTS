import unittest
from endpoint_exact_controls import plan,summarize,validate_spec


class ExactControlsTests(unittest.TestCase):
    def test_strict_execution_spec(self):
        import copy
        spec=plan(1000,2,[8,16]);validate_spec(spec)
        for key,value in [('relative_mcse',.5),('health',{}),('chains',2)]:
            bad=copy.deepcopy(spec);bad[key]=value
            with self.assertRaises(ValueError):validate_spec(bad)
        for key,value in [('marginal','unknown'),('rho',.8),('policy','arbitrary'),('seeds',[])]:
            bad=copy.deepcopy(spec);bad['cells'][0][key]=value
            with self.assertRaises(ValueError):validate_spec(bad)
        bad=copy.deepcopy(spec);bad['cells'][1]['seeds'][0]=bad['cells'][0]['seeds'][0]
        with self.assertRaises(ValueError):validate_spec(bad)

    def test_failed_later_tier_cannot_reuse_earlier_estimator(self):
        row=dict(id='failed',status='failed',finite_estimator=True,usable=True,estimate=[0.,2.],mcse=[1.,1.],truth=[0.,2.])
        self.assertEqual(summarize([row],['failed'],True)['usable'],0)
        self.assertEqual(summarize([row],['failed'])['usable'],0)
    def test_distinct_streams_and_unfrozen_plan(self):
        spec=plan(1000,2,[8,16]);seeds=[s for c in spec['cells'] for s in c['seeds']]
        self.assertEqual(len(spec['cells']),48);self.assertEqual(len(set(seeds)),len(seeds));self.assertFalse(spec['frozen'])
        for cell in spec['cells']:self.assertEqual(len(cell['seeds']),8 if cell['policy']=='restart_first_pass' else 4)

    def test_exact_error_denominator_and_mcse_understatement(self):
        rows=[dict(id=str(i),usable=True,estimate=[v,v+2],mcse=[.5,.5],truth=[0,2]) for i,v in enumerate([-1.,0.,1.])]
        output=summarize(rows,['0','1','2','missing'])
        self.assertEqual(output['usable_rate'],.75)
        self.assertEqual(output['endpoints']['0.05']['mcse_calibration_ratio'],2.)
        self.assertEqual(output['endpoints']['0.05']['usable_with_error_le_04_true_width_rate'],.25)

    def test_fixed_estimator_includes_unhealthy_stationary_draws(self):
        rows=[dict(id=str(i),usable=False,finite_estimator=True,estimate=[v,v+2],mcse=[1.,1.],truth=[0,2]) for i,v in enumerate([-1.,0.,1.])]
        self.assertEqual(summarize(rows,['0','1','2'])['usable'],0)
        self.assertEqual(summarize(rows,['0','1','2'],True)['usable'],3)

    def test_stationary_ar1_covariance_with_filter_initialization(self):
        import numpy as np
        from scipy.signal import lfilter
        # Columns map independent unit-variance noises to states. Their Gram
        # matrix must equal the analytic stationary covariance rho**|i-j|.
        for rho in [0.,.9,.99]:
            n=12;noise_map=np.diag([1.]+[np.sqrt(1-rho*rho)]*(n-1))
            transport=lfilter([1.],[1.,-rho],noise_map,axis=0)
            covariance=transport@transport.T
            expected=rho**np.abs(np.arange(n)[:,None]-np.arange(n)[None,:])
            np.testing.assert_allclose(covariance,expected,rtol=1e-12,atol=1e-12)

    def test_known_bias_is_not_hidden_by_reported_mcse(self):
        rows=[dict(id=str(i),usable=True,estimate=[1.,3.],mcse=[.01,.01],truth=[0.,2.]) for i in range(3)]
        output=summarize(rows,['0','1','2','missing'])
        self.assertEqual(output['endpoints']['0.05']['rmse'],1.)
        self.assertEqual(output['endpoints']['0.05']['mean_error'],1.)
        self.assertEqual(output['endpoints']['0.05']['usable_with_error_le_04_true_width_rate'],0.)
        self.assertEqual(output['missing_ids'],['missing'])

    def test_invalid_specs_and_duplicate_results(self):
        for tiers in [[8,8],[16,8],[1],[True]]:
            with self.assertRaises(ValueError):plan(1,2,tiers)
        with self.assertRaises(ValueError):summarize([{'id':'a'},{'id':'a'}],['a'])


if __name__=='__main__':unittest.main()
