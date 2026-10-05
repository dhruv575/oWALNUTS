import copy,unittest
import numpy as np
from scipy.stats import t
from forecast import posterior,distribution,fit_scaled,forecast,HORIZON

def data(n=30):
 rows=[]
 for i in range(n):
  rows.append(dict(features=dict(origin_receipt_ns=i*HORIZON,anchor=dict(available=True,midpoint=100+i),flow_known=True,total_amount=10+i,signed_amount=(-1)**i),label=dict(horizon_end_receipt_ns=(i+1)*HORIZON,available_at_receipt_ns=(i+1)*HORIZON,observed=True,log_midpoint_return=.001*((i%3)-1))))
 return dict(rows=rows)
class Tests(unittest.TestCase):
 def test_prior_no_observations(self):
  p=posterior(np.empty((0,2)),[]);np.testing.assert_array_equal(p['mean'],[0,0]);np.testing.assert_array_equal(p['covariance_factor'],np.eye(2)*100)
  d=distribution(p,[1,0]);self.assertAlmostEqual(d['predictive_scale'],np.sqrt(.0002/3*101));self.assertAlmostEqual(d['predictive_interval_90'][1],t.ppf(.95,6)*d['predictive_scale'])
 def test_future_label_invariance(self):
  a=data();b=copy.deepcopy(a)
  for row in b['rows'][25:]:row['label']['log_midpoint_return']=12345
  self.assertEqual(forecast(a,25*HORIZON),forecast(b,25*HORIZON))
 def test_immature_label_invariance(self):
  a=data();a['rows'][24]['label']['available_at_receipt_ns']=27*HORIZON;b=copy.deepcopy(a);b['rows'][24]['label']['log_midpoint_return']=999
  self.assertEqual(forecast(a,25*HORIZON),forecast(b,25*HORIZON))
 def test_scaling_inversion(self):
  X=np.array([[1,10,3],[1,20,3],[1,30,3]],float);p,mu,sd,A=fit_scaled(X,[.01,.02,.03]);x=np.array([1,25,3],dtype=float);z=x.copy();z[1:]=(x[1:]-mu)/sd
  self.assertAlmostEqual(z@p['mean'],x@(A@p['mean']));self.assertAlmostEqual(z@p['covariance_factor']@z,x@A@p['covariance_factor']@A.T@x)
 def test_no_history_or_flow(self):
  a=data(2);self.assertEqual(forecast(a,HORIZON)['reason'],'insufficient_mature_history');a=data();a['rows'][25]['features']['flow_known']=False
  self.assertEqual(forecast(a,25*HORIZON)['reason'],'missing_flow');self.assertEqual(forecast(a,25*HORIZON,flow=False)['status'],'forecast')
 def test_predictive_wider(self):
  r=forecast(data(),25*HORIZON);d=r['distribution'];self.assertGreater(d['predictive_interval_90'][1]-d['predictive_interval_90'][0],d['conditional_mean_credible_interval_90'][1]-d['conditional_mean_credible_interval_90'][0])
 def test_wrong_horizon(self):
  d=data();d['rows'][0]['label']['horizon_end_receipt_ns']=2
  with self.assertRaises(ValueError):forecast(d,25*HORIZON)
 def test_invalid_hyperparameters(self):
  for name in ('a0','b0','prior_variance'):
   for value in (True,float('nan'),float('inf'),-1,0):
    with self.subTest(name=name,value=value):
     with self.assertRaises(ValueError):posterior([[1.]],[0.],**{name:value})
 def test_zero_input_degenerate_mean(self):
  d=distribution(posterior(np.empty((0,2)),[]),[0.,0.])
  self.assertEqual(d['conditional_mean_credible_interval_90'],[0.,0.])
  self.assertGreater(d['predictive_scale'],0)
 def test_future_covariate_invariance(self):
  a=data();b=copy.deepcopy(a)
  for row in b['rows'][26:]:
   row['features'].update(total_amount=100000,signed_amount=99999)
   row['features']['anchor']['midpoint']=999999
  self.assertEqual(forecast(a,25*HORIZON),forecast(b,25*HORIZON))
 def test_collinear_design_remains_proper(self):
  X=np.ones((5,3));p=posterior(X,np.zeros(5))
  self.assertTrue(np.all(np.linalg.eigvalsh(p['covariance_factor'])>0))
  self.assertTrue(np.isfinite(distribution(p,[1.,1.,1.])['predictive_interval_90']).all())
if __name__=='__main__':unittest.main()

