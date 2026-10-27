import tempfile,unittest
from pathlib import Path
import numpy as np
from data_contract import inputs,returns_from_bars,HALF,FIRST_ORIGIN_MS
from run_baselines import run,ewma_step
from baselines_snapshot import ewma_t5

class CausalFixtures(unittest.TestCase):
    def test_exact_endpoints_and_future_isolation(self):
        y=np.arange(1739,dtype=float)/100000
        first=inputs(y,1);last=inputs(y,1488)
        self.assertEqual(first['origin_ms'],FIRST_ORIGIN_MS)
        self.assertEqual(last['label_available_ms'],1788220800000)
        np.testing.assert_array_equal(first['window'],y[1:251])
        self.assertEqual(last['label_index'],1738)
        altered=y.copy();altered[251:]=999
        np.testing.assert_array_equal(inputs(altered,1)['window'],first['window'])
        self.assertEqual(inputs(altered,1)['observation'],first['observation'])

    def test_bar_context_cut(self):
        bars=[dict(open_ms=1785024000000+i*HALF,close_available_ms=1785024000000+(i+1)*HALF,close=100+i*.01) for i in range(1776)]
        y=returns_from_bars(bars)
        self.assertEqual(len(y),1739)
        self.assertAlmostEqual(y[0],np.log(bars[37]['close'])-np.log(bars[36]['close']))
        self.assertAlmostEqual(y[-1],np.log(bars[-1]['close'])-np.log(bars[-2]['close']))

    def test_linear_ewma_exact_e60_recursion(self):
        y=np.sin(np.arange(1739))*.002;initial=dict(status='ok',location=.0002,scale=.003)
        variance=5/3*initial['scale']**2
        for tick in range(1,149):
            variance,fit=ewma_step(variance,y[249+tick],initial)
            expected=ewma_t5(y[:250+tick],initial)
            self.assertEqual(fit['scale'],expected['scale']);self.assertEqual(fit['location'],expected['location'])

    def test_baseline_only_sees_initial_and_causal_windows(self):
        y=np.arange(1739,dtype=float)/100000;seen=[]
        def fake_fit(history,deadline):
            seen.append(history.copy());return dict(status='ok',location=0.,scale=.01,df=5)
        with tempfile.TemporaryDirectory() as folder:run(y,Path(folder)/'out',fit_function=fake_fit,planned_ticks=3)
        np.testing.assert_array_equal(seen[0],y[:250])
        for tick in range(1,4):np.testing.assert_array_equal(seen[tick],y[tick:250+tick])

    def test_initial_ewma_error_does_not_remove_rolling(self):
        import json
        calls=0
        def fake_fit(history,deadline):
            nonlocal calls
            calls+=1
            if calls==1:raise ArithmeticError('literal fixture')
            return dict(status='ok',location=0.,scale=.01,df=5)
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'out';run(np.zeros(1739),out,fit_function=fake_fit,planned_ticks=2)
            rolling=json.loads((out/'rolling_t5/tick-0001.json').read_bytes())
            ewma=json.loads((out/'ewma_t5/tick-0001.json').read_bytes())
            self.assertEqual(rolling['status'],'ok');self.assertEqual(ewma['status'],'unavailable')
            self.assertIn('fit_seconds',rolling);self.assertIn('score_seconds',rolling)

if __name__=='__main__':unittest.main()
