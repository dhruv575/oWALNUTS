import copy
import pytest
from active_contract_selection import rank_preperiod
from acquire_deribit_panel import millis


def inputs():
    p = dict(start_utc='2026-09-18T00:00:00+00:00', selection_hours=24,
             exclude_flags=['block_trade_id'],
             forecast=dict(origin_stride_minutes=30, maximum_reference_staleness_minutes=30,
                           feature_bin_minutes=15, availability_lag_seconds=60),
             activity_selection=dict(method='fresh_anchor_then_feature_activity',
                                     minimum_trades=1, minimum_fresh_anchor_bins=1,
                                     minimum_active_feature_bins=1))
    start = millis(p['start_utc'])
    def trade(name, minute, seq, amount=1):
        return dict(instrument_name=name, timestamp=start+minute*60000,
                    trade_id=f'{name}-{seq}', trade_seq=seq, amount=amount,
                    price=.1, direction='buy')
    return p, trade


def test_activity_beats_large_isolated_print_and_is_order_invariant():
    p, trade = inputs()
    rows = [trade('active', minute, i) for i, minute in enumerate([29,59,89,119])]
    rows += [trade('large',29,0,1000000)]
    original = copy.deepcopy(rows)
    a = rank_preperiod(rows,p)
    assert a == rank_preperiod(list(reversed(rows)),p)
    assert a['ranked_candidates'] == ['active','large']
    assert a['scheduled_selection_bins'] == 47 and rows == original
    assert a['selection_available_ms'] == a['selection_end_ms_exclusive'] + 60000


def test_next_day_data_rejected_and_threshold_failure_retained():
    p, trade = inputs()
    with pytest.raises(Exception, match='outside requested bounds'):
        rank_preperiod([trade('future',1440,0)],p)
    p['activity_selection']['minimum_trades'] = 2
    result = rank_preperiod([trade('thin',29,0)],p)
    assert result['ranked_candidates'] == []
    assert result['metrics']['thin']['rejection_reasons'] == ['minimum_trades']
    with pytest.raises(Exception, match='outside requested bounds'):
        rank_preperiod([trade('past',-1,0)],p)


def test_final_day_trade_counts_but_is_not_available_for_earlier_bins():
    p, trade = inputs()
    result = rank_preperiod([trade('late',1439,0)],p)
    assert result['metrics']['late']['eligible_trades'] == 1
    assert result['metrics']['late']['fresh_anchor_bins'] == 0
    assert result['metrics']['late']['active_feature_bins'] == 0
    p['activity_selection']['minimum_fresh_anchor_bins'] = 48
    result = rank_preperiod([trade('thin',29,0)],p)
    assert not result['ranked_candidates']


def test_boundary_exclusion_flags_and_lexical_tie():
    p, trade = inputs()
    rows = [trade(name,15,0) for name in ['b','a']]
    result = rank_preperiod(rows,p)
    assert result['ranked_candidates'] == []  # Left feature endpoint excluded.
    rows = [trade(name,30,0) for name in ['b','a']]
    flagged = trade('ignored',29,0); flagged['block_trade_id']='block'
    result = rank_preperiod(rows+[flagged],p)
    assert result['ranked_candidates'] == ['a','b']
    assert 'ignored' not in result['metrics']
    assert result['metrics']['a']['fresh_anchor_bins'] == 2  # Age exactly30min allowed.
    with pytest.raises(ValueError, match='Duplicate'):
        rank_preperiod(rows+rows,p)
