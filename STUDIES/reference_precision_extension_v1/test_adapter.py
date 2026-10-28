import unittest
import numpy as np
from extended_adapter import fit

class AdapterTests(unittest.TestCase):
    def test_fixed_budget_and_seed_forwarding(self):
        calls={}
        class Compiled:
            def with_data(self,**kwargs):calls['data']=kwargs;return self
        class Nutpie:
            __version__='fixture'
            @staticmethod
            def compile_stan_model():pass
            @staticmethod
            def sample(model,draws,tune,chains,cores,seed,save_warmup,progress_bar,**kwargs):
                calls['sample']=dict(draws=draws,tune=tune,chains=chains,cores=cores,seed=seed)
                raise RuntimeError('stop before fixture trace')
        with self.assertRaisesRegex(RuntimeError,'stop before'):
            fit(Nutpie,Compiled(),np.zeros(250),703028000,dict(api_and_target_verified=True,engine_options={}))
        self.assertEqual(calls['sample'],dict(draws=16000,tune=2000,chains=4,cores=4,seed=703028000))
        self.assertEqual(calls['data']['seed'],703028001)
        self.assertEqual(calls['data']['n'],250)

if __name__=='__main__':unittest.main()
