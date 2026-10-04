"""Independent terminal demanding-screen audit; no new inference or reruns."""
import sys,json,hashlib,math,collections,importlib.util
from pathlib import Path
import numpy as np
from scipy.stats import beta
ROOT=Path(__file__).resolve().parents[2];STUDY=ROOT/'STUDIES/options_flow_v1';sys.path.insert(0,str(STUDY))
import production_calibration_feasibility as c
from production_calibration_adapter import raw_tail
from asof_rolling_execute import validate_hardware,validate_checkpoint_continuity
from flow_mixed_coordinates import to_mixed
from model import functionals
spec=importlib.util.spec_from_file_location('independent_previous_gate',ROOT/'target/posterior-bank-prelaunch-review/terminal_audit.py');previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
BASE=STUDY/'artifacts/demanding-calibration-screen-v1';RUN=BASE/'run-v2'
def main(out):
 checks=[];inventory={};rows=[];summary={}
 def check(name,ok,detail=None):checks.append(dict(name=name,passed=bool(ok),detail=detail))
 def bind(path,expected=None):
  path=str(Path(path).resolve())
  if path not in inventory:inventory[path]=dict(sha256=c.sha(path),bytes=Path(path).stat().st_size)
  if expected is not None:check('artifact_hash:'+path,inventory[path]['sha256']==expected)
  return inventory[path]['sha256']
 plan=c.load(RUN/'plan.json');timing=c.load(RUN/'execution-timing.json');report_time=c.load(RUN/'report-timing.json')
 check('frozen_plan',plan['frozen'] and c.sha(RUN/'plan.json')==(RUN/'plan.sha256').read_text().strip());c.verify(plan);check('all_current_source_runtime_fixture_bindings',True)
 for name in ('plan.json','execution-timing.json','report-timing.json','recipe-intent.json','protocol.json'):bind(RUN/name)
 for path,h in plan['manifests'].items():bind(path,h)
 total_controller=0
 for kind in ('public','reference'):
  manifest=c.load(RUN/f'flow-{kind}-manifest.json');records=c.load(RUN/f'flow-{kind}-normalized.json');coverage=c.load(RUN/f'flow-{kind}-coverage.json');mapping={r['id']:r for r in records};expected=32 if kind=='public' else 8;intervals=[];truths=[];tiers=[]
  for name in (f'flow-{kind}-normalized.json',f'flow-{kind}-coverage.json'):bind(RUN/name)
  check(kind+':full_denominator',len(records)==len(mapping)==len(manifest['cells'])==expected and set(mapping)=={cell['id'] for cell in manifest['cells']})
  for cell in manifest['cells']:
   identity=cell['id'];record=mapping[identity]
   try:
    status=c.load(cell['status_path']);hardware=c.load(cell['hardware_path']);marker=c.load(cell['started_path']);fixture=c.load(cell['fixture_path']);directory=Path(cell['output_directory']);rp=directory/('python-pymc-flow-report.json' if kind=='public' else 'report.json');r=c.load(rp)
    for path,h in record['normalization']['artifact_sha256'].items():bind(path,h)
    bind(rp,record['original_report_sha256']);bind(cell['hardware_path'],status['hardware_sha256']);bind(cell['fixture_path'],cell['fixture_sha256'])
    check(identity+':completed',status['status']=='worker_terminal' and status['returncode']==hardware['returncode']==0 and hardware['status']=='completed')
    command=[plan['python'],str(STUDY/'hardware_control.py'),'--cpus','0','--record',cell['hardware_path'],'--timeout',str(plan['timeout_seconds']),'--',*cell['worker_command']]
    validate_hardware(hardware,command,status['returncode'],plan['timeout_seconds']);check(identity+':hardware',True)
    check(identity+':storage',status['storage_admission']==marker['storage_admission'] and status['storage_admission']['passed'] is True and status['storage_admission']['observed_free_bytes']>=status['storage_admission']['minimum_free_bytes']==12*1024**3)
    check(identity+':marker',all(marker[k]==v for k,v in dict(protocol_sha256=plan['protocol_sha256'],procedure_sha256=manifest['procedure_sha256'],fixture_sha256=cell['fixture_sha256'],dataset_seed=cell['dataset_seed']).items()))
    sources={str(Path(k).resolve()).casefold():v for k,v in r['bindings'].items()};check(identity+':sources',all(sources.get(str(Path(k).resolve()).casefold())==v for k,v in plan['study_bindings'].items()) and sources.get(str(Path(cell['fixture_path']).resolve()).casefold())==cell['fixture_sha256'])
    check(identity+':streams_starts',r['seed']==cell['chain_seed'] and r['predictive_seed']==cell['predictive_seed'] and r['initial_positions']==fixture['data']['initial_positions'])
    check(identity+':parity',r['parity']['passed'] is True)
    attempts=r['attempts'];counts=[a['draws'] for a in attempts];check(identity+':tier_sequence',counts==[1000,2000,4000,8000][:len(counts)])
    passes=[];last_checkpoints=[];calls=r.get('warmup_target_calls',0)
    for attempt in attempts:
     n=attempt['draws'];fp=directory/f'draws-{n}'/'fit-report.json' if kind=='public' else directory/f'draws-{n}-report.json';raw=directory/f'draws-{n}'/'python-pymc-flow-raw.json' if kind=='public' else directory/f'draws-{n}-raw.json';fit=c.load(fp);bind(fp);bind(raw)
     passed,ratio=previous.gate(fit);passes.append(passed);check(identity+f':gate{n}',passed==attempt['screen']['pass'] and math.isclose(ratio,attempt['screen']['max_endpoint_mcse_over_width'],rel_tol=1e-12))
     check(identity+f':raw_starts{n}',raw_tail(raw,'initial_positions')==fixture['data']['initial_positions'] and raw_tail(raw,'sampling_initial_positions')==to_mixed(np.asarray(fixture['data']['initial_positions']),fixture['data']).tolist())
     if kind=='public':
      calls+=attempt['added_target_calls'];check(identity+f':state{n}',raw_tail(raw,'adapted_metadata')==r['adapted_metadata'] and calls==attempt['cumulative_target_calls'])
     else:
      points=fit['checkpoints'];validate_checkpoint_continuity(points);check(identity+f':state{n}',len(points)==n//1000 and points[:len(last_checkpoints)]==last_checkpoints);last_checkpoints=points
    final,ratio=previous.gate(r);check(identity+':firstpass',passes==[False]*(len(passes)-1)+[True] and final and r['precision_pass'] and r['draws']==counts[-1]);check(identity+':selected_output',r['evaluation']==fit['evaluation'] and r['retained_divergences']==fit['retained_divergences'])
    if kind=='public':check(identity+':final_calls',calls==r['total_target_calls']==r['session_progress_before_close']['target_calls'])
    else:check(identity+':final_checkpoints',r['checkpoints']==last_checkpoints)
    vals={k:float(v) for k,v in functionals(np.asarray(fixture['truth']),4).items()};truth={};selected={}
    for selector in manifest['selectors']:
     name=selector['name']
     if selector['kind']=='functional':truth[name]=vals[selector['key']];selected[name]=r['evaluation']['functionals'][selector['key']]['interval_90']
     else:
      h,g=selector['horizon'],selector['group'];truth[name]=fixture['holdout']['y'][h-1][g];forecast=next(x for x in r['evaluation']['forecast']['rows'] if (x['horizon'],x['group'])==(h,g));selected[name]=[forecast['lower'],forecast['upper']];check(identity+':actual_forecast:'+name,forecast['observed']==truth[name])
    check(identity+':truth_intervals',all(math.isclose(truth[n],record['truth'][n],rel_tol=1e-12,abs_tol=1e-12) for n in truth) and selected==record['intervals'])
    check(identity+':normalization',record['usable'] and record['provenance_valid'] and not record['normalization']['errors'])
    seconds=status['elapsed_seconds'];total_controller+=seconds;check(identity+':cost',seconds==record['cost']['controller_seconds']>=hardware['elapsed_seconds']==record['cost']['wrapper_seconds']>=record['cost']['worker_seconds']>=r['end_to_end_seconds'])
    intervals.append(selected);truths.append(truth);tiers.append(counts[-1]);rows.append(dict(id=identity,usable=True,draws=counts[-1],controller_seconds=seconds,max_endpoint_ratio=ratio))
   except Exception as e:check(identity+':complete_evidence',False,f'{type(e).__name__}: {e}');rows.append(dict(id=identity,error=str(e)))
  alpha=manifest['alpha']/manifest['family_size'];hits={}
  for selector in manifest['selectors']:
   name=selector['name'];hit=sum(bounds[name][0]<=truth[name]<=bounds[name][1] for bounds,truth in zip(intervals,truths));hits[name]=hit
   ci=[0 if hit==0 else float(beta.ppf(alpha/2,hit,expected-hit+1)),1 if hit==expected else float(beta.ppf(1-alpha/2,hit+1,expected-hit))];entry=coverage['selectors'][name]
   check(kind+':coverage:'+name,entry['usable_and_covering']==hit and entry['intended']==entry['usable']==expected and entry['conditional_coverage']==entry['unconditional_usable_and_covering_rate']==hit/expected and np.allclose(entry['conditional_simultaneous_ci'],ci,rtol=1e-12) and np.allclose(entry['unconditional_simultaneous_ci'],ci,rtol=1e-12))
  check(kind+':descriptive_only',coverage['qualified'] is False and coverage['record_integrity_pass'] is True and coverage['intended']==coverage['usable']==expected and coverage['coverage_component_meets_prespecified_rule'] is False and math.isclose(coverage['reliability_lower'],alpha**(1/expected),rel_tol=1e-12))
  summary[kind]=dict(intended=expected,usable=len(intervals),tier_counts=dict(collections.Counter(tiers)),coverage_hits=hits)
 check('all40_preserved',len(rows)==40 and len({r['id'] for r in rows})==40)
 check('total_costs',total_controller<=timing['seconds'] and report_time['execution_seconds']==timing['seconds'] and math.isclose(report_time['combined_execution_and_report_seconds'],timing['seconds']+report_time['report_seconds'],abs_tol=1e-8) and report_time['combined_execution_and_report_seconds']<=21600)
 check('no_unresolved',timing['unstarted_count']==timing['storage_skipped']==timing['budget_skipped']==0 and timing['total_budget_unresolved'] is False and report_time['resource_inference_unresolved'] is False and report_time['integrity_issue_count']==0)
 result=dict(integrity_pass=all(x['passed'] for x in checks),checks=checks,rows=rows,summary=summary,execution_seconds=timing['seconds'],report_seconds=report_time['report_seconds'],combined_seconds=report_time['combined_execution_and_report_seconds'],inventory=inventory,hashed_artifact_bytes=sum(v['bytes'] for v in inventory.values()),qualified=False,scope='Fresh T1000/G4 resource screen only; full gates and descriptive coverage independently checked. No powered coverage equivalence/calibration claim; public raw hashes first inventoried here, reference raw hashes also matched normalization evidence.',auditor_sha256=c.sha(__file__))
 with Path(out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
 print(json.dumps(dict(integrity_pass=result['integrity_pass'],checks=len(checks),failed=[x for x in checks if not x['passed']],summary=summary,hashed_artifact_bytes=result['hashed_artifact_bytes'])))
if __name__=='__main__':main(sys.argv[1])
