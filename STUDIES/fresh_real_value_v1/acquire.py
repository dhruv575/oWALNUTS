"""Single fixed historical-bar acquisition; no forecast fitting or outcome display."""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,math,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path

DAY=86400000
HALF=1800000
BASE='https://history.deribit.com/api/v2/public/get_tradingview_chart_data'

def digest(raw):return hashlib.sha256(raw).hexdigest()

def write_json(path,value):
    with Path(path).open('x',encoding='utf8') as handle:
        json.dump(value,handle,indent=2,allow_nan=False);handle.write('\n')

def validate_protocol(p):
    expected=dict(instrument='BTC-PERPETUAL',resolution='30',first_day='2026-07-26',last_day='2026-08-31',
        request_count=37,hard_seconds=300,max_response_bytes=2097152,max_total_response_bytes=16777216,
        minimum_interval_seconds=.5,request_timeout_seconds=20)
    for key,value in expected.items():
        if p.get(key)!=value:raise ValueError('Frozen acquisition setting mismatch: '+key)
    if p.get('endpoint')!=BASE:raise ValueError('Endpoint mismatch')
    return expected

def day_starts(p):
    start=datetime.fromisoformat(p['first_day']).replace(tzinfo=timezone.utc)
    return [int((start+timedelta(days=i)).timestamp()*1000) for i in range(37)]

def validate_response(raw,lo):
    payload=json.loads(raw)
    if not isinstance(payload,dict) or payload.get('error') is not None:raise ValueError('API error/schema')
    result=payload.get('result')
    if not isinstance(result,dict) or result.get('status')!='ok':raise ValueError('Bar status/schema')
    expected=list(range(lo,lo+DAY,HALF));ticks=result.get('ticks')
    if not isinstance(ticks,list) or any(type(x)is not int for x in ticks) or ticks!=expected:
        raise ValueError('Missing/duplicate/out-of-order/extra bar timestamp')
    fields=['open','high','low','close','volume']
    for field in fields:
        values=result.get(field)
        if not isinstance(values,list) or len(values)!=48:raise ValueError('Bar array shape: '+field)
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<0 or (field!='volume' and v==0) for v in values):
            raise ValueError('Invalid bar domain: '+field)
    rows=[]
    for i,tick in enumerate(ticks):
        row={field:result[field][i] for field in fields}
        if not row['low']<=min(row['open'],row['close'])<=max(row['open'],row['close'])<=row['high']:
            raise ValueError('OHLC inequalities')
        rows.append(dict(open_ms=tick,close_available_ms=tick+HALF,**row))
    return rows

def fetch(url,timeout,max_bytes):
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    request=urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'owalnuts-frozen-historical-bars/1'})
    try:
        with urllib.request.build_opener(NoRedirect).open(request,timeout=timeout) as response:
            return response.status,response.read(max_bytes+1),dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code,error.read(max_bytes+1),dict(error.headers)

def acquire(protocol_path,out,fetcher=fetch,clock=time.monotonic,sleep=time.sleep):
    protocol_path=Path(protocol_path);raw_protocol=protocol_path.read_bytes();p=json.loads(raw_protocol)
    validate_protocol(p)
    if p.get('status')!='frozen_authorized':raise ValueError('Acquisition is not authorized by frozen protocol')
    source=Path(__file__);source_hash=digest(source.read_bytes())
    if p.get('acquire_source_sha256')!=source_hash:raise ValueError('Collector source binding mismatch')
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'protocol.json').write_bytes(raw_protocol)
    started=clock();previous=None;total=0;rows=[];completed=[];requests=0
    terminal=dict(status='incomplete',complete=False,planned_requests=37,planned_bars=1776,
        protocol_sha256=digest(raw_protocol),source_sha256=source_hash,started_utc=datetime.now(timezone.utc).isoformat(),
        scope='Fixed historical acquisition only; no forecast analysis or outcome-based selection')
    try:
        for index,lo in enumerate(day_starts(p)):
            if previous is not None:sleep(max(0,p['minimum_interval_seconds']-(clock()-previous)))
            remaining=p['hard_seconds']-(clock()-started)
            if remaining<=0:raise TimeoutError('Global acquisition deadline')
            params=dict(instrument_name=p['instrument'],start_timestamp=lo,end_timestamp=lo+DAY-1,resolution=p['resolution'])
            url=BASE+'?'+urllib.parse.urlencode(params);previous=clock();requests+=1
            request=dict(index=index,url=url,requested_utc=datetime.now(timezone.utc).isoformat(),start_ms=lo,end_ms=lo+DAY-1)
            write_json(out/f'request-{index:03d}.json',request)
            status,raw,headers=fetcher(url,min(p['request_timeout_seconds'],remaining),p['max_response_bytes'])
            with (out/f'response-{index:03d}.json').open('xb') as handle:handle.write(raw)
            total+=len(raw)
            write_json(out/f'response-{index:03d}-metadata.json',dict(http_status=status,headers=headers,bytes=len(raw),sha256=digest(raw)))
            if status!=200:raise ValueError('HTTP status '+str(status))
            if len(raw)>p['max_response_bytes'] or total>p['max_total_response_bytes']:raise ValueError('Response byte cap')
            if clock()-started>p['hard_seconds']:raise TimeoutError('Global acquisition deadline')
            rows.extend(validate_response(raw,lo));completed.append(index)
        expected=list(range(day_starts(p)[0],day_starts(p)[-1]+DAY,HALF))
        if [r['open_ms'] for r in rows]!=expected:raise ValueError('Whole acquisition grid mismatch')
        write_json(out/'bars.json',rows)
        if digest(source.read_bytes())!=source_hash or protocol_path.read_bytes()!=raw_protocol:raise ValueError('Source/protocol changed')
        terminal.update(status='complete',complete=True,bars_sha256=digest((out/'bars.json').read_bytes()))
    except Exception as error:
        terminal.update(error=type(error).__name__,reason=str(error))
    finally:
        terminal.update(completed_requests=completed,requests_attempted=requests,valid_bars=len(rows),response_bytes=total,
            elapsed_seconds=clock()-started,finished_utc=datetime.now(timezone.utc).isoformat())
        write_json(out/'terminal.json',terminal)
    return terminal

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--protocol',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args();terminal=acquire(args.protocol,args.out)
    print(json.dumps(terminal,indent=2));raise SystemExit(0 if terminal['complete'] else 1)
