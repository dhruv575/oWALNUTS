"""Observed transfer reconciliation; not a token-contract or EVM replica."""
import argparse
import hashlib
import json
from pathlib import Path
from pair_snapshot import USDC,WETH,words
from liquidity_states import PAIR

TRANSFER='0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
SYNC='0x1c411e9a96e071241c2f21f7726b17ae89e3cab4c78be50e062b03a9fffbbad1'
ZERO='0x'+'0'*40


def address(word):
    if len(word)!=66 or not word.startswith('0x') or int(word[2:26],16)!=0:raise ValueError('Address ABI padding')
    return '0x'+word[-40:].lower()


def reconcile(initial,final,logs):
    balances={USDC:initial['balance_usdc'],WETH:initial['balance_weth'],PAIR:initial['pair_lp_balance']}
    keys={USDC:'balance_usdc',WETH:'balance_weth',PAIR:'pair_lp_balance'}
    issued=0;zero_out=0;rows=[];last_sync=None
    for log in logs:
        contract=log['address'].lower();topics=log['topics']
        if contract not in balances:raise ValueError('Unexpected contract')
        if topics[0]==TRANSFER:
            if len(topics)!=3:raise ValueError('Transfer topics')
            sender,receiver=address(topics[1]),address(topics[2]);amount=words(log['data'],1)[0]
            delta=amount*((receiver==PAIR)-(sender==PAIR));balances[contract]+=delta
            if not 0<=balances[contract]<2**256:raise ValueError('Reconstructed balance underflow or overflow')
            if contract==PAIR:
                if sender==ZERO:issued+=amount
                elif receiver==ZERO:zero_out+=amount
            if sender==PAIR or receiver==PAIR or (contract==PAIR and (sender==ZERO or receiver==ZERO)):
                rows.append(dict(transaction=log['transactionHash'],log_index=int(log['logIndex'],16),contract=contract,
                                 sender=sender,receiver=receiver,amount=amount,pair_balance_after=balances[contract]))
        elif contract==PAIR and topics[0]==SYNC:
            reserves=words(log['data'],2)
            if reserves!=[balances[USDC],balances[WETH]]:raise ValueError('Sync and transfer-reconstructed balances disagree')
            if any(r>=2**112 for r in reserves):raise ValueError('Sync reserve bound')
            last_sync=reserves
    if any(balances[token]!=final[key] for token,key in keys.items()):raise ValueError('Terminal token balance mismatch')
    if last_sync is not None and last_sync!=final['reserves'][:2]:raise ValueError('Terminal reserves mismatch')
    required_burn=initial['supply']+issued-final['supply']
    return dict(terminal_balances=balances,lp_issuance_from_zero=issued,lp_zero_recipient_outflow=zero_out,
                lp_burn_required_by_boundary_supply=required_burn,
                treating_all_nonmint_zero_outflows_as_burns_matches_supply=required_burn==zero_out,
                transfers=rows,limitation='Matching observed transfers and Sync values does not prove token behavior or classify every zero-recipient LP transfer as a burn. Fee issuance remains unvalidated.')


def run(root,out):
    root=Path(root);read=lambda p:json.loads(p.read_bytes())
    if read(root/'FINAL.json')['status']!='complete':raise ValueError('Completed state acquisition required')
    states=read(root/'STATES.json');logs=read(root/'BLOCK-LOGS.json');rows=[]
    for n,entries in logs.items():
        initial,final=states[str(int(n)-1)],states[n]
        for block,state in ((str(int(n)-1),initial),(n,final)):
            for name,value in state.items():
                files=list(root.glob(f'*-{block}-{name}-response.json'))
                if len(files)!=1:raise ValueError('Unique raw state response required')
                v=words(read(files[0])['result'],3 if name=='reserves' else 1)
                if value!=(v if name=='reserves' else v[0]):raise ValueError('Derived state differs from raw response')
        raw=list(root.glob(f'*-logs-{n}-response.json'))
        if len(raw)!=1 or read(raw[0])['result']!=entries:raise ValueError('Derived logs differ from raw response')
        rows.append(dict(block=int(n),**reconcile(initial,final,entries)))
    result=dict(scope='Observed balance/Sync consistency under transfer accounting; not full liquidity validation',rows=rows,
                sources={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('pair_snapshot.py'),Path(__file__).with_name('liquidity_states.py'))},
                inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'STATES.json',root/'BLOCK-LOGS.json')})
    with Path(out).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('out');a=p.parse_args();r=run(a.root,a.out);print(json.dumps(dict(blocks=len(r['rows']),supply_consistency=[x['treating_all_nonmint_zero_outflows_as_burns_matches_supply'] for x in r['rows']])))
