import sys,json,copy,random
from pathlib import Path
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from .bank_analysis import frozen_counts,weight_contract,validate_policy
from reference_bank import resample_fits


def policy():
 return dict(timeout_seconds=7200,cleanup_reserve_seconds=15,memory_bytes=8*1024**3,cpus=[0],bootstrap_replicates=30000,minimum_tail_count=20,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,max_queries=64,max_rounds=32,absolute_width=.01,cdf_tolerance=1e-8,orders=[16,32,64,128],bootstrap_seed=99,initial_grid=[-4.,4.])


def test_exact_counts_normalization_prefix_backend_and_order():
 fits=[dict(id=str(i),backend=b) for i,b in enumerate(['public','reference','reference','public']*2)]
 counts=frozen_counts(fits,99,23);rng=random.Random(99)
 assert counts==[resample_fits(fits,rng) for _ in range(23)]
 ids,w,digest=weight_contract(fits,counts)
 assert ids==[f'{i}@{n}' for i in range(8) for n in [4000,8000]]
 assert w.shape==(96,16);np.testing.assert_allclose(w.sum(axis=1),1)
 for i,c in enumerate(counts):
  high,low,public,reference=w[(i+1)*4:(i+2)*4]
  np.testing.assert_array_equal(high[1::2],low[::2]);assert not high[::2].any() and not low[1::2].any()
  for j,f in enumerate(fits):
   assert high[2*j+1]==c.get(f['id'],0)/8
   assert public[2*j+1]==(c.get(f['id'],0)/4 if f['backend']=='public' else 0)
   assert reference[2*j+1]==(c.get(f['id'],0)/4 if f['backend']=='reference' else 0)
 assert weight_contract(fits,counts)[2]==digest
 assert weight_contract(fits[::-1],counts)[2]!=digest


@pytest.mark.parametrize('key,value',[('bootstrap_replicates',29999),('alpha',.1),('absolute_width',.02),('max_queries',65),('timeout_seconds',7201),('orders',[64,128])])
def test_exact_policy_cannot_be_tuned_after_results(key,value):
 p=policy();validate_policy(p);p[key]=value
 with pytest.raises(ValueError):validate_policy(p)


def test_same_count_rows_cross_endpoint_covariance():
 fits=[dict(id=str(i),backend='public' if i<4 else 'reference') for i in range(8)];counts=frozen_counts(fits,3,100)
 x=np.array([sum(c.get(str(i),0)*i for i in range(8)) for c in counts]);y=2*x+1
 assert x.var()>0 and np.cov(x,y)[0,1]>0


def test_postbank_source_drift_clears_resolved_state(tmp_path,monkeypatch):
 from . import bank_analysis as a,bank_analysis_preparation as preparation
 import reference_bank,reference_bank_vectorized,reference_bank_allocation,hardware_control,predictive_cdf
 from posterior_resource import bank_adapter,predictive_grid
 ids=[f'f{i}' for i in range(64)];fits=[dict(id=k,backend='public' if i<32 else 'reference') for i,k in enumerate(ids)]
 counts=[dict.fromkeys(ids,1)];columns=[f'{k}@{n}' for k in ids for n in [4000,8000]]
 fixture=tmp_path/'fixture.json';fixture.write_text(json.dumps(dict(data=dict(nu=5),holdout=dict(x=[[.7]]))))
 manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps(dict(posterior_sha256='target',fits=[dict(f,fixture=str(fixture),sampler_seed=100+i,initialization_seed=200+i,fixture_sha256='fixture') for i,f in enumerate(fits)])))
 rows=[]
 for f in fits:
  rows.append(dict(f,parameters={str(n):{name:np.ones((1,1)) for name in bank_adapter.PARAMETERS} for n in [4000,8000]},predictive_inputs={str(n):{name:np.ones((1,1)) for name in ['cdf_location','cdf_future_mean','cdf_future_sd']} for n in [4000,8000]}))
 monkeypatch.setattr(bank_adapter,'collect',lambda m:dict(admitted=rows,outcomes=[dict(id=k,status='admitted') for k in ids]))
 monkeypatch.setattr(a,'frozen_counts',lambda *args:counts)
 monkeypatch.setattr(a,'weight_contract',lambda *args:(columns,np.ones((1,128)),'weights'))
 monkeypatch.setattr(preparation,'verify_materialized',lambda *args:None)
 monkeypatch.setattr(reference_bank_allocation,'memory_limit',lambda *args:None)
 monkeypatch.setattr(reference_bank_allocation,'peak_memory',lambda:dict(measurement='mock'))
 monkeypatch.setattr(hardware_control,'get_affinity',lambda:[0])
 monkeypatch.setattr(predictive_cdf,'PredictiveMixture',lambda *args:object())
 monkeypatch.setattr(predictive_grid,'build',lambda *args,**kw:dict(status='numerically_resolved_for_declared_scenarios',frozen_weights_sha256='weights',ordered_ids=columns,declared_weight_brackets_resolved=True,rows={k:dict(grid=[-1,1],cdf=[0,1]) for k in columns}))
 monkeypatch.setattr(reference_bank_vectorized,'batch_cached_parameter',lambda *args:[])
 def analyze(spec,records,parameter_batch):
  for _ in range(40):parameter_batch([],{},1,'x',.05,counts)
  return dict(status='numerically_resolved_under_declared_checks')
 monkeypatch.setattr(reference_bank,'analyze',analyze)
 checks=[]
 def verify(p):
  checks.append(1)
  if len(checks)==2:raise ValueError('postbank source drift')
 monkeypatch.setattr(a,'verify',verify)
 p=dict(policy(),out=str(tmp_path/'out'),study=str(Path(__file__).resolve().parent.parent),admission_manifest=str(manifest),expected_weight_sha256='weights',ordered_ids=ids,bank_source_sha256='source',bindings={})
 path=tmp_path/'plan.json';path.write_text(json.dumps(p));path.with_suffix('.sha256').write_text(a.sha(path))
 result=a.analyze_plan(path)
 assert result['status']=='unresolved' and result['reference_bank_resolved'] is False and result['integrity_pass'] is False
 assert 'postbank source drift' in result['error']
 assert json.loads((tmp_path/'out/bank-result.json').read_text())['status']=='numerically_resolved_under_declared_checks'


