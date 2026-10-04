from pathlib import Path
import json,hashlib,re,sys
S=Path('C:/dev/owalnuts/STUDIES/options_flow_v1').resolve();D=(S/'artifacts/posterior-resource-pilot-v1').resolve()
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=load(D/'plan-draft.json');checks={}
for k,h in p['bindings'].items():checks['binding:'+k]=sha(k)==h
for k,h in p['package_inventory'].items():checks['package:'+k]=sha(k)==h
auditpath=next(Path(k) for k in p['bindings'] if Path(k).name=='posterior-resource-seed-audit-v3.json');a=load(auditpath)
seeds=[r[k] for r in p['streams'] for k in ['init_seed','seed','predictive_seed']]
checks['exact12streams']=seeds==a['seeds'] and len(set(seeds))==12
checks['unused']=not(set(seeds)&set(a['reserved_seeds'])) and a['hits']==[]
checks['reserve_failed197']=set(range(1970000000,1970003612))<=set(a['reserved_seeds'])
hits=[]
for path,h in a['inventory_files'].items():
 checks['inventory:'+path]=sha(path)==h
 for m in re.finditer(r'(?<![\w.])\d[\d_]*(?![\w.])',Path(path).read_text(encoding='utf-8-sig')):
  if int(m.group().replace('_','')) in set(seeds):hits.append([path,m.group()])
checks['independent_primary_no_hits']=not hits
for path,h in a['supplemental_evidence'].items():checks['supplement:'+path]=sha(path)==h
sys.path.insert(0,str(S));from posterior_resource.controller import validate,posterior
validate(p,D);checks['strict_recipe_runtime_start_reconstruction']=True
checks['draft_unqualified']=p['frozen'] is False and p['qualified'] is False and p['resource_only'] is True
original=load(p['original_fixture']);checks['posterior_identity']=posterior(original)==p['posterior_sha256']
checks['independent_start_sets']=len({json.dumps(load(c['fixture'])['data']['initial_positions']) for c in p['cells']})==4
v=load(D/'validation/validation.json');checks['49_tests_record']=v['status']=='passed' and v['tests']==49 and v['sampling'] is False
checks['test_source']=sha(D/'validation/test_entrypoint.py.txt')==v['test_source_sha256']
h=load(D/'validation/contained-cli/hardware.json');r=load(D/'validation/contained-cli/contained/resource-result.json')
checks['contained_actual_module']=h['command'][1:3]==['-m','posterior_resource.resource_worker'] and h['status']=='worker-failed' and h['returncode']==2 and h['job_active_processes_after_cleanup']==0 and h['realized_cpus']==[0] and h['containment']['assigned_before_worker_execution'] is True
checks['charged_admission_failure']=r['status']=='failed' and 'Unexpected memory policy' in r['error'] and r['last_phase']=='admission' and r['worker_seconds_before_final_report']>0 and not (D/'validation/contained-cli/contained/fit').exists()
out=dict(status='passed' if all(checks.values()) else 'failed',draft_sha256=sha(D/'plan-draft.json'),checks=checks,failed_checks=[k for k,v in checks.items() if not v],seed_inventory_count=len(a['inventory_files']),reserved_seed_count=len(a['reserved_seeds']),independent_primary_hits=hits,scope=['Four independent actual posterior fits, two/backend; fixed8k with dependent4k prefixes, not time-to-first-pass comparison.','Fresh independent physical starts per fit; common posterior and full1012coordinate/14functional/4forecast gates. No calibration or resolved reference-bank claim.','Contained CLI test proves module routing and charged failure cleanup only; it deliberately fails before numerical admission and does not prove full sampler/extraction completion. Existing serialized report/extraction tests support those contracts.','Nested package inventory separately bound from legacy fit-report top-level worker bindings. All extraction, diagnostics and predictive-CDF work is within1800s/cell and7200s overall with15s reserve;8GiB process memory cap.','263 primary files independently rescanned; broad49118-file supplemental evidence hash-bound rather than rerun; original scope limitations retained.'])
with (D/'independent-prefreeze-audit.json').open('x') as f:json.dump(out,f,indent=2)
copy=D/'independent-prefreeze-auditor.py'
with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
with (D/'independent-prefreeze-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),result_sha256=sha(D/'independent-prefreeze-audit.json'),draft_sha256=out['draft_sha256'],runtime=p['runtime'],package_inventory=p['package_inventory']),f,indent=2)
print(json.dumps(dict(status=out['status'],checks=len(checks),failed=out['failed_checks'],draft_sha256=out['draft_sha256'])))
