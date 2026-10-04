"""Pre-fit immutable intent, then mechanical post-fit artifact binding only."""
import argparse,json,sys,time
from pathlib import Path
from .bank_analysis import sha,validate_policy,frozen_counts,weight_contract

def load(p):return json.loads(Path(p).read_text())
def save(p,v):
 with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False)

def verify_intent(path):
 path=Path(path).resolve();v=load(path)
 if v.get('frozen') is not True or path.with_suffix('.sha256').read_text().strip()!=sha(path):raise ValueError('Frozen prefit intent required')
 validate_policy(v['analysis_policy'])
 if {str(p.resolve()):sha(p) for p in Path(v['analysis_source_directory']).rglob('*.py')}!=v['analysis_source_inventory']:raise ValueError('Analysis source inventory changed')
 if any(sha(p)!=h for p,h in v['bindings'].items()):raise ValueError('Prefit bound source/audit changed')
 return v

def require_unstarted(fitting_plan):
 fit=load(fitting_plan);root=Path(fitting_plan).resolve().parent
 if (root/'terminal.json').exists():raise ValueError('Analysis intent must precede every fitting attempt')
 for c in fit['cells']:
  if any((root/(c['id']+suffix)).exists() for suffix in ['', '-started.json','-status.json','-hardware.json','-exit.json','.log']):raise ValueError('Analysis intent cannot follow a started fit')


def bind_execution(intent_path):
 intent_path=Path(intent_path).resolve();v=verify_intent(intent_path);require_unstarted(v['fitting_plan']);path=Path(v['fitting_plan']).parent/'analysis-link.json'
 link=dict(fitting_plan=v['fitting_plan'],fitting_plan_sha256=v['fitting_plan_sha256'],analysis_intent=str(intent_path),analysis_intent_sha256=sha(intent_path),policy='Immutable prefit analysis intent required before any bank fitting')
 save(path,link)
 with path.with_suffix('.sha256').open('x') as f:f.write(sha(path))
 return link

def prepare_intent(fitting_plan,audit_path,out,seed):
 fit=load(fitting_plan);study=Path(fit['study']);sys.path.insert(0,str(study))
 from posterior_resource.bank_controller import verify_frozen
 from posterior_resource.bank_adapter import ENDPOINTS
 from production_calibration_feasibility import audited_seeds
 verify_frozen(fitting_plan);require_unstarted(fitting_plan)
 audit=audited_seeds(audit_path,[seed])
 if any(sha(p)!=h for p,h in audit.get('supplemental_evidence',{}).items()):raise ValueError('Supplemental seed audit changed')
 rows=[dict(id=c['id'],backend=c['backend'],sampler_seed=c['seed'],initialization_seed=c['init_seed'],directory=c['out'],fixture=c['fixture'],fixture_sha256=c['fixture_sha256']) for c in fit['cells']]
 if seed in [r[k] for r in rows for k in ['sampler_seed','initialization_seed']] or seed in [r['sampler_seed']+130000 for r in rows]:raise ValueError('Bootstrap and fitting streams collide')
 counts=frozen_counts(rows,seed,30000);columns,weights,digest=weight_contract(rows,counts)
 policy=dict(timeout_seconds=7200,cleanup_reserve_seconds=15,memory_bytes=8*1024**3,cpus=[0],bootstrap_replicates=30000,minimum_tail_count=20,bootstrap_seed=seed,alpha=.05,relative_half_width=.1,backend_equivalence_relative_width=.02,length_equivalence_relative_width=.1,max_queries=64,max_rounds=32,absolute_width=.01,cdf_tolerance=1e-8,orders=[16,32,64,128],initial_grid=[-4.,4.])
 own=Path(__file__).resolve().parent;bindings=dict(fit['bindings']);bindings.update({str(Path(p).resolve()):sha(p) for p in [fitting_plan,audit_path,*own.rglob('*.py')]});bindings.update(audit['inventory_files']);bindings.update(audit.get('supplemental_evidence',{}))
 out=Path(out).resolve();out.mkdir(exist_ok=False)
 intent=dict(analysis_source_directory=str(own),analysis_source_inventory={str(p.resolve()):sha(p) for p in own.rglob('*.py')},frozen=False,qualified=False,phase='prospective_reference_bank_analysis',analysis_policy=policy,fitting_plan=str(Path(fitting_plan).resolve()),fitting_plan_sha256=sha(fitting_plan),bindings=bindings,expected_fits=rows,ordered_ids=[r['id'] for r in rows],grid_columns=columns,expected_weight_sha256=digest,weight_encoding='little-endian float64 normalized count rows; point4 then bootstrap4 per replicate',endpoints=ENDPOINTS,posterior_sha256=fit['posterior_sha256'],bank_source_sha256=sha(study/'reference_bank.py'),excluded_pilot_manifest=fit['excluded_pilot_manifest'],excluded_pilot_manifest_sha256=fit['excluded_pilot_manifest_sha256'],bootstrap_audit=str(Path(audit_path).resolve()),policy='Intent before any bank fit; postfit materialization may add only exact output hashes, never choose fits or alter thresholds')
 save(out/'intent-draft.json',intent);return intent

