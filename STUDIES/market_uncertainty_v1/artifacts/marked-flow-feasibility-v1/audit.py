"""Read-only marks audit; expiry-calendar-day buckets, not exact settlement TTE."""
import collections,datetime as dt,hashlib,json,math,re,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
SOURCE=ROOT/'target/market-history-acquisition-v1/september-development-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def good(x):return type(x)in(int,float) and math.isfinite(x) and x>0
paths=[SOURCE/n for n in ('trades.jsonl','terminal.json','protocol.json','launch-identity.json','source.py')]
pins={str(p):sha(p) for p in paths};start=time.perf_counter();terminal=json.loads((SOURCE/'terminal.json').read_text())
fields=collections.Counter();missing=collections.Counter();invalid=collections.Counter();buckets={};types=collections.Counter();maturity=collections.Counter();money=collections.Counter();joint=collections.Counter();flags=collections.Counter();seen=set();duplicates=0;examples=[];n=0
months={m:i+1 for i,m in enumerate(['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'])}
for line in (SOURCE/'trades.jsonl').open():
 r=json.loads(line);n+=1;fields.update(r.keys());tid=r.get('trade_id');duplicates+=tid in seen;seen.add(tid);bad=[]
 for key in ('instrument_name','timestamp','index_price','amount','direction'):
  if key not in r or r[key] is None:missing[key]+=1
 match=re.fullmatch(r'BTC-(\d{1,2})([A-Z]{3})(\d{2})-(\d+(?:\.\d+)?)-([CP])',str(r.get('instrument_name')))
 if not match:bad.append('contract_name')
 if not good(r.get('index_price')):bad.append('index_price')
 if not good(r.get('amount')):bad.append('amount')
 if r.get('direction') not in ('buy','sell'):bad.append('direction')
 if type(r.get('timestamp'))is not int:bad.append('timestamp')
 if not bad:
  day,month,year,strike,kind=match.groups()
  try:
   expiry=dt.date(2000+int(year),months[month],int(day));traded=dt.datetime.fromtimestamp(r['timestamp']/1000,dt.timezone.utc).date();days=(expiry-traded).days
   if days<0:bad.append('expired_calendar_date')
   strike=float(strike)
   if not good(strike):bad.append('strike')
  except Exception:bad.append('expiry_date')
 if bad:invalid.update(bad);continue
 mb='0-7_days' if days<=7 else '8-30_days' if days<=30 else '31-90_days' if days<=90 else '91plus_days'
 ratio=strike/r['index_price'];kb='K/index<0.90' if ratio<.90 else '0.90<=K/index<=1.10' if ratio<=1.10 else 'K/index>1.10'
 types[kind]+=1;maturity[mb]+=1;money[kb]+=1;key='|'.join([kind,mb,kb]);joint[key]+=1
 b=buckets.setdefault(key,dict(count=0,total_base_amount=0.,signed_base_amount=0.));b['count']+=1;b['total_base_amount']+=r['amount'];b['signed_base_amount']+=r['amount']*(1 if r['direction']=='buy' else -1)
 for k in ('block_trade_id','combo_id','combo_trade_id'):
  if r.get(k)is not None:flags[k]+=1
 if len(examples)<3:examples.append(dict(trade_id=tid,instrument_name=r['instrument_name'],timestamp=r['timestamp'],index_price=r['index_price'],strike=strike,calendar_days=days,bucket=key))
assert all(sha(Path(p))==h for p,h in pins.items())
result=dict(scope='Read-only September schema/availability audit, not predictive selection or model fit. Fixed coarse buckets selected before counting. Trade-provided index_price only; no later price, Greeks or delta conversion. Calendar-day expiry proxy, no assumed exact settlement hour.',source_hashes=pins,script_sha256=sha(Path(__file__)),terminal=terminal,trades=n,duplicate_ids=duplicates,field_presence=dict(fields),missing=dict(missing),invalid=dict(invalid),eligible=sum(types.values()),put_call=dict(types),calendar_maturity=dict(maturity),strike_over_trade_index=dict(money),joint_buckets=buckets,flagged_fields=dict(flags),examples=examples,seconds=time.perf_counter()-start,limitations=['Archived historical event-time fields do not prove live receipt-time availability.','Trade index value is exchange-supplied; no independent spot validation.','Calendar-day maturity suffices coarse exploration but expiry-hour convention must be pinned before exact time-to-expiry.','All archived prints retained including block/combo; signed raw base amount is not signed delta exposure.','Aggregate bucket occupancy does not establish per-origin coverage or forecasting benefit.'])
with (OUT/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:result[k] for k in ('trades','eligible','missing','invalid','put_call','calendar_maturity','strike_over_trade_index','seconds')}))
