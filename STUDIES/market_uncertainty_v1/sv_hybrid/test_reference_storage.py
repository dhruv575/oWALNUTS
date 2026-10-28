"""Runtime serialization readiness; deterministic arrays, no posterior sampling."""
import tempfile
from pathlib import Path
import unittest
import numpy as np
import arviz as az


class StorageTests(unittest.TestCase):
    def test_warmup_and_diagnostics_survive_netcdf(self):
        values=np.arange(24,dtype=float).reshape(4,6)
        trace=az.from_dict(posterior={'mu':values,'z':values[:,:,None]},
                          sample_stats={'diverging':values.astype(int)%2},
                          warmup_posterior={'mu':-values,'z':-values[:,:,None]},
                          warmup_sample_stats={'diverging':np.zeros_like(values,dtype=bool)},
                          save_warmup=True)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'trace.nc';trace.to_netcdf(path)
            restored=az.from_netcdf(path)
            try:
                self.assertEqual(set(restored.groups()),set(trace.groups()))
                np.testing.assert_array_equal(restored.posterior['z'],values[:,:,None])
                np.testing.assert_array_equal(restored.warmup_posterior['mu'],-values)
                np.testing.assert_array_equal(restored.sample_stats['diverging'],values.astype(int)%2)
                np.testing.assert_array_equal(restored.warmup_sample_stats['diverging'],np.zeros_like(values,dtype=bool))
            finally:
                for group in restored.groups():getattr(restored,group).close()
                restored.close()


if __name__=='__main__':unittest.main()
