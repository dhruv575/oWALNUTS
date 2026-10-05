import datetime as dt
import pytest
from features import build as actual_build,mark,WINDOW_MS
ORIGIN=int(dt.datetime(2026,9,1,12,tzinfo=dt.timezone.utc).timestamp()*1000)
def build(rows,origin):return actual_build(rows,origin,coverage_intervals=[(origin-WINDOW_MS,origin)])
def trade(i,t=None,**kwargs):return dict(dict(trade_id=str(i),timestamp=ORIGIN-1 if t is None else t,instrument_name='BTC-8SEP26-90-C',index_price=100.,amount=2.,direction='buy'),**kwargs)
def test_boundaries_conservation_future_invariance():
 rows=[trade(1,ORIGIN-WINDOW_MS),trade(2,direction='sell',amount=3.),trade(3,ORIGIN,index_price=None),trade(4,ORIGIN-WINDOW_MS-1,index_price=None)]
 r=build(rows,ORIGIN);assert r['count']==2 and r['amount']==5 and r['signed_amount']==-1
 assert r==build(rows[:2]+[trade(5,ORIGIN+1,index_price=-1)],ORIGIN)
 assert sum(v['amount'] for v in r['buckets'].values())==r['amount']
 assert mark(rows[0])=='C|0-7|0.9-1.1'
@pytest.mark.parametrize('expiry,bucket',[('8SEP26','0-7'),('9SEP26','8-30'),('1OCT26','8-30'),('2OCT26','31-90'),('30NOV26','31-90'),('1DEC26','91+')])
def test_maturity(expiry,bucket):assert mark(trade(1,instrument_name=f'BTC-{expiry}-110-P'))==f'P|{bucket}|0.9-1.1'
def test_missing_and_duplicate_rejected():
 with pytest.raises(ValueError):build([trade(1,index_price=None)],ORIGIN)
 with pytest.raises(ValueError):build([trade(1),trade(1)],ORIGIN)
 assert mark(trade(1,instrument_name='BTC-8SEP26-89-P')).endswith('<0.9')
 assert mark(trade(1,instrument_name='BTC-8SEP26-111-P')).endswith('>1.1')


def test_coverage_known_zero_and_gaps():
 assert actual_build([],ORIGIN,coverage_intervals=[(ORIGIN-WINDOW_MS,ORIGIN)])['amount']==0
 for intervals in ([],[(ORIGIN-WINDOW_MS+1,ORIGIN)],[(ORIGIN-WINDOW_MS,ORIGIN-1)],[(ORIGIN-WINDOW_MS,ORIGIN-10),(ORIGIN-9,ORIGIN)]):
  with pytest.raises(ValueError,match='coverage'):actual_build([],ORIGIN,coverage_intervals=intervals)
 assert actual_build([],ORIGIN,coverage_intervals=[(ORIGIN-10,ORIGIN),(ORIGIN-WINDOW_MS,ORIGIN-10)])['count']==0

def test_ratio_overflow():
 with pytest.raises(ValueError,match='ratio'):mark(trade(1,index_price=1e-320,instrument_name='BTC-8SEP26-1000000000000000000000000000000000000000000000000000000000000000000-P'))
