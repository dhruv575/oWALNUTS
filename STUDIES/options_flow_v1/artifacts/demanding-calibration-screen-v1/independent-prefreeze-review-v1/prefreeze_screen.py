"""Independent concrete demanding screen review; no freeze or inference."""
import sys,json,hashlib,re,math,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];STUDY=ROOT/'STUDIES/options_flow_v1';sys.path.insert(0,str(STUDY))
import production_calibration_feasibility as c
from model import simulate
from production_calibration_adapter import fixture_contract,select_truth
BASE=STUDY/'artifacts/demanding-calibration-screen-v1';RUN=BASE/'run-v2';PREP=BASE/'preparation-v2'
def main(out):
 checks=[]
 def check(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
 plan=c.load(RUN/'plan-draft.json');intent=c.load(RUN/'recipe-intent.json');protocol=c.load(RUN/'protocol.json');spec=c.load(PREP/'screen-spec.json');audit=c.load(PREP/'seed-audit.json');broad=c.load(PREP/'historical-audit.json')
 check('draft_only',plan['frozen'] is False and not (RUN/'plan.json').exists())
 check('all40',plan['expected']==40 and len(plan['ordered'])==40 and len({x['id'] for x in plan['ordered']})==40)
 check('fixed_scope',spec['models']==['flow'] and spec['count']==32 and spec['periods']==1000 and spec['groups']==4 and spec['reference_indices']==list(range(0,32,4)))
 check('resource_limits',plan['timeout_seconds']==spec['timeout_seconds']==1800 and plan['total_seconds']==spec['total_seconds']==21600 and plan['minimum_free_bytes']==spec['minimum_free_bytes']==12*1024**3)
 check('pregeneration_intent',intent['screen_spec']==spec and protocol['intent_sha256']==c.sha(RUN/'recipe-intent.json') and c.object_digest(protocol)==plan['protocol_sha256'])
 check('144streams',len(c.seed_inventory(spec['seed_rows'],True))==144 and len(set(c.seed_inventory(spec['seed_rows'],True)))==144)
 seeds=set(c.seed_inventory(spec['seed_rows'],True));check('exact_audited_roles',set(audit['seeds'])==set(broad['seeds'])==seeds and audit['hits']==broad['hits']==[] and audit['status']==broad['status']=='passed')
 check('supplement_hash',audit['supplemental_evidence']['sha256']==c.sha(audit['supplemental_evidence']['path']))
 token=re.compile(r'(?<![\w.])\d[\d_]*(?![\w.])');hits=[]
 for path,h in broad['inventory_files'].items():
  raw=Path(path).read_bytes();check('historical_hash:'+path,hashlib.sha256(raw).hexdigest()==h)
  text=raw.decode('utf-16' if raw[:2] in (b'\xff\xfe',b'\xfe\xff') else 'utf-8-sig')
  found={int(m.group().replace('_','')) for m in token.finditer(text)}&seeds
  if found:hits.append(dict(path=path,seeds=sorted(found)))
 check('independent_literal_scan',not hits,hits)
 proposal=[x for x in broad['excluded'] if 'sha256' in x]
 check('only_two_proposal_exemptions',{Path(x['path']).name for x in proposal}=={'prepare.py','staged_prepare.py'})
 for e in proposal:check('proposal_hash:'+e['path'],c.sha(e['path'])==e['sha256'])
 prior=broad['prior_inventory'];check('prior_inventory_hash',c.sha(prior['path'])==prior['sha256']);previous=c.load(prior['path']);reserved=previous['prior_reserved'];check('prior_reserved_hash',c.sha(reserved['path'])==reserved['sha256']);reserved_values=c.load(reserved['path'])['reserved_seeds'];check('explicit_allocated_history',not seeds.intersection(reserved_values))
 # Verify every source/runtime/input bound by the actual draft, then its runtime.
 c.verify(plan);check('controller_full_binding_runtime_verifier',True)
 manifests={key:c.load(RUN/(key+'-manifest-draft.json')) for key in plan['manifest_keys']}
 check('two_procedures',set(manifests)=={'flow-public','flow-reference'})
 actual_order=[];start_hashes=[]
 for row in spec['seed_rows']:
  i=row['index'];fp=RUN/'fixtures'/f'flow-{i:02d}.json';fixture=c.load(fp);regenerated=c.initialize(simulate(row['dataset_seed'],periods=1000,groups=4,holdout=1,prior=True),'flow',row['init_seed'])
  check(f'fixture_exact_regeneration:{i}',fixture==regenerated)
  contract=fixture_contract(fixture,'flow');check(f'1012x4_starts:{i}',contract['dimension']==1012 and len(contract['starts'])==4)
  start_hashes.append(c.object_digest(contract['starts']))
  altered=dict(fixture,truth=[0.]*1012,holdout=dict(fixture['holdout'],y=[[123.]*4]));check(f'truth_outcome_independent_starts:{i}',c.initialize(altered,'flow',row['init_seed'])['data']['initial_positions']==contract['starts'])
  kinds=['public'] if i%4 else (['reference','public'] if (i//4)%2==0 else ['public','reference'])
  for kind in kinds:
   m=manifests['flow-'+kind];proc=m['procedure'];identity=f'flow-{i:02d}-{kind}';cell=next(x for x in m['cells'] if x['id']==identity);actual_order.append(dict(manifest='flow-'+kind,id=identity))
   chain=row['chain_seed'] if kind=='public' else row['reference_chain_seed'];prediction=row['predictive_seed'] if kind=='public' else row['reference_predictive_seed']
   check(identity+':streams',cell['chain_seed']==chain and cell['predictive_seed']==prediction==chain+130000 and cell['init_seed']==row['init_seed'] and cell['dataset_seed']==row['dataset_seed'])
   check(identity+':same_fixture_truth',Path(cell['fixture_path']).resolve()==fp.resolve() and cell['fixture_sha256']==c.sha(fp) and cell['truth']==select_truth(contract,m['selectors']) and len(m['selectors'])==18)
   check(identity+':procedure',proc['coordinates']=='mixed_slopes' and proc['chains']==4 and proc['warmup']==1000 and proc['tiers']==[1000,2000,4000,8000] and proc['relative_mcse']==.02 and proc['timeout_seconds']==1800 and proc['cpus']==[0] and m['procedure_sha256']==c.object_digest(proc)==protocol['procedures']['flow-'+kind])
   check(identity+':backend',proc.get('block_size')==32 if kind=='public' else proc.get('implementation')=='associative' and proc['target_accept']==.9 and proc['batch_size']==1000)
   expected=c.worker_command(plan['python'],'flow',kind,'mixed_slopes',cell['fixture_path'],cell['output_directory'],chain,proc.get('implementation'));check(identity+':command',cell['worker_command']==expected)
   for k in ('output_directory','status_path','hardware_path','started_path'):check(identity+':unstarted:'+k,not Path(cell[k]).exists())
 check('exact_alternating_order',actual_order==plan['ordered']==protocol['ordered'])
 check('32different_initializations',len(set(start_hashes))==32)
 check('32and8',len(manifests['flow-public']['cells'])==32 and len(manifests['flow-reference']['cells'])==8)
 storage=c.load(PREP/'storage-review.json');free=shutil.disk_usage(RUN).free
 check('honest_storage_scope',storage['fullcohort_storage_guaranteed'] is False and storage['canonical_raw_envelope_bytes']==40*4*15000*1012*46 and plan['minimum_free_bytes']==storage['minimum_free_bytes'])
 check('initial_space_admissible',free>=plan['minimum_free_bytes'])
 result=dict(integrity_pass=all(x['passed'] for x in checks),checks=checks,plan_sha256=c.sha(RUN/'plan-draft.json'),observed_free_bytes=free,storage_scope='12GiB per-worker admission only; no full-cohort guarantee or reserved capacity. All skipped outcomes remain unresolved.',qualified=False,scope='Prospective40cell resource/failure screen, no calibration qualification; no freeze or sampling by auditor',auditor_sha256=c.sha(__file__))
 with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps(dict(integrity_pass=result['integrity_pass'],checks=len(checks),failed=[x for x in checks if not x['passed']],plan_sha256=result['plan_sha256'])))
if __name__=='__main__':main(sys.argv[1])
