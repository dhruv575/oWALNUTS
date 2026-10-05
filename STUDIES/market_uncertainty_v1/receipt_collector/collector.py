"""Public feed recorder. Local receipt times, explicit gaps; no completeness claim."""
import argparse,asyncio,collections,hashlib,json,shutil,time
from pathlib import Path
URL='wss://www.deribit.com/ws/api/v2'
class ByteCap(Exception):pass
class ProtocolError(Exception):pass
class DiskFloor(Exception):pass
class Recorder:
 def __init__(self,out,cap):self.out=out;self.cap=cap;self.used=0
 def save(self,name,value):
  raw=(json.dumps(value,separators=(',',':'),allow_nan=False)+'\n').encode()
  if self.used+len(raw)>self.cap:raise ByteCap()
  with (self.out/name).open('ab' if name.endswith('.jsonl') else 'xb') as f:f.write(raw)
  self.used+=len(raw)
def stamp():return dict(receipt_utc_ns=time.time_ns(),receipt_monotonic_ns=time.monotonic_ns())
def discover(option_quotes,deadline):
 import requests
 def get(method,params):
  remaining=deadline-time.monotonic()
  if remaining<=0:raise TimeoutError('Discovery deadline')
  r=requests.get('https://www.deribit.com/api/v2/public/'+method,params=params,timeout=(min(3,remaining),min(3,remaining)));r.raise_for_status();v=r.json()
  if 'error' in v:raise ProtocolError(str(v['error']))
  return v
 metadata=get('get_instruments',dict(currency='BTC',kind='option',expired='false'))
 snapshot=get('get_book_summary_by_currency',dict(currency='BTC',kind='option')) if option_quotes else {'result':[]}
 available={r['instrument_name']:r for r in metadata['result'] if r.get('is_active')}
 selected=[r['instrument_name'] for r in sorted(snapshot['result'],key=lambda r:(-float(r.get('volume') or 0),r['instrument_name'])) if r['instrument_name'] in available][:option_quotes]
 if len(selected)!=option_quotes:raise ProtocolError('Insufficient active instruments in initial snapshot')
 perpetual=get('get_instrument',dict(instrument_name='BTC-PERPETUAL'))
 return dict(metadata=metadata,snapshot=snapshot,perpetual=perpetual,selected=selected,**stamp())
