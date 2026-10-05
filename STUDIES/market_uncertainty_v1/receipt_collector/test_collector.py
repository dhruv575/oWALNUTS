import asyncio,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from collector import collect
CHANNELS=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2']
class Fake:
 def __init__(self,items):self.items=iter(items)
 async def __aenter__(self):return self
 async def __aexit__(self,*a):pass
 async def send(self,v):pass
 async def recv(self):
  item=next(self.items,None)
  if isinstance(item,Exception):raise item
  if item is None:await asyncio.sleep(2)
  return json.dumps(item)
def ack():return {'id':1,'result':CHANNELS}
def tick():return {'params':{'channel':CHANNELS[1],'data':{'best_bid_price':1,'best_ask_price':2}}}
class Tests(unittest.TestCase):
 def run_case(self,sessions,**kw):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp)/'new';it=iter(sessions)
   r=asyncio.run(collect(out,kw.pop('duration',.04),kw.pop('byte_cap',100000),0,discovery=lambda n:{'selected':[]},connector=lambda:next(it),**kw))
   files={p.name:p.read_text() for p in out.iterdir()};return r,files
 def test_normal(self):
  r,f=self.run_case([Fake([ack(),tick()])]);self.assertEqual(r['status'],'duration_complete');self.assertIn('receipt_monotonic_ns',f['receipts.jsonl']);self.assertEqual(r['bytes_written'],sum(len(v.encode()) for k,v in f.items() if k!='summary.json'))
 def test_drop_exhaustion(self):
  r,f=self.run_case([Fake([ack(),tick(),RuntimeError('drop')])],max_reconnects=0);self.assertEqual(r['status'],'failed');self.assertEqual(len(r['gaps']),1)
 def test_reconnect(self):
  r,f=self.run_case([Fake([ack(),RuntimeError('drop')]),Fake([ack(),tick()])],duration=.35);self.assertEqual(r['status'],'duration_complete_with_gaps');self.assertIn('resubscribed_utc_ns',r['gaps'][0])
 def test_network_oserror_reconnect(self):
  r,f=self.run_case([Fake([ack(),tick(),ConnectionResetError("reset")]),Fake([ack(),tick()])],duration=.35)
  self.assertEqual(r["status"],"duration_complete_with_gaps");self.assertLessEqual(r["gaps"][0]["start_monotonic_ns"],r["gaps"][0]["detected_monotonic_ns"]);self.assertEqual(len(r["coverage_intervals"]),2)
 def test_preack_data(self):
  r,f=self.run_case([Fake([tick()])]);self.assertEqual(r["status"],"failed");self.assertEqual(r["coverage_intervals"],[])
 def test_rpc_error(self):
  r,f=self.run_case([Fake([{'error':{'code':1}}])]);self.assertEqual(r['status'],'failed');self.assertIn('error',f['receipts.jsonl'])
 def test_wrong_ack(self):
  r,f=self.run_case([Fake([{'id':1,'result':[]}])]);self.assertEqual(r['status'],'failed')
 def test_byte_cap(self):
  r,f=self.run_case([Fake([ack(),tick()])],byte_cap=150);self.assertEqual(r['status'],'byte_cap_reached');self.assertLessEqual(r['bytes_written'],150)
 def test_disk_rejection(self):
  with tempfile.TemporaryDirectory() as tmp,patch('collector.shutil.disk_usage',return_value=type('D',(),{'free':0})()):
   r=asyncio.run(collect(Path(tmp)/'o',1,1000,1,discovery=lambda n:self.fail('must not discover')));self.assertEqual(r['status'],'failed')
 def test_no_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaises(FileExistsError):asyncio.run(collect(Path(tmp),1,1000,0))
if __name__=='__main__':unittest.main()
