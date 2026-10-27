"""Descriptive rendering of frozen outputs and existing cost/health telemetry only."""
import json,hashlib
from pathlib import Path
from collections import Counter
import numpy as np
base=Path(__file__).resolve().parent;root=base/'execution-20261027/evidence/long-horizon-k400-20261027/campaign01/work'
def read(p):return json.loads(p.read_text())
q=read(root/'QUERY-COMPARISONS.json');s=read(root/'SCALE-COMPARISONS.json');drift=read(root/'DRIFT-CONTRASTS.json');pair=read(root/'PAIRED-DRIFT-CONTRASTS.json');rows=[]
for variant in ('control','shift'):
 for rep in (0,1):
  a=[x for x in q if x['variant']==variant and x['replicate']==rep and x['role']=='grid'];sc=[x for x in s if x['variant']==variant and x['replicate']==rep];row=dict(variant=variant,replicate=rep,grid_points=len(a),max_abs_cdf=max(abs(x['cdf_error']) for x in a),max_abs_logpdf=max(abs(x['logpdf_error']) for x in a))
  for period,ticks in [('early',[1,500,999]),('late',[1500,1750,2000])]:
   part=[x for x in a if x['tick'] in ticks];row[period+'_max_abs_cdf']=max(abs(x['cdf_error']) for x in part);row[period+'_max_abs_logpdf']=max(abs(x['logpdf_error']) for x in part)
  for prob in (.5,.95):row['scale_'+str(prob)+'_max_abs_relative_error']=max(abs(x['relative_error']) for x in sc if x['probability']==prob)
  rows.append(row)
worst={}
for role in ('grid','observed_label'):
 for metric in ('cdf','logpdf'):
  x=max([v for v in q if v['role']==role],key=lambda v:abs(v[metric+'_error']));worst[role+'_'+metric]={k:x[k] for k in ('variant','replicate','tick','index','cdf_error','logpdf_error')};worst[role+'_'+metric].update(candidate_precision=x['candidate']['precision'],reference_precision=x['reference']['precision'])
health={k:Counter() for k in ('warm_updates','initial_retained','initial_warmup')};cost=[];guards=0;restarts=0;warnings=[];native_times=[];full_times=[];scoring_times=[]
for lane in sorted((root/'lanes').iterdir()):
 ini=read(lane/'INITIAL.json');done=read(lane/'DONE.json');cost.append(dict(lane=lane.name,initialization_seconds=done['initialization_seconds'],initial_sampler_seconds=ini['telemetry']['seconds'],whole_lane_seconds=done['elapsed_seconds'],native_seconds=done['native_seconds'],scoring_seconds=done['scoring_seconds'],record_io_seconds=done['record_io_seconds']))
 warnings.extend(ini['telemetry']['chain_warnings'])
 for c in ini['telemetry']['chains']:
  health['initial_retained'].update(c['work_retained']);health['initial_warmup'].update(c['work_discarded']);guards+=len(c['trapped_chain_checks']);restarts+=sum(x['restarted'] for x in c['trapped_chain_checks'])
 for p in sorted((lane/'records').glob('*.json')):
  row=read(p);native_times.append(row['native_wall_seconds']);scoring_times.extend([row['scoring_seconds']] if 'scoring_seconds' in row else [])
  for c in row['native']['work']:health['warm_updates'].update(c)
 for line in (lane/'progress.jsonl').read_text().splitlines():
  e=json.loads(line)
  if e.get('event')=='tick_completed':full_times.append(e['total_through_record_seconds'])
def distribution(a):return dict(n=len(a),median=float(np.median(a)),p95=float(np.quantile(a,.95)),maximum=float(np.max(a)))
refmetrics=[];refprecision=[];divergences=0
for p in sorted((root/'references').glob('*/RESULT.json')):
 r=read(p);divergences+=sum(r['metadata']['divergences'])
 for c in r['contexts'].values():
  refmetrics.extend(c['reliability']['metrics'].values());refprecision.extend(x['precision'] for x in c['score']['queries'])
result=dict(scope='Post-run descriptive rendering of frozen comparisons and recorded telemetry; no recomputed forecasts, tests, gates or exclusions',table=rows,worst_rows=worst,drift_ranges={metric:[min(x['late_minus_early'] for x in drift if x['metric']==metric),max(x['late_minus_early'] for x in drift if x['metric']==metric)] for metric in ('cdf_error','logpdf_error')},paired_drift_ranges={metric:[min(x['shift_minus_control_drift'] for x in pair if x['metric']==metric),max(x['shift_minus_control_drift'] for x in pair if x['metric']==metric)] for metric in ('cdf_error','logpdf_error')},health={k:dict(v) for k,v in health.items()},guard_checks=guards,guard_restarts=restarts,chain_warnings=warnings,cost=cost,native_update_seconds=distribution(native_times),update_through_record_seconds=distribution(full_times),checkpoint_scoring_seconds=distribution(scoring_times),reference=dict(max_rhat=max(x['rhat'] for x in refmetrics),min_bulk_ess=min(x['bulk_ess'] for x in refmetrics),min_tail_ess=min(x['tail_ess'] for x in refmetrics),max_cdf_mcse=max(x['cdf_mcse'] for x in refprecision),max_logpdf_mcse=max(x['logpdf_delta_mcse'] for x in refprecision),divergences=divergences),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
with (base/'DESCRIPTIVE-REPORT.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k not in ('cost','health')},indent=2));print('health',json.dumps(result['health']))
