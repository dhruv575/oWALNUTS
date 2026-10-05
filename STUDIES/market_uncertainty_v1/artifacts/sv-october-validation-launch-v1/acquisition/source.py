"""Bounded retrospective public trade/bar acquisition; no inference or retries."""
import argparse,datetime,hashlib,json,math,shutil,sqlite3,time,urllib.parse,urllib.request
from pathlib import Path
DAY=86400000
HALF=1800000
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False)
def write(p,x):p.write_text(json.dumps(x,indent=2,allow_nan=False),encoding='utf-8')
def finite(x):return type(x) in (float,int) and math.isfinite(x)

class Collector:
 def __init__(self,protocol,out,fetch=None,protocol_path=None):
  self.p=protocol;self.out=Path(out);self.out.mkdir(exist_ok=False);self.started=time.monotonic();self.requests=0;self.bytes=0;self.fetch=fetch or self.network;self.leaves=[];self.bars=[]
  write(self.out/'protocol.json',protocol);(self.out/'source.py').write_bytes(Path(__file__).read_bytes())
  self.source_sha=sha(Path(__file__).read_bytes());self.protocol_path=Path(protocol_path) if protocol_path else None;self.protocol_sha=sha(self.protocol_path.read_bytes()) if self.protocol_path else sha(canonical(protocol).encode());self.last_progress=self.started
  write(self.out/'launch-identity.json',dict(source_path=str(Path(__file__).resolve()),source_sha256=self.source_sha,protocol_path=str(self.protocol_path.resolve()) if self.protocol_path else None,protocol_sha256=self.protocol_sha))
  self.db=sqlite3.connect(self.out/'trades.sqlite');self.db.execute('CREATE TABLE trades (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
 def network(self,url):
  with urllib.request.urlopen(url,timeout=min(12,max(.01,self.p['max_seconds']-(time.monotonic()-self.started)))) as response:
   return response.status,response.read(self.p['max_response_bytes']+1)
 def request(self,method,params):
  if self.requests>=self.p['max_requests'] or self.bytes>=self.p['max_bytes'] or time.monotonic()-self.started>=self.p['max_seconds']:raise RuntimeError('Resource cap reached')
  if shutil.disk_usage(self.out).free<self.p['minimum_free_bytes']:raise RuntimeError('Disk admission failed')
  url='https://history.deribit.com/api/v2/public/'+method+'?'+urllib.parse.urlencode(params);index=self.requests;self.requests+=1;tick=time.monotonic()
  row={'index':index,'url':url,'requested_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'started'};write(self.out/f'request-{index:05d}.json',row)
  try:
   status,raw=self.fetch(url);self.bytes+=len(raw);(self.out/f'response-{index:05d}.json').write_bytes(raw);row.update(http_status=status,bytes=len(raw),sha256=sha(raw))
   if status!=200 or len(raw)>self.p['max_response_bytes'] or self.bytes>self.p['max_bytes']:raise RuntimeError('Response status/byte cap failed')
   result=json.loads(raw)
   if result.get('error') is not None or not isinstance(result.get('result'),dict):raise ValueError('API error/schema')
   row['status']='completed';return result['result']
  except Exception as exc:row.update(status='failed',error=repr(exc));raise
  finally:
   row['elapsed_seconds']=time.monotonic()-tick;write(self.out/f'request-{index:05d}.json',row)
   if time.monotonic()-self.last_progress>=30:
    print(json.dumps(dict(requests=self.requests,response_bytes=self.bytes,completed_leaves=len(self.leaves),elapsed_seconds=time.monotonic()-self.started)),flush=True);self.last_progress=time.monotonic()
   if self.p['minimum_request_interval_seconds']:time.sleep(max(0,self.p['minimum_request_interval_seconds']-(time.monotonic()-tick)))
 def trades(self,lo,hi):
  """Inclusive integer millisecond interval, recursively partitioned without gaps."""
  r=self.request('get_last_trades_by_currency_and_time',dict(currency='BTC',kind='option',start_timestamp=lo,end_timestamp=hi,count=1000,sorting='asc'))
  rows=r.get('trades');more=r.get('has_more')
  if not isinstance(rows,list) or type(more) is not bool or len(rows)>1000:raise ValueError('Trade schema')
  for t in rows:
   if not isinstance(t,dict) or type(t.get('timestamp')) is not int or not lo<=t['timestamp']<=hi or not isinstance(t.get('trade_id'),str) or not t['trade_id']:raise ValueError('Trade identity/time')
   if not isinstance(t.get('instrument_name'),str) or not t['instrument_name'].startswith('BTC-') or not t['instrument_name'].endswith(('-C','-P')):raise ValueError('Nonoption trade')
   if t.get('direction') not in ('buy','sell') or not finite(t.get('amount')) or t['amount']<=0 or not finite(t.get('price')) or t['price']<=0:raise ValueError('Trade value')
   payload=canonical(t);old=self.db.execute('SELECT payload FROM trades WHERE id=?',(t['trade_id'],)).fetchone()
   if old is not None and old[0]!=payload:raise ValueError('Conflicting duplicate trade ID')
   self.db.execute('INSERT OR IGNORE INTO trades VALUES (?,?)',(t['trade_id'],payload))
  self.db.commit()
  if more:
   if lo==hi:raise ValueError('Unresolved saturated one-millisecond interval')
   mid=(lo+hi)//2;self.trades(lo,mid);self.trades(mid+1,hi)
  else:
   self.leaves.append({'start_ms':lo,'end_ms':hi,'count':len(rows),'request_index':self.requests-1});write(self.out/'completed-trade-leaves.json',self.leaves)
 def day_bars(self,lo):
  r=self.request('get_tradingview_chart_data',dict(instrument_name='BTC-PERPETUAL',start_timestamp=lo,end_timestamp=lo+DAY-1,resolution='30'))
  expected=list(range(lo,lo+DAY,HALF))
  if r.get('status')!='ok' or r.get('ticks')!=expected:raise ValueError('Missing/irregular bar grid')
  for k in ('open','high','low','close','volume'):
   if not isinstance(r.get(k),list) or len(r[k])!=48 or any(not finite(v) or v<0 or (k!='volume' and v==0) for v in r[k]):raise ValueError('Invalid bar values')
  for i,t in enumerate(expected):
   row={k:r[k][i] for k in ('open','high','low','close','volume')}
   if not row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:raise ValueError('Inconsistent OHLC')
   self.bars.append(dict(open_ms=t,close_available_ms=t+HALF,**row))
 def run(self):
  result={'status':'incomplete','complete':False,'estimand':self.p['estimand']}
  try:
   for lo in range(self.p['start_ms'],self.p['end_ms_exclusive'],DAY):self.trades(lo,lo+DAY-1);self.day_bars(lo)
   leaves=sorted(self.leaves,key=lambda x:x['start_ms']);cursor=self.p['start_ms']
   for leaf in leaves:
    if leaf['start_ms']!=cursor:raise ValueError('Trade coverage gap/overlap')
    cursor=leaf['end_ms']+1
   if cursor!=self.p['end_ms_exclusive']:raise ValueError('Trade coverage incomplete')
   import bisect
   ends=[leaf['end_ms'] for leaf in leaves]
   for (payload,) in self.db.execute('SELECT payload FROM trades'):
    stamp=json.loads(payload)['timestamp'];i=bisect.bisect_left(ends,stamp)
    if i==len(leaves) or not leaves[i]['start_ms']<=stamp<=leaves[i]['end_ms']:raise ValueError('Stored trade outside completed leaves')
   write(self.out/'bars.json',self.bars)
   with (self.out/'trades.jsonl').open('x',encoding='utf-8') as f:
    for (payload,) in self.db.execute('SELECT payload FROM trades ORDER BY id'):f.write(payload+'\n')
   result.update(status='completed',complete=True,trade_count=self.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0],bar_count=len(self.bars))
  except Exception as exc:result['error']=repr(exc)
  finally:
   try:
    if sha(Path(__file__).read_bytes())!=self.source_sha or (self.protocol_path and sha(self.protocol_path.read_bytes())!=self.protocol_sha):raise ValueError('Source or protocol content changed')
   except Exception as exc:result.update(status='incomplete',complete=False,integrity_error=repr(exc))
   self.db.close();result.update(requests=self.requests,response_bytes=self.bytes,elapsed_seconds=time.monotonic()-self.started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());write(self.out/'terminal.json',result)
  return result

def validate(p):
 if p.get('schema')!='historical-pooled-option-flow-v1':raise ValueError('Protocol schema')
 for k in ('start_ms','end_ms_exclusive','max_requests','max_bytes','max_seconds','max_response_bytes','minimum_free_bytes'):
  if type(p.get(k)) is not int or p[k]<=0:raise ValueError(k)
 if p['start_ms']%DAY or p['end_ms_exclusive']%DAY or p['end_ms_exclusive']<=p['start_ms']:raise ValueError('UTC full-day interval required')
 if not finite(p.get('minimum_request_interval_seconds')) or p['minimum_request_interval_seconds']<.5:raise ValueError('Request pacing required')
 return p
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--protocol',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args();p=validate(json.loads(a.protocol.read_text()))
 if p.get('status')!='frozen_authorized':raise SystemExit('CLI requires frozen_authorized protocol')
 raise SystemExit(0 if Collector(p,a.out,protocol_path=a.protocol).run()['complete'] else 1)
