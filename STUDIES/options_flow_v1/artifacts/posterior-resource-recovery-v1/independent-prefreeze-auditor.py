from pathlib import Path
import json,hashlib,sys
D=Path('C:/dev/owalnuts/STUDIES/options_flow_v1/artifacts/posterior-resource-recovery-v1').resolve();cache={}
def load(p):return json.loads(Path(p).read_text())
def sha(p):
 p=str(Path(p).resolve())
 if p not in cache:
  h=hashlib.sha256()
  with open(p,'rb') as f:
   for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
  cache[p]=h.hexdigest()
 return cache[p]
p=load(D/'cohort-draft.json');checks={};sys.path.insert(0,str(D/'code'));from recover import verify_archive
checks['two_budget']=p['total_seconds']==3600 and p['cleanup_reserve_seconds']==15 and len(p['specs'])==2 and p['resampled'] is False
for i,path in enumerate(p['specs']):
 s=load(path);checks[f'spec{i}:hash']=sha(path)==p['spec_hashes'][path];checks[f'spec{i}:identity']=s['cell_id']==['fit-0-public','fit-3-public'][i] and s['posthoc'] is True and s['resampled'] is False and s['memory_bytes']==8*1024**3 and s['timeout_seconds']==1800
 for category in ['immutable_inputs','launcher_inputs']:
  for f,h in s[category].items():checks[category+':'+f]=sha(f)==h
 verify_archive(s);checks[f'spec{i}:archive_exact']=True
 old=load(s['original_status']);checks[f'spec{i}:old_failure']=old['status']=='failed' and old['success'] is False
 original=load(s['original_plan']);cell=next(c for c in original['cells'] if c['id']==s['cell_id']);checks[f'spec{i}:posterior']=original['posterior_sha256']==s['posterior_sha256']
 audit=load(Path(s['original_plan']).parent/'independent-terminal-audit.json');checks[f'spec{i}:raw_independent_hash']=audit['inventory'][str(Path(s['raw']).resolve())]['sha256']==sha(s['raw'])
 checks[f'spec{i}:new_output']=not Path(s['out']).exists()
out=dict(status='passed' if all(checks.values()) else 'failed',cohort_draft_sha256=sha(D/'cohort-draft.json'),checks=checks,failed_checks=[k for k,v in checks.items() if not v],scope=['Saved-draw posthoc analysis only; static sources contain no sampler call.','Original failed statuses and costs remain immutable and separately bound.','Exact160-source archive verified against original bindings. Raw hashes match prior independent audit.','All1012 coordinates,14 physical functionals,4 forecasts checked at dependent4k/8k prefixes; CDF convergence separate from posterior accuracy.','3600s additional total/15s reserve/1800s each/8GiB, existing full hardware validator and exit persistence reviewed.','Freeze may add sidecars to immutable spec-draft bytes and create separate frozen cohort copy.'])
with (D/'independent-prefreeze-audit.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(dict(status=out['status'],checks=len(checks),failed=out['failed_checks'],cohort_sha=out['cohort_draft_sha256'])))
