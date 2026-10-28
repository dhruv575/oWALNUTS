"""Fixed finalized range, bounded read-only liquidity-event discovery."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from Crypto.Hash import keccak
from pair_snapshot import BLOCK, BLOCK_HASH

PAIR='0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc'
START=BLOCK-4095
ENDPOINT='https://eth.drpc.org'


def topic(signature):return '0x'+keccak.new(digest_bits=256,data=signature.encode()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    topics=[topic('Mint(address,uint256,uint256)'),topic('Burn(address,uint256,uint256,address)')]
    write(root/'PLAN.json',dict(scope='Fixed-range liquidity discovery only; not accounting validation or strategy evaluation',
        pair=PAIR,start=START,end=BLOCK,end_hash=BLOCK_HASH,endpoint=ENDPOINT,topics=topics,
        max_requests=20,total_seconds=120,max_response_bytes=2097152,max_total_bytes=8388608,
        timeout_seconds=15,minimum_interval_seconds=.25,retries=0,max_event_blocks=8,
        sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('pair_snapshot.py'))}))
    started=time.monotonic();previous=0.;result=dict(status='incomplete',completed_requests=0,response_bytes=0)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(role,method,params):
        nonlocal previous
        if method not in ('eth_chainId','eth_getLogs','eth_getBlockByNumber'):raise ValueError('Read-only allowlist')
        time.sleep(max(0,.25-(time.monotonic()-previous)));remaining=120-(time.monotonic()-started)
        index=result['completed_requests']
        if remaining<=0 or index>=20:raise TimeoutError('Acquisition cap')
        call=dict(jsonrpc='2.0',id=index+1,method=method,params=params);raw=json.dumps(call).encode()
        (root/f'{index:02d}-{role}-request.json').write_bytes(raw)
        request=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-fixed-liquidity-probe/1'})
        previous=time.monotonic()
        with urllib.request.build_opener(NoRedirect).open(request,timeout=min(15,remaining)) as response:
            body=response.read(2097153);(root/f'{index:02d}-{role}-response.json').write_bytes(body)
        result['response_bytes']+=len(body)
        if len(body)>2097152 or result['response_bytes']>8388608:raise ValueError('Byte cap')
        data=json.loads(body)
        if data.get('id')!=call['id'] or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('RPC response identity or error')
        result['completed_requests']+=1
        return data['result']
    def logs(role,lo,hi):return rpc(role,'eth_getLogs',[dict(address=PAIR,fromBlock=hex(lo),toBlock=hex(hi),topics=[topics])])
    try:
        if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        if rpc('anchor','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor mismatch')
        events=logs('full',START,BLOCK);split=[]
        for i in range(4):split.extend(logs(f'quarter-{i}',START+1024*i,START+1024*(i+1)-1))
        if not isinstance(events,list) or events!=split:raise ValueError('Full/split mismatch')
        write(root/'EVENTS.json',events)
        blocks=sorted({int(e['blockNumber'],16) for e in events})
        if len(blocks)>8:raise ValueError('Event-block cap; retain discovery without selecting a subset')
        headers={n:rpc(f'event-block-{n}','eth_getBlockByNumber',[hex(n),False]) for n in blocks}
        keys=[]
        for e in events:
            n=int(e['blockNumber'],16)
            if not START<=n<=BLOCK or e.get('removed') is not False or e['address'].lower()!=PAIR or e['topics'][0] not in topics:
                raise ValueError('Event identity mismatch')
            if int(headers[n]['number'],16)!=n or e['blockHash']!=headers[n]['hash']:raise ValueError('Event block mismatch')
            keys.append((n,int(e['transactionIndex'],16),int(e['logIndex'],16)))
        if keys!=sorted(set(keys)):raise ValueError('Event order or duplicate')
        if rpc('anchor-recheck','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Anchor changed')
        write(root/'HEADERS.json',headers)
        result.update(status='complete',events=len(events),event_blocks=len(blocks),
            limitation='One provider; full/split agreement and event block identities, not independent completeness or full header ancestry. No liquidity accounting validated.')
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['elapsed_seconds']=time.monotonic()-started;write(root/'FINAL.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');a=p.parse_args();print(json.dumps(run(a.root)))
