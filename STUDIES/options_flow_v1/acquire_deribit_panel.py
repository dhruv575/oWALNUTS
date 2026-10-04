"""Bounded public crypto access feasibility. No import-time network or fitting.
Run only after protocol review and quiet-window authorization. Fresh output only.
"""
import argparse,datetime,hashlib,json,math,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path

class Incomplete(RuntimeError):pass

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def millis(text):return int(datetime.datetime.fromisoformat(text).timestamp()*1000)
def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False)
def digest_bytes(value):return hashlib.sha256(value).hexdigest()
def canonical_digest(value):return digest_bytes(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
def validate_protocol(p):
    if p['production_base']!='https://www.deribit.com/api/v2/':raise ValueError('Only approved production base allowed')
    dates=[datetime.datetime.fromisoformat(p[k]) for k in ['start_utc','end_utc_exclusive']]
    if any(d.tzinfo is None or d.utcoffset()!=datetime.timedelta(0) for d in dates) or dates[1]<=dates[0]:raise ValueError('UTC-aware increasing panel bounds required')
    for k,v in p['limits'].items():
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:raise ValueError('Positive finite limits required')
    if p['limits']['requests_including_retries']>500 or p['limits']['raw_response_bytes']>50000000 or p['limits']['requests_per_second']>2:raise ValueError('Protocol exceeds hard ceilings')
    if not isinstance(p['count'],int) or isinstance(p['count'],bool) or not 1<=p['count']<=1000:raise ValueError('Invalid page size')
    if p['contracts']!=4 or p['minimum_retrieval_lag_hours']<48:raise ValueError('Invalid selection or aging constraint')
    if p['forecast']['origin_stride_minutes']<p['forecast']['horizon_minutes']:raise ValueError('Overlapping origins prohibited')

def eligible(trade,protocol):
    return not any(trade.get(k) is not None for k in protocol['exclude_flags'])
def valid_trade(t,lo,hi,instrument=None):
    required=['timestamp','trade_id','trade_seq','instrument_name','amount','price','direction']
    if any(k not in t for k in required):raise Incomplete('Missing trade fields')
    if not lo<=t['timestamp']<=hi:raise Incomplete('Trade outside requested bounds')
    if instrument is not None and t['instrument_name']!=instrument:raise Incomplete('Instrument mismatch')
    if t['direction'] not in ['buy','sell'] or not isinstance(t['trade_seq'],int):raise Incomplete('Invalid direction/sequence')
    if any(isinstance(t[k],bool) or not isinstance(t[k],(int,float)) or not math.isfinite(t[k]) or t[k]<=0 for k in ['price','amount']):raise Incomplete('Invalid trade price/amount')

def merge(rows):
    byid={};byseq={}
    for t in rows:
        key=str(t['trade_id']);seq=(t['instrument_name'],t['trade_seq'])
        if key in byid and byid[key]!=t:raise Incomplete('Conflicting duplicate trade ID')
        if seq in byseq and byseq[seq]!=key:raise Incomplete('Conflicting instrument sequence')
        byid[key]=t;byseq[seq]=key
    return sorted(byid.values(),key=lambda t:(t['timestamp'],t['instrument_name'],t['trade_seq']))

class Client:
    def __init__(self,protocol,out):
        self.protocol=protocol;self.out=Path(out);self.requests=0;self.bytes=0;self.last=-math.inf
        self.protocol_digest=canonical_digest(protocol);self.source_digest=digest_bytes(Path(__file__).read_bytes())
    def verify(self):
        if canonical_digest(self.protocol)!=self.protocol_digest or digest_bytes(Path(__file__).read_bytes())!=self.source_digest:raise Incomplete('Protocol/source mutation')
        saved=self.out/'protocol.json'
        if saved.exists() and canonical_digest(json.loads(saved.read_text()))!=self.protocol_digest:raise Incomplete('Archived protocol mutation')
    def request(self,method,params):
        self.verify()
        if method not in ['public/get_last_trades_by_currency_and_time','public/get_last_trades_by_instrument','public/get_instrument']:raise Incomplete('Unapproved API method')
        limits=self.protocol['limits'];url=self.protocol['production_base']+method+'?'+urllib.parse.urlencode(params)
        for attempt in range(limits['attempts_per_request']):
            self.verify()
            if self.requests>=limits['requests_including_retries'] or self.bytes>=limits['raw_response_bytes']:raise Incomplete('Acquisition budget exhausted')
            time.sleep(max(0,1/limits['requests_per_second']-(time.monotonic()-self.last)))
            self.last=time.monotonic();self.requests+=1;stem=f'{self.requests:04d}'
            record=dict(method=method,params=params,url=url,attempt=attempt+1,started_utc=utc())
            raw=b'';error=None;status=None
            try:
                response=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'owalnuts-access-feasibility/1'}),timeout=limits['timeout_seconds'])
                with response:
                    status=response.status;remaining=limits['raw_response_bytes']-self.bytes
                    raw=response.read(remaining)
                    # Conservatively fail if exact budget reached; never read past budget.
            except urllib.error.HTTPError as exc:
                status=exc.code;raw=exc.read(limits['raw_response_bytes']-self.bytes);error=str(exc)
            except (OSError,TimeoutError) as exc:error=str(exc)
            self.bytes+=len(raw);record.update(finished_utc=utc(),http_status=status,error=error,response_bytes=len(raw),response_sha256=digest_bytes(raw),cumulative_requests=self.requests,cumulative_raw_bytes=self.bytes)
            with (self.out/(stem+'.response')).open('xb') as f:f.write(raw)
            write_new(self.out/(stem+'.request.json'),record)
            self.verify()
            if self.bytes>=limits['raw_response_bytes']:raise Incomplete('Raw-byte budget reached; response may be truncated')
            if error or status!=200:
                if status is not None and status not in [429,500,502,503,504]:raise Incomplete('HTTP access failure')
                continue
            try:payload=json.loads(raw)
            except (ValueError,UnicodeError) as exc:raise Incomplete('Invalid JSON response') from exc
            if 'error' in payload:raise Incomplete('API error: '+str(payload['error']))
            if 'result' not in payload:raise Incomplete('Missing API result')
            return payload['result']
        raise Incomplete('Request retries exhausted')

