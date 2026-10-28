"""Fixed block-boundary state and logs; not pre-transaction state."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
from pair_snapshot import BLOCK,BLOCK_HASH,FACTORY,USDC,WETH,words
from liquidity_receipts import EVENTS_SHA

PAIR='0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc'
ENDPOINT='https://mainnet.gateway.tenderly.co'
BALANCE='0x70a08231'+'0'*24+PAIR[2:]
CALLS=[('reserves',PAIR,'0x0902f1ac',3),('supply',PAIR,'0x18160ddd',1),
       ('k_last',PAIR,'0x7464fc3d',1),('fee_to',FACTORY,'0x017e7e58',1),
       ('balance_usdc',USDC,BALANCE,1),('balance_weth',WETH,BALANCE,1),('pair_lp_balance',PAIR,BALANCE,1)]


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def run(events_path,out):
    events_path=Path(events_path)
    if hashlib.sha256(events_path.read_bytes()).hexdigest()!=EVENTS_SHA:raise ValueError('Frozen events')
    events=json.loads(events_path.read_bytes());event_blocks=sorted({int(e['blockNumber'],16) for e in events})
    if len(events)!=5 or len(event_blocks)!=3:raise ValueError('Fixed events')
    blocks=sorted({n for b in event_blocks for n in (b-1,b)})
    out=Path(out);out.mkdir(exist_ok=False)
    write(out/'PLAN.json',dict(scope='Block-boundary states and complete pair/token block logs; not pre-transaction state',
          endpoint=ENDPOINT,events_sha256=EVENTS_SHA,event_blocks=event_blocks,state_blocks=blocks,state_calls=CALLS,
          max_requests=70,total_seconds=180,max_response_bytes=4194304,max_total_bytes=20971520,timeout_seconds=15,
          minimum_interval_seconds=.25,retries=0,sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in
          (Path(__file__),Path(__file__).with_name('pair_snapshot.py'),Path(__file__).with_name('liquidity_receipts.py'))}))
    result=dict(status='incomplete',completed_requests=0,response_bytes=0);started=time.monotonic();previous=0.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(role,method,params):
        nonlocal previous
        if method not in ('eth_chainId','eth_getBlockByNumber','eth_call','eth_getLogs'):raise ValueError('Read-only allowlist')
        time.sleep(max(0,.25-(time.monotonic()-previous)));remaining=180-(time.monotonic()-started);i=result['completed_requests']
        if i>=70 or remaining<=0:raise TimeoutError('Acquisition bound')
        call=dict(jsonrpc='2.0',id=i+1,method=method,params=params);raw=json.dumps(call).encode()
        (out/f'{i:02d}-{role}-request.json').write_bytes(raw);previous=time.monotonic()
        req=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-liquidity-state/1'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=min(15,remaining)) as response:body=response.read(4194305)
        except urllib.error.HTTPError as exc:
            (out/f'{i:02d}-{role}-http-error.bin').write_bytes(exc.read(4194305));raise
        (out/f'{i:02d}-{role}-response.json').write_bytes(body);result['response_bytes']+=len(body)
        if len(body)>4194304 or result['response_bytes']>20971520:raise ValueError('Byte cap')
        data=json.loads(body)
        if data.get('id')!=i+1 or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('RPC response identity or error')
        result['completed_requests']+=1
        return data['result']
    try:
        if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        if rpc('anchor','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor mismatch')
        headers={};states={};logs={}
        for n in blocks:
            h=rpc(f'header-{n}','eth_getBlockByNumber',[hex(n),False]);headers[n]=h
            if int(h['number'],16)!=n:raise ValueError('Header number mismatch')
            states[n]={}
            for name,to,data,count in CALLS:
                value=words(rpc(f'{n}-{name}','eth_call',[dict(to=to,data=data),hex(n)]),count)
                states[n][name]=value if count>1 else value[0]
        for n in event_blocks:
            if headers[n]['parentHash']!=headers[n-1]['hash'] or any(e['blockHash']!=headers[n]['hash'] for e in events if int(e['blockNumber'],16)==n):raise ValueError('Event boundary ancestry mismatch')
            entries=rpc(f'logs-{n}','eth_getLogs',[dict(address=[PAIR,USDC,WETH],fromBlock=hex(n),toBlock=hex(n))]);keys=[]
            for e in entries:
                if e['blockHash']!=headers[n]['hash'] or int(e['blockNumber'],16)!=n or e['address'].lower() not in (PAIR,USDC,WETH) or e.get('removed') is not False:raise ValueError('Block log identity mismatch')
                keys.append((int(e['transactionIndex'],16),int(e['logIndex'],16)))
            if keys!=sorted(set(keys)):raise ValueError('Block log ordering')
            logs[n]=entries
        for n in blocks:
            if rpc(f'recheck-{n}','eth_getBlockByNumber',[hex(n),False])['hash']!=headers[n]['hash']:raise ValueError('State block changed')
        if rpc('anchor-recheck','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor changed')
        write(out/'STATES.json',states);write(out/'BLOCK-LOGS.json',logs);write(out/'HEADERS.json',headers)
        result.update(status='complete',state_blocks=len(states),event_blocks=len(logs),logs=sum(map(len,logs.values())),
                      limitation='One provider; block-end calls are not pre-transaction balances. Transfer semantics and liquidity reconciliation remain unvalidated.')
    except Exception as exc:result['error']=repr(exc)
    finally:result['elapsed_seconds']=time.monotonic()-started;write(out/'FINAL.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('events');p.add_argument('out');a=p.parse_args();print(json.dumps(run(a.events,a.out)))
