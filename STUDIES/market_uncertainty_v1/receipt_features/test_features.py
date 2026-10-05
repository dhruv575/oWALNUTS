import copy,json
from features import build,QUOTE,TRADE
from features import collector_context

def row(t,channel,data):return dict(receipt_monotonic_ns=t,receipt_utc_ns=t+1000,raw=json.dumps(dict(params=dict(channel=channel,data=data))))
def quote(t,bid=100,ask=102):return row(t,QUOTE,dict(instrument_name='BTC-PERPETUAL',state='open',best_bid_price=bid,best_ask_price=ask,timestamp=t))
def test_future_perturbation_preserves_features():
 a=[quote(0),quote(10),quote(20,110,112)];b=a[:2]+[quote(20,900,902)]
 args=dict(origins_ns=[10],horizon_ns=10,window_ns=10,staleness_ns=5,coverage_intervals=[(0,20)])
 assert build(a,**args)['rows'][0]['features']==build(b,**args)['rows'][0]['features']
 assert build(a,**args)['rows'][0]['label']!=build(b,**args)['rows'][0]['label']
def test_crossed_and_stale_no_fallback():
 args=dict(origins_ns=[10],horizon_ns=10,window_ns=10,staleness_ns=5)
 for latest in (quote(10,103,102),quote(3)):
  r=build([quote(0),latest,quote(20)],**args)['rows'][0]
  assert not r['features']['anchor']['available'] and not r['label']['observed']
def test_unknown_vs_known_zero_gap():
 a=[quote(0),quote(10),quote(20)];args=dict(origins_ns=[10],horizon_ns=10,window_ns=10,staleness_ns=5)
 assert build(a,**args)['rows'][0]['features']['signed_amount'] is None
 assert build(a,coverage_intervals=[(0,20)],**args)['rows'][0]['features']['flow_status']=='known_zero'
 assert build(a,coverage_intervals=[(0,20)],gaps=[(5,7)],**args)['rows'][0]['features']['signed_amount'] is None
def test_amount_receipt_not_event_and_dedup():
 trade=dict(trade_id='a',instrument_name='BTC-30OCT26-90000-C',amount=2,direction='sell',timestamp=-999)
 a=[quote(0),row(5,TRADE,[trade]),row(6,TRADE,[trade]),quote(10),quote(20)]
 f=build(a,origins_ns=[10],horizon_ns=10,window_ns=10,staleness_ns=5,coverage_intervals=[(0,20)])['rows'][0]['features']
 assert f['signed_amount']==-2 and f['observed_trade_count']==1

def test_collector_gap_and_silent_terminal():
 summary=dict(end_monotonic_ns=25,coverage_intervals=[dict(start_monotonic_ns=0,end_monotonic_ns=10),dict(start_monotonic_ns=15,end_monotonic_ns=25)],gaps=[dict(start_monotonic_ns=10,resubscribed_monotonic_ns=15)])
 context=collector_context(summary)
 r=build([quote(0),quote(10),quote(20)],origins_ns=[20],horizon_ns=5,window_ns=10,staleness_ns=6,**context)['rows'][0]
 assert r['features']['signed_amount'] is None
 assert r['label']['observed'] and r['label']['available_at_receipt_ns']==25
