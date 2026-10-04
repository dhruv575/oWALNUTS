from pathlib import Path
import json,hashlib,sys,re,importlib.metadata
ROOT=Path('C:/dev/owalnuts/STUDIES/options_flow_v1')
D=ROOT/'artifacts/correlated-reference-study-v1'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=load(D/'plan-draft.json');a=load(p['seed_audit']['path']);checks={}
checks['pinned_draft']=sha(D/'plan-draft.json')=='a09be1246fbf4722289f11a0577d2830cfec275d47bea474393e0af77912c97c'
checks['pinned_inventory']=sha(p['seed_audit']['path'])==p['seed_audit']['sha256']=='ce0dd7a02663b16e2d22d119ad4063747b993847d83c4e7764f31e6d0b32b281'
streams=[x for c in p['cells'] for x in c['fit_seeds']+c['init_seeds']+[c['bootstrap_seed']]]
checks['exact_3612_streams']=streams==a['candidate_seeds']==list(range(1970000000,1970003612))
checks['no_reserved_overlap']=not(set(streams)&set(a['reserved_seeds']))
for f,h in a['inventory_files'].items():checks['inventory:'+f]=sha(f)==h
for n,h in p['source'].items():checks['source:'+n]=sha(ROOT/n)==h
for f,h in p['own_source'].items():checks['own_source:'+f]=sha(f)==h
checks['python']=sha(p['python'])==p['python_sha256']
checks['runtime']=p['runtime']=={n:importlib.metadata.version(n) for n in ['numpy','scipy']}
configs=[('sentinel',r,s,i) for i,(r,s) in enumerate([(0.,0.),(.9,0.),(.9,.1),(.9,.5)])]+[('main',r,s,i) for r,s,count in [(.9,0.,12),(0.,0.,4),(.9,.1,4),(.9,.5,4)] for i in range(count)]
checks['all_28_configs']=len(p['cells'])==28 and all(c['id']==f'{phase}-rho{rho}-shift{shift}-{i}' and c['phase']==phase and c['rho']==rho and c['backend_b_shift']==shift and c['fits_per_backend']==32 and c['lengths']==[4096,8192] for c,(phase,rho,shift,i) in zip(p['cells'],configs))
checks['draft_only']=p['frozen'] is False and p['qualified'] is False
sys.path.insert(0,str(ROOT));from correlated_reference_study import validate,verify
validate(p);verify(p,require_frozen=False);checks['production_validation']=True
out=dict(status='passed' if all(checks.values()) else 'failed',draft_sha256=sha(D/'plan-draft.json'),checks=checks,failed_checks=[k for k,v in checks.items() if not v],unique_streams=len(set(streams)),intended_cells=28,main_cells=24,scope=['Independent exact stream/schedule/hash checks plus reviewed production strict statistical/resource validation.','Primary8192/paired4096 with1024 descriptive only;32 independent paths/backend;30k bootstrap; unchanged .02 agreement/.1 uncertainty and length gates.','Four worst-case sentinels then4x max-fullworker projection;3600s total with15s cleanup reserve,2GiB nested memory job,CPU0 contained workers. All failed/unattempted cells retained.','Prior inventory and repository-wide audit are immutable hash-bound evidence; their original declared scope limitations are preserved. No new exhaustive repository scan claimed.','Gaussian AR indicator covariance finite-N calculation is independent; quantile delta covariance is approximate. Exploratory progression, no posterior accuracy or calibration claim.'],static_containment_review=dict(existing_hardware_validator=True,exit_saved_before_postverification=True,no_outer_unsafe_timeout=True,no_retry_existing_output=True,final_integrity_check=True))
with (D/'independent-prefreeze-audit.json').open('x') as f:json.dump(out,f,indent=2)
copy=D/'independent-prefreeze-auditor.py'
with copy.open('xb') as f:f.write(Path(__file__).read_bytes())
with (D/'independent-prefreeze-provenance.json').open('x') as f:json.dump(dict(auditor_sha256=sha(copy),result_sha256=sha(D/'independent-prefreeze-audit.json'),draft_sha256=out['draft_sha256'],interpreter_sha256=sha(sys.executable),source=p['source'],own_source=p['own_source']),f,indent=2)
print(json.dumps(dict(status=out['status'],checks=len(checks),failures=out['failed_checks'],streams=len(set(streams)))))
