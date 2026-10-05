import copy
import numpy as np
from issue import decide,HORIZON,inputs

def dataset():
 return dict(rows=[dict(features=dict(origin_receipt_ns=i*HORIZON,anchor=dict(available=True,midpoint=float(100*np.exp(.001*i))),flow_known=True,total_amount=i+1.,signed_amount=(-1.)**i),label=dict(observed=True,horizon_end_receipt_ns=(i+1)*HORIZON,available_at_receipt_ns=(i+1)*HORIZON,log_midpoint_return=.001)) for i in range(24)])
def config():return dict(initialization_seed=1,sampler_seed=2,predictive_seed=3,bindings={})
def report(dimension=30):
 stat=dict(rhat=1.,bulk_ess=1000.,tail_ess=1000.,all_finite=True)
 f={name:dict(stat,interval=[-.1,.1],endpoint_mcse=[.001,.001]) for name in ['mu','sigma','h_terminal','next_observed','beta_0','beta_1','beta_2','beta_3','gamma_0','gamma_1']}
 return dict(status='completed',precision_pass=True,arm='public',seed=2,predictive_seed=3,attempts=[dict(draws=1000,divergences=0,evaluation=dict(canonical=dict(all_parameters=[stat]*dimension),functionals=f))])
def test_causal_design_p4k2_and_future_labels_ignored():
 d=dataset();a=inputs.build(d,22*HORIZON,ablation='both',minimum_history=20,lookback=256)
 assert a['data']['x'].shape[1]==4 and a['data']['w'].shape[1]==2
 assert a['data']['observed'][0]==False
 e=copy.deepcopy(d)
 for r in e['rows'][22:]:r['label']={'future':'ignored'}
 b=inputs.build(e,22*HORIZON,ablation='both',minimum_history=20,lookback=256)
 np.testing.assert_array_equal(a['data']['y'],b['data']['y'])
 assert a['scaling']==b['scaling']

def test_after_compute_deadline_and_precision_withhold(tmp_path):
 origin=22*HORIZON;now=[origin+3_000_000_000]
 def worker(*args):now[0]=origin+61_000_000_000;return report()
 r=decide(dataset(),origin,config(),tmp_path,clock=lambda:now[0],worker=worker)
 assert r['status']=='not_issued' and 'Late' in r['reason']
 other=tmp_path/'second';other.mkdir();now[0]=origin+3_000_000_000
 r=decide(dataset(),origin,config(),other,clock=lambda:now[0],worker=lambda *a:{'status':'completed','precision_pass':False})
 assert r['status']=='not_issued' and r['reason']=='Precision failed'

def test_nohistory_and_runtime_failure_preserved(tmp_path):
 r=decide(dataset(),3*HORIZON,config(),tmp_path,clock=lambda:3*HORIZON+1,worker=lambda *a:(_ for _ in ()).throw(AssertionError('Must not fit')))
 assert r['status']=='issued_no_forecast'
 def bad(*a):raise ValueError('Actual runtime identity differs')
 r=decide(dataset(),22*HORIZON,config(),tmp_path,clock=lambda:22*HORIZON+1,worker=bad)
 assert r['status']=='not_issued' and 'runtime' in r['reason']


def test_success_and_source_change_withhold(tmp_path,monkeypatch):
 import issue
 origin=22*HORIZON
 r=decide(dataset(),origin,config(),tmp_path,clock=lambda:origin+4_000_000_000,worker=lambda *a:report())
 assert r['status']=='issued' and r['cutoff_lag_seconds']==4
 assert r['worker_result_sha256'] and r['fixture_sha256']
 other=tmp_path/'drift';other.mkdir();real=issue.sha;changed=[False]
 def worker(*a):changed[0]=True;return report()
 def hashed(path):
  if changed[0] and str(path).endswith('inputs.py'):return '0'*64
  return real(path)
 monkeypatch.setattr(issue,'sha',hashed)
 r=decide(dataset(),origin,config(),other,clock=lambda:origin+4_000_000_000,worker=worker)
 assert r['status']=='not_issued' and r['reason']=='Source/input drift'

