import copy,json
from pathlib import Path
import score as s
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v));return s.digest(p.read_bytes())
def setup(tmp_path,monkeypatch):
 issued=tmp_path/'issued';capture=tmp_path/'later';origin=10**13
 source=tmp_path/'source.py';source.write_text('immutable source')
 current={'features':{'origin_receipt_ns':origin},'label':{'observed':False,'log_midpoint_return':None}}
 asof=write(issued/'asof-features.json',{'rows':[current]})
 pins={}
 for name in ('receipts.jsonl','lifecycle.jsonl','selection.json'):
  p=issued/'snapshot'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{}\n');pins[name]=s.digest(p.read_bytes());q=capture/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
 prefix={'files_sha256':pins,'receipt_prefix':{'cap_clipped':False,'bytes':(issued/'snapshot/receipts.jsonl').stat().st_size,'sha256':pins['receipts.jsonl']},'lifecycle_prefix':{'bytes':(issued/'snapshot/lifecycle.jsonl').stat().st_size,'sha256':pins['lifecycle.jsonl']},'coverage_intervals':[{'start_monotonic_ns':0,'end_monotonic_ns':origin}],'gaps':[]}
 ps=write(issued/'snapshot/prefix-summary.json',prefix)
 summary=dict(prefix,schema='public-receipt-collector-v2',status='duration_complete',end_monotonic_ns=origin+s.HORIZON)
 write(capture/'summary.json',summary);write(capture/'prefix-summary.json',dict(summary,schema='public-receipt-prefix-snapshot-v1',status='prefix_snapshot_not_terminal'))
 dim=28;fixture={'data':{'y':[0]*20,'x':[[1]*4]*20,'w':[[1]*2]*20,'rho':.9,'nu':5.},'starts':[[0]*dim]*4,'predictive_seed':2};fs=write(issued/'fixture.json',fixture)
 d={'rhat':1.,'bulk_ess':500.,'tail_ess':500.};fn={k:dict(d,interval=[-.1,.1],endpoint_mcse=[.001,.001]) for k in ['mu','sigma','h_terminal','next_observed',*[f'beta_{i}' for i in range(4)],*[f'gamma_{i}' for i in range(2)]]}
 report={'status':'completed','precision_pass':True,'arm':'public','seed':1,'predictive_seed':2,'coordinates':'prior_whitened','physical_initial_positions':fixture['starts'],'attempts':[{'draws':1000,'divergences':0,'evaluation':{'canonical':{'all_parameters':[d]*dim},'functionals':fn}}]};rs=write(issued/'worker-result.json',report)
 record={'schema':'research-live-sv-issuance-v1','status':'issued','origin_receipt_ns':origin,'horizon_end_receipt_ns':origin+s.HORIZON,'issued_monotonic_ns':origin+3*10**9,'maximum_lag_seconds':60,'source_sha256':{str(source):s.digest(source.read_bytes())},'snapshot_summary_sha256':ps,'asof_features_sha256':asof,'worker_result_sha256':rs,'fixture_sha256':fs,'sampler_seed':1,'predictive_seed':2,'model':'sv_both_prior_whitened','precision_pass':True,'predictive_interval_90':[-.1,.1]}
 h=write(issued/'issuance.json',record)
 monkeypatch.setattr(s.snapshot,'reconcile',lambda *a:{'requires_rebuild':False})
 monkeypatch.setattr(s.features,'collector_context',lambda x:{})
 monkeypatch.setattr(s.features,'build',lambda *a,**kw:{'rows':[dict(features=current['features'],label={'observed':True,'log_midpoint_return':.2})]})
 return issued,capture,record,h,report
def test_terminal_and_provisional_score(tmp_path,monkeypatch):
 issued,capture,r,h,_=setup(tmp_path,monkeypatch)
 for provisional in (False,True):
  out=s.score(issued,capture,expected_issuance_sha256=h,provisional=provisional)
  assert out['scored'] and not out['covered'] and abs(out['interval_score']-2.2)<1e-12 and out['provisional']==provisional
def test_wrong_identity_and_future_label_rejected(tmp_path,monkeypatch):
 issued,capture,r,h,_=setup(tmp_path,monkeypatch)
 assert not s.score(issued,capture,expected_issuance_sha256='0'*64)['scored']
 asof=json.loads((issued/'asof-features.json').read_text());asof['rows'][0]['label']['observed']=True;r['asof_features_sha256']=write(issued/'asof-features.json',asof);h=write(issued/'issuance.json',r)
 assert s.score(issued,capture,expected_issuance_sha256=h)['status']=='invalid_issuance'
def test_gap_retracts(tmp_path,monkeypatch):
 issued,capture,r,h,_=setup(tmp_path,monkeypatch);monkeypatch.setattr(s.snapshot,'reconcile',lambda *a:{'requires_rebuild':True})
 out=s.score(issued,capture,expected_issuance_sha256=h);assert out['status']=='invalidated_receipt_coverage' and not out['scored']
def test_nonissuance_retains_reason(tmp_path,monkeypatch):
 issued,capture,r,h,_=setup(tmp_path,monkeypatch)
 for status,reason in [('not_issued','Precision failed'),('not_issued','Late after computation'),('issued_no_forecast','insufficient_mature_history')]:
  r.update(status=status,reason=reason);h=write(issued/'issuance.json',r);out=s.score(issued,capture,expected_issuance_sha256=h);assert not out['scored'] and out['reason']==reason
def test_numeric_gate_not_boolean_only(tmp_path,monkeypatch):
 issued,capture,r,h,report=setup(tmp_path,monkeypatch);report['attempts'][0]['evaluation']['canonical']['all_parameters'][0]['rhat']=1.3;r['worker_result_sha256']=write(issued/'worker-result.json',report);h=write(issued/'issuance.json',r)
 assert s.score(issued,capture,expected_issuance_sha256=h)['status']=='invalid_issuance'
