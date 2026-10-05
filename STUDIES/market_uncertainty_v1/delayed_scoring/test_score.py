import hashlib,json,math
from pathlib import Path
import pytest
from score import score,interval_score,features,snapshot,HORIZON,MODELS

def write(p,v):p.write_text(json.dumps(v));return hashlib.sha256(p.read_bytes()).hexdigest()
def lines(p,rows):p.write_text(''.join(json.dumps(r)+'\n' for r in rows));return hashlib.sha256(p.read_bytes()).hexdigest()
def quote(t,price):return dict(receipt_monotonic_ns=t,receipt_utc_ns=t+1000,connection=1,raw=json.dumps(dict(params=dict(channel='ticker.BTC-PERPETUAL.agg2',data=dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=price,best_ask_price=price)))))

def case(tmp_path,missing=False,no_forecast=False):
 c=tmp_path/'capture';c.mkdir();i=tmp_path/'issue';i.mkdir();origin=HORIZON;channels=['trades.option.BTC.100ms','ticker.BTC-PERPETUAL.agg2']
 rows=[dict(receipt_monotonic_ns=1,receipt_utc_ns=1001,connection=1,raw=json.dumps(dict(id=1,result=channels))),quote(origin,100.)]
 lines(c/'receipts.jsonl',rows);lines(c/'lifecycle.jsonl',[dict(kind='subscribed',receipt_monotonic_ns=2,receipt_utc_ns=1002,connection=1)]);write(c/'selection.json',dict(channels=channels))
 pref=snapshot.snapshot(c,i/'snapshot');ctx=features.collector_context(pref)
 asof=features.build(rows,origins_ns=[origin],**ctx);af=write(i/'asof-features.json',asof)
 forecasts=[dict(model=m,status='no_forecast' if no_forecast else 'forecast',reason='insufficient_mature_history' if no_forecast else None,origin_receipt_ns=origin,horizon_ns=HORIZON,distribution=dict(predictive_interval_90=[-.1,.1])) for m in MODELS]
 issue=dict(status='issued_no_forecast' if no_forecast else 'issued',origin_receipt_ns=origin,horizon_end_receipt_ns=origin+HORIZON,issued_monotonic_ns=origin+1,maximum_lag_seconds=10,snapshot_summary_sha256=hashlib.sha256((i/'snapshot/prefix-summary.json').read_bytes()).hexdigest(),asof_features_sha256=af,forecasts=forecasts)
 write(i/'issuance.json',issue)
 end=origin+HORIZON
 if not missing:rows.append(quote(end,100.))
 lines(c/'receipts.jsonl',rows)
 final=dict(schema='public-receipt-collector-v2',status='duration_complete',end_monotonic_ns=end,end_utc_ns=end+1000,coverage_intervals=[dict(start_monotonic_ns=1,end_monotonic_ns=end,connection=1)],gaps=[],files_sha256={n:hashlib.sha256((c/n).read_bytes()).hexdigest() for n in ('receipts.jsonl','lifecycle.jsonl','selection.json')})
 write(c/'summary.json',final);return i,c,issue,final

def test_actual_score_and_immutable_issue(tmp_path):
 i,c,_,_=case(tmp_path);before=(i/'issuance.json').read_bytes();r=score(i,c)
 assert all(o['status']=='scored' and o['covered'] and o['interval_score']==.2 for o in r['outcomes'])
 assert (i/'issuance.json').read_bytes()==before

def test_late_gap_retracts_score_not_original(tmp_path):
 i,c,_,s=case(tmp_path);s['gaps']=[dict(start_monotonic_ns=HORIZON-1,detected_monotonic_ns=HORIZON+10)]
 write(c/'summary.json',s);r=score(i,c)
 assert all(o['status']=='invalidated_receipt_coverage' for o in r['outcomes'])

def test_receipt_tamper_rejected(tmp_path):
 i,c,_,_=case(tmp_path)
 with (c/'receipts.jsonl').open('ab') as f:f.write(b'\n')
 with pytest.raises(ValueError,match='identity'):score(i,c)

def test_future_missing_not_zero_return(tmp_path):
 i,c,_,_=case(tmp_path,missing=True);r=score(i,c)
 assert all(o['status']=='outcome_unavailable' and 'observed_return' not in o for o in r['outcomes'])

def test_no_forecast_preserved_even_with_late_gap(tmp_path):
 i,c,_,s=case(tmp_path,no_forecast=True);s['gaps']=[dict(start_monotonic_ns=HORIZON-1,detected_monotonic_ns=HORIZON+10)];write(c/'summary.json',s)
 assert all(o['status']=='no_forecast' and o['receipt_coverage_invalidated'] for o in score(i,c)['outcomes'])

def test_nonissuance_does_not_require_future_capture(tmp_path):
 i=tmp_path/'i';i.mkdir();write(i/'issuance.json',dict(status='not_issued',origin_receipt_ns=1,reason='late'))
 assert all(o['status']=='not_issued' for o in score(i,tmp_path/'absent')['outcomes'])

def test_interval_boundaries_and_penalty():
 assert interval_score(-1,[-1,1])==2 and interval_score(1,[-1,1])==2
 assert interval_score(2,[-1,1])==22
 with pytest.raises(ValueError):interval_score(0,[1,-1])
 with pytest.raises(ValueError):interval_score(0,[-1,1],alpha=True)

def test_status_contradiction_and_future_label_rejected(tmp_path):
 i,c,issue,_=case(tmp_path);issue['status']='issued_no_forecast';write(i/'issuance.json',issue)
 with pytest.raises(ValueError,match='contradiction'):score(i,c)
 issue['status']='issued';a=json.loads((i/'asof-features.json').read_text());a['rows'][-1]['label']['observed']=True;issue['asof_features_sha256']=write(i/'asof-features.json',a);write(i/'issuance.json',issue)
 with pytest.raises(ValueError,match='already present'):score(i,c)
