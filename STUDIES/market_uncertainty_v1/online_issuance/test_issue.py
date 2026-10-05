import json,hashlib,tempfile,unittest,copy
from pathlib import Path
from issue import issue,asof_data,schedule,WINDOW,HORIZON

def row(t,price):return dict(receipt_monotonic_ns=t,receipt_utc_ns=t+10000,connection=1,raw=json.dumps(dict(params=dict(channel='ticker.BTC-PERPETUAL.agg2',data=dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=price,best_ask_price=price+1)))))
def rows():return [row(100,100),row(100+WINDOW,101),row(100+WINDOW+3_000_000_000,999)]
def summary(rs):return dict(end_monotonic_ns=rs[-1]['receipt_monotonic_ns'],coverage_intervals=[dict(start_monotonic_ns=100,end_monotonic_ns=rs[-1]['receipt_monotonic_ns'])],gaps=[])
class Tests(unittest.TestCase):
 def case(self,clock,hook=None):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);cap=root/'capture';cap.mkdir();rs=rows();(cap/'receipts.jsonl').write_text('\n'.join(json.dumps(r) for r in rs)+'\n')
  def snapshot(capture,out):
   out.mkdir();raw=(capture/'receipts.jsonl').read_bytes();(out/'receipts.jsonl').write_bytes(raw);s=summary(rs);s['files_sha256']={'receipts.jsonl':hashlib.sha256(raw).hexdigest()};(out/'prefix-summary.json').write_text(json.dumps(s))
   if hook:hook(s)
   return s
  return issue(cap,root/'issued',clock=clock,utc=lambda:123456,snapshot_fn=snapshot),root
 def test_issue_insufficient_history(self):
  r,root=self.case(lambda:100+WINDOW+3_000_000_000);self.assertEqual(r['status'],'issued_no_forecast');self.assertEqual(len(r['forecasts']),2);self.assertTrue(all(f['status']=='no_forecast' for f in r['forecasts']));self.assertEqual(r['cutoff_lag_seconds'],3)
  data=json.loads((root/'issued/asof-features.json').read_text());self.assertFalse(data['rows'][-1]['label']['observed'])
 def test_future_receipt_perturbation(self):
  a=rows();b=copy.deepcopy(a);b[-1]=row(b[-1]['receipt_monotonic_ns'],1234567)
  self.assertEqual(asof_data(a,summary(a),100+WINDOW),asof_data(b,summary(b),100+WINDOW))
 def test_late_and_matured_reject(self):
  r,_=self.case(lambda:100+WINDOW+11_000_000_000);self.assertEqual(r['reason'],'late_issuance')
  r,_=self.case(lambda:100+WINDOW+HORIZON);self.assertEqual(r['reason'],'target_already_matured')
 def test_computation_overrun(self):
  times=iter([100+WINDOW+3_000_000_000,100+WINDOW+11_000_000_000]);r,_=self.case(lambda:next(times));self.assertEqual(r['status'],'not_issued');self.assertNotIn('forecasts',r)
 def test_not_due(self):
  r,_=self.case(lambda:100+WINDOW);self.assertEqual(r['reason'],'not_due_after_snapshot_delay')
 def test_clipped_snapshot(self):
  r,_=self.case(lambda:100+WINDOW+3_000_000_000,lambda s:s.update(receipt_prefix={'cap_clipped':True}));self.assertEqual(r['status'],'not_issued');self.assertNotIn('forecasts',r)
 def test_source_drift_withholds(self):
  from unittest.mock import patch
  import issue as mod
  with tempfile.TemporaryDirectory() as tmp:
   source=Path(tmp)/'baseline.py';source.write_text('original')
   with patch.object(mod.baseline,'__file__',str(source)):
    r,_=self.case(lambda:100+WINDOW+3_000_000_000,lambda s:source.write_text('changed'))
   self.assertEqual(r['status'],'not_issued');self.assertNotIn('forecasts',r)
 def test_schedule(self):
  self.assertEqual(schedule(100,'first'),100+WINDOW)
  with self.assertRaises(ValueError):schedule(100,str(100+WINDOW+1))
if __name__=='__main__':unittest.main()