def capture(tmp_path):
 import json
 from issue import WINDOW
 c=tmp_path/'capture';c.mkdir();channels=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2']
 rows=[dict(receipt_monotonic_ns=1,receipt_utc_ns=1001,connection=1,raw=json.dumps(dict(id=1,result=channels)))]
 for j in range(23):
  t=1+WINDOW+j*HORIZON
  rows.append(dict(receipt_monotonic_ns=t,receipt_utc_ns=t+1000,connection=1,raw=json.dumps(dict(params=dict(channel=channels[1],data=dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=100.+j,best_ask_price=100.+j))))))
 (c/'receipts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
 (c/'lifecycle.jsonl').write_text(json.dumps(dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1002,connection=1))+'\n')
 (c/'selection.json').write_text(json.dumps(dict(channels=channels)))
 return c,rows[-1]['receipt_monotonic_ns']

def test_actual_issue_path_receipt_build_worker_and_invalid_grid(tmp_path):
 import issue,json
 c,origin=capture(tmp_path)
 r=issue.issue(c,tmp_path/'valid',origin,config(),clock=lambda:origin+4_000_000_000,worker=lambda *a:report())
 assert r['status']=='issued',r
 assert r['snapshot_summary_sha256'] and r['asof_features_sha256']
 r=issue.issue(c,tmp_path/'bad',origin+1,config(),clock=lambda:origin+4_000_000_000)
 assert r['status']=='not_issued' and 'grid' in r['reason']
 assert json.loads((tmp_path/'bad/issuance.json').read_text())==r

def test_hashing_overrun_and_snapshot_failure_have_records(tmp_path,monkeypatch):
 import issue,json
 c,origin=capture(tmp_path);now=[origin+4_000_000_000];real=issue.sha
 def hashed(p):
  if str(p).endswith('worker-result.json'):now[0]=origin+61_000_000_000
  return real(p)
 monkeypatch.setattr(issue,'sha',hashed)
 r=issue.issue(c,tmp_path/'late',origin,config(),clock=lambda:now[0],worker=lambda *a:report())
 assert r['status']=='not_issued' and 'Late' in r['reason']
 def broken(*a,**kw):raise ValueError('Broken prefix')
 monkeypatch.setattr(issue.snapshot,'snapshot',broken)
 r=issue.issue(c,tmp_path/'broken',origin,config())
 assert r['status']=='not_issued' and (tmp_path/'broken/issuance.json').exists()

def test_false_pass_boolean_cannot_hide_bad_numeric_scope(tmp_path):
 r=report();r['attempts'][0]['evaluation']['canonical']['all_parameters'][0]['rhat']=1.2
 origin=22*HORIZON
 got=decide(dataset(),origin,config(),tmp_path,clock=lambda:origin+1,worker=lambda *a:r)
 assert got['status']=='not_issued' and 'Numeric precision' in got['reason']

def test_missing_malformed_hardware_are_fatal_but_clean_failure_local(tmp_path,monkeypatch):
 import issue,json,pytest
 from types import SimpleNamespace
 cfg=dict(python='python',package='package',sampler_seed=2)
 for mode in ('missing','malformed','clean_failure','launch_failure'):
  out=tmp_path/mode;out.mkdir()
  def launch(*a,**kw):
   if mode=='launch_failure':raise OSError('launch failed')
   if mode=='malformed':(out/'hardware.json').write_text('{broken')
   if mode=='clean_failure':(out/'hardware.json').write_text(json.dumps(dict(job_active_processes_after_cleanup=0,realized_cpus=[0,1,2,3],returncode=1,enforced_before_worker_launch=True,containment=dict(assigned_before_worker_execution=True))))
   return SimpleNamespace(returncode=1)
  monkeypatch.setattr(issue.subprocess,'run',launch)
  with pytest.raises(RuntimeError,match='Worker failed or precision unavailable' if mode=='clean_failure' else 'Worker containment failed'):
   issue.production_worker(out/'fixture.json',cfg,out,5.)
