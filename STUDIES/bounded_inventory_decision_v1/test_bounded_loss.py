import time,unittest,os,sys,importlib.util
from pathlib import Path
import numpy as np
from scipy.integrate import quad
from scipy.special import stdtr
from bounded_loss import A,COST,ABS_TOL,TAIL_BOUND,action,score,realized_downside,split_points,integrate_cdf_components,evaluate

class AnalyticTests(unittest.TestCase):
    def backend(self):
        path=Path(os.environ.get('OWALNUTS_NUMERICAL_BACKEND',str(Path(__file__).resolve().parents[1]/'resident_predictive_harness_v1/numerical_backend.py')))
        sys.path.insert(0,str(path.parent));spec=importlib.util.spec_from_file_location('bounded_fixture_backend',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
    def test_actual_backend_broad_mixture_independent_integral(self):
        beta=.0002;m=-10.;sigma=.8;draws=np.tile([m,np.log(sigma),beta,m],(4,4,1))
        value=evaluate(draws,self.backend(),time.perf_counter()+15)
        def conditional(z):
            h=m+sigma*z;scale=np.exp(h/2);points=split_points(np.array([beta]),np.array([h/2]))
            inner,_=quad(lambda r:np.exp(r)*stdtr(5,(r-beta)/scale),-A,0,points=points,epsabs=1e-11,epsrel=0,limit=300)
            return inner*np.exp(-z*z/2)/np.sqrt(2*np.pi)
        independent,_=quad(conditional,-9,9,epsabs=1e-10,epsrel=0,limit=150)
        self.assertLess(abs(value['mean_downside']-independent),2e-8)
    def test_actual_backend_duplication_and_permutation(self):
        draws=np.tile([-12.,np.log(.2),-.0001,-12.],(4,4,1));draws[:,:,2]+=np.arange(16).reshape(4,4)*.00001
        backend=self.backend();a=evaluate(draws,backend,time.perf_counter()+10);b=evaluate(draws[::-1,::-1],backend,time.perf_counter()+10);c=evaluate(np.repeat(draws,2,axis=1),backend,time.perf_counter()+10)
        self.assertAlmostEqual(a['mean_downside'],b['mean_downside'],places=10);self.assertAlmostEqual(a['mean_downside'],c['mean_downside'],places=10)
    def test_bounded_realized_loss_and_decision(self):
        self.assertTrue(np.allclose(realized_downside(np.array([-1000.,0.,1000.])),[1,0,0]))
        self.assertEqual(action(COST),'retain');self.assertEqual(action(COST+1e-10),'convert')
        for m in (0.,COST,.1,1.):
            expected=min(m,COST);chosen=COST if action(m)=='convert' else m;self.assertEqual(expected,chosen)
        self.assertEqual(score(.1,1000.)['decision_cost'],COST)
    def test_degenerate_returns(self):
        atoms=np.array([-10.,-.001,-1e-6,0.,.001])
        points=sorted(set(list(atoms[(atoms>-A)&(atoms<0)])+split_points(atoms,np.full(5,np.log(.001)))))
        values,diagnostics=integrate_cdf_components(lambda r:(r>=atoms).astype(float),points,time.perf_counter()+5)
        self.assertTrue(np.allclose(values,realized_downside(atoms),rtol=0,atol=TAIL_BOUND+1e-9))
    def test_single_t5_independent_density_integral(self):
        beta=-.0001;scale=.003
        cdf=lambda r:np.array([stdtr(5,(r-beta)/scale)])
        value,_=integrate_cdf_components(cdf,split_points(np.array([beta]),np.array([np.log(scale)])),time.perf_counter()+5)
        # Independent variable/representation: integrate payoff against t5 density.
        from scipy.stats import t
        exact,err=quad(lambda z:float(-np.expm1(beta+scale*z))*t.pdf(z,5),-np.inf,-beta/scale,epsabs=1e-11,epsrel=1e-11,limit=300)
        self.assertLess(abs(value[0]-exact),2e-8)
    def test_tiny_scale_and_shift_monotonicity(self):
        beta=np.array([-1e-5,-1e-6,0.,1e-6]);scale=1e-9
        points=split_points(beta,np.full(4,np.log(scale)))
        value,_=integrate_cdf_components(lambda r:stdtr(5,(r-beta)/scale),points,time.perf_counter()+5)
        self.assertTrue(np.all(np.diff(value)<=1e-10));self.assertTrue(np.allclose(value,realized_downside(beta),atol=2e-8,rtol=0))
    def test_tail_bound_linearity_permutation_and_deadline(self):
        value,_=integrate_cdf_components(lambda r:np.array([.2,.7]),[],time.perf_counter()+5)
        self.assertTrue(np.allclose(value,np.array([.2,.7])*(1-TAIL_BOUND),atol=1e-12))
        self.assertAlmostEqual(float(value.mean()),.45*(1-TAIL_BOUND))
        with self.assertRaises(TimeoutError):integrate_cdf_components(lambda r:np.array([.5]),[],time.perf_counter()-1)
    def test_squared_error_mean_target_and_units(self):
        y=np.array([0.,.1,.4]);p=np.array([.2,.5,.3]);m=float(p@y);variance=float(p@(y-m)**2)
        for forecast in (0.,m,.8):self.assertAlmostEqual(float(p@(y-forecast)**2),variance+(forecast-m)**2)
        s=12345.;loss=float(realized_downside(-.1));self.assertAlmostEqual(s*loss,s*(1-np.exp(-.1)))
if __name__=='__main__':unittest.main()
