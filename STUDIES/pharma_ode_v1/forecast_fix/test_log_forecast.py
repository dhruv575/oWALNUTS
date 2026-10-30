import ctypes,json,unittest
from pathlib import Path
import numpy as np
from scipy.integrate import solve_ivp
from backend import Backend,ROOT,DP

class Tests(unittest.TestCase):
    def test_tail_forecast_and_unchanged_density(self):
        data=json.loads((ROOT/'data/theoph_1.json').read_text())
        receipt=json.loads(Path('/home/ubuntu/lanes/pharma-ode-20261029/PREDICTION-FAILURE-DIAGNOSIS.json').read_text())
        q=np.array(receipt['q']);b=Backend(data);prediction=b.predict(q)
        np.testing.assert_allclose(prediction,receipt['log_state_prediction'],rtol=2e-6,atol=2e-6)
        old=b.lib.create(b'/home/ubuntu/lanes/pharma-ode-20261029/build/model_model.so',json.dumps(data).encode(),data['P'],data['Npred'],b.center.ctypes.data_as(DP),b.A.ctypes.data_as(DP))
        self.assertTrue(old)
        try:
            for j in range(8):
                x=np.ascontiguousarray(q+.05*np.sin(np.arange(len(q))+j));g=np.empty(len(q));lp=np.empty(1)
                self.assertEqual(b.lib.evaluate(len(q),x.ctypes.data_as(DP),g.ctypes.data_as(DP),lp.ctypes.data_as(DP),old),0)
                new,newg=b.value(x);self.assertAlmostEqual(new,lp[0],places=12);np.testing.assert_allclose(newg,g,rtol=1e-12,atol=1e-12)
        finally:b.lib.destroy(old);b.close()

if __name__=='__main__':unittest.main()