async def collect(out,duration,byte_cap,minimum_free_bytes,option_quotes=0,max_reconnects=3,*,discovery=None,connector=None):
 if duration<=0 or byte_cap<=0 or minimum_free_bytes<0 or not 0<=option_quotes<=20 or max_reconnects<0:raise ValueError('Invalid bounds')
 out=Path(out);out.mkdir(parents=True,exist_ok=False);rec=Recorder(out,byte_cap);start=time.monotonic();deadline=start+duration
 result=dict(schema='public-receipt-collector-v2',status='started',target='BTC-PERPETUAL quoted prices; not index or executable fill',duration_seconds=duration,byte_cap=byte_cap,minimum_free_bytes=minimum_free_bytes,counts={},gaps=[],connections=0)
 counts=collections.Counter();gap=None;coverage=None;last_receipt=stamp();result['coverage_intervals']=[]
 def event(kind,**fields):rec.save('lifecycle.jsonl',dict(kind=kind,**stamp(),**fields))
 try:
  free=shutil.disk_usage(out).free;result['initial_free_bytes']=free
  if free<minimum_free_bytes:raise DiskFloor('Disk admission failed')
  event('started')
  data=discovery(option_quotes) if discovery is not None else discover(option_quotes,deadline)
  rec.save('discovery.json',data)
  channels=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2']+['ticker.'+n+'.agg2' for n in data['selected']]
  rec.save('selection.json',dict(selected=data['selected'],channels=channels,rule='Initial active-instrument snapshot only; descending reported volume then lexical; never refreshed',flow_universe='All BTC option trade channel; selected options affect optional quotes only'))
  if connector is None:
   import websockets
   connector=lambda:websockets.connect(URL,open_timeout=10,close_timeout=3,max_size=min(byte_cap,2_000_000))
  retries=0
  while time.monotonic()<deadline:
   if shutil.disk_usage(out).free<minimum_free_bytes:raise DiskFloor('Disk admission failed before connection')
   try:
    last_receipt=stamp()
    async with asyncio.timeout(max(.001,deadline-time.monotonic())), connector() as ws:
     result['connections']+=1;connection=result['connections'];event('connected',connection=connection)
     await ws.send(json.dumps(dict(jsonrpc='2.0',id=1,method='public/subscribe',params=dict(channels=channels))))
     acknowledged=False;ack_deadline=min(deadline,time.monotonic()+10)
     while time.monotonic()<deadline:
      wait_until=deadline if acknowledged else ack_deadline
      try:raw=await asyncio.wait_for(ws.recv(),max(.001,wait_until-time.monotonic()))
      except asyncio.TimeoutError:
       if not acknowledged:raise ProtocolError('Subscription acknowledgment deadline')
       break
      receipt=stamp();last_receipt=receipt;raw=raw.decode() if isinstance(raw,bytes) else raw
      message=json.loads(raw);rec.save('receipts.jsonl',dict(**receipt,connection=connection,raw=raw))
      if 'error' in message:raise ProtocolError(str(message['error']))
      if message.get('id')==1:
       if set(message.get('result',[]))!=set(channels):raise ProtocolError('Subscription acknowledgment differs')
       acknowledged=True;event('subscribed',connection=connection)
       coverage=dict(connection=connection,start_utc_ns=receipt['receipt_utc_ns'],start_monotonic_ns=receipt['receipt_monotonic_ns']);result['coverage_intervals'].append(coverage)
       if gap is not None:gap.update(resubscribed_utc_ns=receipt['receipt_utc_ns'],resubscribed_monotonic_ns=receipt['receipt_monotonic_ns']);gap=None
      channel=message.get('params',{}).get('channel')
      if channel:
       if not acknowledged:raise ProtocolError('Data arrived before subscription acknowledgment')
       if channel not in channels:raise ProtocolError('Unexpected channel')
       counts[channel]+=1
      if shutil.disk_usage(out).free<minimum_free_bytes:raise DiskFloor('Disk floor reached')
     if acknowledged:break
   except asyncio.TimeoutError:
    if time.monotonic()>=deadline:break
    raise
   except (ByteCap,ProtocolError,DiskFloor):raise
   except Exception as exc:
    gap=dict(start_utc_ns=last_receipt['receipt_utc_ns'],start_monotonic_ns=last_receipt['receipt_monotonic_ns'],detected_utc_ns=time.time_ns(),detected_monotonic_ns=time.monotonic_ns(),error=repr(exc));
    if coverage is not None:coverage.update(end_utc_ns=gap['start_utc_ns'],end_monotonic_ns=gap['start_monotonic_ns']);coverage=None
    result['gaps'].append(gap);event('connection_gap',**gap)
    if retries>=max_reconnects:raise RuntimeError('Reconnect budget exhausted') from exc
    retries+=1
    await asyncio.sleep(min(.25,max(0,deadline-time.monotonic())))
  result['status']='duration_complete_with_gaps' if result['gaps'] else 'duration_complete'
  if not result['connections'] or not counts:result['status']='no_data'
 except ByteCap:result['status']='byte_cap_reached'
 except asyncio.TimeoutError:result['status']='discovery_timeout'
 except Exception as exc:result.update(status='failed',error=repr(exc))
 finally:
  ended=stamp();result.update(end_utc_ns=ended['receipt_utc_ns'],end_monotonic_ns=ended['receipt_monotonic_ns'])
  if coverage is not None:coverage.update(end_utc_ns=ended['receipt_utc_ns'],end_monotonic_ns=ended['receipt_monotonic_ns'])
  result.update(elapsed_seconds=time.monotonic()-start,bytes_written=rec.used,counts=dict(counts),limitations=['Local UTC clock uncertified; monotonic timestamps process-local','Aggregated feed, no completeness guarantee, no gap filling','Reconnect intervals excluded by downstream as-of builder','Control summary outside payload cap; synchronous discovery connect/read each bounded3seconds (up to6seconds final request overrun), no background thread; websocket close up to3seconds'])
  result['files_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
  with (out/'summary.json').open('x') as f:json.dump(result,f,indent=2)
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);p.add_argument('--duration',type=float,required=True);p.add_argument('--byte-cap',type=int,required=True);p.add_argument('--minimum-free-bytes',type=int,default=1024**3);p.add_argument('--option-quotes',type=int,default=0);p.add_argument('--max-reconnects',type=int,default=3);a=p.parse_args()
 result=asyncio.run(collect(a.output,a.duration,a.byte_cap,a.minimum_free_bytes,a.option_quotes,a.max_reconnects));print(json.dumps(result));return 0 if result['status']=='duration_complete' else 1
if __name__=='__main__':raise SystemExit(main())
