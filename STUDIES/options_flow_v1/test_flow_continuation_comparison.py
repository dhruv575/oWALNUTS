import copy,tempfile,unittest
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import flow_continuation_comparison as f
class Contracts(unittest.TestCase):
 def case(self,arm):
  c=dict(arm=arm,seed=100710001,predictive_seed=100840001,dimension=140,forecast_rows=4,fixture=str(Path('fixture.json').resolve()),fixture_sha256='fixture',starts=[[1]*140]*4,id='cell')
  p=dict(python='python',study_bindings={str(Path('module.py').resolve()):'source'},bound_files={str(Path('python.exe').resolve()):'python',str(Path('package/owalnuts/__init__.py').resolve()):'adapter',str(Path('package/owalnuts/_owalnuts.pyd').resolve()):'binary'},pythonpath=str(Path('package').resolve()))
  d=dict(rhat=1.,bulk_ess=500,tail_ess=500)
  e=dict(chain_count=4,functionals={n:dict(d,interval_90=[0,1],endpoint_mcse=[.01,.01]) for n in f.NAMES},canonical_parameter_diagnostics={str(i):dict(d) for i in range(140)},forecast=dict(rows=[dict(lower=0,upper=1,endpoint_mcse=[.01,.01]) for _ in range(4)]))
  r=dict(status='completed',model='flow',seed=c['seed'],predictive_seed=c['predictive_seed'],settings=dict(warmup=1000,chains=4,block_size=32,target_accept=.9),coordinates='noncentered',evaluation=e,retained_divergences=0,precision_pass=True,parity=dict(passed=True),precision_plan=dict(names=f.NAMES),attempts=[dict(draws=1000,screen={'pass':True,'parameter_functionals':f.NAMES,'forecast_rows':4,'threshold':.02})])
  r.update(source_sha256={'module.py':'source'},fixture_sha256='fixture',extension_sha256='binary',adapter_source_sha256='adapter',extension_path=str(Path('package/owalnuts/_owalnuts.pyd').resolve()),initial_positions=c['starts'],bindings=dict(p['study_bindings'],**p['bound_files'],**{c['fixture']:'fixture'}))
  return p,c,r
 def test_schemas_commands(self):
  for arm in ['restart','owalnuts_continuation','numpyro_continuation']:
   p,c,r=self.case(arm);self.assertTrue(f.validate_worker(p,c,r));cmd=f.command(p,c,Path('out/cell'));self.assertIn('1800',cmd)
   if arm=='restart':self.assertEqual(cmd[cmd.index('--precision-names')+1:],f.NAMES)
   elif arm=='numpyro_continuation':self.assertIn('0.9',cmd)
 def test_missing_scope(self):
  for key in ['forecast','functionals','canonical_parameter_diagnostics']:
   p,c,r=self.case('restart');v=r['evaluation'][key]
   if key=='forecast':v['rows'].pop()
   else:v.pop(next(iter(v)))
   with self.assertRaises(ValueError):f.validate_worker(p,c,r)
 def test_unhealthy_and_failed_cap(self):
  p,c,r=self.case('numpyro_continuation');r['retained_divergences']=3
  with self.assertRaises(ValueError):f.validate_worker(p,c,r)
  r['precision_pass']=False;s=dict(r['attempts'][0]['screen']);s['pass']=False;r['attempts']=[dict(draws=n,screen=s) for n in f.TIERS]
  self.assertFalse(f.validate_worker(p,c,r));r['attempts'].pop()
  with self.assertRaises(ValueError):f.validate_worker(p,c,r)
 def test_bindings_starts(self):
  p,c,r=self.case('owalnuts_continuation');r['initial_positions']=[]
  with self.assertRaises(ValueError):f.validate_worker(p,c,r)
  p,c,r=self.case('restart');r['extension_path']='elsewhere/_owalnuts.pyd'
  with self.assertRaises(ValueError):f.validate_worker(p,c,r)
 def test_fixture(self):
  data=dict(y=[[0]*4]*128,x=[[0]*4]*128,initial_positions=[[j]*140 for j in range(4)])
  v=dict(data=data,holdout=dict(y=[[0]*4],x=[[0]*4]),truth=1);a=f.fixture_contract(v,128);v['truth']=999;self.assertEqual(a,f.fixture_contract(v,128));data['initial_positions'][0]=[0]*139
  with self.assertRaises(ValueError):f.fixture_contract(v,128)
 def test_seed_utf16(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'status.json').write_text('{"seed":100710001}',encoding='utf-16');(p/'raw.json').write_text('100710002');a=f.seed_history(p,[100710001,100710002]);self.assertEqual(len(a['hits']),1);self.assertEqual(len(a['excluded_large_or_raw_files']),1)
 def test_all_six_worker_failures_terminalized(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fixture=root/'fixture.json';fixture.write_text('{}')
   cells=[dict(id=str(i),arm='restart',fixture=str(fixture),fixture_sha256=f.sha(fixture)) for i in range(6)]
   plan=dict(frozen=True,cells=cells,pythonpath='package');path=root/'plan.json';f.save(path,plan)
   def run(args,**kwargs):
    cell=cells[int(args[0])];f.save(root/(cell['id']+'-hardware.json'),dict(status='worker-failed',job_active_processes_after_cleanup=0,realized_cpus=[0]))
    return SimpleNamespace(returncode=7)
   with patch.object(f,'verify'),patch.object(f,'command',side_effect=lambda p,c,o:[c['id']]),patch.object(f.subprocess,'run',side_effect=run):f.execute(path)
   for cell in cells:
    status=f.load(root/(cell['id']+'-status.json'));self.assertFalse(status['success']);self.assertEqual(status['returncode'],7);self.assertGreater(status['elapsed_seconds'],0)
 def test_provenance_abort_preserves_exit_and_remaining(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);fixture=root/'fixture.json';fixture.write_text('{}');cells=[dict(id=str(i),arm='restart',fixture=str(fixture),fixture_sha256=f.sha(fixture)) for i in range(6)]
   path=root/'plan.json';f.save(path,dict(frozen=True,cells=cells,pythonpath='package'))
   with patch.object(f,'verify',side_effect=[None,None,ValueError('drift')]),patch.object(f,'command',return_value=[]),patch.object(f.subprocess,'run',return_value=SimpleNamespace(returncode=7)):f.execute(path)
   self.assertEqual(f.load(root/'0-exit.json')['returncode'],7)
   for i in range(1,6):self.assertEqual(f.load(root/f'{i}-status.json')['status'],'unattempted_provenance_abort')
if __name__=='__main__':unittest.main()