def discovery(client,protocol,lo,hi):
    """Inclusive overlapping recursion; saturated same-ms discovery fails closed."""
    pending=[(lo,hi)];complete=[]
    while pending:
        start,end=pending.pop();r=client.request('public/get_last_trades_by_currency_and_time',dict(currency='BTC',kind='option',start_timestamp=start,end_timestamp=end,count=protocol['count'],sorting='asc'))
        if not isinstance(r.get('has_more'),bool) or not isinstance(r.get('trades'),list):raise Incomplete('Missing pagination fields')
        for t in r['trades']:valid_trade(t,start,end)
        if r['has_more']:
            if start==end:raise Incomplete('Unresolved same-millisecond discovery saturation')
            mid=(start+end)//2
            if mid==start:pending.extend([(start,start),(end,end)])
            else:pending.extend([(mid,end),(start,mid)])
        else:complete.extend(r['trades'])
    return merge(complete)

def instrument_panel(client,protocol,name,lo,hi):
    # Never combine sequence/time filters: official docs do not define precedence.
    first=client.request('public/get_last_trades_by_instrument',dict(instrument_name=name,start_timestamp=lo,count=1,sorting='asc'))['trades']
    last_page=client.request('public/get_last_trades_by_instrument',dict(instrument_name=name,end_timestamp=hi,count=1,sorting='desc'))['trades']
    if not first or not last_page:raise Incomplete('Missing instrument boundary probes')
    valid_trade(first[0],lo,hi,name);valid_trade(last_page[0],lo,hi,name)
    lower=first[0]['trade_seq'];upper=last_page[0]['trade_seq']
    if upper<lower:raise Incomplete('Inconsistent frozen sequence bounds')
    rows=[];last=lower
    while True:
        params=dict(instrument_name=name,start_seq=last,end_seq=upper,count=protocol['count'],sorting='asc')
        r=client.request('public/get_last_trades_by_instrument',params);trades=r.get('trades')
        if not isinstance(trades,list) or not isinstance(r.get('has_more'),bool):raise Incomplete('Missing instrument pagination fields')
        for t in trades:valid_trade(t,lo,hi,name)
        sequences=[t['trade_seq'] for t in trades]
        if sequences!=sorted(sequences) or len(sequences)!=len(set(sequences)):raise Incomplete('Nonmonotonic/duplicate sequence page')
        if last is not None and (not sequences or sequences[0]!=last):raise Incomplete('Sequence boundary overlap not verified')
        rows.extend(trades)
        if not r['has_more']:
            if not sequences or sequences[-1]!=upper:raise Incomplete('Terminal sequence bound not reached')
            break
        if not sequences or (last is not None and sequences[-1]<=last):raise Incomplete('Pagination makes no progress')
        last=sequences[-1]
    result=merge(rows);seq=[t['trade_seq'] for t in result]
    if any(b!=a+1 for a,b in zip(seq,seq[1:])):raise Incomplete('Unexplained sequence gap; panel not fit-ready')
    return result

