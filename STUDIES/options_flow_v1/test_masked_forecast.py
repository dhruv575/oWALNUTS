import copy
import unittest
import numpy as np
from masked_forecast import forecast,summarize,precision_forecast_screen
from evaluate import summarize as dense_summary


class MaskedForecastTests(unittest.TestCase):
    def fixture(self):
        data=dict(y=[[0.],[0.]],x=[[0.],[0.]],observation_mask=[[True],[True]],grid_index=[0,1],rho=.95,nu=5.)
        future=dict(y=[[.1],[.2],[.3]],x=[[.1],[.2],[.3]],y_available=[[True],[True],[True]],x_available=[[True],[True],[True]],grid_index=[2,3,4])
        rng=np.random.default_rng(782);q=rng.normal(0,.03,(4,128,8));q[...,1]=-1+q[...,1];q[...,2]=-1+q[...,2];q[...,3]=-1.5+q[...,3];q[...,-2:]-=1
        return q,dict(data=data,holdout=future)

    def test_dense_equivalence_and_allcanonical_diagnostics(self):
        q,f=self.fixture();masked=summarize(q,f,71);dense=dense_summary(q,f,71)
        self.assertEqual(masked['canonical_parameter_diagnostics'],dense['canonical_parameter_diagnostics'])
        self.assertEqual(masked['functionals'],dense['functionals'])
        for a,b in zip(masked['forecast']['rows'],dense['forecast']['rows']):
            for key in ['lower','upper','endpoint_mcse','covered','interval_score']:self.assertEqual(a[key],b[key])

    def test_label_changes_never_change_forecasts_or_missing_score(self):
        q,f=self.fixture();original=forecast(q,f['data'],f['holdout'],77)
        future=copy.deepcopy(f['holdout']);future['y_available'][1]=[False];future['y'][1]=[np.nan];future['y'][0]=[1000.]
        changed=forecast(q,f['data'],future,77)
        for a,b in zip(original['rows'],changed['rows']):
            for key in ['lower','upper','endpoint_mcse']:self.assertEqual(a[key],b[key])
        self.assertIsNone(changed['rows'][1]['observed']);self.assertIsNone(changed['rows'][1]['covered']);self.assertIsNone(changed['rows'][1]['interval_score'])
        self.assertEqual(changed['scheduled_cells'],3);self.assertEqual(changed['scored_cells'],2)

    def test_missing_feature_keeps_gap_and_requires_frozen_family(self):
        q,f=self.fixture();full=forecast(q,f['data'],f['holdout'],81)
        future=copy.deepcopy(f['holdout']);future['x_available'][1]=[False];future['x'][1]=[np.nan]
        masked=forecast(q,f['data'],future,81)
        self.assertEqual(masked['rows'][2]['lower'],full['rows'][2]['lower'])
        self.assertEqual(masked['rows'][2]['upper'],full['rows'][2]['upper'])
        self.assertFalse(masked['rows'][1]['forecast_available']);self.assertIsNone(masked['rows'][1]['lower'])
        screen=precision_forecast_screen(masked,[(1,0),(2,0),(3,0)])
        self.assertFalse(screen['passed']);self.assertTrue(any('family' in v for v in screen['reasons']))
        future['grid_index']=[2,4,5]
        with self.assertRaises(ValueError):forecast(q,f['data'],future)

    def test_shape_and_availability_contract(self):
        q,f=self.fixture();f['holdout']['y'].pop()
        with self.assertRaises(ValueError):forecast(q,f['data'],f['holdout'])
        q,f=self.fixture();future=f['holdout'];future['observation_mask']=future.pop('y_available');future['grid_index']=[0,1,2]
        future['observation_mask'][1]=[False];future['y'][1]=[None]
        self.assertEqual(forecast(q,f['data'],future)['observed_target_cells'],2)
        q,f=self.fixture();f['holdout']['y'][0]=[np.nan]
        with self.assertRaises(ValueError):forecast(q,f['data'],f['holdout'])


if __name__=='__main__':unittest.main()
