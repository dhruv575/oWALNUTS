import copy
from pathlib import Path
import pytest
from analyze_outcomes import load,summarize,interval


def failed_case():
    plan=load(Path(__file__).with_name('plan-draft.json'))
    rows=[dict(id=c['id'],status='not_started',seconds=0.) for c in plan['cells']]
    return plan,rows


def test_missing_cell_cannot_disappear():
    p,r=failed_case()
    with pytest.raises(ValueError):summarize(p,r[:-1],{})
    r[-1]=r[0]
    with pytest.raises(ValueError):summarize(p,r,{})


def test_unstarted_alternatives_do_not_pass_by_zero_resolutions():
    p,r=failed_case();result=summarize(p,r,{})
    assert result['expected']==28 and not result['all_progression_pass']
    assert all(not g['progression_pass'] for g in result['groups'].values())
    assert all(g['evaluable_completed_only_coverage_ci95'] is None and g['evaluable_completed_only_resolved_ci95'] is None for g in result['groups'].values())
    assert sum(g['intended'] for g in result['groups'].values())==24
    assert len(result['sentinels'])==4


def test_binomial_boundary_and_failures_cost():
    assert interval(0,4)[0]==0 and interval(4,4)[1]==1
    p,r=failed_case();r[0].update(status='failed',seconds=12.5)
    assert summarize(p,r,{})['total_seconds']==12.5
    r[0]['seconds']=float('nan')
    with pytest.raises(ValueError):summarize(p,r,{})
