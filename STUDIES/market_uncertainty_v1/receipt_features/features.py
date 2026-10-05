"""Causal receipt-clock features; no interpolation, networking, or model fitting."""
import argparse,bisect,hashlib,json,math
from pathlib import Path
TRADE='trades.option.BTC.100ms'
QUOTE='ticker.BTC-PERPETUAL.agg2'

def positive(x):return type(x) in (int,float) and math.isfinite(x) and x>0

def build(receipts,*,origins_ns,horizon_ns=1800_000_000_000,window_ns=900_000_000_000,staleness_ns=5_000_000_000,coverage_intervals=(),gaps=(),observation_end_ns=None):
 if any(type(v)is not int or v<=0 for v in (horizon_ns,window_ns,staleness_ns)):raise ValueError('Positive integer durations required')
 if not receipts:raise ValueError('No receipts')
 stamps=[r['receipt_monotonic_ns'] for r in receipts]
 if any(type(t)is not int for t in stamps) or any(b<a for a,b in zip(stamps,stamps[1:])):raise ValueError('Receipt clock must be monotone')
 observed_end=stamps[-1] if observation_end_ns is None else observation_end_ns
 if type(observed_end)is not int or observed_end<stamps[-1]:raise ValueError('Invalid observed terminal clock')
 if any(type(t)is not int for t in origins_ns) or len(set(origins_ns))!=len(origins_ns):raise ValueError('Distinct integer origins required')
 for intervals in (coverage_intervals,gaps):
  if any(len(v)!=2 or any(type(t)is not int for t in v) or v[1]<v[0] for v in intervals):raise ValueError('Invalid coverage/gap interval')
 quotes=[];trades=[];seen={};bad_trades=[]
 for entry in receipts:
  t=entry['receipt_monotonic_ns'];message=json.loads(entry['raw']);params=message.get('params',{});channel=params.get('channel');data=params.get('data')
  if channel==QUOTE:
   if not isinstance(data,dict):raise ValueError('Malformed quote message')
   bid=data.get('best_bid_price');ask=data.get('best_ask_price')
   valid=data.get('instrument_name')=='BTC-PERPETUAL' and data.get('state')=='open' and positive(bid) and positive(ask) and bid<=ask
   quotes.append(dict(receipt_ns=t,receipt_utc_ns=entry['receipt_utc_ns'],event_ms=data.get('timestamp'),midpoint=(bid+ask)/2 if valid else None,valid=bool(valid)))
  elif channel==TRADE:
   if not isinstance(data,list):raise ValueError('Malformed trade message')
   for trade in data:
    identity=trade.get('trade_id');name=trade.get('instrument_name','');amount=trade.get('amount');direction=trade.get('direction')
    if identity is None or not isinstance(name,str) or not name.startswith('BTC-') or not name.endswith(('-C','-P')) or not positive(amount) or direction not in ('buy','sell'):
     bad_trades.append(t);continue
    key=str(identity);canonical=json.dumps(trade,sort_keys=True,separators=(',',':'))
    if key in seen:
     if seen[key]!=canonical:raise ValueError('Conflicting duplicate trade')
     continue
    seen[key]=canonical;trades.append(dict(receipt_ns=t,trade_id=key,instrument=name,amount=amount,signed_amount=amount if direction=='buy' else -amount,flagged=any(trade.get(k) is not None for k in ('block_trade_id','combo_id','combo_trade_id'))))
 qtimes=[q['receipt_ns'] for q in quotes]
 def quote_at(t):
  idx=bisect.bisect_right(qtimes,t)-1
  if idx<0:return dict(available=False,reason='no_received_quote')
  q=quotes[idx];gap=any(a<=t and b>=q['receipt_ns'] for a,b in gaps)
  reason='invalid_latest_quote' if not q['valid'] else 'stale_quote' if t-q['receipt_ns']>staleness_ns else 'gap_since_quote' if gap else None
  return dict(q,available=reason is None,reason=reason)
 result=[]
 for origin in sorted(origins_ns):
  if not stamps[0]<=origin<=observed_end:raise ValueError('Origin outside observed receipt span')
  left=origin-window_ns;end=origin+horizon_ns
  flow=[t for t in trades if left<t['receipt_ns']<=origin]
  known=any(a<=left and b>=origin for a,b in coverage_intervals) and not any(a<=origin and b>left for a,b in gaps) and not any(left<t<=origin for t in bad_trades)
  total=math.fsum(t['amount'] for t in flow);signed=math.fsum(t['signed_amount'] for t in flow)
  anchor=quote_at(origin);future=quote_at(end) if end<=observed_end else dict(available=False,reason='horizon_not_collected')
  label=math.log(future['midpoint']/anchor['midpoint']) if anchor['available'] and future['available'] else None
  features=dict(origin_receipt_ns=origin,flow_window_start_ns=left,flow_known=known,flow_status=('known_zero' if not flow else 'known_received_flow') if known else 'unknown_or_partial',observed_trade_count=len(flow),observed_flagged_trade_count=sum(t['flagged'] for t in flow),observed_signed_amount=signed,observed_total_amount=total,signed_amount=signed if known else None,total_amount=total if known else None,anchor=anchor)
  result.append(dict(features=features,label=dict(horizon_end_receipt_ns=end,available_at_receipt_ns=end if end<=observed_end else None,observed=label is not None,log_midpoint_return=label,future_quote=future)))
 return dict(schema='receipt-flow-midpoint/v1',qualified=False,rows=result,scope='Raw BTC-option amount, not delta exposure. Receipt-clock BTC-PERPETUAL bid/ask midpoint target; not index or executable PnL. Known flow means collector-declared observed connection coverage, not exchange feed completeness. Local clocks are not certified.',invalid_trade_receipts=len(bad_trades))

