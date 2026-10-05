"""Causal trade-event marked raw BTC amount; no Greeks or predictive claim."""
import datetime as dt
import math
import re
WINDOW_MS=900000
MONTHS={m:i+1 for i,m in enumerate(('JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'))}
MATURITIES=('0-7','8-30','31-90','91+')
MONEYNESS=('<0.9','0.9-1.1','>1.1')
BUCKETS=tuple(f'{k}|{d}|{m}' for k in ('P','C') for d in MATURITIES for m in MONEYNESS)
def positive(x):return type(x)in(int,float) and math.isfinite(x) and x>0

def mark(trade):
 t=trade.get('timestamp');index=trade.get('index_price');amount=trade.get('amount')
 if type(t)is not int or not positive(index) or not positive(amount) or trade.get('direction') not in ('buy','sell'):
  raise ValueError('Observed trade requires integer timestamp, positive index/amount and buy/sell direction')
 match=re.fullmatch(r'BTC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([PC])',str(trade.get('instrument_name')))
 if not match:raise ValueError('Invalid BTC option instrument')
 day,month,year,strike,kind=match.groups()
 try:days=(dt.date(2000+int(year),MONTHS[month],int(day))-dt.datetime.fromtimestamp(t/1000,dt.timezone.utc).date()).days
 except (KeyError,ValueError,OverflowError,OSError) as e:raise ValueError('Invalid expiry or trade date') from e
 if days<0 or not positive(float(strike)):raise ValueError('Expired calendar date or invalid strike')
 maturity=MATURITIES[0 if days<=7 else 1 if days<=30 else 2 if days<=90 else 3]
 ratio=float(strike)/index
 if not math.isfinite(ratio):raise ValueError('Nonfinite strike/index ratio')
 moneyness=MONEYNESS[0 if ratio<.9 else 1 if ratio<=1.1 else 2]
 return f'{kind}|{maturity}|{moneyness}'

def require_coverage(intervals,left,right):
 cursor=left
 normalized=[]
 for interval in intervals:
  if len(interval)!=2 or any(type(v)is not int for v in interval) or interval[1]<=interval[0]:raise ValueError('Invalid half-open coverage interval')
  normalized.append(tuple(interval))
 for a,b in sorted(normalized):
  if b<=cursor:continue
  if a>cursor:break
  cursor=max(cursor,b)
  if cursor>=right:return
 raise ValueError('Unknown or partial event-time flow coverage')

def build(trades,origin_ms,*,coverage_intervals):
 """Only selected past-window rows are marked; future marks cannot affect output.

 No scaling is fitted here. Downstream transformations must fit on training
 origins only. Calendar-date maturity is a proxy, not exact settlement TTE.
 """
 if type(origin_ms)is not int:raise ValueError('Integer origin required')
 require_coverage(coverage_intervals,origin_ms-WINDOW_MS,origin_ms)
 values={b:[] for b in BUCKETS};seen=set()
 for trade in trades:
  t=trade.get('timestamp')
  if type(t)is not int:raise ValueError('Cannot determine causal membership without timestamp')
  if not origin_ms-WINDOW_MS<=t<origin_ms:continue
  identity=trade.get('trade_id')
  if not isinstance(identity,(str,int)) or isinstance(identity,bool):raise ValueError('Trade identity required')
  if str(identity) in seen:raise ValueError('Duplicate observed trade identity')
  seen.add(str(identity));bucket=mark(trade)
  values[bucket].append((trade['amount'],trade['amount']*(1 if trade['direction']=='buy' else -1)))
 buckets={b:dict(count=len(v),amount=math.fsum(x[0] for x in v),signed_amount=math.fsum(x[1] for x in v)) for b,v in values.items()}
 return dict(origin_ms=origin_ms,window_start_ms=origin_ms-WINDOW_MS,buckets=buckets,count=len(seen),amount=math.fsum(x['amount'] for x in buckets.values()),signed_amount=math.fsum(x['signed_amount'] for x in buckets.values()),scope='Event-time [origin-15min,origin); exchange-reported raw BTC option amount, not delta exposure. Trade-provided contemporaneous index. Calendar-day expiry buckets; zero publication lag assumed by retrospective use. No fitted scaling, Greeks or predictive claim.')
