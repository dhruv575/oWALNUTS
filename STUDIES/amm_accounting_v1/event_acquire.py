"""Fixed 64-block pool-event engineering acquisition; no strategy evaluation."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from rpc_probe import write
from pair_snapshot import BLOCK, BLOCK_HASH, words

PAIR='0xb4e16d0168e52d35cacd2c6185b44281ec28c9dc'
START=BLOCK-63
ENDPOINT='https://eth.drpc.org'


def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    source=Path(__file__)
    write(root/'PLAN.json',dict(scope='Fixed 64-block accounting-data engineering panel; no policy evaluation',
                               endpoint=ENDPOINT,pair=PAIR,start=START,end=BLOCK,end_hash=BLOCK_HASH,
                               max_requests=80,max_bytes=20971520,max_response_bytes=2097152,total_seconds=240,
                               timeout_seconds=15,minimum_interval_seconds=.25,retries=0,
                               sources={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,source.with_name('pair_snapshot.py'),source.with_name('rpc_probe.py'))}))
    result=dict(status='incomplete',completed_requests=0,response_bytes=0);started=time.monotonic();previous=0.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(role,method,params):
        nonlocal previous
        index=result['completed_requests']
        time.sleep(max(0,.25-(time.monotonic()-previous)))
        remaining=240-(time.monotonic()-started)
        if index>=80 or remaining<=0:raise TimeoutError('Acquisition bound')
        if method not in ('eth_chainId','eth_call','eth_getLogs','eth_getBlockByNumber'):raise ValueError('Read-only methods only')
        call=dict(jsonrpc='2.0',id=index+1,method=method,params=params);raw=json.dumps(call).encode()
        (root/f'{index:02d}-{role}-request.json').write_bytes(raw)
        request=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-fixed-pool-events/1'})
        previous=time.monotonic()
        with urllib.request.build_opener(NoRedirect).open(request,timeout=min(15,remaining)) as response:
            body=response.read(2097153)
            (root/f'{index:02d}-{role}-response.json').write_bytes(body)
            write(root/f'{index:02d}-{role}-metadata.json',dict(http_status=response.status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        result['response_bytes']+=len(body)
        if len(body)>2097152 or result['response_bytes']>20971520:raise ValueError('Byte cap')
        data=json.loads(body)
        if data.get('id')!=call['id'] or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('RPC error or identity mismatch')
        result['completed_requests']+=1
        return data['result']
    def state(role,block):
        reserves=words(rpc(role+'-reserves','eth_call',[dict(to=PAIR,data='0x0902f1ac'),hex(block)]),3)
        supply=words(rpc(role+'-supply','eth_call',[dict(to=PAIR,data='0x18160ddd'),hex(block)]),1)[0]
        return dict(block=block,reserves_raw=reserves,total_supply_raw=supply)
    def logs(role,lo,hi):return rpc(role,'eth_getLogs',[dict(address=PAIR,fromBlock=hex(lo),toBlock=hex(hi))])
    try:
        if rpc('chain','eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        header=rpc('end-header','eth_getBlockByNumber',[hex(BLOCK),False])
        if header['hash']!=BLOCK_HASH:raise ValueError('Pinned end hash mismatch')
        initial=state('initial',START-1);final=state('final',BLOCK)
        all_logs=logs('full',START,BLOCK)
        middle=START+31
        split=logs('left',START,middle)+logs('right',middle+1,BLOCK)
        if not isinstance(all_logs,list) or all_logs!=split:raise ValueError('Full/split log response mismatch')
        headers=[]
        for number in range(START-1,BLOCK):
            h=rpc(f'block-{number}','eth_getBlockByNumber',[hex(number),False])
            if int(h['number'],16)!=number:raise ValueError('Header number mismatch')
            headers.append(h)
        headers.append(header)
        for left,right in zip(headers,headers[1:]):
            if right['parentHash']!=left['hash']:raise ValueError('Header ancestry mismatch')
        hashes={int(h['number'],16):h['hash'] for h in headers}
        keys=[]
        for log in all_logs:
            number=int(log['blockNumber'],16)
            if not START<=number<=BLOCK or log.get('removed') is not False or log['address'].lower()!=PAIR or log['blockHash']!=hashes[number]:raise ValueError('Log identity or canonical-header mismatch')
            keys.append((number,int(log['transactionIndex'],16),int(log['logIndex'],16)))
        if keys!=sorted(set(keys)):raise ValueError('Log ordering or duplicate')
        if rpc('end-recheck','eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('End hash changed')
        write(root/'EVENTS.json',all_logs)
        write(root/'HEADERS.json',headers)
        write(root/'STATES.json',dict(initial=initial,final=final))
        result.update(status='complete',logs=len(all_logs),headers=len(headers),start=START,end=BLOCK,
                      completeness_scope='Full versus two half-range responses and header ancestry agree; provider-independent completeness not established')
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['elapsed_seconds']=time.monotonic()-started;write(root/'FINAL.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args();print(json.dumps(run(args.root)))
