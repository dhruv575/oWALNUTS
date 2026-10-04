"""Compact, nonmutating resource-screen analysis; no raw draws or sampler."""
import json,hashlib,statistics,collections,math
from pathlib import Path
OUT=Path(__file__).resolve().parent;RUN=OUT.parent/'run-v2';bindings={}
def read(name):
 p=RUN/name;data=p.read_bytes();bindings[str(p)]=hashlib.sha256(data).hexdigest();return json.loads(data)
execution=read('execution-timing.json');timing=read('report-timing.json');results={};paired=[]
for arm,n in [('public',32),('reference',8)]:
 rows=read('flow-'+arm+'-normalized.json');coverage=read('flow-'+arm+'-coverage.json');manifest=read('flow-'+arm+'-manifest.json')
 expected={c['id'] for c in manifest['cells']};assert len(expected)==n and len(rows)==n and {r['id'] for r in rows}==expected
 assert len({r['id'] for r in rows})==n
 assert all(r['provenance_valid'] for r in rows) and coverage['record_integrity_pass']
 counts={}
 for name,value in coverage['selectors'].items():
  success=sum(r['usable'] and r['intervals'][name][0]<=r['truth'][name]<=r['intervals'][name][1] for r in rows)
  assert success==value['usable_and_covering']
  counts[name]=dict(covering=success,intended=n,usable=sum(r['usable'] for r in rows),rate=success/n,simultaneous_ci=value['unconditional_simultaneous_ci'])
 costs=[r['cost']['controller_seconds'] for r in rows];assert all(math.isfinite(t) and t>=0 for t in costs)
 results[arm]=dict(intended=n,usable=sum(r['usable'] for r in rows),coverage=counts,coverage_gate=coverage['coverage_component_meets_prespecified_rule'],reliability_lower=coverage['reliability_lower'],family_size=coverage['family_size'],selected_draws=dict(collections.Counter(r['normalization'].get('selected_draws') for r in rows)),controller_seconds=sum(costs),mean_controller_seconds=statistics.mean(costs),median_controller_seconds=statistics.median(costs),max_controller_seconds=max(costs),rows=rows)
by_seed={r['dataset_seed']:r for r in results['public']['rows']}
for reference in results['reference']['rows']:
 public=by_seed[reference['dataset_seed']];assert public['fixture_sha256']==reference['fixture_sha256'] and public['truth']==reference['truth']
 paired.append(dict(dataset_seed=reference['dataset_seed'],public_id=public['id'],reference_id=reference['id'],both_usable=public['usable'] and reference['usable'],public_seconds=public['cost']['controller_seconds'],reference_seconds=reference['cost']['controller_seconds'],reference_over_public=reference['cost']['controller_seconds']/public['cost']['controller_seconds'],coverage_disagreements=[k for k in public['intervals'] if (public['intervals'][k][0]<=public['truth'][k]<=public['intervals'][k][1])!=(reference['intervals'][k][0]<=reference['truth'][k]<=reference['intervals'][k][1])]))
assert len(paired)==8
for arm in results:del results[arm]['rows']
result=dict(qualified=False,scope='Prospective resource screen, posthoc descriptive summary. No calibration or speed qualification.',arms=results,paired=paired,paired_cost_ratio_of_totals=sum(r['reference_seconds'] for r in paired)/sum(r['public_seconds'] for r in paired),paired_median_ratio=statistics.median(r['reference_over_public'] for r in paired),execution=execution,reporting=timing,bindings=bindings)
with (OUT/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k not in ('bindings','paired','arms')},indent=2))
for arm,r in results.items():print(arm,{k:v for k,v in r.items() if k!='coverage'});print('coverage',[(k,v['covering']) for k,v in r['coverage'].items()])
