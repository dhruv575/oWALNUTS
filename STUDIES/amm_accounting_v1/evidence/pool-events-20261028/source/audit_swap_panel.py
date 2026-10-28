"""Strict swap-only integer accounting check; rejects unsupported pool events."""
import argparse
import hashlib
import json
from pathlib import Path
from Crypto.Hash import keccak
from pair_snapshot import words


def topic(signature):
    return '0x'+keccak.new(digest_bits=256,data=signature.encode()).hexdigest()


def transition(before, after, flows):
    if len(before)!=2 or len(after)!=2 or len(flows)!=4:
        raise ValueError('Transition dimensions')
    if any(type(v) is not int or v<0 for v in (*before,*after,*flows)):
        raise ValueError('Nonnegative integer values required')
    a0,a1,o0,o1=flows
    if not (a0 or a1) or not (o0 or o1) or o0>=before[0] or o1>=before[1]:
        raise ValueError('Invalid swap input/output domain')
    if after!=[before[0]+a0-o0,before[1]+a1-o1]:
        raise ValueError('Integer reserve conservation failed')
    adjusted=[after[0]*1000-a0*3,after[1]*1000-a1*3]
    slack=adjusted[0]*adjusted[1]-before[0]*before[1]*1000000
    if min(adjusted)<0 or slack<0:raise ValueError('Fee-adjusted product invariant failed')
    return slack


def run(root):
    root=Path(root)
    def read(name):return json.loads((root/name).read_bytes())
    if read('FINAL.json')['status']!='complete':raise ValueError('Completed acquisition required')
    events,states,headers=read('EVENTS.json'),read('STATES.json'),read('HEADERS.json')
    raw_full=list(root.glob('*-full-response.json'))
    if len(raw_full)!=1 or read(raw_full[0].name)['result']!=events:raise ValueError('Derived event list differs from raw response')
    if len(events)%2:raise ValueError('Swap-only panel requires paired events')
    timestamps={int(h['number'],16):int(h['timestamp'],16) for h in headers}
    reserves=states['initial']['reserves_raw'][:2]
    stamp=states['initial']['reserves_raw'][2]
    rows=[]
    for sync,swap in zip(events[::2],events[1::2]):
        if sync['topics']!=[topic('Sync(uint112,uint112)')] or len(swap['topics'])!=3 or swap['topics'][0]!=topic('Swap(address,uint256,uint256,uint256,uint256,address)'):
            raise ValueError('Unsupported event or event order; no rows excluded')
        if sync['transactionHash']!=swap['transactionHash'] or sync['blockHash']!=swap['blockHash'] or int(sync['logIndex'],16)>=int(swap['logIndex'],16):raise ValueError('Sync/Swap identity mismatch')
        after=words(sync['data'],2);flows=words(swap['data'],4)
        if max(after)>=2**112:raise ValueError('Reserve integer bound')
        slack=transition(reserves,after,flows)
        rows.append(dict(block=int(swap['blockNumber'],16),transaction=swap['transactionHash'],before=reserves,after=after,flows=flows,invariant_slack=slack))
        reserves=after;stamp=timestamps[int(sync['blockNumber'],16)]%(2**32)
    if [*reserves,stamp]!=states['final']['reserves_raw']:raise ValueError('Terminal reserve state mismatch')
    if states['initial']['total_supply_raw']!=states['final']['total_supply_raw']:raise ValueError('Supply changed without decoded LP events')
    inputs=['PLAN.json','FINAL.json','EVENTS.json','STATES.json','HEADERS.json',raw_full[0].name]
    return dict(scope='Fixed observed swap-only panel; no economic counterfactual or profit claim',swaps=len(rows),events=len(events),
                exact_terminal_reserves=True,unchanged_lp_supply=True,
                inputs_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in inputs},
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),rows=rows,
                limitations='No mint/burn/standalone-sync branches exercised; no provider-independent event completeness or executable liquidation validation')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');a=p.parse_args();result=run(a.root)
    with Path(a.out).open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
