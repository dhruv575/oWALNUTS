from pathlib import Path
import json,hashlib,re,sys,math
s=Path('C:/dev/owalnuts/STUDIES/options_flow_v1');pfile=s/'artifacts/persistent-comparison-v1/run/plan-draft.json';p=json.loads(pfile.read_text());checks={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=json.loads(Path(p['seed_audit_path']).read_text());seeds=set(a['seeds']);hits=[]
for category in ['bound_files','study_bindings']:
 for f,h in p[category].items():checks[category+':'+f]=sha(f)==h
for f,h in a['inventory_files'].items():
 checks['seed_primary:'+f]=sha(f)==h
 for m in re.finditer(r'(?<![\w.])\d[\d_]*(?![\w.])',Path(f).read_text(encoding='utf-8-sig')):
  if int(m.group().replace('_','')) in seeds:hits.append([f,m.group()])
for f,h in a['supplemental_evidence'].items():
 checks['supplement:'+f]=sha(f)==h
 if 'refresh' in f:
  r=json.loads(Path(f).read_text());checks['refresh_clean']=r['status']=='passed' and not r['hits']
  for ff,hh in r['inventory_files'].items():checks['refresh:'+ff]=sha(ff)==hh
checks['primary_no_seed_hits']=not hits
checks['exact_14_streams']=seeds==set(range(106510001,106510007))|set(range(106640001,106640007))|{106380001,106380002}
checks['draft_not_qualified']=p['frozen'] is False and p['qualified'] is False
for i,f in enumerate(p['fixtures']):
 raw=json.loads(Path(f['path']).read_text());d=raw['data'];h=raw['holdout'];starts=d['initial_positions']
 checks[f'fixture{i}:starts']=starts==f['starts'] and len(starts)==4 and all(len(r)==140 and all(math.isfinite(x) for x in r) for r in starts) and len({tuple(r) for r in starts})==4
 checks[f'fixture{i}:observations']=sum(map(sum,d['observation_mask']))==[22,33][i]==f['observed_count']
 checks[f'fixture{i}:forecast']=f['forecast_cells']==[[1,i]] and h['y']==[[None]*4] and h['observation_mask']==[[False]*4]
sys.path.insert(0,str(s));from persistent_comparison_plan import validate_plan
validate_plan(p,pfile.parent);checks['production_recipe_archived_anchors_and_fixture_reconstruction']=True
out=dict(status='passed' if all(checks.values()) else 'failed',plan_sha256=sha(pfile),checks=checks,failed_checks=[k for k,v in checks.items() if not v],expected_processes=4,expected_fits=12,primary_inventory_count=len(a['inventory_files']),independent_seed_hits=hits,review_notes=['No blocking static issue identified. Fresh NumPyro warmup and new native session per posterior; fixed canonical starts reused across arms and A repeats. Native normalized parity is enforced before sampling.','All 140 canonical coordinates and 14 functionals gated; forecast horizon 1 groups 0/1 respectively are the explicit eligible families.','Whole cohort costs authoritative; first/later fit costs separated. All 12 planned fits retained, speed eligibility requires both full cohorts successful.','Primary 270 files rehashed and independently integer-token scanned. Original broad inventory hash-bound, not repeated; UTF8/dynamic arithmetic scope limitations preserved. Changed-file refresh hashes verified.','Development computational evidence only, not market accuracy or calibrated reliability.','Auditor initial validation call incorrectly passed plan file rather than directory and initial internal forecast check used zero-based horizon; both corrected before this audit artifact. No plan/source/outcomes changed.'],static_checks=dict(fresh_adaptation=True,native_parity_checked=True,within_fit_frozen_adaptation=True,source_before_after=True,returncode_before_postcheck=True,contained_cpu0_timeout=True))
with (pfile.parent/'independent-prefreeze-audit.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps({k:out[k] for k in ['status','plan_sha256','failed_checks','primary_inventory_count']}));print('checks',len(checks))
