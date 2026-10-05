import hashlib,json,math,shutil,zipfile
from pathlib import Path
R=Path.cwd();P=R/'target/sv-online-production-smoke-v1';O=P/'run-v1';A=R/'STUDIES/market_uncertainty_v1/artifacts/live-sv-production-smoke-v1';A.mkdir(exist_ok=False,parents=True)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())
c=load(P/'prepared-v1/config.json');r=load(O/'result.json');i=load(O/'issued/issuance.json');w=load(O/'issued/worker-result.json');f=load(O/'issued/fixture.json');hw=load(O/'issued/hardware.json');wc=load(O/'issued/worker-config.json');checks={}
def check(name,truth):checks[name]=bool(truth)
check('config_identity',sha(P/'prepared-v1/config.json')==r['config_sha256'])
for p,h in {**c['bindings'],**c['runtime_bindings']}.items():check('binding:'+p,sha(p)==h)
for field,name in [('worker_result_sha256','worker-result.json'),('fixture_sha256','fixture.json'),('hardware_sha256','hardware.json'),('worker_config_sha256','worker-config.json'),('snapshot_summary_sha256','snapshot/prefix-summary.json'),('asof_features_sha256','asof-features.json')]:check(field,sha(O/'issued'/name)==i[field])
check('actual_runtime',w['runtime_bindings']==c['runtime_bindings']==wc['runtime_bindings'])
check('real_worker_command',any(str(x).endswith('workflow.py') for x in hw['command']))
check('containment',hw['returncode']==0 and hw['job_active_processes_after_cleanup']==0 and hw['realized_cpus']==[0,1,2,3] and hw['enforced_before_worker_launch'] and hw['containment']['assigned_before_worker_execution'])
check('physical_starts',w['physical_initial_positions']==f['starts'])
check('scope',len(f['data']['x'][0])==4 and len(f['data']['w'][0])==2 and len(f['data']['y'])==23)
e=w['attempts'][-1]['evaluation'];func=e['functionals'];coords=e['canonical']['all_parameters'];dim=2+4+2+23
check('dimension',len(coords)==dim)
check('names',set(func)=={'mu','sigma','h_terminal','next_observed','beta_0','beta_1','beta_2','beta_3','gamma_0','gamma_1'})
check('health',all(all(isinstance(v[k],(int,float)) and math.isfinite(v[k]) for k in ['rhat','bulk_ess','tail_ess']) and 0<v['rhat']<=1.01 and v['bulk_ess']>=400 and v['tail_ess']>=400 for v in coords+list(func.values())))
check('precision',all(len(v['endpoint_mcse'])==2 and all(math.isfinite(x) for x in v['interval']+v['endpoint_mcse']) and v['interval'][1]>v['interval'][0] and min(v['endpoint_mcse'])>=0 and max(v['endpoint_mcse'])/(v['interval'][1]-v['interval'][0])<=.02 for v in func.values()))
check('firsttier',len(w['attempts'])==1 and w['attempts'][0]['draws']==1000 and w['attempts'][0]['divergences']==0)
check('issued_interval',i['predictive_interval_90']==func['next_observed']['interval'])
check('postcompute_clock',0<=i['issued_monotonic_ns']-i['origin_receipt_ns']<=60e9 and r['issuance_elapsed_seconds']>=i['cutoff_lag_seconds'])
check('no_mock_in_runner','worker=' not in (P/'smoke.py').read_text() and 'issuer.issue(' in (P/'smoke.py').read_text())
check('scoring',r['provisional']['scored'] and r['terminal']['scored'] and r['provisional']['observed_return']==r['terminal']['observed_return']==.001700000000000068)
for label in ('provisional','terminal'):
 for p,h in r[label]['input_and_source_sha256'].items():check(label+':'+p,sha(p)==h)
files=[P/'smoke.py',P/'README.md',P/'test_smoke.py',* (P/'prepared-v1').rglob('*'),*O.rglob('*')]
raw={}
for path in files:
 if not path.is_file():continue
 if path.suffix=='.npy':raw[str(path)]=sha(path);continue
 dest=A/path.relative_to(P);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
with zipfile.ZipFile(A/'executed-sources.zip','x',zipfile.ZIP_DEFLATED) as z:
 for n,(path,h) in enumerate(c['bindings'].items()):
  if Path(path).suffix=='.py' and sha(path)==h:z.write(path,f'{n}/{Path(path).name}')
result=dict(integrity_pass=all(checks.values()),checks=checks,checks_count=len(checks),worker_seconds=w['end_to_end_seconds'],issuer_seconds=r['issuance_elapsed_seconds'],outer_seconds=r['outer_elapsed_seconds'],draws=1000,qualified=False,scope='Actual contained CFunc sampling from synthetic receipt replay and simulated clocks; reported diagnostics checked, not recomputed from raw draws; no real-market publication or coverage evidence')
(A/'independent-audit.json').write_text(json.dumps(result,indent=2));(A/'raw-hashes.json').write_text(json.dumps(raw,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='checks'}));print('failures',[k for k,v in checks.items() if not v])