def freeze_intent(directory):
 directory=Path(directory).resolve();v=load(directory/'intent-draft.json')
 if v.get('frozen') is not False:raise ValueError('Explicit draft required')
 if any(sha(p)!=h for p,h in v['bindings'].items()):raise ValueError('Source changed before freeze')
 validate_policy(v['analysis_policy']);require_unstarted(v['fitting_plan']);v['frozen']=True;save(directory/'intent.json',v)
 with (directory/'intent.sha256').open('x') as f:f.write(sha(directory/'intent.json'))

def materialize(intent_path):
 materialization_started=time.perf_counter()
 intent_path=Path(intent_path).resolve();v=verify_intent(intent_path);fit=load(v['fitting_plan']);study=Path(fit['study']);sys.path.insert(0,str(study));directory=intent_path.parent
 terminal=Path(v['fitting_plan']).parent/'terminal.json'
 if not terminal.exists() or load(terminal).get('recorded')!=64 or load(terminal).get('expected')!=64:raise ValueError('All64 terminal outcomes required before analysis materialization')
 rows=[];artifact_bindings={}
 for declared in v['expected_fits']:
  r=dict(declared,study=str(study),initialization_helper_sha256=sha(study/'masked_market_comparison_plan.py'),resource_plan=v['fitting_plan'],resource_plan_sha256=v['fitting_plan_sha256'])
  root=Path(r['directory']);result=root/'resource-result.json';worker=root/('fit/python-pymc-flow-report.json' if r['backend']=='public' else 'fit/report.json');raw=root/('fit/draws-8000/python-pymc-flow-raw.json' if r['backend']=='public' else 'fit/draws-8000-raw.json')
  status_path=Path(v['fitting_plan']).parent/(r['id']+'-status.json');hardware_path=Path(v['fitting_plan']).parent/(r['id']+'-hardware.json')
  r.update(worker_report=str(worker),raw=str(raw),controller_status=str(status_path),hardware_record=str(hardware_path))
  # Missing/failed artifacts remain explicit incomplete rows; collect retains all64.
  try:
   status=load(status_path)
   if status.get('id')!=r['id'] or status.get('status')!='resource_completed' or status.get('success') is not True or status.get('returncode')!=0:raise ValueError('Fit controller did not admit this result')
   hardware=load(hardware_path)
   if hardware.get('status')!='completed' or hardware.get('returncode')!=0 or hardware.get('job_active_processes_after_cleanup')!=0 or hardware.get('realized_cpus')!=[0] or hardware.get('containment',{}).get('assigned_before_worker_execution') is not True:raise ValueError('Fit hardware terminal evidence invalid')
   from asof_rolling_execute import validate_hardware
   started_path=Path(v['fitting_plan']).parent/(r['id']+'-started.json');started=load(started_path)
   command=[fit['python'],'-m','posterior_resource.resource_worker','--plan',v['fitting_plan'],'--cell',r['id']]
   validate_hardware(hardware,['--',*command],0,started['timeout_seconds'])
   if started.get('id')!=r['id'] or started.get('plan_sha256')!=v['fitting_plan_sha256']:raise ValueError('Started marker binds another fit')
   resource=load(result);w=load(worker)
   if status.get('resource_result_sha256')!=sha(result):raise ValueError('Controller result binding differs')
   r.update(result_sha256=sha(result),worker_report_sha256=sha(worker),compact_sha256=resource['extraction']['compact_sha256'],raw_sha256=resource['extraction']['raw_sha256'],predictive_contract=resource['extraction']['predictive_contract'],worker_bindings=w['bindings'])
  except (OSError,KeyError,ValueError) as exc:r['materialization_error']=str(exc)
  paths=[result,worker,raw,root/'extracted/canonical.npy',root/'extracted/compact.npz',status_path,hardware_path,Path(v['fitting_plan']).parent/(r['id']+'-started.json'),Path(v['fitting_plan']).parent/(r['id']+'-exit.json')]
  paths += [root/f'{name}-{n}.json' for name in ['checkpoint','predictive-cdf'] for n in [4000,8000]]
  for artifact in paths:
   if artifact.is_file():artifact_bindings[str(artifact.resolve())]=sha(artifact)
  rows.append(r)
 pilot=load(v['excluded_pilot_manifest'])
 manifest=dict(qualified=False,phase='prospective_reference_bank',posterior_sha256=v['posterior_sha256'],excluded_pilot_manifest=v['excluded_pilot_manifest'],excluded_pilot_manifest_sha256=v['excluded_pilot_manifest_sha256'],excluded_resource_pilot_ids=[c['id'] for c in pilot['cells']],endpoints=v['endpoints'],fits=rows)
 mp=directory/'admission-manifest.json';save(mp,manifest)
 bindings=dict(v['bindings']);bindings.update(artifact_bindings);bindings[str(intent_path)]=sha(intent_path);bindings[str(mp)]=sha(mp);bindings[str(terminal)]=sha(terminal)
 plan=dict(v['analysis_policy'],materialization_seconds=time.perf_counter()-materialization_started,materialization_timing_scope='Admission/source/artifact hashing through plan construction; final small manifest write measured separately',out=str(directory/'analysis-output'),study=str(study),python=fit['python'],bindings=bindings,prefit_intent=str(intent_path),prefit_intent_sha256=sha(intent_path),admission_manifest=str(mp),expected_weight_sha256=v['expected_weight_sha256'],ordered_ids=v['ordered_ids'],bank_source_sha256=v['bank_source_sha256'])
 save(directory/'analysis-plan.json',plan)
 with (directory/'analysis-plan.sha256').open('x') as f:f.write(sha(directory/'analysis-plan.json'))
 save(directory/'materialization-timing.json',dict(seconds_including_plan_writes=time.perf_counter()-materialization_started,analysis_plan_sha256=sha(directory/'analysis-plan.json')))
 with (directory/'materialization-timing.sha256').open('x') as f:f.write(sha(directory/'materialization-timing.json'))
 return plan

