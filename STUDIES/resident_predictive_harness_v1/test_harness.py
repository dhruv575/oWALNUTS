import ctypes, math, time, unittest
import numpy as np
from scipy.stats import norm,t
import owalnuts
from sv_target import compile_target,compile_functional,TargetOwner,components,remap,RHO
from harness import summarize,processor,Resident
from unittest.mock import Mock,patch
from types import SimpleNamespace

class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compiled=compile_target();cls.functional=compile_functional()
    def test_target_density_and_gradient(self):
        y=np.array([.001,-.004,.003,.002]);owner=TargetOwner(self.compiled,y)
        q=np.array([2*np.log(.005),np.log(.2),.0001,.2,-.4,.1,.3])
        def independent(q):
            mu,ls,beta=q[:3];sigma=np.exp(ls);h=mu+sigma/np.sqrt(1-RHO**2)*q[3];hs=[h]
            for z in q[4:]:h=mu+RHO*(h-mu)+sigma*z;hs.append(h)
            return norm.logpdf(mu,2*np.log(.005),1)+norm.logpdf(ls,np.log(.2),.5)+norm.logpdf(beta,0,.002)+norm.logpdf(q[3:]).sum()+t.logpdf(y,5,loc=beta,scale=np.exp(np.array(hs)/2)).sum()
        g=np.zeros_like(q);ptr=ctypes.POINTER(ctypes.c_double)
        value=self.compiled.ctypes(len(q),q.ctypes.data_as(ptr),g.ctypes.data_as(ptr),owner.y.ctypes.data)
        self.assertAlmostEqual(value,independent(q),places=11)
        fd=[]
        for j in range(len(q)):
            eps=1e-7 if j==2 else 1e-5;a=q.copy();b=q.copy();a[j]+=eps;b[j]-=eps
            fd.append((independent(a)-independent(b))/(2*eps))
        np.testing.assert_allclose(g,fd,rtol=1e-6,atol=1e-5)
    def test_window_overlap_and_zero_fill(self):
        q=np.array([[-10.,np.log(.2),0.,.2,-.4,.3,.1],[-9.,np.log(.4),.001,-.3,.7,.2,-.1]])
        old=owalnuts.WarmState(q,np.array([.02,.03]),np.ones_like(q));new=remap(old)
        for c in range(2):
            def path(z):
                h=z[0]+np.exp(z[1])/np.sqrt(1-RHO**2)*z[3];hs=[h]
                for zz in z[4:]:h=z[0]+RHO*(h-z[0])+np.exp(z[1])*zz;hs.append(h)
                return hs
            np.testing.assert_allclose(path(old.positions[c])[1:],path(new.positions[c])[:-1],atol=1e-13)
        np.testing.assert_array_equal(new.positions[:,-1],0)
    def test_known_scale_and_independent_return(self):
        a=np.array([[[-10.,np.log(.3),.001,-10.]]]);r=summarize(a,time.perf_counter()+10)
        np.testing.assert_allclose(r['scale_p50_p95'],np.exp((-10+.3*norm.ppf([.5,.95]))/2),rtol=1e-10)
        for pp,q in zip((.05,.5,.95),r['return_p5_p50_p95']):
            actual,error=processor.independent_cdf(q,[-10],[.3],[.001],5)
            self.assertLess(abs(actual-pp),1e-8)
    def test_failure_and_broad_fixture(self):
        with self.assertRaises(ValueError):summarize(np.full((1,1,4),np.nan),time.perf_counter()+1)
        with self.assertRaises(TimeoutError):summarize(np.zeros((1,1,4)),time.perf_counter()-1)
        processor.validate(time.perf_counter()+20)
    def test_compact_and_refresh_parity(self):
        owner=TargetOwner(self.compiled,np.array([.001,-.004,.003,.002]))
        q=np.tile([2*np.log(.005),np.log(.2),0.,.2,-.4,.1,.3],(2,1))
        state=owalnuts.WarmState(q,np.array([.0001,.0001]),np.ones_like(q))
        kw=dict(seed=99371004,threads=1,tuning=owalnuts.Tuning(max_depth=3))
        with owalnuts.WarmSession(owner.target,state,**kw) as a,owalnuts.WarmSession(owner.target,state,**kw) as b:
            raw=a.refresh(3); compact=b.refresh_functionals(3,[self.functional],retain_draws=True)
        np.testing.assert_array_equal(raw.samples,compact.samples)
        np.testing.assert_allclose(compact.values,components(raw.samples),rtol=1e-14,atol=1e-14)
    def test_fail_closed_paths(self):
        def fake():
            r=Resident.__new__(Resident);r.backend=None;r.closed=False;r.y=np.array([1.,2.,3.]);r.compiled=None;r.functional=None;r.session=Mock()
            return r
        r=fake()
        row=r.tick(4.,0)
        self.assertEqual(row['phase'],'validate');r.session.retarget.assert_not_called()
        self.assertTrue(r.closed);np.testing.assert_array_equal(r.y,[1,2,3])
        r=fake();r.session.retarget.side_effect=RuntimeError('injected retarget failure')
        with patch('harness.remap',return_value=None),patch('harness.TargetOwner',return_value=SimpleNamespace(target=None)):
            row=r.tick(4.,2)
        self.assertEqual(row['state_advanced'],'uncertain');self.assertTrue(r.closed)
        np.testing.assert_array_equal(r.y,[1,2,3]);r.session.refresh_functionals.assert_not_called()
        r=fake();r.session.refresh_functionals.return_value=SimpleNamespace(values=np.zeros((1,2,4)),seed=7,
            diagnostics=[{'divergent':[False,False]}],metadata=[{}],work=[{}],target_calls=23,call_index=0)
        with patch('harness.remap',return_value=None),patch('harness.TargetOwner',return_value=SimpleNamespace(target=None)),patch('harness.summarize',side_effect=ValueError('injected numerical failure')):
            row=r.tick(4.,2)
        self.assertEqual(row['phase'],'summary');self.assertEqual(row['target_calls'],23)
        self.assertTrue(row['state_advanced']);self.assertTrue(r.closed);np.testing.assert_array_equal(r.y,[2,3,4])
        second=r.tick(5.,2);self.assertEqual(second['status'],'failed')
        self.assertEqual(r.session.refresh_functionals.call_count,1);np.testing.assert_array_equal(r.y,[2,3,4])
    def test_explicit_backends_preserve_base_and_fixtures(self):
        from numerical_backend import Backend,ConfiguredReturnCDF
        original=processor.stdtr
        scipy_backend=Backend();exact=Backend('exact_t5')
        for m,sigma,beta in [([-10.],[.3],[.001]),([-11.,-8.8],[.2,1.4],[-.001,.002])]:
            deadline=time.perf_counter()+20
            frozen=processor.ReturnCDF(m,sigma,beta,5,128,deadline,67108864)
            default=ConfiguredReturnCDF(m,sigma,beta,5,128,deadline,67108864,backend=scipy_backend)
            candidate=ConfiguredReturnCDF(m,sigma,beta,5,128,deadline,67108864,backend=exact)
            q=frozen.quantiles()['quantiles'];np.testing.assert_array_equal(default.quantiles()['quantiles'],q)
            np.testing.assert_allclose(candidate.quantiles()['quantiles'],q,rtol=0,atol=1e-12)
            for prob,x in zip((.05,.5,.95),q):
                val,error=processor.independent_cdf(x,m,sigma,beta,5)
                self.assertLess(abs(val-candidate(x)),1e-7)
        self.assertIs(processor.stdtr,original)
    def test_backend_rejection_and_failure(self):
        from numerical_backend import Backend,ConfiguredReturnCDF
        with self.assertRaises(ValueError):Backend('unreviewed')
        with self.assertRaises(ValueError):ConfiguredReturnCDF([-10],[.2],[0],7,64,time.perf_counter()+1,1000,backend=Backend('exact_t5'))
        bad=Backend();bad.cdf=lambda nu,x:np.full_like(x,np.nan)
        c=ConfiguredReturnCDF([-10],[.2],[0],5,64,time.perf_counter()+1,1000,backend=bad)
        with self.assertRaises(ValueError):c(0.)
if __name__=='__main__':unittest.main()
