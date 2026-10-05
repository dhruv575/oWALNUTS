"""Separate research SV issuance; never modifies the baseline scheduler/capture."""
import hashlib,importlib.util,json,math,os,subprocess,time
from pathlib import Path
import numpy as np
STUDY=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
inputs=load('live_sv_inputs',Path(__file__).with_name('inputs.py'))
features=load('live_sv_features',STUDY/'receipt_features/features.py')
snapshot=load('live_sv_snapshot',STUDY/'live_snapshot/snapshot.py')
HORIZON=1800_000_000_000;WINDOW=900_000_000_000
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 with Path(p).open('x') as f:json.dump(x,f,indent=2,allow_nan=False,default=lambda a:a.tolist())

def verify(pins):
 if any(sha(p)!=h for p,h in pins.items()):raise ValueError('Source/input drift')

def gate(report,dimension,p,k):
 expected={'mu','sigma','h_terminal','next_observed',*[f'beta_{i}' for i in range(p)],*[f'gamma_{i}' for i in range(k)]}
 attempts=report['attempts'];tiers=[a['draws'] for a in attempts]
 if not tiers or tiers!=[1000,2000,4000][:len(tiers)]:raise ValueError('Invalid tier prefix')
 for i,a in enumerate(attempts):
  e=a['evaluation'];c=e['canonical']['all_parameters'];f=e['functionals']
  if len(c)!=dimension or set(f)!=expected:raise ValueError('Diagnostic scope differs')
  healthy=all(all(type(v.get(key))in(int,float) and math.isfinite(v[key]) for key in ('rhat','bulk_ess','tail_ess')) and 0<v['rhat']<=1.01 and v['bulk_ess']>=400 and v['tail_ess']>=400 for v in c+list(f.values()))
  precise=True
  for v in f.values():
   interval=v['interval'];mc=v['endpoint_mcse']
   valid=len(interval)==len(mc)==2 and all(type(x)in(int,float) and math.isfinite(x) for x in interval+mc) and interval[1]>interval[0] and min(mc)>=0
   precise &= valid and max(mc)/(interval[1]-interval[0])<=.02
  passed=healthy and precise and a['divergences']==0
  if i<len(attempts)-1 and passed:raise ValueError('Continued past first passing tier')
 if not passed:raise ValueError('Numeric precision failed')

def production_worker(fixture,config,out,seconds):
 config_path=out/'worker-config.json';save(config_path,config)
 root=STUDY.parents[1];python=config['python'];hardware=out/'hardware.json'
 cmd=[python,str(root/'STUDIES/options_flow_v1/hardware_control.py'),'--cpus','0,1,2,3','--record',str(hardware),'--timeout',str(seconds),'--',python,str(STUDY/'sv_prototype/workflow.py'),'--fixture',str(fixture),'--config',str(config_path),'--arm','public','--seed',str(config['sampler_seed']),'--out',str(out/'fit')]
 env=dict(os.environ,PYTHONPATH=config['package'],OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
 try:
  with (out/'worker.log').open('x') as log:proc=subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT)
  h=json.loads(hardware.read_text())
  if h.get('job_active_processes_after_cleanup')!=0 or h.get('realized_cpus')!=[0,1,2,3] or h.get('returncode')!=proc.returncode or h.get('enforced_before_worker_launch') is not True or h.get('containment',{}).get('assigned_before_worker_execution') is not True:raise ValueError('Invalid cleanup/affinity identity')
 except Exception as exc:raise RuntimeError('Worker containment failed: '+repr(exc)) from exc
 if proc.returncode!=0:raise RuntimeError('Worker failed or precision unavailable')
 return json.loads((out/'fit/report.json').read_text())

