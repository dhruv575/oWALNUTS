import hashlib,json
from pathlib import Path
from common import ROOT
ref=json.loads((ROOT/'REFERENCE.json').read_text());names=ref['names'];rows=[];inputs={};supervision=[]
for run,seeds,kind in [('run02',range(943100001,943100005),'global'),('conditional03',range(944100001,944100005),'conditional')]:
 final=json.loads((ROOT/run/'FINAL.json').read_text());assert final['unchanged']
 for job in final['results']:assert job['exit_code']==0 and job['group_drained']
 supervision.append(dict(run=run,seconds=final['seconds'],jobs=len(final['results']),peak_rss=max(j['peak_rss'] for j in final['results'])))
 for seed in seeds:
  p=ROOT/run/str(seed)/'RESULT.json';inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();result=json.loads(p.read_text())
  rs=result['rows'] if kind=='global' else [dict(arm='conditional_importance',**result)]
  for r in rs:
   worst=lambda key:max(range(24),key=lambda i:r[key][i])
   rows.append(dict(seed=seed,arm=r['arm'],passed=r['passed'],ess=r['ess'],pareto_k=r['pareto_k'],max_mean_error_sd=max(r['mean_error_sd']),worst_mean=names[worst('mean_error_sd')],max_relative_sd_error=max(r['relative_sd_error']),worst_sd=names[worst('relative_sd_error')],max_combined_z=max(r['combined_z']),seconds=r['seconds'],calls=(result['calls'] if r['arm']=='importance' else dict(gradient=0,value=0,errors=0)) if kind=='global' else result['stan_calls'],conditional_work=result.get('counts')))
summary=dict(reference_qualified=ref['qualified'],reference_rhat_max=max(ref['stats']['rhat']),reference_bulk_min=min(ref['stats']['bulk']),reference_tail_min=min(ref['stats']['tail']),rows=rows,supervision=supervision,global_importance_admitted=all(r['passed'] for r in rows if r['arm']=='importance'),conditional_importance_admitted=all(r['passed'] for r in rows if r['arm']=='conditional_importance'),interpretation='Synthetic benchmark;24-functional adequacy, not full posterior/decision validation. No sampler speed comparison.')
(ROOT/'SUMMARY-v2.json').write_text(json.dumps(summary,indent=2)+'\n');(ROOT/'ANALYSIS-INPUTS-v2.json').write_text(json.dumps(inputs,indent=2)+'\n');print(json.dumps(summary,indent=2))
