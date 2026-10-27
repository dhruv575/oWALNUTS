import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from scipy.optimize._numdiff import approx_derivative
from baselines import objective, nig_ar1, fit_t5, ewma_t5, score_distribution, FLOOR

class BaselineTests(unittest.TestCase):
    def test_gradient(self):
        y=np.array([-3.,-.7,0,.2,1.,4.])
        for theta in [np.array([.3,-.8]),np.array([-1.,1.2])]:
            np.testing.assert_allclose(objective(theta,y)[1],
                approx_derivative(lambda v:objective(v,y)[0],theta).ravel(),rtol=1e-6,atol=1e-8)

    def test_nig_startup_and_observation_noise(self):
        y=np.sin(np.arange(300))*.01
        for n,expected in [(251,250),(257,256),(300,256)]:
            got=nig_ar1(y[:n]);self.assertEqual(got['training_pairs'],expected)
            start=max(1,n-256);lag=y[start-1:n-1];response=y[start:n]
            x=np.column_stack([np.ones(len(lag)),(lag-lag.mean())/lag.std()])
            v=np.linalg.inv(x.T@x+np.eye(2)/100);m=v@x.T@response
            z=np.array([1,(y[n-1]-lag.mean())/lag.std()])
            b=.0002+.5*((response-x@m)@(response-x@m)+m@m/100)
            expected_scale=np.sqrt(b/(3+len(lag)/2)*(1+z@v@z))
            self.assertAlmostEqual(got['scale'],expected_scale,14)

    def test_constant_fit_floor(self):
        fit=fit_t5(np.ones(250)*.02)
        self.assertEqual(fit['status'],'ok');self.assertEqual(len(fit['attempts']),4)
        self.assertAlmostEqual(fit['location'],.02,12)
        self.assertAlmostEqual(fit['scale'],FLOOR,14);self.assertTrue(fit['floor_hit'])

    def test_mle_determinism_translation(self):
        y=np.linspace(-.03,.03,250)**3*100
        first=fit_t5(y);second=fit_t5(y)
        self.assertEqual(first,second);self.assertEqual(first['status'],'ok')
        shifted=fit_t5(y+.1)
        self.assertAlmostEqual(shifted['location']-first['location'],.1,10)
        self.assertAlmostEqual(shifted['scale'],first['scale'],10)

    def test_ewma_index_and_variance(self):
        y=np.zeros(252);y[250]=.1;y[251]=.3
        initial=dict(status='ok',location=.01,scale=.02)
        got=ewma_t5(y[:251],initial)
        v=.94*(5/3)*.02**2+.06*(.1-.01)**2
        self.assertAlmostEqual(got['variance'],v)
        self.assertAlmostEqual(got['scale']**2,3*v/5)
        self.assertEqual(got['updates'],1)
        y[251]=900
        self.assertEqual(got,ewma_t5(y[:251],initial))

    def test_deadline(self):
        with self.assertRaises(TimeoutError):fit_t5(np.arange(250.),deadline=0)

    def test_nonfinite_optimizer_and_score_are_preserved(self):
        invalid=SimpleNamespace(x=np.array([np.nan,np.nan]),success=False,message='fixture',nfev=1,nit=1)
        with patch('baselines.minimize',return_value=invalid):
            fit=fit_t5(np.arange(250.))
        self.assertEqual(fit['status'],'unavailable');json.dumps(fit,allow_nan=False)
        self.assertIsNone(fit['attempts'][0]['mean_nll'])
        with patch('baselines.t.logpdf',return_value=np.nan):
            with self.assertRaises(ValueError):score_distribution(0,1,5,0)

if __name__=='__main__':unittest.main()
