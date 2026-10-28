"""Bounded read-only call traces for the three fixed liquidity transactions."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
from liquidity_receipts import EVENTS_SHA,ENDPOINT,verify_receipt
from pair_snapshot import BLOCK,BLOCK_HASH


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def run(events_path,receipts_path,out):
    events_path,receipts_path=Path(events_path),Path(receipts_path)
    if hashlib.sha256(events_path.read_bytes()).hexdigest()!=EVENTS_SHA:raise ValueError('Fixed event identity')
    events=json.loads(events_path.read_bytes());receipts=json.loads(receipts_path.read_bytes())
    txs=list(dict.fromkeys(e['transactionHash'] for e in events))
    if len(txs)!=3 or len(receipts)!=3 or {r['transactionHash'] for r in receipts}!=set(txs):raise ValueError('Fixed receipt denominator')
    for r in receipts:verify_receipt(r,[e for e in events if e['transactionHash']==r['transactionHash']])
    out=Path(out);out.mkdir(exist_ok=False)
    options=dict(tracer='callTracer',timeout='10s',tracerConfig=dict(onlyTopCall=False))
    write(out/'PLAN.json',dict(scope='Read-only trace acquisition; no transaction execution or submission',endpoint=ENDPOINT,
          transactions=txs,options=options,max_requests=6,total_seconds=90,timeout_seconds=20,max_response_bytes=4194304,
          max_total_bytes=12582912,minimum_interval_seconds=.25,retries=0,
          inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (events_path,receipts_path)},
          sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('liquidity_receipts.py'),Path(__file__).with_name('pair_snapshot.py'))}))
    result=dict(status='incomplete',completed_requests=0,response_bytes=0);started=time.monotonic();previous=0.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(role,method,params):
        nonlocal previous
        if method not in ('eth_chainId','eth_getBlockByNumber','debug_traceTransaction'):raise ValueError('Read-only allowlist')
        time.sleep(max(0,.25-(time.monotonic()-previous)));remaining=90-(time.monotonic()-started);i=result['completed_requests']
        if i>=6 or remaining<=0:raise TimeoutError('Acquisition cap')
        call=dict(jsonrpc='2.0',id=i+1,method=method,params=params);raw=json.dumps(call).encode()
        (out/f'{i:02d}-{role}-request.json').write_bytes(raw);previous=time.monotonic()
        req=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-liquidity-traces/1'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=min(20,remaining)) as response:body=response.read(4194305)
        except urllib.error.HTTPError as exc:
            (out/f'{i:02d}-{role}-http-error.bin').write_bytes(exc.read(4194305));raise
        (out/f'{i:02d}-{role}-response.json').write_bytes(body);result['response_bytes']+=len(body)
        if len(body)>4194304 or result['response_bytes']>12582912:raise ValueError('Byte cap')
        data=json.loads(body)
        if data.get('id')!=i+1 or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('RPC identity or error')
        result['completed_requests']+=1
        return data['result']
    try:
        if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        if rpc('anchor','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor mismatch')
        traces=[]
        for i,tx in enumerate(txs):
            trace=rpc(f'trace-{i}','debug_traceTransaction',[tx,options])
            if not isinstance(trace,dict) or trace.get('error'):raise ValueError('Invalid or reverted root trace')
            traces.append(dict(transaction=tx,trace=trace))
        if rpc('anchor-recheck','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor changed')
        write(out/'TRACES.json',traces);result.update(status='complete',traces=len(traces),limitation='Single-provider execution traces; not independently replayed or yet interpreted')
    except Exception as exc:result['error']=repr(exc)
    finally:result['elapsed_seconds']=time.monotonic()-started;write(out/'FINAL.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('events');p.add_argument('receipts');p.add_argument('out');a=p.parse_args();print(json.dumps(run(a.events,a.receipts,a.out)))
