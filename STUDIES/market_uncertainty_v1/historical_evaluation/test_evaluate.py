import unittest,copy,math
from evaluate import convert,forecast,HALF

def bars(n):return [dict(open_ms=i*HALF,close_available_ms=(i+1)*HALF,close=100*math.exp(.001*math.sin(i))) for i in range(n)]
class Tests(unittest.TestCase):
 def test_half_open_flow_boundary(self):
  trades=[dict(trade_id=str(i),timestamp=t,amount=1.,direction='buy') for i,t in enumerate([HALF-900001,HALF-900000,HALF-1,HALF])]
  r=convert(trades,bars(2),0,2*HALF);self.assertEqual(r[0]['flow_count'],2);self.assertEqual(r[1]['flow_count'],0)
 def test_future_outcomes_and_flow_do_not_change_forecast(self):
  b=bars(40);rows=convert([],b,0,40*HALF);before=forecast(rows,25,True)
  changed=copy.deepcopy(rows)
  for r in changed[25:]:r['log_bar_close_return']=100.;r['label_available_ms']=None
  for r in changed[26:]:r['lag_return']=999.;r['total_amount']=9999.;r['signed_amount']=-9999.
  self.assertEqual(before,forecast(changed,25,True));self.assertEqual(before['status'],'forecast');self.assertEqual(before['training_count'],24)
 def test_training_scaling_and_lookback(self):
  rows=convert([],bars(80),0,80*HALF);r=forecast(rows,60,False,minimum_history=20,lookback=25)
  self.assertEqual(r['training_count'],25);self.assertEqual(r['training_origins'][0],rows[35]['origin_ms']);self.assertEqual(r['training_origins'][-1],rows[59]['origin_ms'])
 def test_gaps_duplicates_and_no_forecasts_retained(self):
  with self.assertRaises(ValueError):convert([],bars(3)[::2],0,3*HALF)
  tr=dict(trade_id='x',timestamp=1,amount=1.,direction='buy')
  with self.assertRaises(ValueError):convert([tr,tr],bars(2),0,2*HALF)
  rows=convert([],bars(5),0,5*HALF);self.assertEqual(forecast(rows,0,False)['reason'],'missing_lag');self.assertEqual(forecast(rows,4,True)['reason'],'insufficient_mature_history')
if __name__=='__main__':unittest.main()