def verify_materialized(plan):
 intent=verify_intent(plan['prefit_intent'])
 if sha(plan['prefit_intent'])!=plan['prefit_intent_sha256'] or any(plan.get(k)!=v for k,v in intent['analysis_policy'].items()):raise ValueError('Postfit policy differs from prefit intent')
 for key in ['expected_weight_sha256','ordered_ids','bank_source_sha256']:
  if plan[key]!=intent[key]:raise ValueError('Postfit order/weights/source differs')
 manifest=load(plan['admission_manifest'])
 if manifest['endpoints']!=intent['endpoints'] or manifest['posterior_sha256']!=intent['posterior_sha256'] or len(manifest['fits'])!=64:raise ValueError('Postfit target/family differs')
 for row,expected in zip(manifest['fits'],intent['expected_fits']):
  if any(row.get(k)!=v for k,v in expected.items()):raise ValueError('Postfit selected/replaced a declared fit')

if __name__=='__main__':
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='action',required=True);prep=sub.add_parser('prepare')
 for key in ['fitting-plan','audit-path','out']:prep.add_argument('--'+key,required=True)
 prep.add_argument('--seed',type=int,required=True)
 for name in ['freeze','materialize','link']:sub.add_parser(name).add_argument('path')
 a=p.parse_args()
 if a.action=='prepare':prepare_intent(a.fitting_plan,a.audit_path,a.out,a.seed)
 elif a.action=='freeze':freeze_intent(a.path)
 elif a.action=='link':bind_execution(a.path)
 else:materialize(a.path)