def collector_context(summary):
 """Translate v2 acknowledged sessions and conservative reconnect gaps."""
 end=summary['end_monotonic_ns']
 if type(end)is not int:raise ValueError('Explicit terminal monotonic clock required')
 coverage=[(s['start_monotonic_ns'],s['end_monotonic_ns']) for s in summary['coverage_intervals']]
 gaps=[(g['start_monotonic_ns'],g.get('resubscribed_monotonic_ns',end)) for g in summary['gaps']]
 if any(b>end for a,b in coverage+gaps):raise ValueError('Coverage extends past terminal')
 return dict(coverage_intervals=coverage,gaps=gaps,observation_end_ns=end)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--receipts',required=True);p.add_argument('--config',required=True);p.add_argument('--out',required=True);p.add_argument('--collector-summary');a=p.parse_args()
 raw=Path(a.receipts).read_bytes();config=json.loads(Path(a.config).read_text())
 rows=[json.loads(line) for line in raw.decode().splitlines() if line]
 if set(config)&{'coverage_intervals','gaps','observation_end_ns'}:raise ValueError('CLI coverage must come from collector summary')
 if a.collector_summary:
  summary=json.loads(Path(a.collector_summary).read_text())
  if summary['files_sha256'].get(Path(a.receipts).name)!=hashlib.sha256(raw).hexdigest():raise ValueError('Collector receipt binding differs')
  context=collector_context(summary)
  if set(context)&set(config):raise ValueError('Do not override collector coverage')
  config.update(context)
 stride=config.pop('origin_stride_ns',1800_000_000_000)
 if type(stride)is not int or stride<=0:raise ValueError('Positive origin stride required')
 if 'origins_ns' not in config:
  start=rows[0]['receipt_monotonic_ns']+config.get('window_ns',900_000_000_000)
  end=config.get('observation_end_ns',rows[-1]['receipt_monotonic_ns'])
  config['origins_ns']=list(range(start,end+1,stride))
 result=build(rows,**config);result['receipts_sha256']=hashlib.sha256(raw).hexdigest();result['config_sha256']=hashlib.sha256(Path(a.config).read_bytes()).hexdigest();result['source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 if a.collector_summary:result['collector_summary_sha256']=hashlib.sha256(Path(a.collector_summary).read_bytes()).hexdigest()
 with Path(a.out).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
