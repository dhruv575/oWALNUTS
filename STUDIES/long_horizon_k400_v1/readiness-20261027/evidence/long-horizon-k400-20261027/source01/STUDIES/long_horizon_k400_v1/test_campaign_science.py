import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from data_model import generate,canonical_targets
from checkpoint import checkpoint,reference_reliability
from analyze import analyze

class LiteralRNG:
    def normal(self,loc=0,scale=1,size=None):return float(loc) if size is None else np.linspace(-.1,.1,size)
    def standard_t(self,df,size):return np.ones(size)
class Tests(unittest.TestCase):
    def test_shift_boundary(self):
        d=generate(0,lambda seed:LiteralRNG());a=d['control_y'];b=d['shift_y'];self.assertTrue(np.array_equal(a[1000:1250],b[1000:1250]));self.assertNotEqual(a[1250],b[1250]);self.assertFalse(np.array_equal(a[1001:1251],b[1001:1251]));self.assertEqual(len(canonical_targets([1,500,999,1000,1001,1002,1010,1025,1500,1750,2000])),18)
    def test_label_failure_does_not_poison_grid(self):
        class Failure(Exception):diagnostics={'gh64_128':'preserved'}
        def evaluator(draws,y):
            if y==999:raise Failure('literal numerical failure')
            return dict(cdf=.5,logpdf=-1.,pit_by_chain_draw=np.full((4,8),.5),density_mcse=dict(mean_scaled_density=1.,scaled_density=np.ones((4,8))))
        draws=np.zeros((4,8,4));draws[:,:,0]=-10;draws[:,:,1]=-1
        with patch('checkpoint.evaluate_scale',return_value={'quantiles':[1,2]}):result=checkpoint(draws,np.linspace(-1,1,250),999,1000,evaluator)
        self.assertEqual(sum(q['status']=='ok' for q in result['queries']),5);self.assertEqual(result['queries'][-1]['numerical_failure'],Failure.diagnostics)
        with patch('checkpoint.az.rhat',return_value=1.),patch('checkpoint.az.ess',return_value=2000.):quality=reference_reliability(draws,result,[0]*4)
        self.assertTrue(quality['reliable']);self.assertFalse(quality['observed_label_reliable'])
    def test_missing_full_denominators(self):
        p=json.loads((Path(__file__).parent/'protocol.json').read_text(encoding='utf-8-sig'))
        with tempfile.TemporaryDirectory() as t:
            analyze(t,p);summary=json.loads((Path(t)/'SUMMARY.json').read_text());self.assertEqual(summary['planned_updates'],8000);self.assertEqual(summary['available_query_comparisons'],0);self.assertEqual(len(json.loads((Path(t)/'CHECKPOINT-LEDGER.json').read_text())),44);self.assertEqual(len(json.loads((Path(t)/'SCALE-COMPARISONS.json').read_text())),88)
if __name__=='__main__':unittest.main()
