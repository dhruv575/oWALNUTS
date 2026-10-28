"""Bounded read-only identity/state snapshot at a previously finalized block."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request
from rpc_probe import ENDPOINT, write

FACTORY='0x5c69bee701ef814a2b6a3edd4b1652cb9cc5aa6f'
USDC='0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48'
WETH='0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2'
BLOCK=26290256
BLOCK_HASH='0xc16c4e48c8281db0d4bb49675df01bd4bb3ab359e617141407644a66b18862e6'


def words(value, count):
    if not isinstance(value,str) or not value.startswith('0x') or len(value)!=2+64*count:
        raise ValueError('Unexpected ABI result length')
    return [int(value[2+64*i:2+64*(i+1)],16) for i in range(count)]


def address(value):
    number=words(value,1)[0]
    if number>=2**160:raise ValueError('Nonzero address padding')
    return '0x'+format(number,'040x')


def run(root, endpoint=ENDPOINT):
    if endpoint not in (ENDPOINT,'https://eth.drpc.org'):
        raise ValueError('Declared public endpoint required')
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    source=Path(__file__)
    write(root/'PLAN.json',dict(scope='Single fixed finalized-block engineering snapshot; no strategy or trading',
                               endpoint=endpoint,block=BLOCK,block_hash=BLOCK_HASH,factory=FACTORY,tokens=[USDC,WETH],
                               max_requests=16,max_response_bytes=2097152,total_seconds=90,timeout_seconds=15,retries=0,
                               sources={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,source.with_name('rpc_probe.py'))}))
    result=dict(status='incomplete',completed_requests=0);started=time.monotonic()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    def rpc(method,params):
        index=result['completed_requests']
        if index>=16 or time.monotonic()-started>=90:raise TimeoutError('Snapshot bound')
        if method not in ('eth_chainId','eth_call','eth_getCode','eth_getBlockByNumber'):raise ValueError('Read-only method required')
        call=dict(jsonrpc='2.0',id=index+1,method=method,params=params)
        raw=json.dumps(call).encode();(root/f'request-{index:02d}.json').write_bytes(raw)
        request=urllib.request.Request(endpoint,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-research-readonly-snapshot/1'})
        with urllib.request.build_opener(NoRedirect).open(request,timeout=min(15,90-(time.monotonic()-started))) as response:
            body=response.read(2097153)
            (root/f'response-{index:02d}.json').write_bytes(body)
            write(root/f'metadata-{index:02d}.json',dict(http_status=response.status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
        if len(body)>2097152:raise ValueError('Response size bound')
        decoded=json.loads(body)
        if decoded.get('id')!=call['id'] or decoded.get('jsonrpc')!='2.0' or 'error' in decoded:raise ValueError('RPC error or identity mismatch')
        result['completed_requests']+=1
        return decoded['result']
    def call(to,data):return rpc('eth_call',[dict(to=to,data=data),hex(BLOCK)])
    try:
        if rpc('eth_chainId',[])!='0x1':raise ValueError('Wrong chain')
        header=rpc('eth_getBlockByNumber',[hex(BLOCK),False])
        if header['hash']!=BLOCK_HASH or int(header['number'],16)!=BLOCK:raise ValueError('Pinned block mismatch')
        pair=address(call(FACTORY,'0xe6a43905'+USDC[2:].zfill(64)+WETH[2:].zfill(64)))
        if int(pair,16)==0:raise ValueError('Pair absent')
        if address(call(pair,'0xc45a0155'))!=FACTORY:raise ValueError('Pair factory mismatch')
        if address(call(pair,'0x0dfe1681'))!=USDC or address(call(pair,'0xd21220a7'))!=WETH:raise ValueError('Pair token ordering mismatch')
        decimals=[words(call(token,'0x313ce567'),1)[0] for token in (USDC,WETH)]
        if decimals!=[6,18]:raise ValueError('Unexpected token decimals')
        reserves=words(call(pair,'0x0902f1ac'),3)
        if reserves[0]>=2**112 or reserves[1]>=2**112 or reserves[2]>=2**32:raise ValueError('Reserve ABI bounds')
        supply=words(call(pair,'0x18160ddd'),1)[0]
        code=rpc('eth_getCode',[pair,hex(BLOCK)])
        codebytes=bytes.fromhex(code.removeprefix('0x'))
        if not codebytes:raise ValueError('Empty pair runtime bytecode')
        fee_to=address(call(FACTORY,'0x017e7e58'))
        if rpc('eth_getBlockByNumber',[hex(BLOCK),False])['hash']!=BLOCK_HASH:raise ValueError('Pinned header changed')
        result.update(status='complete',block=BLOCK,block_hash=BLOCK_HASH,block_timestamp=int(header['timestamp'],16),
                      pair=pair,token0=USDC,token1=WETH,decimals=decimals,reserves_raw=reserves,total_supply_raw=supply,
                      runtime_bytecode_sha256=hashlib.sha256(codebytes).hexdigest(),runtime_bytecode_bytes=len(codebytes),fee_to=fee_to,
                      code_scope='Observed bytecode fingerprint, not independently reproduced compiler equivalence')
    except Exception as exc:result['error']=repr(exc)
    finally:
        result['elapsed_seconds']=time.monotonic()-started;write(root/'FINAL.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--endpoint',default=ENDPOINT);a=p.parse_args();print(json.dumps(run(a.root,a.endpoint)))
