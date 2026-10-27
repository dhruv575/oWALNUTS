import copy,json,tempfile,unittest
from pathlib import Path
from ledger import build_ledger
from report import summarize
from orchestrate import campaign
from evidence import atomic

class GlobalFixtures(unittest.TestCase):
 def test_fixed_missing_denominator_and_interrupted_arm(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'stream-00';p.mkdir();atomic(p/'side.json',dict(rows=[],in_progress=dict(tick=2,arm='oracle')))
   rows=build_ledger(d)
   self.assertEqual(len(rows),1024);self.assertEqual(rows[1]['arms']['oracle']['status'],'interrupted')
   self.assertEqual(rows[1]['arms']['baseline']['status'],'not_started')
   out=summarize(rows,replicates=10,bootstrap_seed=17)
   self.assertIsNone(out['arms']['candidate']['negative_logscore']['full_mean'])
   self.assertFalse(out['all_candidate_origins_valid'])
 def test_stream_cluster_pairing_and_partial_no_full_interval(self):
  with tempfile.TemporaryDirectory() as d:rows=build_ledger(d)
  for r in rows:
   for a in r['arms']:r['arms'][a]=dict(status='ok',cdf=.5,logpdf=float(r['stream'])+(1 if a=='candidate' else 0))
  out=summarize(rows,replicates=25,bootstrap_seed=17)
  pair=out['paired']['candidate_logscore_minus_baseline']
  self.assertEqual(pair['full_mean'],1.);self.assertEqual(pair['cluster_interval95'],[1.,1.])
  rows[0]['arms']['candidate']={'status':'unavailable'}
  out=summarize(rows,replicates=25,bootstrap_seed=17)
  self.assertIsNone(out['paired']['candidate_logscore_minus_baseline']['cluster_interval95'])
  self.assertEqual(out['arms']['candidate']['negative_logscore']['available_origins'],1023)
 def test_global_failure_retains_every_planned_job(self):
  spec=json.loads((Path(__file__).parent/'PROTOCOL-DRAFT.json').read_text());spec['status']='frozen_authorized'
  calls=[]
  def fake(kind,index,root,cap):
   calls.append((kind,index));return dict(status='terminated',reason='rss_limit',group_drained=True)
  with tempfile.TemporaryDirectory() as d:
   result=campaign(spec,Path(d)/'run',fake,clock=lambda:0.)
   self.assertEqual(calls,[('candidate',0)]);self.assertEqual(len(result['jobs']),73)
   self.assertEqual(sum(j['status']=='not_started' for j in result['jobs']),72)
   self.assertEqual(len(json.loads((Path(d)/'run/ledger.json').read_text())),1024)
 def test_draft_cannot_launch(self):
  with tempfile.TemporaryDirectory() as d:
   with self.assertRaises(ValueError):campaign({'status':'draft'},Path(d)/'run',lambda *args:self.fail('launched'))
 def test_nonfinite_evidence_cannot_be_status_ok(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'stream-00';p.mkdir()
   atomic(p/'candidate.json',dict(rows=[dict(tick=1,candidate_status='ok',forecast=dict(cdf=.5,logpdf=float('nan')))]))
   with self.assertRaises(ValueError):build_ledger(d)
 def test_candidate_mcse_nan_and_shape_fail_closed(self):
  import numpy as np
  from worker import candidate_mcse
  logs=np.zeros((4,400));pit=np.full((4,400),.5)
  with self.assertRaises(ValueError):candidate_mcse(logs,pit,lambda a:float('nan'))
  with self.assertRaises(ValueError):candidate_mcse(logs[:,:50],pit,lambda a:0.)
  pit[0,0]=1.1
  with self.assertRaises(ValueError):candidate_mcse(logs,pit,lambda a:0.)
  pit[0,0]=.5
  self.assertEqual(candidate_mcse(logs,pit,lambda a:0.)['status'],'available')
 def test_literal_fixture_has_no_reserved_seed_or_generator(self):
  from readiness import literal_data
  from unittest.mock import patch
  with patch('generator.generate',side_effect=AssertionError('Study generation forbidden')):
   data=literal_data()
  self.assertEqual(data['y'].shape,(283,));self.assertIsNone(data['seeds']['data'])
  self.assertEqual(data['seeds']['initial'],993711000)
 def test_duplicate_origin_rejected(self):
  with tempfile.TemporaryDirectory() as d:rows=build_ledger(d)
  rows[1]=copy.deepcopy(rows[0])
  with self.assertRaises(ValueError):summarize(rows,replicates=2,bootstrap_seed=17)
if __name__=='__main__':unittest.main()