@pytest.mark.parametrize('changed',['fit','order','policy','weights','family'])
def test_materialized_manifest_cannot_change_prefit_choices(tmp_path,changed):
 from .bank_analysis_preparation import verify_materialized
 from .bank_analysis import sha
 rows=[dict(id=f'f{i}',backend='public' if i<32 else 'reference',sampler_seed=100+i,initialization_seed=200+i,directory=f'fit{i}',fixture='fixture',fixture_sha256='fixture') for i in range(64)]
 intent=dict(analysis_source_directory=str(tmp_path),analysis_source_inventory={},frozen=True,analysis_policy=policy(),bindings={},expected_fits=rows,ordered_ids=[r['id'] for r in rows],expected_weight_sha256='weights',bank_source_sha256='source',endpoints={'family':'fixed'},posterior_sha256='target')
 ip=tmp_path/'intent.json';ip.write_text(json.dumps(intent));ip.with_suffix('.sha256').write_text(sha(ip))
 mp=tmp_path/'manifest.json';manifest=dict(fits=copy.deepcopy(rows),endpoints={'family':'fixed'},posterior_sha256='target');mp.write_text(json.dumps(manifest))
 p=dict(policy(),prefit_intent=str(ip),prefit_intent_sha256=sha(ip),admission_manifest=str(mp),expected_weight_sha256='weights',ordered_ids=intent['ordered_ids'],bank_source_sha256='source')
 verify_materialized(p)
 if changed=='fit':manifest['fits'][0]['sampler_seed']=999
 elif changed=='order':manifest['fits'].reverse()
 elif changed=='policy':p['relative_half_width']=.2
 elif changed=='weights':p['expected_weight_sha256']='other'
 else:manifest['endpoints']={}
 mp.write_text(json.dumps(manifest))
 with pytest.raises(ValueError):verify_materialized(p)


@pytest.mark.parametrize('suffix',['-started.json','-status.json','-hardware.json','-exit.json','.log',''])
def test_intent_rejects_already_started_fitting(tmp_path,suffix):
 from .bank_analysis_preparation import require_unstarted
 path=tmp_path/'plan.json';path.write_text(json.dumps(dict(cells=[dict(id='fit0')])))
 require_unstarted(path)
 artifact=tmp_path/('fit0'+suffix)
 if suffix:artifact.write_text('{}')
 else:artifact.mkdir()
 with pytest.raises(ValueError):require_unstarted(path)


def test_launcher_charges_materialization_and_refuses_exhausted_budget(tmp_path,monkeypatch):
 from . import bank_analysis_launch as launcher
 from .bank_analysis import sha
 p=dict(policy(),out=str(tmp_path/'out'),study='mock',python='mock',bindings={},materialization_seconds=7190)
 path=tmp_path/'plan.json';path.write_text(json.dumps(p));path.with_suffix('.sha256').write_text(sha(path));(tmp_path/'materialization-timing.json').write_text(json.dumps(dict(seconds_including_plan_writes=7191,analysis_plan_sha256=sha(path))))
 (tmp_path/'materialization-timing.sha256').write_text(sha(tmp_path/'materialization-timing.json'))
 monkeypatch.setattr(launcher.subprocess,'run',lambda *args,**kw:pytest.fail('No remaining analysis budget'))
 result=launcher.launch(path)
 assert result['reference_bank_resolved'] is False and result['materialization_seconds']==7191
 assert result['total_analysis_seconds']>=7191 and 'budget exhausted' in result['error']
 with pytest.raises(ValueError,match='Never retry'):launcher.launch(path)


