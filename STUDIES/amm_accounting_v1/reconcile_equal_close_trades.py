"""Reconcile fixed saved responses; never infer completeness for truncated lists."""
import hashlib,json
from decimal import Decimal
from pathlib import Path


def reconcile(root):
    root=Path(root);original=json.loads((root/'REPORT.json').read_bytes())
    input_raw=(root/'INPUT.json').read_bytes()
    assert hashlib.sha256(input_raw).hexdigest()==original['plan']['audit_sha256']
    bars=json.loads(input_raw)['pairs'];rows=[]
    for i,(pair,old) in enumerate(zip(bars,original['rows'],strict=True)):
        raw=(root/f'response-{i:02d}.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==old['sha256']
        data=json.loads(raw,parse_float=Decimal)['result'];trades=data['trades']
        seq=[t['trade_seq'] for t in trades]
        assert len(seq)==len(set(seq))
        bar=pair['current'];lo=bar['open_ms'];hi=bar['close_available_ms']
        assert all(t['instrument_name']=='BTC-PERPETUAL' and lo<=t['timestamp']<hi for t in trades)
        row=dict(index=pair['index'],trades=len(trades),has_more=data['has_more'],response_sha256=old['sha256'])
        if not trades:
            row.update(status='empty_response',bar_volume=bar['volume'],flat_bar=len({bar[k] for k in ['open','high','low','close']})==1)
        elif data['has_more']:
            row['status']='incomplete_no_full_reconciliation'
        else:
            ordered=sorted(trades,key=lambda t:(t['timestamp'],t['trade_seq']))
            prices=[Decimal(t['price']) for t in ordered]
            reconstructed=dict(open=prices[0],close=prices[-1],high=max(prices),low=min(prices))
            volume=sum(Decimal(t['amount'])/Decimal(t['price']) for t in trades)
            residual=volume-Decimal(str(bar['volume']))
            ordinary=[t for t in ordered if 'combo_trade_id' not in t]
            combo=[t for t in ordered if 'combo_trade_id' in t]
            row.update(combo_trades=len(combo),combo_base_volume=str(sum((Decimal(t['amount'])/Decimal(t['price']) for t in combo),Decimal(0))),noncombo_high=None if not ordinary else str(max(Decimal(t['price']) for t in ordinary)))
            row.update(status='reconciled',ohlc={k:str(v) for k,v in reconstructed.items()},ohlc_matches={k:v==Decimal(str(bar[k])) for k,v in reconstructed.items()},base_volume=str(volume),bar_volume=str(bar['volume']),volume_residual=str(residual),volume_within_1e_8=abs(residual)<=Decimal('0.00000001'),all_observed_prices_on_half_dollar_grid=all((p*2)%1==0 for p in prices))
        rows.append(row)
    return dict(scope='Saved same-provider historical responses; has_more=false is service-reported completeness, not independent archival proof. Price lattice does not prove historical minimum tick or latent rounding.',rows=rows,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


if __name__=='__main__':
    import sys
    result=reconcile(sys.argv[1]);out=Path(sys.argv[2])
    with out.open('x',encoding='utf8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result))
