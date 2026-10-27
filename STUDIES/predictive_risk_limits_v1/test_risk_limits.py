import json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from evaluator import baseline,score
from inputs import origins,references,module
from readiness import literal,equivalence
from report import valid,load_rows,bootstrap

class Tests(unittest.TestCase):
    def test_sign_ties_and_negative_limits(self):
        q=dict(q05=.01,q95=.03);s=score(q,.02)
        self.assertAlmostEqual(s['long']['pinball'],.0005);self.assertEqual(s['long']['limit'],-.01)
        self.assertEqual(score(q,.01)['long']['exceedance'],0)
        self.assertAlmostEqual(score(q,0)['long']['pinball'],.0095)
        self.assertAlmostEqual(score(q,.04)['short']['pinball'],.0095)
    def test_baseline_exact(self):
        q=baseline(dict(status='ok',location=.003,scale=.01,df=5))
        self.assertAlmostEqual(q['q05']+q['q95'],.006)
        with self.assertRaises(ValueError):baseline(dict(status='ok',location=0,scale=-1,df=5))
    def test_partition(self):
        for queue in (origins(),references()):
            shards=[queue[i::12] for i in range(12)]
            self.assertEqual(len(set(sum(shards,[]))),len(queue))
            self.assertEqual(sum(map(len,shards)),len(queue))
    def test_missing_accounting(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'started/candidate/2026-04/000001.json';p.parent.mkdir(parents=True);p.write_text('{}')
            rows=load_rows(d,'2026-04');self.assertEqual(len(rows),1440)
            self.assertEqual(rows[0]['arms']['candidate']['status'],'interrupted')
            self.assertEqual(rows[1]['arms']['candidate']['status'],'not_started')
            self.assertFalse(valid(dict(status='ok',q05=float('nan'))))
    def test_bootstrap_paired_wrap(self):
        class Fixed:
            def integers(self,lo,hi,size):return np.full(size,hi-1)
        matrix=np.stack([np.arange(100),3*np.arange(100)],axis=1)
        with patch('report.np.random.default_rng',return_value=Fixed()):r=bootstrap(matrix,17,repetitions=1)
        for length in (24,48,96):
            indices=((99+np.arange(length))[None,:]%100).repeat(int(np.ceil(100/length)),axis=0).ravel()[:100]
            expected=matrix[indices].mean(axis=0)
            self.assertTrue(np.allclose(np.array(r[str(length)])[:,0],expected))
    def test_inherited_tail_equivalence(self):
        root=Path(__file__).resolve().parents[2]
        backend=module(root/'STUDIES/resident_predictive_harness_v1/numerical_backend.py','fixture_backend')
        self.assertTrue(equivalence(literal(12),backend,time.perf_counter()+30))
if __name__=='__main__':unittest.main()
