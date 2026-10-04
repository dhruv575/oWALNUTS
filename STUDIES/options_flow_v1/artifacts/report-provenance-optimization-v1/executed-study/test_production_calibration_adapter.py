"""Static-authored adapter tests. Execute only after timing hold is released."""
import copy,json,tempfile,unittest
from pathlib import Path
import production_calibration_adapter as a

class Adapter(unittest.TestCase):
 def mixed(self,root):
  m,c,old=self.build(root);p=m['procedure'];p.update(implementation='associative',coordinates='mixed_slopes',worker_arm='numpyro-mixed-slopes-continuation',target_accept=.9)
  ph=a.object_digest(p);m['procedure_sha256']=c['procedure_sha256']=ph
  marker=a.load(c['started_path']);marker['procedure_sha256']=ph;self.write(Path(c['started_path']),marker)
  report=a.load(old);report.update(arm=p['worker_arm'],coordinates='mixed_slopes',implementation='associative')
  report['settings'].update(implementation='associative',batch=1000,tiers=[1000],target_accept=.9)
  import numpy as np
  from flow_mixed_coordinates import to_mixed
  fixture=a.load(c['fixture_path']);fixture['data'].update(rho=.95,nu=5.);self.write(Path(c['fixture_path']),fixture)
  c['fixture_sha256']=a.digest(c['fixture_path']);marker['fixture_sha256']=c['fixture_sha256'];self.write(Path(c['started_path']),marker)
  report['bindings'][c['fixture_path']]=c['fixture_sha256']
  report['sampling_initial_positions']=to_mixed(np.asarray(fixture['data']['initial_positions']),fixture['data']).tolist()
  report['checkpoints'][0].update(start_iterations=[1000]*4,end_iterations=[2000]*4)
  rp=self.write(old.parent/'report.json',report)
  fit=a.load(old.parent/'draws-1000-report.json');fit['checkpoints']=report['checkpoints'];self.write(old.parent/'draws-1000-report.json',fit)
  raw=a.load(old.parent/'numpyro-continuation-raw.json');raw['sampling_initial_positions']=report['sampling_initial_positions'];self.write(old.parent/'draws-1000-raw.json',raw)
  status=a.load(c['status_path']);status['report_sha256']=a.digest(rp);self.write(Path(c['status_path']),status)
  return m,c,rp
 def write(self,path,value):
  path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return path
 def build(self,root,public=False):
  root=Path(root);worker=root/'worker.py';worker.write_text('mock worker');python=root/'python.exe';python.write_text('mock interpreter')
  fixture=dict(prior_predictive=True,seed=7,data=dict(y=[[0.],[1.]],x=[[0.],[1.]],initial_positions=[[0,-1,-1,-1.5,0,0,-1,-1+j*.01] for j in range(4)]),truth=[0,-1,-1,-1.5,0,0,-1,-1],holdout=dict(y=[[.2]],x=[[0.]]))
  fp=self.write(root/'fixture.json',fixture);contract=a.fixture_contract(fixture,'flow');output=root/'out';output.mkdir()
  sources={str(worker):a.digest(worker)} if public else {'worker.py':a.digest(worker)}
  procedure=dict(worker_kind='public' if public else 'reference',worker_arm='mock',coordinates='noncentered',warmup=1000,chains=4,tiers=[1000],relative_mcse=.02,timeout_seconds=600,cpus=[0],bound_files={str(worker):a.digest(worker),str(python):a.digest(python)},runtime_bindings={str(python):a.digest(python)},study_directory=str(root),batch_size=1000)
  ph=a.object_digest(procedure)
  cell=dict(id='one',model='flow',arm='candidate',procedure_sha256=ph,dataset_seed=7,chain_seed=100,source_sha256=sources,fixture_sha256=a.digest(fp),truth={'beta':0.},fixture_path=str(fp),output_directory=str(output),status_path=str(root/'status.json'),hardware_path=str(root/'hardware.json'),started_path=str(root/'started.json'),worker_command=[str(python),str(worker)])
  manifest=dict(status='FROZEN',model='flow',arm='candidate',procedure_sha256=ph,protocol_sha256='protocol',alpha=.05,nominal=.9,tolerance=.08,family_size=3,min_replicates=1,minimum_usable_probability=.5,selectors=[dict(name='beta',kind='functional',key='beta_bar')],cells=[cell],procedure=procedure)
  diagnostic=dict(rhat=1.,bulk_ess=500.,tail_ess=500.)
  ev=dict(chain_count=4,functionals={n:dict(diagnostic,interval_90=[-10,10],endpoint_mcse=[.01,.01],truth=contract['truth'][n]) for n in contract['names']},canonical_parameter_diagnostics={f'q_{i}':dict(diagnostic) for i in range(8)},forecast=dict(rows=[dict(horizon=1,group=0,observed=.2,lower=-10,upper=10,endpoint_mcse=[.01,.01])]))
  fit=dict(status='completed',draws=1000,settings=dict(draws=1000),evaluation=ev,retained_divergences=0)
  report=dict(fit,seed=100,arm='mock',coordinates='noncentered',source_sha256=sources,fixture_sha256=cell['fixture_sha256'],precision_pass=True,end_to_end_seconds=8.,settings=dict(chains=4,warmup=1000),attempts=[dict(draws=1000,screen={'pass':True,'parameter_functionals':contract['names'],'forecast_rows':1,'threshold':.02},added_target_calls=5,cumulative_target_calls=10,sampling_seconds=1.)],warmup_seconds=1.,checkpoints=[dict(draws_per_chain=1000,adaptation_sha256='fixed',seconds=1.)])
  report.update(bindings={str(worker):a.digest(worker),str(python):a.digest(python),str(fp):a.digest(fp)},initial_positions=contract['starts'],predictive_seed=130100,parity={'passed':True},adapted_metadata=['fixed'],total_target_calls=10,warmup_target_calls=5,total_sampling_seconds=2.,adapt_seconds=1.)
  rp=self.write(output/('python-pymc-flow-report.json' if public else 'numpyro-continuation-report.json'),report)
  self.write(output/('draws-1000/fit-report.json' if public else 'draws-1000-report.json'),fit)
  self.write(output/('draws-1000/python-pymc-flow-raw.json' if public else 'numpyro-continuation-raw.json'),dict(canonical_draws=[],adapted_metadata=['fixed'],initial_positions=contract['starts']))
  self.write(output/'invocation-timing.json',dict(seconds_including_output=9.))
  hp=self.write(root/'hardware.json',dict(elapsed_seconds=10.,returncode=0,status='completed',realized_cpus=[0],job_active_processes_after_cleanup=0,containment=dict(assigned_before_worker_execution=True),command=cell['worker_command']))
  self.write(root/'status.json',dict(elapsed_seconds=11.,returncode=0,hardware_sha256=a.digest(hp),report_sha256=a.digest(rp)))
  self.write(root/'started.json',dict(protocol_sha256='protocol',procedure_sha256=ph,fixture_sha256=cell['fixture_sha256'],dataset_seed=7))
  return manifest,cell,rp
 def test_public_and_reference_normalize(self):
  for public in [False,True]:
   with tempfile.TemporaryDirectory() as d:
    m,c,_=self.build(d,public);r=a.normalize(m)[0];self.assertTrue(r['usable'],r['normalization']['errors']);self.assertEqual(r['truth'],{'beta':0.});self.assertEqual(r['cost']['controller_seconds'],11.)
 def test_bad_worker_truth_cannot_replace_verified_truth(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.build(d);r=a.load(rp);r['evaluation']['functionals']['beta_bar']['truth']=5;self.write(rp,r);sp=Path(c['status_path']);status=a.load(sp);status['report_sha256']=a.digest(rp);self.write(sp,status)
   result=a.normalize(m)[0];self.assertFalse(result['usable']);self.assertEqual(result['truth'],{'beta':0.})
 def test_wrong_fixture_and_source_fail_with_cost(self):
  for key in ['fixture_path','source']:
   with tempfile.TemporaryDirectory() as d:
    m,c,_=self.build(d)
    Path(c['fixture_path'] if key=='fixture_path' else Path(d)/'worker.py').write_text('mutated')
    r=a.normalize(m)[0];self.assertFalse(r['usable']);self.assertEqual(r['cost']['controller_seconds'],11.)
 def test_no_retroactive_envelope(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,_=self.build(d);Path(c['started_path']).unlink();self.assertFalse(a.normalize(m)[0]['usable'])
 def test_full_scope_not_just_primary(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,_=self.build(d);fp=Path(c['output_directory'])/'draws-1000-report.json';fit=a.load(fp);fit['evaluation']['functionals']['sigma_h']['rhat']=1.2;self.write(fp,fit);self.assertFalse(a.normalize(m)[0]['usable'])
 def test_starts_and_tier_count(self):
  for raw in [True,False]:
   with tempfile.TemporaryDirectory() as d:
    m,c,_=self.build(d);out=Path(c['output_directory'])
    if raw:self.write(out/'numpyro-continuation-raw.json',{'initial_positions':[]})
    else:
     fp=out/'draws-1000-report.json';r=a.load(fp);r['settings']['draws']=2000;self.write(fp,r)
    self.assertFalse(a.normalize(m)[0]['usable'])
 def test_timeout_retains_denominator_and_cost(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,_=self.build(d);hp=Path(c['hardware_path']);h=a.load(hp);h.update(status='worker-timeout',returncode=124,elapsed_seconds=600.1);self.write(hp,h);sp=Path(c['status_path']);s=a.load(sp);s.update(returncode=124,elapsed_seconds=601.,hardware_sha256=a.digest(hp));self.write(sp,s);r=a.normalize(m);self.assertEqual(len(r),1);self.assertFalse(r[0]['usable']);self.assertEqual(r[0]['cost']['wrapper_seconds'],600.1)
 def test_local_truth_and_empirical_bayes_exclusion(self):
  f=dict(prior_predictive=True,truth=[1.,2.,-2.,-3.],data=dict(y=[1.,2.],anchor_mode='exogenous',initial_positions=[[1+j*.01,2,-2,-3] for j in range(4)]),holdout=dict(y=[3.]))
  self.assertEqual(a.fixture_contract(f,'local_level')['truth']['h_mean'],1.5);f['data']['anchor_mode']='empirical_bayes_first_observation'
  with self.assertRaises(ValueError):a.fixture_contract(f,'local_level')
 def test_missing_report_failure_binding_is_integrity_valid(self):
  from production_calibration_report import summarize
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.build(d);rp.unlink();r=a.normalize(m);self.assertFalse(r[0]['usable']);self.assertIsNone(r[0]['original_report_sha256']);self.assertTrue(summarize(m,r)['record_integrity_pass'])
 def test_timeout_without_report_valid_failure(self):
  from production_calibration_report import summarize
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.build(d);rp.unlink();hp=Path(c['hardware_path']);h=a.load(hp);h.update(status='worker-timeout',returncode=124,elapsed_seconds=600.1);self.write(hp,h);sp=Path(c['status_path']);s=a.load(sp);s.update(returncode=124,elapsed_seconds=601.,hardware_sha256=a.digest(hp));self.write(sp,s)
   records=a.normalize(m);self.assertTrue(summarize(m,records)['record_integrity_pass']);self.assertEqual(summarize(m,records)['intended'],1)
 def test_warmup_callback_base_independent(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.build(d,True);r=a.load(rp);r['warmup_target_calls']=6;self.write(rp,r);sp=Path(c['status_path']);s=a.load(sp);s['report_sha256']=a.digest(rp);self.write(sp,s);self.assertFalse(a.normalize(m)[0]['usable'])
 def test_real_reference_exception_schema(self):
  from production_calibration_report import summarize
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.build(d);pr=m['procedure']
   failed_plan=dict(model='flow',coordinates='noncentered',arm='mock',seed=c['chain_seed'],warmup=1000,chains=4,batch_size=1000,tiers=[1000],source_sha256=c['source_sha256'],fixture_sha256=c['fixture_sha256'])
   self.write(rp,dict(status='failed',phase='exploratory',qualified=False,plan=failed_plan,error='runtime failure',traceback='mock',attempts=[],end_to_end_seconds=3.))
   sp=Path(c['status_path']);s=a.load(sp);s['report_sha256']=a.digest(rp);self.write(sp,s)
   r=a.normalize(m);self.assertFalse(r[0]['usable']);self.assertTrue(r[0]['provenance_valid'],r[0]['normalization']['errors']);self.assertTrue(summarize(m,r)['record_integrity_pass'])
 def test_associative_reference_current_schema(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.mixed(d);r=a.normalize(m)[0]
   self.assertTrue(r['usable'],r['normalization']['errors'])
   self.assertIn(str(rp.parent/'draws-1000-raw.json'),r['normalization']['artifact_sha256'])
 def test_associative_reference_rejects_policy_drift(self):
  for field,value in [('implementation','sequential'),('batch',500),('tiers',[2000])]:
   with self.subTest(field=field),tempfile.TemporaryDirectory() as d:
    m,c,rp=self.mixed(d);r=a.load(rp);r['settings'][field]=value;self.write(rp,r)
    status=a.load(c['status_path']);status['report_sha256']=a.digest(rp);self.write(Path(c['status_path']),status)
    self.assertFalse(a.normalize(m)[0]['usable'])
 def test_associative_reference_exception_retained(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.mixed(d);r=a.load(rp);r.update(status='failed',error='integration failure',attempts=[]);self.write(rp,r)
   status=a.load(c['status_path']);status['report_sha256']=a.digest(rp);self.write(Path(c['status_path']),status)
   r=a.normalize(m)[0];self.assertFalse(r['usable']);self.assertTrue(r['provenance_valid'],r['normalization']['errors'])
 def test_associative_reference_raw_start_drift(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.mixed(d);self.write(rp.parent/'draws-1000-raw.json',dict(initial_positions=[]))
   self.assertFalse(a.normalize(m)[0]['usable'])
 def test_associative_reference_iteration_gap(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.mixed(d);fp=rp.parent/'draws-1000-report.json';fit=a.load(fp);fit['checkpoints'][0]['end_iterations'][0]+=1;self.write(fp,fit)
   self.assertFalse(a.normalize(m)[0]['usable'])
 def test_associative_reference_sampling_start_drift(self):
  with tempfile.TemporaryDirectory() as d:
   m,c,rp=self.mixed(d);raw=rp.parent/'draws-1000-raw.json';r=a.load(raw);r['sampling_initial_positions'][0][0]+=.1;self.write(raw,r)
   self.assertFalse(a.normalize(m)[0]['usable'])
if __name__=='__main__':unittest.main()