def collect(protocol,out):
    validate_protocol(protocol)
    start=millis(protocol['start_utc']);end=millis(protocol['end_utc_exclusive']);now=int(time.time()*1000)
    if now-end<protocol['minimum_retrieval_lag_hours']*3600000:raise Incomplete('Panel end has not aged48hours')
    out=Path(out);out.mkdir(parents=True,exist_ok=False);write_new(out/'protocol.json',protocol)
    client=Client(protocol,out);summary=dict(phase='public_crypto_access_feasibility',qualified=False,status='incomplete',started_utc=utc(),selected=[])
    try:
        first=discovery(client,protocol,start,start+86400000-1)
        volume={}
        for t in first:
            if eligible(t,protocol):volume[t['instrument_name']]=volume.get(t['instrument_name'],0.)+t['amount']
        selected=[];metadata={}
        for name in sorted(volume,key=lambda x:(-volume[x],x)):
            instrument=client.request('public/get_instrument',{'instrument_name':name});metadata[name]=instrument
            if instrument.get('instrument_name')!=name or instrument.get('kind')!='option' or instrument.get('base_currency')!='BTC':raise Incomplete('Contract metadata mismatch')
            if instrument['expiration_timestamp']>end and instrument['creation_timestamp']<=start:selected.append(name)
            if len(selected)==protocol['contracts']:break
        if len(selected)!=protocol['contracts']:raise Incomplete('Fewer than four eligible first-day contracts')
        write_new(out/'selection.json',dict(selected=selected,first_day_volume=volume,metadata=metadata,selection_completed_utc=utc()))
        summary['selected']=selected
        counts={}
        quality={}
        for ordinal,name in enumerate(selected,1):
            rows=instrument_panel(client,protocol,name,start,end-1)
            # Verify first-day discovery against independently paginated selected history.
            expected={str(t['trade_id']) for t in first if t['instrument_name']==name}
            actual={str(t['trade_id']) for t in rows if t['timestamp']<start+86400000}
            if actual!=expected:raise Incomplete('Discovery/instrument first-day disagreement')
            filename=f'trades-{ordinal:02d}.json'
            write_new(out/filename,rows);counts[name]=len(rows)
            quality[name]=dict(file=filename,total=len(rows),index_price_valid=sum(isinstance(t.get('index_price'),(int,float)) and math.isfinite(t['index_price']) and t['index_price']>0 for t in rows),mark_price_valid=sum(isinstance(t.get('mark_price'),(int,float)) and math.isfinite(t['mark_price']) and t['mark_price']>0 for t in rows))
        summary.update(status='complete_access_panel',trade_counts=counts,field_quality=quality,fit_ready=False,note='Acquisition completeness checks passed; separate leakage/feature/target audit still required, no model fit or US-market claim.')
    except Exception as exc:summary['error']=f'{type(exc).__name__}: {exc}'
    finally:
        try:client.verify()
        except Exception as exc:summary.update(status='incomplete',error=str(exc))
        summary.update(protocol_sha256=client.protocol_digest,source_sha256=client.source_digest,finished_utc=utc(),requests=client.requests,raw_response_bytes=client.bytes)
        write_new(out/'summary.json',summary)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--collect',action='store_true');a=p.parse_args()
    if not a.collect:p.error('Explicit --collect required; review protocol and wait for quiet window first')
    result=collect(json.loads(a.protocol.read_text()),a.out);print(json.dumps(result));raise SystemExit(0 if result['status']=='complete_access_panel' else 2)