def test_mutation_during_score_invalidates(tmp_path,monkeypatch):
 issued,capture,r,h,_=setup(tmp_path,monkeypatch)
 def drift(*a,**kw):
  (issued/'fixture.json').write_text('{}');return {'rows':[{'features':{'origin_receipt_ns':r['origin_receipt_ns']},'label':{'observed':True,'log_midpoint_return':0.}}]}
 monkeypatch.setattr(s.features,'build',drift);out=s.score(issued,capture,expected_issuance_sha256=h);assert out['status']=='invalid_provenance' and not out['scored'] and 'interval_score' not in out
def test_production_evidence_pair_and_containment(tmp_path,monkeypatch):
 issued,capture,r,h,report=setup(tmp_path,monkeypatch);runtime={str(tmp_path/'source.py'):s.digest((tmp_path/'source.py').read_bytes())};report['runtime_bindings']=runtime;r['worker_result_sha256']=write(issued/'worker-result.json',report)
 config={'sampler_seed':1,'predictive_seed':2,'bindings':runtime,'runtime_bindings':runtime};hardware={'returncode':0,'job_active_processes_after_cleanup':0,'realized_cpus':[0,1,2,3],'enforced_before_worker_launch':True,'containment':{'assigned_before_worker_execution':True}}
 r['worker_config_sha256']=write(issued/'worker-config.json',config);h=write(issued/'issuance.json',r);assert s.score(issued,capture,expected_issuance_sha256=h)['status']=='invalid_issuance'
 r['hardware_sha256']=write(issued/'hardware.json',hardware);h=write(issued/'issuance.json',r);assert s.score(issued,capture,expected_issuance_sha256=h)['scored']
 hardware['job_active_processes_after_cleanup']=1;r['hardware_sha256']=write(issued/'hardware.json',hardware);h=write(issued/'issuance.json',r);assert s.score(issued,capture,expected_issuance_sha256=h)['status']=='invalid_issuance'
def test_actual_issuer_snapshot_to_delayed_scoring(tmp_path):
 issuer=s.load('scorer_real_issuer',s.STUDY/'sv_online_issuance/issue.py')
 capture=tmp_path/'capture';capture.mkdir();channels=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2'];window=900_000_000_000
 rows=[dict(receipt_monotonic_ns=1,receipt_utc_ns=1001,connection=1,raw=json.dumps(dict(id=1,result=channels)))]
 def quote(stamp,price):return dict(receipt_monotonic_ns=stamp,receipt_utc_ns=stamp+1000,connection=1,raw=json.dumps(dict(params=dict(channel=channels[1],data=dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=price,best_ask_price=price)))))
 rows.extend(quote(1+window+j*s.HORIZON,100.+j) for j in range(23));origin=rows[-1]['receipt_monotonic_ns']
 (capture/'receipts.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows));(capture/'lifecycle.jsonl').write_text(json.dumps(dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1002,connection=1))+'\n');write(capture/'selection.json',dict(channels=channels))
 config=dict(initialization_seed=1,sampler_seed=2,predictive_seed=3,bindings={},runtime_bindings={})
 def worker(path,cfg,out,seconds):
  fixture=json.loads(path.read_text());dim=len(fixture['starts'][0]);stat=dict(rhat=1.,bulk_ess=1000.,tail_ess=1000.,all_finite=True);names=['mu','sigma','h_terminal','next_observed',*[f'beta_{i}' for i in range(4)],*[f'gamma_{i}' for i in range(2)]]
  write(out/'worker-config.json',cfg);write(out/'hardware.json',dict(returncode=0,job_active_processes_after_cleanup=0,realized_cpus=[0,1,2,3],enforced_before_worker_launch=True,containment={'assigned_before_worker_execution':True}))
  return dict(status='completed',precision_pass=True,arm='public',seed=2,predictive_seed=3,coordinates='prior_whitened',physical_initial_positions=fixture['starts'],runtime_bindings={},attempts=[dict(draws=1000,divergences=0,evaluation=dict(canonical={'all_parameters':[stat]*dim},functionals={n:dict(stat,interval=[-.1,.1],endpoint_mcse=[.001,.001]) for n in names}))])
 issued=tmp_path/'issued';r=issuer.issue(capture,issued,origin,config,clock=lambda:origin+4_000_000_000,worker=worker);assert r['status']=='issued',r
 identity=s.digest((issued/'issuance.json').read_bytes());assert not json.loads((issued/'asof-features.json').read_text())['rows'][-1]['label']['observed']
 with (capture/'receipts.jsonl').open('a') as f:f.write(json.dumps(quote(origin+s.HORIZON,123.))+'\n')
 later=tmp_path/'later';prefix=issuer.snapshot.snapshot(capture,later)
 provisional=s.score(issued,later,expected_issuance_sha256=identity,provisional=True);assert provisional['scored'],provisional
 terminal=dict(prefix,schema='public-receipt-collector-v2',status='duration_complete');write(later/'summary.json',terminal)
 final=s.score(issued,later,expected_issuance_sha256=identity);assert final['scored'] and final['observed_return']==provisional['observed_return']
 assert not s.score(issued,later,expected_issuance_sha256='0'*64)['scored']
 terminal['gaps']=[dict(start_monotonic_ns=origin-100,resubscribed_monotonic_ns=origin+100)];write(later/'summary.json',terminal)
 revoked=s.score(issued,later,expected_issuance_sha256=identity);assert revoked['status']=='invalidated_receipt_coverage' and not revoked['scored']
