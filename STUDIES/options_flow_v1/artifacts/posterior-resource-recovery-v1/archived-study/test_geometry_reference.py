import unittest
import numpy as np
from model import simulate,log_density
from flow_starts import to_noncentered
from geometry import FixedGeometry,transformed_log_density
class ReferenceCoordinateTests(unittest.TestCase):
    def test_noncentered_conversion_preserves_nondefault_starts(self):
        import jax.numpy as jnp
        from optimized_reference import canonical_noncentered
        data=simulate(123,8,2,1)['data']
        q=np.random.default_rng(19).normal(size=(3,16))
        q[:,3]=[-2,-1.5,-1]
        z=to_noncentered(q,data)
        rebuilt=np.stack([np.asarray(canonical_noncentered(jnp.array(v),data)) for v in z])
        np.testing.assert_allclose(rebuilt,q,rtol=1e-12,atol=1e-12)
    def test_geometry_normalized_density_against_dense_jacobian(self):
        data=simulate(4,6,2,1)['data'];q=np.random.default_rng(61).normal(size=14)
        for shear in [False,True]:
            geom=FixedGeometry.from_data(data,shear);u=geom.to_transformed(q)
            n=len(q);base=geom.to_canonical(np.zeros(n))
            jac=np.stack([geom.to_canonical(np.eye(n)[j])-base for j in range(n)],axis=1)
            sign,logdet=np.linalg.slogdet(jac)
            self.assertEqual(sign,1)
            self.assertAlmostEqual(float(transformed_log_density(u,data,geom)),float(log_density(q,data)+logdet),places=10)
    def test_geometry_worker_accepts_exact_canonical_starts(self):
        from geometry_reference import run
        data=simulate(5,4,2,1)['data'];starts=np.zeros((2,12));starts[:,:4]=[.1,-1,-1,-1.5];starts[:,8:]=-.75
        result=run(data,15,8,8,2,'fisher-shear',starts)
        np.testing.assert_array_equal(result['initial_positions'],starts)
        geom=FixedGeometry.from_data(data,True)
        np.testing.assert_allclose(geom.to_canonical(np.array(result['transformed_initial_positions'])),starts,atol=1e-12)
        self.assertEqual(np.array([c['draws'] for c in result['chains']]).shape,(2,8,12))
if __name__=='__main__':unittest.main()
