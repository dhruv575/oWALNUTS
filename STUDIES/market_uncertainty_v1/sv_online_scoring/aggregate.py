"""Complete planned-origin final SV scoring; no acquisition, fitting or deployment."""
import argparse,hashlib,json,math
from pathlib import Path
ALLOWED={'scored','outcome_unavailable','invalidated_receipt_coverage','no_forecast','not_issued','invalid_issuance','invalid_provenance'}
BASELINES=('price_history_only','price_plus_pooled_flow')
def finite(x):return type(x) in (int,float) and math.isfinite(x)
def hashfile(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def values(row):
 y=row['observed_return'];lo,hi=row['interval']
 if not all(finite(v) for v in (y,lo,hi)) or hi<=lo or row.get('nominal_coverage')!=.9:raise ValueError('Invalid scored predictive interval')
 score=hi-lo+20*(max(lo-y,0)+max(y-hi,0));covered=lo<=y<=hi
 if row.get('covered') is not covered or not finite(row.get('width')) or not math.isclose(row['width'],hi-lo,rel_tol=1e-12,abs_tol=1e-12) or not finite(row.get('interval_score')) or not math.isclose(row['interval_score'],score,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Stored score arithmetic differs')
 return dict(observed_return=y,interval=[lo,hi],width=hi-lo,covered=covered,lower_miss=y<lo,upper_miss=y>hi,interval_score=score)
def stats(rows,n):
 scored=[r['score'] for r in rows if r.get('score') is not None];count=len(scored)
 return dict(intended=n,issued=sum(r['issued'] for r in rows),usable=sum(r['usable'] for r in rows),scored=count,issued_fraction=sum(r['issued'] for r in rows)/n,usable_fraction=sum(r['usable'] for r in rows)/n,scored_fraction=count/n,coverage_given_scored=sum(r['covered'] for r in scored)/count if count else None,usable_and_covering_count=sum(r['covered'] for r in scored),usable_and_covering_fraction=sum(r['covered'] for r in scored)/n,mean_width=sum(r['width'] for r in scored)/count if count else None,mean_interval_score=sum(r['interval_score'] for r in scored)/count if count else None,lower_misses=sum(r['lower_miss'] for r in scored),upper_misses=sum(r['upper_miss'] for r in scored))
def summarize(plan,events,scores,baselines=()):
 origins=plan['origins_ns']
 if plan.get('schema')!='receipt-live-sv-schedule-v1' or len(origins)!=95 or any(type(o)is not int for o in origins) or origins!=sorted(set(origins)):raise ValueError('Exact distinct 95-origin plan required')
 def index(rows,key):
  if any(type(r.get(key)) is not int for r in rows):raise ValueError('Strict integer origin required')
  out={r[key]:r for r in rows}
  if len(out)!=len(rows):raise ValueError('Duplicate origin')
  return out
 ledger=index(events,'origin_receipt_ns');results=index(scores,'origin_receipt_ns')
 if set(ledger)!=set(origins) or set(results)!=set(origins):raise ValueError('Exactly one terminal event and final score per planned origin required')
 rows=[]
 for origin in origins:
  event=ledger[origin];r=results[origin]
  if r.get('schema')!='delayed-live-sv-score-v1' or r.get('provisional') is not False or r.get('final_reconciliation_required') is not False:raise ValueError('Final SV score required')
  if r.get('issuance_sha256')!=event.get('issuance_sha256') or r.get('issuance_status')!=event.get('status'):raise ValueError('Score/event issuance identity differs')
  if event.get('status') not in ('issued','issued_no_forecast','not_issued') or r.get('status') not in ALLOWED:raise ValueError('Unknown terminal outcome')
  if r.get('scored') is not (r['status']=='scored'):raise ValueError('Scored status contradiction')
  if r['status'] in ('scored','outcome_unavailable','invalidated_receipt_coverage') and event['status']!='issued':raise ValueError('Unissued interval cannot score')
  row=dict(origin_receipt_ns=origin,issuance_status=event['status'],status=r['status'],original_score_status=r.get('original_score_status',r['status']),reason=r.get('reason',r.get('error')),integrity_error=r.get('aggregate_lineage_error'),issued=event['status']=='issued',usable=r['status'] in ('scored','outcome_unavailable'),score=values(r) if r['status']=='scored' else None)
  rows.append(row)
 output=dict(schema='complete-live-sv-aggregate-v1',qualified=False,origins=origins,outcomes=rows,summary=stats(rows,len(origins)),status_counts={s:sum(r['status']==s for r in rows) for s in sorted(ALLOWED)},scope='Complete prospective schedule, descriptive dependent outcomes. Conditional coverage is among scored forecasts only; all-origin fractions retain nonissuance and unavailable outcomes.')
 if baselines:
  b=index(baselines,'origin_receipt_ns')
  if set(b)-set(origins):raise ValueError('Baseline origin outside SV plan')
  paired={name:[] for name in BASELINES}
  for row in rows:
   origin=row['origin_receipt_ns'];record=b.get(origin)
   if record is None:continue
   if record.get('schema')!='issued-market-interval-score/v1' or record.get('provisional',False) is not False:raise ValueError('Final baseline score required')
   outcomes={r['model']:r for r in record['outcomes']}
   if len(outcomes)!=len(record['outcomes']) or set(outcomes)!=set(BASELINES):raise ValueError('Baseline model family differs')
   for name,outcome in outcomes.items():
    if row['score'] is None or outcome.get('status')!='scored':continue
    value=values(outcome)
    if value['observed_return']!=row['score']['observed_return']:raise ValueError('Paired observed return differs')
    paired[name].append(dict(origin_receipt_ns=origin,sv=row['score'],baseline=value))
  output['baseline_comparisons']={name:dict(intended_origins=95,common_scored=len(rows),origins=[r['origin_receipt_ns'] for r in rows],mean_interval_score_difference_sv_minus_baseline=sum(r['sv']['interval_score']-r['baseline']['interval_score'] for r in rows)/len(rows) if rows else None,mean_width_difference_sv_minus_baseline=sum(r['sv']['width']-r['baseline']['width'] for r in rows)/len(rows) if rows else None) for name,rows in paired.items()}
 return output
def aggregate(plan_path,events_path,score_paths,*,baseline_paths=()):
 tracked={}
 def bind(path,expected=None):
  p=str(Path(path).resolve());h=hashfile(p)
  if expected is not None and h!=expected:raise ValueError('Bound input differs: '+p)
  if p in tracked and tracked[p]!=h:raise ValueError('Conflicting input identity')
  tracked[p]=h;return p
 def read(path):p=bind(path);return json.loads(Path(p).read_text())
 bind(__file__);plan=read(plan_path);event_path=bind(events_path);events=[json.loads(s) for s in Path(event_path).read_text().splitlines() if s]
 plan_lineage=dict(plan.get('source_sha256',{}))
 if 'configuration_sha256' in plan:plan_lineage[str(Path(plan_path).parent/'configuration.json')]=plan['configuration_sha256']
 for event in events:
  p=bind(event['path'],event['issuance_sha256']);issued=json.loads(Path(p).read_text())
  if issued.get('origin_receipt_ns')!=event['origin_receipt_ns'] or issued.get('status')!=event['status']:raise ValueError('Event file identity differs')
 scores=[read(p) for p in score_paths];baselines=[read(p) for p in baseline_paths]
 # Validate original terminal schemas/statuses before any lineage invalidation
 # can replace a status; provisional or malformed records remain hard errors.
 summarize(plan,events,scores,baselines)
 # Validate each unique transitive input once, before and after aggregation.
 declared={};lineage=[]
 def invalidate(record,error):
  record.setdefault('original_score_status',record.get('status'))
  record['aggregate_lineage_error']=error
  if record.get('schema')=='delayed-live-sv-score-v1':record.update(status='invalid_provenance',scored=False,error=error)
  else:
   record['outcomes']=[dict(model=r['model'],status='invalid_provenance',reason=error) for r in record.get('outcomes',[])]
 for record in scores+baselines:
  pins=record.get('input_and_source_sha256')
  if not isinstance(pins,dict) or not pins:
   invalidate(record,'Scorer input/source lineage missing');lineage.append((record,{}));continue
  if record.get('schema')=='delayed-live-sv-score-v1':
   overlap=set(pins)&set(plan_lineage)
   if any(pins[k]!=plan_lineage[k] for k in overlap):invalidate(record,'Plan and score source lineage conflict')
   pins={**plan_lineage,**pins}
  expected={}
  for path,h in pins.items():
   key=str(Path(path).resolve())
   expected[key]=h
   if key not in declared:
    try:declared[key]=hashfile(key)
    except OSError:declared[key]=None
   if declared[key]!=h:invalidate(record,'Changed or missing scorer lineage: '+key)
  lineage.append((record,expected))
 for record in baselines:
  if record.get('aggregate_lineage_error'):continue
  matches=[p for p,h in record['input_and_source_sha256'].items() if h==record.get('issuance_sha256')]
  if not matches:raise ValueError('Baseline issuance not bound by scorer lineage')
  if not any(json.loads(Path(p).read_text()).get('origin_receipt_ns')==record['origin_receipt_ns'] for p in matches):raise ValueError('Baseline issuance origin differs')
 # A failed score may deliberately identify changed upstream bytes. Preserve
 # that failure in its origin rather than aborting the complete denominator.
 result=summarize(plan,events,scores,baselines)
 changed=set()
 for p,h in declared.items():
  try:current=hashfile(p)
  except OSError:current=None
  if current!=h:changed.add(p)
 for record,pins in lineage:
  if changed.intersection(pins):invalidate(record,'Scorer lineage changed during aggregation')
 if changed:result=summarize(plan,events,scores,baselines)
 for p,h in tracked.items():
  if hashfile(p)!=h:raise ValueError('Aggregation input/source changed')
 result['input_and_source_sha256']=tracked;result['transitive_lineage_observed_sha256']=declared;result['transitive_lineage_changed_during_aggregation']=sorted(changed);return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True,type=Path);p.add_argument('--events',required=True,type=Path);p.add_argument('--scores',required=True,type=Path,nargs='+');p.add_argument('--baseline-scores',type=Path,nargs='*',default=[]);p.add_argument('--out',required=True,type=Path);a=p.parse_args();r=aggregate(a.plan,a.events,a.scores,baseline_paths=a.baseline_scores)
 with a.out.open('x') as f:json.dump(r,f,indent=2,allow_nan=False)
