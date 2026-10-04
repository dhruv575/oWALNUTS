"""Authored during timing hold: run only after explicit quiet release."""
import copy,unittest
from unittest.mock import patch
import production_calibration_report as p

class Evidence(unittest.TestCase):
 def fixture(self,n=10):
  m=dict(model='flow',arm='candidate',procedure_sha256='procedure',status='FROZEN',protocol_sha256='protocol',alpha=.05,nominal=.9,tolerance=.08,family_size=3,min_replicates=5,minimum_usable_probability=.7,selectors=[dict(name='beta',kind='functional',key='beta_bar')],cells=[dict(id=str(i),model='flow',arm='candidate',procedure_sha256='procedure',dataset_seed=1000+i,source_sha256={'worker':'source'},fixture_sha256='fixture'+str(i),truth={'beta':0.}) for i in range(n)])
  records=[dict(c,protocol_sha256='protocol',original_report_sha256='report'+c['id'],usable=True,intervals={'beta':[-1,1]},rank_sufficient=False) for c in m['cells']]
  return m,records
 def test_missing_and_extra_and_duplicates(self):
  m,r=self.fixture();r.pop();r.append(dict(r[0]));r.append(dict(r[1],id='extra'))
  out=p.summarize(m,r);self.assertEqual(out['intended'],10);self.assertEqual(out['usable'],8);self.assertEqual(out['missing'],['9']);self.assertEqual(out['duplicate_ids'],['0']);self.assertEqual(out['extra_ids'],['extra']);self.assertFalse(out['record_integrity_pass'])
 def test_truth_source_rejected(self):
  m,r=self.fixture();r[0]['truth']={'beta':2};r[1]['source_sha256']={'worker':'wrong'}
  out=p.summarize(m,r);self.assertEqual(out['usable'],8);self.assertFalse(out['record_integrity_pass'])
 def test_rank_never_filters_coverage(self):
  m,r=self.fixture();a=p.summarize(m,r)
  for row in r:row['rank_sufficient']=True
  self.assertEqual(a,p.summarize(m,r));self.assertEqual(a['selectors']['beta']['usable_and_covering'],10)
 def test_failed_interval_distinct_denominators(self):
  m,r=self.fixture();r[0]['usable']=False;out=p.summarize(m,r);v=out['selectors']['beta'];self.assertEqual(v['conditional_coverage'],1.);self.assertEqual(v['unconditional_usable_and_covering_rate'],.9)
 def test_multiplicity_widens_intervals(self):
  m,r=self.fixture(100);a=p.summarize(m,r);m['family_size']=12;b=p.summarize(m,r)
  self.assertLess(b['selectors']['beta']['unconditional_simultaneous_ci'][0],a['selectors']['beta']['unconditional_simultaneous_ci'][0]);self.assertLess(b['reliability_lower'],a['reliability_lower'])
  m['family_size']=2
  with self.assertRaises(ValueError):p.summarize(m,r)
 def test_configurable_count_and_allowed_failure(self):
  m,r=self.fixture(100);r[0]['usable']=False;m.update(nominal=.8,tolerance=.19,minimum_usable_probability=.5,min_replicates=10)
  # Isolate policy from exact interval calculations: one failed row is permitted
  # if the prospectively configured lower bound and equivalence actually pass.
  with patch.object(p,'exact_interval',return_value=[.7,.95]),patch.object(p,'reliability_lower',return_value=.8):
   out=p.summarize(m,r);self.assertTrue(out['coverage_component_meets_prespecified_rule']);self.assertFalse(out['qualified'])
 def test_zero_usable(self):
  m,r=self.fixture();out=p.summarize(m,[]);self.assertEqual(out['usable'],0);self.assertIsNone(out['selectors']['beta']['conditional_coverage']);self.assertIsNone(out['selectors']['beta']['conditional_simultaneous_ci'])
 def test_duplicate_expected_selector_and_cell(self):
  m,r=self.fixture();m['cells'].append(m['cells'][0])
  with self.assertRaises(ValueError):p.summarize(m,r)
  m,r=self.fixture();m['selectors'].append(dict(m['selectors'][0],name='alias'));m['family_size']=5
  with self.assertRaises(ValueError):p.summarize(m,r)
 def test_repeated_dataset_rejected(self):
  for key in ['fixture_sha256','dataset_seed']:
   m,r=self.fixture();m['cells'][1][key]=m['cells'][0][key]
   with self.assertRaises(ValueError):p.summarize(m,r)
 def test_mixed_model_arm_procedure_rejected(self):
  for key in ['model','arm','procedure_sha256']:
   m,r=self.fixture();m['cells'][1][key]='other'
   with self.assertRaises(ValueError):p.summarize(m,r)
 def test_record_procedure_bound(self):
  m,r=self.fixture();r[0]['procedure_sha256']='other';out=p.summarize(m,r);self.assertEqual(out['usable'],9);self.assertFalse(out['record_integrity_pass'])
 def test_malformed_interval_mapping_is_failure(self):
  for bad in [None,[],17]:
   m,r=self.fixture();r[0]['intervals']=bad;out=p.summarize(m,r);self.assertEqual(out['usable'],9);self.assertIn('invalid interval mapping',out['cells']['0']['reasons'])
if __name__=='__main__':unittest.main()
