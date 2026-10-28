"""Restricted observed mint/burn blocks under explicit token/fee assumptions."""
import argparse
import hashlib
import json
from pathlib import Path
from pair_snapshot import USDC,WETH,words
from liquidity_balance_audit import PAIR,ZERO,TRANSFER,SYNC,address,reconcile
from liquidity_math import mint,burn

MINT='0x4c209b5fc8ad50758f13e2e1088ba56a560dff690a1c6fef26394f4c03821c4f'
BURN='0xdccd412f0b1252819cb1fd330b93224ca42612892bb3f4f789976e6d81936496'


def audit(initial,final,logs):
    reconcile(initial,final,logs)
    if initial['fee_to']!=final['fee_to']:raise ValueError('Fee recipient boundary change')
    if initial['supply']==0:raise ValueError('Established pool required')
    fee_to='0x'+format(initial['fee_to'],'040x');fee_on=fee_to!=ZERO
    if fee_to==PAIR:raise ValueError('Fee-to-pair requires separate handling')
    balances={USDC:initial['balance_usdc'],WETH:initial['balance_weth']}
    held=initial['pair_lp_balance'];reserves=initial['reserves'][:2];supply=initial['supply'];k_last=initial['k_last']
    issuance=[];burns=[];sync=None;rows=[]
    for log in logs:
        contract=log['address'].lower();topic=log['topics'][0];tx=log['transactionHash']
        if topic==TRANSFER:
            sender,receiver=address(log['topics'][1]),address(log['topics'][2]);amount=words(log['data'],1)[0]
            if contract in balances:
                balances[contract]+=amount*((receiver==PAIR)-(sender==PAIR))
                if burns and sender==PAIR:
                    burns[-1]['outflows'].append((contract,receiver,amount,tx))
            elif contract==PAIR:
                if sender==ZERO:issuance.append((receiver,amount,tx))
                elif sender==PAIR and receiver==ZERO and amount:
                    burns.append(dict(amount=amount,held_before=held,balances=[balances[USDC],balances[WETH]],transaction=tx,outflows=[]))
                held+=amount*((receiver==PAIR)-(sender==PAIR))
            continue
        if contract!=PAIR:continue
        if topic==SYNC:
            if sync is not None:raise ValueError('Unpaired or multiple Sync events')
            sync=dict(reserves=words(log['data'],2),transaction=tx)
            continue
        if topic not in (MINT,BURN):raise ValueError('Unsupported pair event in restricted liquidity block')
        if sync is None or sync['transaction']!=tx:raise ValueError('Missing same-transaction Sync')
        if any(t!=tx for _,_,t in issuance):raise ValueError('Unpaired issuance from other transaction')
        amounts=words(log['data'],2)
        if topic==MINT:
            if burns:raise ValueError('Burn before Mint')
            calculated=mint(reserves,sync['reserves'],supply,k_last,fee_on)
            expected=[(fee_to,calculated['protocol_liquidity'])] if calculated['protocol_liquidity'] else []
            if len(issuance)!=len(expected)+1:raise ValueError('Mint issuance count mismatch')
            expected.append((issuance[-1][0],calculated['liquidity']))
            if [(a,v) for a,v,_ in issuance]!=expected:raise ValueError('Mint issuance amount or recipient mismatch')
        else:
            if len(burns)!=1 or burns[0]['transaction']!=tx or burns[0]['amount']!=burns[0]['held_before']:
                raise ValueError('Burn must consume observed pair-held LP balance')
            calculated=burn(reserves,burns[0]['balances'],supply,k_last,fee_on,burns[0]['amount'])
            receiver=address(log['topics'][2])
            expected_outflows=[(USDC,receiver,calculated['amounts'][0],tx),(WETH,receiver,calculated['amounts'][1],tx)]
            if burns[0]['outflows']!=expected_outflows:raise ValueError('Burn transfer amounts, recipient or order mismatch')
            expected=[(fee_to,calculated['protocol_liquidity'])] if calculated['protocol_liquidity'] else []
            if [(a,v) for a,v,_ in issuance]!=expected:raise ValueError('Burn protocol issuance mismatch')
        if calculated['amounts']!=amounts or calculated['reserves']!=sync['reserves']:
            raise ValueError('Liquidity amounts or reserve update mismatch')
        rows.append(dict(transaction=tx,log_index=int(log['logIndex'],16),kind='mint' if topic==MINT else 'burn',
                         before=dict(reserves=reserves,supply=supply,k_last=k_last),calculated=calculated))
        reserves=calculated['reserves'];supply=calculated['supply'];k_last=calculated['k_last']
        issuance=[];burns=[];sync=None
    if issuance or burns or sync is not None:raise ValueError('Unpaired liquidity evidence at block end')
    if reserves!=final['reserves'][:2] or supply!=final['supply'] or k_last!=final['k_last'] or held!=final['pair_lp_balance']:
        raise ValueError('Terminal liquidity state mismatch')
    return dict(operations=rows,final_supply=supply,final_k_last=k_last,
                assumptions=['feeTo constant within block, observed only at boundaries','ordinary token transfers without unobserved balance-changing callbacks','upstream pair semantics; no deployed-bytecode equivalence proven'],
                scope='Conditional integer reconstruction of restricted liquidity-only blocks, not general EVM replay')


def run(root,out):
    root=Path(root);read=lambda name:json.loads((root/name).read_bytes())
    if read('FINAL.json')['status']!='complete':raise ValueError('Complete acquisition required')
    states=read('STATES.json');logs=read('BLOCK-LOGS.json')
    rows=[dict(block=int(n),**audit(states[str(int(n)-1)],states[n],entries)) for n,entries in logs.items()]
    result=dict(rows=rows,inputs={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('STATES.json','BLOCK-LOGS.json')},
                sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('liquidity_math.py'),Path(__file__).with_name('liquidity_balance_audit.py'))})
    with Path(out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');a=p.parse_args();r=run(a.root,a.out);print(json.dumps(dict(blocks=len(r['rows']),operations=sum(len(x['operations']) for x in r['rows']))))
