import copy
import numpy as np
from market_inputs import build,HORIZON,ARMS

def fixture():
 return dict(rows=[dict(features=dict(origin_receipt_ns=i*HORIZON,anchor=dict(available=True,midpoint=100.),flow_known=True,total_amount=i+1.,signed_amount=(-1)**i),label=dict(horizon_end_receipt_ns=(i+1)*HORIZON,available_at_receipt_ns=(i+1)*HORIZON,observed=True,log_midpoint_return=.001*i)) for i in range(8)])

def test_four_arms_causal_and_native_returns():
 d=fixture()
 for arm in ARMS:
  a=build(d,5*HORIZON,ablation=arm,minimum_history=3,lookback=4)
  altered=copy.deepcopy(d)
  for r in altered['rows'][5:]:r['label']={'garbage':'future'}
  altered['rows'][6]['features']['total_amount']=1e50
  b=build(altered,5*HORIZON,ablation=arm,minimum_history=3,lookback=4)
  assert a['status']=='ready'
  for k in a['data']:np.testing.assert_array_equal(a['data'][k],b['data'][k])
  np.testing.assert_array_equal(a['data']['y'],[.001,.002,.003,.004])
  assert a['scaling']==b['scaling']

def test_missing_outcomes_keep_grid_but_unknown_scale_fails():
 d=fixture();d['rows'][2]['label']['observed']=False
 a=build(d,5*HORIZON,ablation='both',minimum_history=3,lookback=4)
 assert a['status']=='ready' and len(a['data']['y'])==4
 assert a['data']['observed'].tolist()==[True,False,True,True]
 d['rows'][2]['features']['flow_known']=False
 assert build(d,5*HORIZON,ablation='both',minimum_history=3,lookback=4)['reason']=='unknown_scale_covariates'
 assert build(d,5*HORIZON,ablation='mean',minimum_history=3,lookback=4)['status']=='ready'

def test_immature_label_is_masked_and_missing_row_rejected():
 d=fixture();d['rows'][2]['label']['available_at_receipt_ns']=9*HORIZON
 a=build(d,5*HORIZON,ablation='neither',minimum_history=3,lookback=4)
 assert a['training_count']==3 and not a['data']['observed'][1]
 del d['rows'][3]
 assert build(d,5*HORIZON,ablation='neither',minimum_history=2,lookback=4)['reason']=='missing_scheduled_grid_rows'

