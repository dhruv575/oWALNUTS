"""Supplemental descriptive latency accounting; never changes frozen score analysis."""
import argparse,json,math
from pathlib import Path
import numpy as np

def metric(values,planned):
 good=[float(v) for v in values if isinstance(v,(int,float)) and math.isfinite(v)]
 return dict(planned=planned,observed=len(good),missing_or_invalid=planned-len(good),sum_seconds=sum(good),median_seconds=float(np.median(good)) if good else None,p95_seconds=float(np.quantile(good,.95,method='linear')) if good else None,max_seconds=max(good) if good else None)
def summarize(root):
 root=Path(root);campaign=json.loads((root/'campaign.json').read_text());initial=[];rows=[];states={};stage={}
 for stream in range(32):
  p=root/f'stream-{stream:02d}'/'candidate.json'
  if not p.exists():continue
  d=json.loads(p.read_text());states[str(stream)]=dict(status=d.get('status'),valid_ticks=d.get('valid_ticks'),unattempted=d.get('unattempted_ticks'))
  initial.append((d.get('initial_fit') or {}).get('seconds'));rows.extend(d.get('rows',[]))
 for kind,planned in [('candidate',32),('sides',32),('reference',8),('report',1)]:
  jobs=[j for j in campaign['jobs'] if j['kind']==kind];status={}
  for j in jobs:status[j['status']]=status.get(j['status'],0)+1
  stage[kind]=dict(monitored_job_status_counts=status,latency_all_started_jobs=metric([j.get('elapsed_seconds') for j in jobs],planned),job_outcomes=[])
  for i in range(planned):
   p=root/'job-records'/f'{kind}-{i:02d}.json'
   stage[kind]['job_outcomes'].append(dict(id=i,**({k:v for k,v in json.loads(p.read_text()).items() if k in ('status','valid_ticks','error')} if p.exists() else {'status':'not_started'})))
 return dict(scope='Supplemental descriptive latency accounting; fixed predictive/bootstrap results unchanged, no qualification gate',units='seconds',quantile_method='linear',campaign_wall_seconds=campaign['elapsed_seconds'],planned_streams=32,planned_origins=1024,candidate_status=states,phases=stage,initial_native_fit=metric(initial,32),update_total=metric([r.get('candidate_total_seconds') for r in rows],1024),preparation=metric([(r.get('native') or {}).get('preparation_seconds') for r in rows],1024),native_sampling=metric([(r.get('native') or {}).get('sampling_seconds') for r in rows],1024),observed_label_evaluation=metric([r.get('evaluation_seconds') for r in rows],1024),limitations=['Per-update total excludes initialization, persistence, imports and final integrity checks; whole-job latency includes these.','Initial native fit timer excludes later diagnostic-summary and session-construction overhead.','Observed-return CDF/logpdf scoring has no quantile root finding; not a complete return-quantile update measurement.','Started failed/timed-out job costs remain included; missing origin metrics are counted, never imputed.'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('campaign');p.add_argument('output');a=p.parse_args();d=summarize(a.campaign)
 with Path(a.output).open('x') as f:json.dump(d,f,indent=2,allow_nan=False);f.write('\n')
