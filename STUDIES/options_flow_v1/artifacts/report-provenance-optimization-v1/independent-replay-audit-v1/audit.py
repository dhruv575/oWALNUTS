"""Independent saved40 replay audit; no repeated raw-array content hashing."""
import json,hashlib,zipfile,math
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def main():
 checks=[]
 def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
 planpath=BASE/'saved-plan-v3.json';plan=read(planpath);out=Path(plan['out']);result=read(out/'result.json');hardware=read(BASE/'saved40-v2-hardware.json');records=read(out/'records.json');mapping=read(out/'archive-path-map.json')
 check('completed_result',result['status']=='completed' and result['exact_record_comparison_pass'] is True and result['differing_ids']==[] and result['expected']==40 and result['qualified'] is False and result['sampling_performed'] is False)
 check('plan_hash',result['plan_sha256']==sha(planpath))
 for path,h in plan['bindings'].items():check('live_binding:'+path,sha(path)==h)
 baseline=[r for path in plan['baseline_records'] for r in read(path)]
 intended=[cell['id'] for path in plan['manifests'] for cell in read(path)['cells']]
 check('baseline_exact40unique',len(baseline)==len({r['id'] for r in baseline})==40)
 check('result_exact40unique',len(records)==len({r['id'] for r in records})==40)
 check('intended_exact40unique',len(intended)==len(set(intended))==40)
 check('exact_ordered_all_record_equality',records==baseline and [r['id'] for r in records]==intended)
 check('actual_success_scope',all(r['usable'] and r['provenance_valid'] for r in records))
 expected_map={}
 for source in [dict(archive=plan['archive'],manifest=plan['archive_manifest']),*plan.get('supplemental_archives',[])]:
  manifest=read(source['manifest'])['files']
  with zipfile.ZipFile(source['archive']) as z:
   check('archive_members:'+source['archive'],set(z.namelist())==set(manifest))
   for relative,meta in manifest.items():
    check('archive_entry:'+relative,hashlib.sha256(z.read(relative)).hexdigest()==meta['sha256'])
    original=str((Path(plan['original_root'])/relative).resolve());expected_map[original.casefold()]=dict(original_path=original,archive=source['archive'],archive_entry=relative,sha256=meta['sha256'],git_blob_oid=meta.get('git_blob_oid'))
 check('archive_identity_mapping',mapping==expected_map)
 # Cross-check runner's raw pins against already independently recorded terminal
 # raw hashes. Do not reread these large arrays for this lightweight review.
 original_audit=Path(plan['original_root'])/'STUDIES/options_flow_v1/artifacts/demanding-calibration-screen-v1/independent-terminal-audit-v1/audit.json'
 prior=read(original_audit)['inventory'];prior={str(Path(p).resolve()).casefold():v for p,v in prior.items()}
 raw_count=0;raw_bytes=0
 for path,h in plan['original_artifacts'].items():
  if Path(path).name.endswith('-raw.json'):
   raw_count+=1;entry=prior.get(str(Path(path).resolve()).casefold());check('raw_pin_prior_audit:'+path,entry is not None and entry['sha256']==h and Path(path).stat().st_size==entry['bytes']);raw_bytes+=Path(path).stat().st_size
  else:check('compact_original_artifact:'+path,sha(path)==h)
 check('contained_completed',hardware['status']=='completed' and hardware['returncode']==0 and hardware['realized_cpus']==hardware['requested_cpus']==[0] and hardware['enforced_before_worker_launch'] is True and hardware['containment']['assigned_before_worker_execution'] is True and hardware['containment']['kill_on_job_close'] is True and hardware['containment']['breakaway_allowed'] is False and hardware['job_active_processes_after_cleanup']==0)
 command=hardware['command'];check('actual_command',Path(command[1]).resolve()==(BASE/'saved_alternate.py').resolve() and command[2]=='--plan' and Path(command[3]).resolve()==planpath.resolve() and Path(command[0]).name=='python.exe')
 stages=result['stages'];check('cost_enclosure',all(math.isfinite(v) and v>=0 for v in stages.values()) and sum(stages.values())<=result['seconds_including_admission_and_checks']<=hardware['elapsed_seconds']<plan['resource_policy']['timeout_seconds']==1800)
 check('explicit_cpu_scope',plan['resource_policy']['cpus']==[0])
 evidence=dict(integrity_pass=all(x['passed'] for x in checks),checks=checks,expected=40,exact_record_equality=records==baseline,inner_seconds=result['seconds_including_admission_and_checks'],wrapper_seconds=hardware['elapsed_seconds'],normalization_transaction_seconds=stages['normalization_transaction_seconds'],raw_pin_count=raw_count,raw_pin_bytes=raw_bytes,raw_hash_scope='Raw hashes cross-checked against earlier independent terminal audit and present sizes; this audit does not repeat raw content hashes. Executed runner verified all original-artifact content before/after, and live runner/source/plan hashes are checked here.',timing_scope='Posthoc saved-output replay: includes archive resolution and extra raw pre/post hashing; excludes original coverage-summary generation. Inner timer excludes module imports. Not a matched isolated-normalization or sampler benchmark.',failure_scope='All40 original records usable: equality is evidence for these successful outputs; failure behavior relies on separate tests.',qualified=False,bindings={str(p):sha(p) for p in [planpath,out/'result.json',out/'records.json',out/'archive-path-map.json',BASE/'saved40-v2-hardware.json',Path(__file__),original_audit]})
 destination=Path(__file__).with_name('result.json')
 with destination.open('x') as f:json.dump(evidence,f,indent=2,allow_nan=False)
 print(json.dumps(dict(integrity_pass=evidence['integrity_pass'],checks=len(checks),failed=[x for x in checks if not x['passed']],wrapper_seconds=hardware['elapsed_seconds'],raw_pin_count=raw_count)))
if __name__=='__main__':main()
