import json,tempfile,unittest
from pathlib import Path
from scheduler import run
from issue import WINDOW,HORIZON
class Clock:
 def __init__(self,t):self.t=t
 def now(self):return self.t
 def sleep(self,s):self.t+=int(s*1e9)
class Tests(unittest.TestCase):
 def setup_case(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);cap=root/'capture';cap.mkdir();(cap/'receipts.jsonl').write_text(json.dumps({'receipt_monotonic_ns':100})+'\n');return root,cap
 def fake_issue(self,clock,calls):
  def f(capture,out,origin):
   calls.append((int(origin),clock.now()));out.mkdir();r=dict(status='issued_no_forecast',origin_receipt_ns=int(origin));(out/'issuance.json').write_text(json.dumps(r));return r
  return f
 def test_missed_then_future(self):
  root,cap=self.setup_case();clock=Clock(100+WINDOW+11_000_000_000);calls=[]
  r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=2,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=self.fake_issue(clock,calls))
  self.assertEqual(r['expected'],2);self.assertEqual(r['outcomes'][0]['reason'],'missed_origin');self.assertEqual(len(calls),1);self.assertEqual(calls[0][1]-calls[0][0],3_000_000_000)
 def test_budget_retains_denominator(self):
  root,cap=self.setup_case();clock=Clock(100);calls=[]
  r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=3,deadline_seconds=1,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=self.fake_issue(clock,calls))
  self.assertEqual(len(r['outcomes']),3);self.assertEqual(calls,[]);self.assertTrue(all(x['reason']=='scheduler_budget' for x in r['outcomes']))
 def test_no_overwrite_or_capture_write(self):
  root,cap=self.setup_case()
  with self.assertRaises(ValueError):run(cap,cap/'out',capture_end_ns=100+2*HORIZON)
  out=root/'out';out.mkdir()
  with self.assertRaises(FileExistsError):run(cap,out,capture_end_ns=100+2*HORIZON)
 def test_terminal_capture_stops(self):
  root,cap=self.setup_case();(cap/'summary.json').write_text('{}');clock=Clock(100+WINDOW+3_000_000_000);calls=[]
  r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=3,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=self.fake_issue(clock,calls))
  self.assertEqual(calls,[]);self.assertTrue(all(x['reason']=='capture_terminated' for x in r['outcomes']))
 def test_storage_floor(self):
  from unittest.mock import patch
  root,cap=self.setup_case();clock=Clock(100+WINDOW+3_000_000_000);calls=[]
  with patch('scheduler.shutil.disk_usage',return_value=type('D',(),{'free':0})()):
   r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=3,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=self.fake_issue(clock,calls))
  self.assertEqual(calls,[]);self.assertTrue(all(x['reason']=='scheduler_storage_floor' for x in r['outcomes']));self.assertFalse(r['outcomes'][0]['storage_admission']['passed'])
 def test_source_drift_return_latches(self):
  root,cap=self.setup_case();clock=Clock(100+WINDOW+3_000_000_000);calls=[]
  def drift(capture,out,origin):
   calls.append(origin);out.mkdir();r=dict(status='not_issued',reason='source_drift');(out/'issuance.json').write_text(json.dumps(r));return r
  r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=3,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=drift)
  self.assertEqual(len(calls),1);self.assertTrue(all(x['reason']=='source_drift' for x in r['outcomes']))
 def test_worker_exception_retains_remaining(self):
  root,cap=self.setup_case();clock=Clock(100+WINDOW+3_000_000_000)
  def fail(*a):raise RuntimeError('injected')
  r=run(cap,root/'out',capture_end_ns=100+WINDOW+3*HORIZON,max_origins=3,clock=clock.now,utc=lambda:10,sleep=clock.sleep,issue_fn=fail)
  self.assertEqual(len(r['outcomes']),3);self.assertTrue(all(x['reason']=='scheduler_error' for x in r['outcomes']))
if __name__=='__main__':unittest.main()
