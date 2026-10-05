import copy
import math
import numpy as np
from STUDIES.market_uncertainty_v1.marked_flow.inputs import build
from STUDIES.market_uncertainty_v1.marked_flow.features import BUCKETS, WINDOW_MS


def fixture():
    rows=[]; marked={}
    for i in range(260):
        t=i*1800000
        rows.append(dict(origin_ms=t,bar_close=100.,lag_return=i*.0001,
                         label_available_ms=t+1800000,log_bar_close_return=i*.00001))
        marked[t]=dict(origin_ms=t,window_start_ms=t-WINDOW_MS,
                       buckets={b:dict(amount=float(i+j) if j<2 else 0.) for j,b in enumerate(BUCKETS)})
    return rows,marked,256*1800000


def test_dimensions_native_and_prior():
    rows,marked,t=fixture();r=build(rows,marked,t)
    assert r['status']=='ready' and r['data']['x'].shape==(256,2)
    assert r['data']['w'].shape==(256,24) and r['future']['w'].shape==(24,)
    assert r['dimensions']['q']==284
    np.testing.assert_array_equal(r['data']['y'],[x['log_bar_close_return'] for x in rows[:256]])
    assert r['suggested_priors']['gamma_sd']==.03/math.sqrt(24)
    np.testing.assert_allclose(r['data']['w'][:,:2].mean(0),0,atol=1e-14)
    np.testing.assert_allclose(r['data']['w'][:,:2].std(0),1)


def test_future_labels_and_covariates_never_read():
    rows,marked,t=fixture();a=build(rows,marked,t)
    for r in rows[256:]:r['log_bar_close_return']='poison';r['label_available_ms']='poison'
    for r in rows[257:]:r['lag_return']='poison'
    for stamp in list(marked):
        if stamp>t:marked[stamp]=None
    b=build(rows,marked,t)
    for k in a['data']:np.testing.assert_equal(a['data'][k],b['data'][k])
    assert a['scaling']==b['scaling']


def test_missing_state_training_scaling_and_zero_columns():
    rows,marked,t=fixture();rows[8]['label_available_ms']=t+1800000
    rows[8]['log_bar_close_return']='unavailable'
    marked[8*1800000]['buckets'][BUCKETS[0]]['amount']=1e100
    marked[t]['buckets'][BUCKETS[2]]['amount']=999.
    r=build(rows,marked,t)
    assert len(r['data']['y'])==256 and not r['data']['observed'][8]
    assert np.isnan(r['data']['y'][8])
    training=np.log1p([i for i in range(256) if i!=8])
    assert math.isclose(r['scaling']['w']['mean'][0],training.mean())
    np.testing.assert_array_equal(r['data']['w'][:,2:],0)
    assert r['future']['w'][2]==math.log1p(999.)


def test_unknown_coverage_and_grid_preserved():
    rows,marked,t=fixture();del marked[8*1800000]
    assert build(rows,marked,t)['reason']=='unknown_marked_coverage'
    rows,marked,t=fixture();marked[t]['flow_known']=False
    assert build(rows,marked,t)['status']=='no_fit'
    rows,marked,t=fixture();del rows[8]
    assert build(rows,marked,t)['reason']=='missing_scheduled_grid_rows'
    rows,marked,t=fixture()
    assert build(rows,marked,20*1800000)['reason']=='insufficient_fixed_grid_history'


def test_ablation_targets_and_pooled_units():
    rows,marked,t=fixture()
    for arm,k in [('neither',0),('pooled_activity',1),('marked_activity',24)]:
        r=build(rows,marked,t,ablation=arm)
        assert r['data']['w'].shape==(256,k) and r['data']['x'].shape==(256,2)
        assert r['suggested_priors']['gamma_sd']==(.03/math.sqrt(k) if k else .03)
        assert r['dimensions']['q']==260+k
    r=build(rows,marked,t,ablation='pooled_activity')
    assert math.isclose(r['scaling']['w']['mean'][0],np.log1p(2*np.arange(256)+1).mean())
