import json
import pytest
from collector import Collector,DAY,HALF,validate
def protocol():return dict(schema='historical-pooled-option-flow-v1',start_ms=DAY,end_ms_exclusive=2*DAY,max_requests=30,max_bytes=1000000,max_seconds=60,max_response_bytes=100000,minimum_free_bytes=1,minimum_request_interval_seconds=.5,estimand='retrospective')
def trade(i,t,amount=1):return dict(trade_id=str(i),timestamp=t,instrument_name='BTC-30SEP26-100000-C',direction='buy',amount=amount,price=.1)
def collector(tmp_path,responses):
 p=protocol();p['minimum_request_interval_seconds']=0
 iterator=iter(responses)
 return Collector(p,tmp_path/'run',lambda url:(200,json.dumps({'result':next(iterator)}).encode()))
def test_subdivision_complete_and_dedup(tmp_path):
 c=collector(tmp_path,[{'trades':[trade(1,10)],'has_more':True},{'trades':[trade(1,10)],'has_more':False},{'trades':[trade(2,12)],'has_more':False}]);c.trades(10,13)
 assert [(x['start_ms'],x['end_ms']) for x in c.leaves]==[(10,11),(12,13)]
 assert c.db.execute('SELECT COUNT(*) FROM trades').fetchone()[0]==2;c.db.close()
def test_conflict(tmp_path):
 c=collector(tmp_path,[{'trades':[trade(1,10)],'has_more':True},{'trades':[trade(1,10,2)],'has_more':False}])
 with pytest.raises(ValueError,match='Conflicting'):c.trades(10,11)
 c.db.close()
def test_saturated_ms(tmp_path):
 c=collector(tmp_path,[{'trades':[trade(1,10)],'has_more':True}])
 with pytest.raises(ValueError,match='saturated'):c.trades(10,10)
 c.db.close()
def test_terminal_failure_and_no_overwrite(tmp_path):
 c=collector(tmp_path,[{'trades':[trade(1,0)],'has_more':False}]);r=c.run();assert not r['complete'] and (c.out/'terminal.json').exists()
 with pytest.raises(FileExistsError):Collector(protocol(),c.out)
def test_full_day_bars_and_availability(tmp_path):
 bars=dict(status='ok',ticks=list(range(DAY,2*DAY,HALF)),open=[1]*48,high=[2]*48,low=[.5]*48,close=[1.5]*48,volume=[0]*48)
 c=collector(tmp_path,[{'trades':[],'has_more':False},bars]);r=c.run();assert r['complete'] and r['bar_count']==48 and r['trade_count']==0
 assert json.loads((c.out/'bars.json').read_text())[0]['close_available_ms']==DAY+HALF
def test_missing_bars_fails(tmp_path):
 c=collector(tmp_path,[{'trades':[],'has_more':False},{'status':'ok','ticks':[]}]);assert not c.run()['complete']
def test_cap_is_incomplete(tmp_path):
 c=collector(tmp_path,[]);c.p['max_requests']=0;assert not c.run()['complete'] and c.requests==0
def test_validation():
 assert validate(protocol())
 p=protocol();p['max_requests']=True
 with pytest.raises(ValueError):validate(p)
