import copy
import numpy as np
import pytest
from historical_inputs import build, HALF, ARMS


def rows():
    return [dict(origin_ms=(i+1)*HALF, bar_close=100., lag_return=.001*i,
                 flow_known=True, total_amount=i+1., signed_amount=(-1)**i,
                 label_available_ms=(i+2)*HALF, log_bar_close_return=.002*i)
            for i in range(9)]


def test_all_arms_causal_shapes_and_target_admission():
    from target import Target, Priors
    data = rows(); changed = copy.deepcopy(data)
    for row in changed[6:]:
        row['label_available_ms'] = 'future poison'
        row['log_bar_close_return'] = 'future poison'
    changed[8]['total_amount'] = 1e50
    for arm in ARMS:
        a = build(data, 7*HALF, ablation=arm, minimum_history=3, lookback=4)
        b = build(changed, 7*HALF, ablation=arm, minimum_history=3, lookback=4)
        assert a['status'] == b['status'] == 'ready'
        for key in a['data']:
            np.testing.assert_array_equal(a['data'][key], b['data'][key])
        assert a['scaling'] == b['scaling']
        np.testing.assert_array_equal(a['data']['y'], [.004, .006, .008, .010])
        m = Target(**a['data'], rho=.9, nu=5., priors=Priors(-10, 1, -2, .5, .002, .03))
        assert m.t == 4 and m.p == (4 if arm in ('mean', 'both') else 2)


def test_missing_labels_keep_states_and_unknown_scale_rejects():
    data = rows(); data[3]['label_available_ms'] = 10*HALF
    data[3]['log_bar_close_return'] = 'not yet available'
    a = build(data, 7*HALF, ablation='both', minimum_history=3, lookback=4)
    assert a['data']['observed'].tolist() == [True, False, True, True]
    assert len(a['data']['y']) == 4
    data[3]['flow_known'] = False
    assert build(data, 7*HALF, ablation='both', minimum_history=3, lookback=4)['reason'] == 'unknown_scale_covariates'
    assert build(data, 7*HALF, ablation='mean', minimum_history=3, lookback=4)['status'] == 'ready'


def test_grid_and_availability_validation():
    data = rows(); data[3]['label_available_ms'] = data[3]['origin_ms']
    with pytest.raises(ValueError, match='availability'):
        build(data, 7*HALF, ablation='neither', minimum_history=3, lookback=4)
    data = rows(); del data[3]
    assert build(data, 7*HALF, ablation='neither', minimum_history=3, lookback=4)['reason'] == 'missing_scheduled_grid_rows'