def decide(dataset,origin,config,out,*,clock=time.monotonic_ns,utc=time.time_ns,worker=production_worker,source_pins=None,artifact_pins=None):
 """Dataset must be produced from a pinned receipt prefix cut at origin.

    Caller issues through issue(), which supplies that cutoff and its hashes.
    No interval is published until fit precision and postcompute deadline pass.
    """
 out=Path(out);result=dict(schema='research-live-sv-issuance-v1',status='not_issued',origin_receipt_ns=origin,horizon_end_receipt_ns=origin+HORIZON,maximum_lag_seconds=60,qualified=False)
 source_paths=[Path(__file__),Path(inputs.__file__),Path(features.__file__),Path(snapshot.__file__)]
 pins=source_pins if source_pins is not None else {str(p.resolve()):sha(p) for p in source_paths}
 allpins={**config['bindings'],**config.get('runtime_bindings',{}),**pins,**(artifact_pins or {})}
 try:
  verify(allpins)
  if not origin<=clock()<origin+60_000_000_000:raise ValueError('Origin not current or already late')
  built=inputs.build(dataset,origin,ablation='both',minimum_history=20,lookback=256)
  if built['status']!='ready':
   verify(allpins);issued=clock()
   if issued>origin+60_000_000_000:raise ValueError('Late after preparation')
   result.update(status='issued_no_forecast',reason=built['reason'],issued_monotonic_ns=issued,issued_utc_ns=utc(),source_sha256=pins);return result
  data=built['data'];data['x'][~data['observed']]=0;data['y'][~data['observed']]=0
  data.update(rho=.9,nu=5.)
  pr=dict(mu_mean=2*math.log(.005),mu_sd=1.,log_sigma_mean=math.log(.2),log_sigma_sd=.5,beta_sd=.002,gamma_sd=.03)
  p,k,t=data['x'].shape[1],data['w'].shape[1],len(data['y']);mean=np.r_[pr['mu_mean'],pr['log_sigma_mean'],np.zeros(p+k+t)];sd=np.r_[1.,.5,np.full(p,.002),np.full(k,.03),np.ones(t)]
  starts=mean+.25*sd*np.random.default_rng(config['initialization_seed']).normal(size=(4,len(mean)))
  fixture=dict(data=data,priors=pr,starts=starts,future=dict(x=built['forecast']['x_next'],w=built['forecast']['w_next']),predictive_seed=config['predictive_seed'])
  path=out/'fixture.json';save(path,fixture);cfg=dict(config);cfg['bindings']={**config['bindings'],**pins,str(path.resolve()):sha(path)}
  remaining=(origin+60_000_000_000-clock())/1e9-5
  if remaining<=0:raise ValueError('No worker admission time remains')
  report=worker(path,cfg,out,remaining)
  save(out/'worker-result.json',report)
  if report.get('status')!='completed' or report.get('precision_pass') is not True:raise ValueError('Precision failed')
  if report.get('arm')!='public' or report.get('seed')!=config['sampler_seed'] or report.get('predictive_seed')!=config['predictive_seed']:raise ValueError('Worker identity differs')
  if config.get('runtime_bindings') and report.get('runtime_bindings')!=config['runtime_bindings']:raise ValueError('Actual native runtime differs')
  gate(report,len(mean),p,k)
  interval=report['attempts'][-1]['evaluation']['functionals']['next_observed']['interval']
  if len(interval)!=2 or not all(type(v)in(int,float) and math.isfinite(v) for v in interval) or interval[0]>=interval[1]:raise ValueError('Invalid interval')
  hashes=dict(worker_result_sha256=sha(out/'worker-result.json'),fixture_sha256=sha(path))
  for name in ('hardware.json','worker-config.json'):
   if (out/name).exists():hashes[name.replace('.json','').replace('-','_')+'_sha256']=sha(out/name)
  verify(allpins)
  issued=clock()
  if issued>origin+60_000_000_000:raise ValueError('Late after computation')
  result.update(status='issued',issued_monotonic_ns=issued,issued_utc_ns=utc(),cutoff_lag_seconds=(issued-origin)/1e9,predictive_interval_90=interval,source_sha256=pins,model='sv_both_prior_whitened',precision_pass=True,sampler_seed=config['sampler_seed'],predictive_seed=config['predictive_seed'],**hashes)
 except Exception as exc:result.update(status='not_issued',reason=str(exc))
 return result

def issue(capture,out,origin,config,**kwargs):
 out=Path(out);out.mkdir(parents=True,exist_ok=False)
 pins={str(p.resolve()):sha(p) for p in (Path(__file__),Path(inputs.__file__),Path(features.__file__),Path(snapshot.__file__))}
 result=dict(schema='research-live-sv-issuance-v1',status='not_issued',origin_receipt_ns=origin,horizon_end_receipt_ns=origin+HORIZON,maximum_lag_seconds=60,qualified=False,source_sha256=pins)
 try:
  verify({**config['bindings'],**config.get('runtime_bindings',{}),**pins})
  pref=snapshot.snapshot(Path(capture),out/'snapshot',max_bytes=536870912)
  if pref['receipt_prefix'].get('cap_clipped'):raise ValueError('Clipped prefix')
  raw=(out/'snapshot/receipts.jsonl').read_bytes()
  if hashlib.sha256(raw).hexdigest()!=pref['files_sha256']['receipts.jsonl']:raise ValueError('Receipt identity differs')
  rows=[json.loads(line) for line in raw.splitlines()]
  if not rows:raise ValueError('Empty receipt prefix')
  first=rows[0]['receipt_monotonic_ns']
  if type(origin)is not int or origin<first+WINDOW or (origin-first-WINDOW)%HORIZON:raise ValueError('Origin off frozen grid')
  if pref['end_monotonic_ns']<origin:raise ValueError('Prefix has not reached origin')
  rows=[r for r in rows if r['receipt_monotonic_ns']<=origin]
  context=features.collector_context(pref);context['observation_end_ns']=origin
  dataset=features.build(rows,origins_ns=list(range(first+WINDOW,origin+1,HORIZON)),**context)
  if not dataset['rows'] or dataset['rows'][-1]['label']['observed']:raise ValueError('Current label leaked or empty asof rows')
  save(out/'asof-features.json',dataset)
  artifacts={str((out/name).resolve()):sha(out/name) for name in ('asof-features.json','snapshot/prefix-summary.json','snapshot/receipts.jsonl','snapshot/lifecycle.jsonl','snapshot/selection.json')}
  hashes=dict(snapshot_summary_sha256=artifacts[str((out/'snapshot/prefix-summary.json').resolve())],asof_features_sha256=artifacts[str((out/'asof-features.json').resolve())])
  result=decide(dataset,origin,config,out,source_pins=pins,artifact_pins=artifacts,**kwargs)
  result.update(hashes)
 except Exception as exc:result.update(status='not_issued',reason=str(exc))
 save(out/'issuance.json',result);return result
