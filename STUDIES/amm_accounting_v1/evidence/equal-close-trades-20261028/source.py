"""Fixed nine-interval historical trade probe; truncated lists stay incomplete."""
import hashlib,json,sys,time,urllib.request,urllib.parse,urllib.error
from pathlib import Path


def run(audit_path,out):
    raw=Path(audit_path).read_bytes();audit=json.loads(raw)
    assert audit['equal_close_pairs']==9 and len(audit['pairs'])==9
    out=Path(out);out.mkdir(exist_ok=False);started=time.monotonic();rows=[]
    source=Path(__file__).read_bytes()
    plan=dict(audit_sha256=hashlib.sha256(raw).hexdigest(),source_sha256=hashlib.sha256(source).hexdigest(),requests=9,count=1000,sorting='desc',per_request_bytes=2097152,timeout_seconds=20,whole_seconds=210,retries=0,scope='Existing nine anomalous intervals only; no new confirmatory panel')
    (out/'PLAN.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'INPUT.json').write_bytes(raw)
    for j,pair in enumerate(audit['pairs']):
        bar=pair['current'];lo=bar['open_ms'];hi=bar['close_available_ms']-1
        params=dict(instrument_name='BTC-PERPETUAL',start_timestamp=lo,end_timestamp=hi,count=1000,sorting='desc')
        url='https://history.deribit.com/api/v2/public/get_last_trades_by_instrument_and_time?'+urllib.parse.urlencode(params)
        row=dict(index=pair['index'],request=url,start_ms=lo,end_ms=hi,bar_close=bar['close'],bar_volume=bar['volume'])
        (out/f'request-{j:02d}.json').write_text(json.dumps(row,indent=2)+'\n')
        try:
            remaining=210-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError('Whole probe deadline')
            req=urllib.request.Request(url,headers={'User-Agent':'owalnuts-observation-audit/1','Accept':'application/json'})
            try:
                with urllib.request.urlopen(req,timeout=min(20,remaining)) as response:status=response.status;body=response.read(2097153)
            except urllib.error.HTTPError as e:status=e.code;body=e.read(2097153)
            (out/f'response-{j:02d}.json').write_bytes(body)
            row.update(http_status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
            if status!=200 or len(body)>2097152:raise ValueError('HTTP/byte admission')
            payload=json.loads(body)
            if payload.get('error') is not None:raise ValueError('RPC error '+str(payload['error']))
            result=payload['result'];trades=result['trades'];more=result['has_more']
            if type(more)is not bool or not isinstance(trades,list):raise ValueError('Schema')
            if any(t['instrument_name']!='BTC-PERPETUAL' or not lo<=t['timestamp']<=hi for t in trades):raise ValueError('Out-of-scope trade')
            seq=[t['trade_seq'] for t in trades]
            if seq!=sorted(set(seq),reverse=True):raise ValueError('Duplicate/unordered sequence')
            row.update(status='observed',trades=len(trades),has_more=more,complete_interval=not more,last_price=None if not trades else trades[0]['price'],close_match=None if not trades else trades[0]['price']==bar['close'])
        except Exception as e:row.update(status='failed',error=repr(e),complete_interval=False)
        rows.append(row);time.sleep(.5)
    result=dict(plan=plan,rows=rows,elapsed_seconds=time.monotonic()-started)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':run(sys.argv[1],sys.argv[2])
