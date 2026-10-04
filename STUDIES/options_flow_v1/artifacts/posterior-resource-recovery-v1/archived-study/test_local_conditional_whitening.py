"""Prototype correctness tests; run only after coordinated quiet window."""
import unittest
import numpy as np
import local_conditional_whitening as guide
from local_level import log_density as canonical_density


class ConditionalWhiteningTests(unittest.TestCase):
    def data(self,t):
        return dict(y=np.linspace(-.2,.4,t).tolist(),dt=np.linspace(.4,1.6,t-1).tolist(),anchor=.13,anchor_mode='exogenous',nu=5.)

    def dense(self,data,lo,lr):
        t=len(data['y']);r=np.exp(-2*lr)/np.asarray(data['dt']);w=np.exp(-2*lo)
        R=np.zeros((t,t));R[0,0]=1/1.5**2
        for i,v in enumerate(r):
            R[i,i]+=v;R[i+1,i+1]+=v;R[i,i+1]-=v;R[i+1,i]-=v
        Q=R+w*np.eye(t);b=w*np.asarray(data['y']);b[0]+=data['anchor']/1.5**2
        return Q,b,np.linalg.cholesky(Q)

    def test_factor_roundtrip_and_jacobian(self):
        for t in [1,2,7,128]:
            data=self.data(t)
            for lo,lr in [(-2.5,-2.),(-9.,-1.),(-1.,-9.),(2.,1.)]:
                u=np.r_[np.linspace(-.5,.7,t),lo,lr]
                m,d,e=guide._guide(lo,lr,data)
                Q,b,L=self.dense(data,lo,lr)
                actual=np.diag(d)+np.diag(e,-1)
                np.testing.assert_allclose(actual@actual.T,Q,rtol=1e-12,atol=1e-8)
                np.testing.assert_allclose(Q@m,b,rtol=1e-7,atol=2e-8)
                np.testing.assert_allclose(actual,L,rtol=2e-8,atol=1e-8)
                q=guide.to_canonical(u,data)
                np.testing.assert_allclose(guide.to_whitened(q,data),u,rtol=1e-8,atol=1e-8)
                np.testing.assert_allclose(guide.log_density(u,data),canonical_density(q,data)-np.log(d).sum(),rtol=1e-11,atol=1e-8)

    def test_gaussian_control(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        for t in [1,7]:
            data=self.data(t);u=np.r_[np.linspace(-.6,.8,t),-2.2,-1.7]
            def analytic(v):
                z,lo,lr=v[:-2],v[-2],v[-1]
                w=jnp.exp(-2*lo);r=jnp.exp(-2*lr)/jnp.asarray(data['dt'])
                # Dense independent solve, no guide recurrence reuse.
                D=jnp.asarray(np.diff(np.eye(t),axis=0))
                R=D.T@(r[:,None]*D)+jnp.diag(jnp.r_[1/1.5**2,jnp.zeros(t-1)])
                Q=R+w*jnp.eye(t);b=w*jnp.asarray(data['y']);b=b.at[0].add(data['anchor']/1.5**2)
                m=jnp.linalg.solve(Q,b)
                energy=(m[0]-data['anchor'])**2/1.5**2+jnp.sum(r*jnp.diff(m)**2)+w*jnp.sum((jnp.asarray(data['y'])-m)**2)
                logdetR=np.log(1/1.5**2)+jnp.log(r).sum()
                marginal=-t/2*np.log(2*np.pi)+.5*(logdetR+t*jnp.log(w)-jnp.linalg.slogdet(Q)[1])-energy/2
                priors=-.5*(lo-np.log(.08))**2-.5*(lr-np.log(.12))**2-np.log(2*np.pi)
                return marginal+priors-.5*jnp.sum(z*z)-t/2*np.log(2*np.pi)
            density=lambda v:guide.log_density(v,data,jnp,gaussian=True)
            value,gradient=jax.value_and_grad(density)(u)
            ref,refgrad=jax.value_and_grad(analytic)(u)
            np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-10)
            np.testing.assert_allclose(gradient,refgrad,rtol=1e-9,atol=1e-9)
            np.testing.assert_allclose(gradient[:-2],-u[:-2],atol=1e-10)
            np.testing.assert_allclose(jax.hessian(density)(u)[:-2,-2:],0.,atol=1e-9)
            scan=lambda v:guide.jax_log_density(v,data,gaussian=True)
            scan_value,scan_gradient=jax.value_and_grad(scan)(u)
            np.testing.assert_allclose(scan_value,ref,rtol=1e-10,atol=1e-10)
            np.testing.assert_allclose(scan_gradient,refgrad,rtol=1e-9,atol=1e-9)
            np.testing.assert_allclose(jax.hessian(scan)(u)[:-2,-2:],0.,atol=1e-9)

    def test_compiled_density_gradient_and_starts(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from pymc_workflow import compile_target,evaluate_cfunc,coordinate_transport,canonical_starts
        from continuation_precision import local_configuration
        for t in [1,7]:
            data=self.data(t);starts=canonical_starts(data,4)
            data['initial_positions']=starts.tolist()
            encode,decode=coordinate_transport(data,'conditional_whitening')
            initial,reference_starts,potential,canonical=local_configuration(data,4,'conditional_whitening')
            np.testing.assert_array_equal(initial,starts)
            np.testing.assert_array_equal(reference_starts,encode(starts))
            np.testing.assert_allclose(canonical(reference_starts[:,None,:])[:,0,:],starts,atol=1e-12)
            target,meta=compile_target(data,'conditional_whitening')
            vg=jax.value_and_grad(lambda u:guide.log_density(u,data,jnp))
            for lo,lr in [(-2.5,-2.),(-9.,-1.),(-1.,-9.)]:
                u=np.r_[np.linspace(-.5,.7,t),lo,lr]
                value,grad=evaluate_cfunc(target,u);ref,refgrad=vg(u)
                np.testing.assert_allclose(value,ref,rtol=1e-9,atol=1e-7)
                np.testing.assert_allclose(grad,refgrad,rtol=1e-7,atol=1e-6)
                direction=np.arange(1,len(u)+1,dtype=float);direction/=np.linalg.norm(direction)
                eps=1e-5
                finite=(guide.log_density(u+eps*direction,data)-guide.log_density(u-eps*direction,data))/(2*eps)
                np.testing.assert_allclose(grad@direction,finite,rtol=2e-5,atol=2e-5)

    def test_invalid_positions(self):
        data=self.data(7)
        for u in [np.zeros(8),np.full(9,np.nan),np.r_[np.zeros(7),1000.,-2.],np.r_[np.zeros(7),-1000.,-2.]]:
            for convert in [guide.to_canonical,guide.to_whitened]:
                with self.assertRaises(ValueError):convert(u,data)

    def test_heterogeneous_batch(self):
        data=self.data(7)
        positions=np.zeros((2,3,9));positions[...,:7]=np.linspace(-.4,.6,7)
        positions[...,-2]=np.array([[-4.,-3.,-2.],[-1.,0.,1.]])
        positions[...,-1]=np.array([[-1.,-2.,-3.],[-4.,1.,0.]])
        canonical=guide.to_canonical(positions,data)
        np.testing.assert_allclose(guide.to_whitened(canonical,data),positions,rtol=1e-10,atol=1e-10)
        for i in range(2):
            for j in range(3):np.testing.assert_allclose(canonical[i,j],guide.to_canonical(positions[i,j],data),atol=1e-12)

    def test_scan_matches_independent_loop_gradient(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        for t in [1,2,7,128]:
            data=self.data(t)
            for lo,lr in [(-2.,-2.),(-9.,-1.),(-1.,-9.)]:
                u=np.r_[np.linspace(-.5,.7,t),lo,lr]
                value,gradient=jax.value_and_grad(lambda q:guide.jax_log_density(q,data))(u)
                ref,refgrad=jax.value_and_grad(lambda q:guide.log_density(q,data,jnp))(u)
                np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8)
                np.testing.assert_allclose(gradient,refgrad,rtol=1e-8,atol=1e-7)

    def test_compiled_tie_and_long_path(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        from pymc_workflow import compile_target,evaluate_cfunc
        for t in [2,128]:
            data=self.data(t)
            lo=-2.;lr=-.5*np.log((np.exp(-2*lo)+1/1.5**2)*data['dt'][0])
            target,_=compile_target(data,'conditional_whitening')
            u=np.r_[np.linspace(-.5,.7,t),lo,lr]
            value,grad=evaluate_cfunc(target,u)
            ref,refgrad=jax.value_and_grad(lambda q:guide.log_density(q,data,jnp))(u)
            np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(grad,refgrad,rtol=1e-8,atol=1e-7)
            for k in [-2,-1]:
                delta=np.zeros_like(u);delta[k]=1e-5
                finite=(guide.log_density(u+delta,data)-guide.log_density(u-delta,data))/(2e-5)
                np.testing.assert_allclose(grad[k],finite,rtol=1e-6,atol=1e-6)


class CombinedSolveTests(unittest.TestCase):
    def test_combined_compiled_target_parity(self):
        import jax
        jax.config.update('jax_enable_x64',True)
        import jax.numpy as jnp
        import owalnuts
        from pymc_workflow import evaluate_cfunc
        for t in [1,2,128]:
            data=dict(y=np.linspace(-.2,.4,t).tolist(),dt=np.linspace(.4,1.6,t-1).tolist(),anchor=.13,anchor_mode='exogenous',nu=5.)
            target,dim,initial,names,unravel=owalnuts.from_pymc(guide.build_model(data,combine_solve=True),gil_free=True)
            self.assertEqual(dim,t+2)
            reference=jax.jit(jax.value_and_grad(lambda u:guide.jax_log_density(u,data)))
            for lo,lr in [(-2.5,-2.),(-9.,-1.),(-1.,-9.)]:
                u=np.r_[np.linspace(-.5,.7,t),lo,lr]
                value,gradient=evaluate_cfunc(target,u);ref,grad=reference(jnp.asarray(u))
                np.testing.assert_allclose(value,ref,rtol=1e-9,atol=1e-7)
                np.testing.assert_allclose(gradient,grad,rtol=1e-7,atol=2e-6)
                q=guide.to_canonical(u,data);_,d,_=guide._guide(lo,lr,data)
                np.testing.assert_allclose(value,canonical_density(q,data)-np.log(d).sum(),rtol=1e-9,atol=1e-7)
                direction=np.zeros_like(u);direction[-2:]=[.6,.8];eps=1e-5
                finite=(guide.log_density(u+eps*direction,data)-guide.log_density(u-eps*direction,data))/(2*eps)
                np.testing.assert_allclose(gradient@direction,finite,rtol=3e-5,atol=3e-5)

if __name__=='__main__':unittest.main()
