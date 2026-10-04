"""Posthoc saved-output comparison only. Never imports or invokes a sampler."""
import argparse,copy,hashlib,json,os,sys,time,zipfile
from pathlib import Path
R=Path(__file__).resolve().parents[2];S=R/'STUDIES/options_flow_v1';sys.path.insert(0,str(S))
import production_calibration_adapter as adapter
from cohort_validation import normalize_cohort

def sha(p):return adapter.digest(p)
def load(p):return adapter.load(p)
def save(p,x):
 with Path(p).open('x',encoding='utf8') as f:json.dump(x,f,indent=2,allow_nan=False)
def verify(bindings):
 for p,h in bindings.items():
  if sha(p)!=h:raise ValueError('Pinned alternate-analysis input changed: '+p)
def run(plan_path):
 tick=time.perf_counter();plan=load(plan_path);original=sha(plan_path);out=Path(plan['out']);out.mkdir(parents=True,exist_ok=False)
 result=dict(status='failed',qualified=False,posthoc=True,sampling_performed=False,plan_sha256=original,stages={});counts={'live_hashes':0,'archive_hashes':0}
 try:
  before=time.perf_counter();verify(plan['bindings']);verify(plan['original_artifacts']);result['stages']['input_validation_seconds']=time.perf_counter()-before
  archived={};mapping={}
  archives=[dict(archive=plan['archive'],manifest=plan['archive_manifest']),*plan.get('supplemental_archives',[])]
  for source in archives:
   archive_manifest=load(source['manifest'])['files']
   with zipfile.ZipFile(source['archive']) as z:
    if set(z.namelist())!=set(archive_manifest):raise ValueError('Archive membership mismatch')
    for relative,item in archive_manifest.items():
     raw=z.read(relative)
     if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Archive entry hash mismatch')
     original_path=str((Path(plan['original_root'])/relative).resolve());key=os.path.normcase(original_path)
     if key in archived and archived[key]!=raw:raise ValueError('Conflicting archived source identity')
     archived[key]=raw;mapping[key]=dict(original_path=original_path,archive=source['archive'],archive_entry=relative,sha256=item['sha256'],git_blob_oid=item.get('git_blob_oid'))
  manifests=[load(p) for p in plan['manifests']];baseline=[row for p in plan['baseline_records'] for row in load(p)]
  by_id={r['id']:r for r in baseline};owners={};cells=[]
  for m in manifests:
   adapter.validate_manifest(m)
   for c in m['cells']:
    if c['id'] in owners:raise ValueError('Duplicate intended id')
    owners[c['id']]=m;cell=dict(c);cell['record_template']=copy.deepcopy(by_id[c['id']]);cell['known_cost']=copy.deepcopy(by_id[c['id']]['cost']);cells.append(cell)
  if len(cells)!=40 or set(owners)!=set(by_id):raise ValueError('Exact original40 outcome family required')
  # Original identities remain intact. Only archived-source paths resolve to their
  # verified historical bytes; nonarchived runtime/history inputs remain live-hashed.
  def historical_hash(path):
   key=os.path.normcase(str(Path(path).resolve()))
   if key in archived:counts['archive_hashes']+=1;return hashlib.sha256(archived[key]).hexdigest()
   counts['live_hashes']+=1;return sha(path)
  expected=[entry['original_path'] for entry in mapping.values() if entry['original_path'].lower().endswith('.py')]
  allbound={os.path.normcase(str(Path(p).resolve())) for m in manifests for p in m['procedure']['bound_files']}
  expected=[p for p in expected if os.path.normcase(p) in allbound]
  if not expected:raise ValueError('No archived bound source inventory')
  def inventory():
   # Archive identity itself is checked pre/post, including additions/removals.
   verify({p:plan['bindings'][p] for source in archives for p in (source['archive'],source['manifest'])})
   return expected
  before=time.perf_counter()
  transaction=normalize_cohort(cells,[m['procedure']['bound_files'] for m in manifests],lambda c,ctx:adapter.normalize_cell(owners[c['id']],c,shared_context=ctx),inventory,expected,historical_hash)
  result['stages']['normalization_transaction_seconds']=time.perf_counter()-before
  if not transaction['shared_validation_passed']:raise ValueError(transaction['shared_error'])
  differences=[row['id'] for row in transaction['records'] if row!=by_id[row['id']]]
  result.update(exact_record_comparison_pass=not differences,differing_ids=differences,expected=40,hash_counts=counts)
  if differences:raise ValueError('Normalized scientific/failure/cost/provenance record mismatch')
  before=time.perf_counter();verify(plan['bindings']);verify(plan['original_artifacts'])
  for row in baseline:
   for path,h in row['normalization']['artifact_sha256'].items():
    if sha(path)!=h:raise ValueError('Original artifact drift')
  if sha(plan_path)!=original:raise ValueError('Alternate plan drift')
  result['stages']['final_validation_seconds']=time.perf_counter()-before
  save(out/'records.json',transaction['records']);save(out/'archive-path-map.json',mapping);result['status']='completed'
 except Exception as exc:result.update(error=f'{type(exc).__name__}: {exc}',exact_record_comparison_pass=False)
 finally:
  result['seconds_including_admission_and_checks']=time.perf_counter()-tick;save(out/'result.json',result)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',type=Path,required=True);a=p.parse_args();raise SystemExit(0 if run(a.plan)['status']=='completed' else 1)
