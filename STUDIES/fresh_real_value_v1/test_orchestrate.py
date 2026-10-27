import json,tempfile,unittest
from pathlib import Path
from orchestrate import campaign

class CampaignFixtures(unittest.TestCase):
    def spec(self):return json.loads(Path(__file__).with_name('COMPUTE-DRAFT.json').read_bytes())
    def test_failed_candidate_does_not_remove_baseline_or_reference_jobs(self):
        called=[]
        def fake(phase,index,root,cap):
            called.append((phase,index));return dict(status='exited',exit_code=1 if phase=='candidate' else 0,group_drained=True)
        with tempfile.TemporaryDirectory() as folder:
            result=campaign(self.spec(),Path(folder)/'out',fake,clock=lambda:0.)
            self.assertEqual(len(called),11);self.assertIn(('baselines',0),called);self.assertIn(('reference',7),called)
            self.assertTrue(result['accounting_complete']);self.assertFalse(result['execution_complete'])
            self.assertFalse(result['all_planned_forecasts_available'])
    def test_all_budget_skipped_is_accounted_but_not_executed(self):
        spec=self.spec();spec['bounds']['whole_seconds']=0
        def forbidden(*args):raise AssertionError('No budget means no launch')
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'out';result=campaign(spec,out,forbidden,clock=lambda:0.)
            self.assertEqual(len(result['jobs']),11);self.assertTrue(all(j['status']=='not_started' for j in result['jobs']))
            self.assertTrue(result['accounting_complete']);self.assertFalse(result['execution_complete'])
            self.assertEqual(result['valid_scores'],dict(candidate=0,rolling_t5=0,ewma_t5=0))
            validation=json.loads((out/'evidence-validation.json').read_bytes());self.assertTrue(validation['accounting_complete']);self.assertFalse(validation['execution_complete'])

if __name__=='__main__':unittest.main()
