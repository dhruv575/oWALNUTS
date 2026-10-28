"""Two-request public RPC engineering probe; no wallet, trades or strategy data."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.request

ENDPOINT='https://ethereum-rpc.publicnode.com'


def write(path, value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def run(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    calls=[dict(jsonrpc='2.0',id=1,method='eth_chainId',params=[]),
           dict(jsonrpc='2.0',id=2,method='eth_getBlockByNumber',params=['finalized',False])]
    write(root/'PLAN.json',dict(scope='Public RPC availability only; no economic dataset or performance evidence',endpoint=ENDPOINT,
                               calls=calls,timeout_seconds=15,max_response_bytes=524288,retries=0,
                               source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    result=dict(status='incomplete',planned=2,completed=0)
    started=time.monotonic()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    try:
        for index,call in enumerate(calls):
            raw=json.dumps(call).encode()
            (root/f'request-{index}.json').write_bytes(raw)
            request=urllib.request.Request(ENDPOINT,data=raw,headers={'Content-Type':'application/json','User-Agent':'owalnuts-research-readonly-probe/1'})
            with urllib.request.build_opener(NoRedirect).open(request,timeout=15) as response:
                received=response.read(524289)
                (root/f'response-{index}.json').write_bytes(received)
                write(root/f'metadata-{index}.json',dict(http_status=response.status,bytes=len(received),sha256=hashlib.sha256(received).hexdigest()))
            if len(received)>524288:raise ValueError('Response byte cap')
            data=json.loads(received)
            if data.get('id')!=call['id'] or data.get('jsonrpc')!='2.0' or 'error' in data:raise ValueError('Invalid RPC response')
            if index==0:
                if data['result']!='0x1':raise ValueError('Unexpected chain')
                result['chain_id']=1
            else:
                block=data['result']
                if not isinstance(block,dict) or not block.get('hash') or not block.get('number'):raise ValueError('Missing finalized block')
                result.update(finalized_number=int(block['number'],16),finalized_hash=block['hash'],block_timestamp=int(block['timestamp'],16))
            result['completed']+=1
        result['status']='complete'
    except Exception as exc:
        result['error']=repr(exc)
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        write(root/'FINAL.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root');args=parser.parse_args()
    print(json.dumps(run(args.root)))
