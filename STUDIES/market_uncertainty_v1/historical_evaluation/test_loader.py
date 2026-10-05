import importlib.util,json,tempfile,unittest
from pathlib import Path
from urllib.parse import urlparse,parse_qs
from evaluate import verified_load
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'target/market-history-acquisition-v1/collector.py'
class LoaderTests(unittest.TestCase):
 def test_collector_boundary_and_corruption_rejection(self):
  spec=importlib.util.spec_from_file_location('test_history_collector',SOURCE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  protocol=json.loads((SOURCE.parent/'protocol-frozen-v1.json').read_text());protocol.update(start_ms=0,end_ms_exclusive=86400000,minimum_request_interval_seconds=0,minimum_free_bytes=1)
  def fetch(url):
   q=parse_qs(urlparse(url).query)
   if 'get_last_trades' in url:r=dict(trades=[],has_more=False)
   else:r=dict(status='ok',ticks=list(range(0,86400000,1800000)),open=[100.]*48,high=[100.]*48,low=[100.]*48,close=[100.]*48,volume=[0.]*48)
   return 200,json.dumps(dict(result=r)).encode()
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);pp=tmp/'protocol.json';pp.write_text(json.dumps(protocol));out=tmp/'raw';result=module.Collector(protocol,out,fetch=fetch,protocol_path=pp).run();self.assertTrue(result['complete'])
   dataset=verified_load(out,protocol_path=pp,collector_source=SOURCE);self.assertEqual(len(dataset['rows']),48);self.assertTrue(all(r['flow_known'] and r['flow_count']==0 for r in dataset['rows']))
   (out/'response-00000.json').write_text('{}')
   with self.assertRaises(ValueError):verified_load(out,protocol_path=pp,collector_source=SOURCE)
if __name__=='__main__':unittest.main()
