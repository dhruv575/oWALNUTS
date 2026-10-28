"""Bounded receipt acquisition for every transaction in fixed discovery evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import urllib.error
from pair_snapshot import BLOCK,BLOCK_HASH

EVENTS_SHA='424a0a2c616450ec451cea4b15ea4f349d69ec24fffd7793821121c3e2cf2d30'
ENDPOINT='https://mainnet.gateway.tenderly.co'


def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def verify_receipt(receipt,events):
    tx=events[0]['transactionHash'];block=events[0]['blockHash']
    if receipt['transactionHash']!=tx or receipt['blockHash']!=block or receipt['status']!='0x1':
        raise ValueError('Receipt transaction, block or success mismatch')
    keys=[int(log['logIndex'],16) for log in receipt['logs']]
    if keys!=sorted(set(keys)):raise ValueError('Receipt log ordering')
    lookup={log['logIndex']:log for log in receipt['logs']}
    fields=('address','topics','data','blockNumber','blockHash','transactionHash','transactionIndex','logIndex')
    for e in events:
        observed=lookup[e['logIndex']]
        if any(observed[k]!=e[k] for k in fields) or observed.get('removed') is not False:
            raise ValueError('Discovery and receipt log mismatch')


def run(events_path,out):
    events_path=Path(events_path)
    if hashlib.sha256(events_path.read_bytes()).hexdigest()!=EVENTS_SHA:raise ValueError('Frozen event identity')
    events=json.loads(events_path.read_bytes());txs=list(dict.fromkeys(e['transactionHash'] for e in events))
    blocks=sorted({int(e['blockNumber'],16) for e in events})
    if len(events)!=5 or len(txs)!=3 or len(blocks)!=3:raise ValueError('Fixed discovery dimensions')
    out=Path(out);out.mkdir(exist_ok=False)
    write(out/'PLAN.json',dict(scope='Receipts and event header identity only; no liquidity accounting claim',events_sha256=EVENTS_SHA,
          transactions=txs,blocks=blocks,endpoint=ENDPOINT,max_requests=12,total_seconds=90,max_response_bytes=2097152,
          max_total_bytes=8388608,timeout_seconds=15,minimum_interval_seconds=.25,retries=0,
          sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('pair_snapshot.py'))}))
    result=dict(status='incomplete',completed_requests=0,response_bytes=0);started=time.monotonic();previous=0.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(role,method,params):
        nonlocal previous
        if method not in ('eth_chainId','eth_getTransactionReceipt','eth_getBlockByNumber'):raise ValueError('Read-only allowlist')
        time.sleep(max(0,.25-(time.monotonic()-previous)));remaining=90-(time.monotonic()-started)
        i=result['completed_requests']
        if i>=12 or remaining<=0:raise TimeoutError('Acquisition bound')
        call=dict(jsonrpc='2.0',id=i+1,method=method,params=params);raw=json.dumps(call).encode()
        (out/f'{i:02d}-{role}-request.json').write_bytes(raw);previous=time.monotonic()
        req=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-fixed-liquidity-receipts/1'})
        try:
            with urllib.request.build_opener(NoRedirect).open(req,timeout=min(15,remaining)) as response:body=response.read(2097153)
        except urllib.error.HTTPError as exc:
            (out/f'{i:02d}-{role}-http-error.bin').write_bytes(exc.read(2097153));raise
        (out/f'{i:02d}-{role}-response.json').write_bytes(body);result['response_bytes']+=len(body)
        if len(body)>2097152 or result['response_bytes']>8388608:raise ValueError('Byte cap')
        data=json.loads(body)
        if data.get('id')!=i+1 or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('RPC identity or error')
        result['completed_requests']+=1
        return data['result']
    try:
        if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        if rpc('anchor','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor mismatch')
        receipts=[]
        for i,tx in enumerate(txs):
            r=rpc(f'receipt-{i}','eth_getTransactionReceipt',[tx]);verify_receipt(r,[e for e in events if e['transactionHash']==tx]);receipts.append(r)
        for n in blocks:
            h=rpc(f'header-{n}','eth_getBlockByNumber',[hex(n),False])
            if int(h['number'],16)!=n or any(e['blockHash']!=h['hash'] for e in events if int(e['blockNumber'],16)==n):raise ValueError('Event header mismatch')
        if rpc('anchor-recheck','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor changed')
        write(out/'RECEIPTS.json',receipts)
        result.update(status='complete',receipts=len(receipts),matched_events=len(events),
                      limitation='One provider; transaction receipts do not supply pre-transaction balances or complete intermediate state.')
    except Exception as exc:result['error']=repr(exc)
    finally:result['elapsed_seconds']=time.monotonic()-started;write(out/'FINAL.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('events');p.add_argument('out');a=p.parse_args();print(json.dumps(run(a.events,a.out)))
