import copy
import pytest
from aggregate import summarize, MODELS


def row(t, a, b):
    outcomes = []
    for model, score in zip(MODELS, (a, b)):
        outcomes.append(dict(model=model, status='no_forecast' if score is None else 'scored',
                             width=1., interval_score=score, observed_return=0., covered=score == 1.))
    return dict(origin_receipt_ns=t, outcomes=outcomes)


def test_denominator_and_paired_comparison_do_not_reward_missingness():
    result = summarize([1, 2, 3], [row(1, 4., 2.), row(2, 1., None), row(3, None, None)])
    assert result['scheduled'] == 3
    assert result['arms'][MODELS[0]]['scored_fraction'] == 2/3
    assert result['arms'][MODELS[1]]['scored_fraction'] == 1/3
    assert result['paired']['count'] == 1
    assert result['paired']['mean_flow_minus_price_interval_score'] == -2.
    assert result['paired']['statistics'][MODELS[0]]['mean_interval_score'] == 4.
    assert result['uncertainty']['status'] == 'not_estimated'


def test_no_scores_means_unavailable_not_perfect_coverage():
    result = summarize([1], [row(1, None, None)])
    assert result['paired']['mean_flow_minus_price_interval_score'] is None
    assert result['arms'][MODELS[0]]['available_outcome_statistics']['coverage'] is None


def test_incomplete_duplicate_and_mismatched_outcomes_rejected():
    with pytest.raises(ValueError, match='Missing'):
        summarize([1, 2], [row(1, 1., 1.)])
    with pytest.raises(ValueError, match='Duplicate'):
        summarize([1], [row(1, 1., 1.), row(1, 1., 1.)])
    r = row(1, 1., 1.)
    r['outcomes'][1]['observed_return'] = .2
    with pytest.raises(ValueError, match='identical'):
        summarize([1], [r])

def test_boolean_origin_and_nonfinite_score_rejected():
    r = row(1, 1., 1.)
    r['origin_receipt_ns'] = True
    with pytest.raises(ValueError):
        summarize([1], [r])
    r = row(1, 1., 1.)
    r['outcomes'][0]['interval_score'] = float('nan')
    with pytest.raises(ValueError, match='Finite'):
        summarize([1], [r])


def test_all_failure_categories_remain_in_denominator():
    states = ['not_issued', 'no_forecast', 'outcome_unavailable', 'invalidated_receipt_coverage']
    records = [row(i, None, None) for i in range(4)]
    for r, status in zip(records, states):
        for o in r['outcomes']:
            o['status'] = status
    result = summarize(list(range(4)), records)
    for arm in result['arms'].values():
        assert arm['scheduled'] == 4
        assert arm['status_counts'] == dict.fromkeys(states, 1)
        assert arm['scored_fraction'] == 0
    assert result['paired']['count'] == 0