def test_contained_actual_analysis_cli_failure(tmp_path):
 import subprocess,os
 if os.name!='nt':pytest.skip('Windows job protocol')
 study=Path(__file__).resolve().parent.parent;p=dict(policy(),out=str(tmp_path/'out'),study=str(study));p['timeout_seconds']=1
 path=tmp_path/'plan.json';path.write_text(json.dumps(p));hardware=tmp_path/'hardware.json'
 args=[sys.executable,str(study/'hardware_control.py'),'--cpus','0','--record',str(hardware),'--timeout','30','--',sys.executable,'-m','posterior_resource.bank_analysis','--plan',str(path)]
 process=subprocess.run(args,cwd=study,capture_output=True,text=True,timeout=45)
 assert process.returncode==2,process.stderr
 h=json.loads(hardware.read_text());r=json.loads((tmp_path/'out/analysis-result.json').read_text())
 assert h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0] and h['containment']['assigned_before_worker_execution'] is True
 assert r['status']=='unresolved' and r['reference_bank_resolved'] is False and r['worker_seconds_before_final_report']>0
 assert 'prospective analysis policy' in r['error']


def test_actual_materialize_binds_one_completed_and_retains63_missing(tmp_path,monkeypatch):
 from . import bank_analysis_preparation as prep
 from .bank_analysis import sha
 study=Path(__file__).resolve().parent.parent
 run=tmp_path/'run';run.mkdir();analysis=tmp_path/'analysis';analysis.mkdir()
 fitting=run/'plan.json';fitting.write_text(json.dumps(dict(study=str(study),python=sys.executable)))
 (run/'terminal.json').write_text(json.dumps(dict(expected=64,recorded=64)))
 pilot=tmp_path/'pilot.json';pilot.write_text(json.dumps(dict(cells=[dict(id='pilot')])))
 rows=[dict(id=f'bank-{i:02d}',backend='public' if i<32 else 'reference',sampler_seed=100+i,initialization_seed=200+i,directory=str(run/f'bank-{i:02d}'),fixture='fixture',fixture_sha256='fixture') for i in range(64)]
 first=rows[0];root=Path(first['directory']);(root/'fit').mkdir(parents=True);(root/'extracted').mkdir()
 raw=root/'fit/draws-8000/python-pymc-flow-raw.json';raw.parent.mkdir();raw.write_text('original raw bytes')
 for n in ['canonical.npy','compact.npz']:(root/'extracted'/n).write_bytes(b'bound artifact bytes')
 for n in [4000,8000]:
  for name in ['checkpoint','predictive-cdf']:(root/f'{name}-{n}.json').write_text('{}')
 worker=root/'fit/python-pymc-flow-report.json';worker.write_text(json.dumps(dict(bindings={'source':'hash'})))
 resource=root/'resource-result.json';resource.write_text(json.dumps(dict(extraction=dict(compact_sha256=sha(root/'extracted/compact.npz'),raw_sha256=sha(raw),predictive_contract={'x_next':.7}))))
 status=run/'bank-00-status.json';status.write_text(json.dumps(dict(id='bank-00',status='resource_completed',success=True,returncode=0,resource_result_sha256=sha(resource))))
 (run/'bank-00-started.json').write_text(json.dumps(dict(id='bank-00',plan_sha256=sha(fitting),timeout_seconds=1800)))
 (run/'bank-00-exit.json').write_text(json.dumps(dict(returncode=0)))
 command=[sys.executable,'-m','posterior_resource.resource_worker','--plan',str(fitting),'--cell','bank-00']
 (run/'bank-00-hardware.json').write_text(json.dumps(dict(status='completed',command=command,returncode=0,job_active_processes_after_cleanup=0,realized_cpus=[0],enforced_before_worker_launch=True,containment=dict(kind='windows-job-object',assigned_before_worker_execution=True),elapsed_seconds=1)))
 (run/'bank-01-status.json').write_text(json.dumps(dict(id='bank-01',status='worker_or_validation_failed',success=False)))
 intent_path=analysis/'intent.json';intent_path.write_text('{}')
 intent=dict(fitting_plan=str(fitting),fitting_plan_sha256=sha(fitting),expected_fits=rows,excluded_pilot_manifest=str(pilot),excluded_pilot_manifest_sha256=sha(pilot),endpoints={'fixed':'family'},posterior_sha256='target',bindings={},analysis_policy=policy(),expected_weight_sha256='weights',ordered_ids=[r['id'] for r in rows],bank_source_sha256='source')
 monkeypatch.setattr(prep,'verify_intent',lambda p:intent)
 plan=prep.materialize(intent_path)
 manifest=json.loads((analysis/'admission-manifest.json').read_text())
 assert len(manifest['fits'])==64 and 'materialization_error' not in manifest['fits'][0]
 assert all('materialization_error' in r for r in manifest['fits'][1:])
 for path in [raw,resource,worker,root/'extracted/canonical.npy',root/'extracted/compact.npz',root/'checkpoint-4000.json',root/'predictive-cdf-8000.json',status]:
  assert plan['bindings'][str(path.resolve())]==sha(path)
 timing=json.loads((analysis/'materialization-timing.json').read_text())
 assert timing['seconds_including_plan_writes']>=plan['materialization_seconds']>=0
 assert timing['analysis_plan_sha256']==sha(analysis/'analysis-plan.json')
 assert (analysis/'materialization-timing.sha256').read_text()==sha(analysis/'materialization-timing.json')
 with pytest.raises(FileExistsError):prep.materialize(intent_path)
