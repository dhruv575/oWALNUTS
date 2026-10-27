import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
import data_contract as dc
from reuse import calendar
from worker import terminal_accounting
from aggregate import summarize as aggregate

E62=Path(__file__).resolve().parent.parent/'fresh_real_value_v1'
class CalendarFixtures(unittest.TestCase):
 def bars(self):
  return [dict(open_ms=1774483200000+i*dc.HALF,close_available_ms=1774483200000+(i+1)*dc.HALF,close=float(np.exp(i*1e-5))) for i in range(4656)]
 def test_all_month_boundaries_and_no_future_fit_inputs(self):
  bars=self.bars()
  for row in dc.MONTHS:
   dc.configure(row['month']);y=dc.panel_returns(bars,row['month']);n=row['origins']
   self.assertEqual(y.shape,(n+251,));first=dc.inputs(y,1);last=dc.inputs(y,n)
   self.assertEqual(first['origin_ms'],row['first_origin_ms']);self.assertEqual(last['label_available_ms'],row['first_origin_ms']+n*dc.HALF)
   np.testing.assert_array_equal(first['window'],y[1:251]);self.assertEqual(first['label'],y[251]);np.testing.assert_array_equal(last['window'],y[n:n+250]);self.assertEqual(last['label'],y[n+250])
   changed=y.copy();changed[251:]+=100
   np.testing.assert_array_equal(dc.inputs(changed,1)['window'],first['window']);self.assertNotEqual(dc.inputs(changed,1)['label'],first['label'])
 def test_only_report_calendar_shape_differs_from_E62(self):
  expected=(E62/'report.py').read_text().replace('reshape(31,48)','reshape(N//48,48)').replace('Fixed unique1488-origin ledger required','Fixed unique full-month ledger required')
  self.assertEqual(Path(__file__).with_name('report.py').read_text(),expected)
 def test_30_and31day_fixed_report_blocks_and_missing_denominators(self):
  for row in dc.MONTHS:
   m=calendar(row['month'],E62);n=row['origins'];rows=[dict(tick=i,arms={a:dict(status='ok',logpdf=float(j+i),pit=.5) for j,a in enumerate(['candidate','rolling_t5','ewma_t5'])}) for i in range(1,n+1)]
   starts=lambda length,count:np.full((count,int(np.ceil(n/length))),n-1,dtype=int)
   result=m['report'].summarize(rows,replicates=2,seed=17,starts_provider=starts)
   self.assertEqual(len(result['paired']['candidate_minus_rolling_t5']['daily_means']),n//48);self.assertEqual(result['paired']['candidate_minus_rolling_t5']['full_mean'],-1)
   rows[-1]['arms']['candidate']={'status':'not_started'};result=m['report'].summarize(rows,replicates=2,seed=17,starts_provider=starts)
   self.assertIsNone(result['paired']['candidate_minus_rolling_t5']['full_mean']);self.assertEqual(result['paired']['candidate_minus_rolling_t5']['available_origins'],n-1)
 def test_each_month_baseline_reset_and_exact_causal_windows(self):
  for row in dc.MONTHS:
   m=calendar(row['month'],E62);y=np.arange(row['origins']+251,dtype=float)*1e-5;seen=[]
   def fit(window,deadline):seen.append(window.copy());return dict(status='ok',location=.0,scale=.01,df=5)
   with tempfile.TemporaryDirectory() as d:m['baseline'].run(y,Path(d)/'baseline',fit_function=fit,planned_ticks=2)
   self.assertEqual(len(seen),3);np.testing.assert_array_equal(seen[0],y[:250]);np.testing.assert_array_equal(seen[1],y[1:251]);np.testing.assert_array_equal(seen[2],y[2:252])
 def test_terminal_all_skipped_preserves_all_month_slots(self):
  jobs=[dict(phase=p,index=i,status='not_started') for p,count in [('candidate',1),('baselines',1),('reference',8),('report',1)] for i in range(count)]
  for row in dc.MONTHS:
   with tempfile.TemporaryDirectory() as d:
    value=terminal_accounting({'e62_root':str(E62)},row['month'],d,jobs)
    self.assertTrue(value['accounting_complete']);self.assertFalse(value['execution_complete']);self.assertEqual(value['planned_origins'],row['origins']);self.assertEqual(value['valid_scores']['candidate'],0)
 def test_descriptive_aggregate_requires_all_three_complete_panels(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)
   for i,row in enumerate(dc.MONTHS):
    folder=root/row['month'];folder.mkdir();value=dict(month=row['month'],planned_origins=row['origins'],paired={name:dict(full_mean=[1.,2.,4.][i]) for name in ['candidate_minus_rolling_t5','candidate_minus_ewma_t5']});(folder/'summary.json').write_text(json.dumps(value))
   result=aggregate(root);self.assertEqual(result['paired']['candidate_minus_rolling_t5']['full_origin_weighted_mean'],(1440+1488*2+1440*4)/4368)
   (root/'2026-06/summary.json').unlink();self.assertIsNone(aggregate(root)['paired']['candidate_minus_rolling_t5']['full_origin_weighted_mean'])

if __name__=='__main__':unittest.main()
