"""Fixed six-way partitions of the two previously truncated intervals."""
import json,hashlib,sys,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path

root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
raw=(root/'INPUT.json').read_bytes();pairs=json.loads(raw)['pairs']
selected=[p for p in pairs if p['index'] in [2289,4114]]
assert len(selected)==2
plan=dict(indices=[2289,4114],parts=6,requests=12,count=1000,seconds=270,per_response_bytes=2097152,retries=0,input_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(out/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n');started=time.monotonic();rows=[]
for p in selected:
 for part in range(6):
  lo=p['current']['open_ms']+part*300000;hi=lo+299999
  params=dict(instrument_name='BTC-PERPETUAL',start_timestamp=lo,end_timestamp=hi,count=1000,sorting='desc')
  url='https://history.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time?'+urllib.parse.urlencode(params)
  row=dict(index=p['index'],part=part,start_ms=lo,end_ms=hi,url=url);name=f"{p['index']}-{part}"
  (out/(name+'-request.json')).write_text(json.dumps(row,indent=2)+'\n')
  try:
   remaining=270-(time.monotonic()-started)
   if remaining<=0:raise TimeoutError('Global deadline')
   req=urllib.request.Request(url,headers={'User-Agent':'owalnuts-observation-audit/1'})
   try:
    with urllib.request.urlopen(req,timeout=min(20,remaining)) as f:status=f.status;body=f.read(2097153)
   except urllib.error.HTTPError as e:status=e.code;body=e.read(2097153)
   (out/(name+'-response.json')).write_bytes(body)
   row.update(http_status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
   if status!=200 or len(body)>2097152:raise ValueError('HTTP/bytes')
   obj=json.loads(body)
   if obj.get('error') is not None:raise ValueError(str(obj['error']))
   r=obj['result'];t=r['trades']
   assert type(r['has_more'])is bool
   assert len({x['trade_seq'] for x in t})==len(t)
   assert all(x['instrument_name']=='BTC-PERPETUAL' and lo<=x['timestamp']<=hi for x in t)
   row.update(status='observed',count=len(t),has_more=r['has_more'])
  except Exception as e:row.update(status='failed',error=repr(e))
  rows.append(row);time.sleep(.5)
result=dict(plan=plan,rows=rows,elapsed_seconds=time.monotonic()-started)
(out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
