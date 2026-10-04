"""Prospective preperiod activity ranking; no acquisition or model fitting.

This policy is distinct from the historical volume-ranked acquisition. Contract
expiry/creation eligibility must still be verified before selecting a universe.
All thresholds must be supplied in a frozen acquisition protocol.
"""
import bisect
from acquire_deribit_panel import eligible, millis, valid_trade


def rank_preperiod(trades, protocol):
    policy = protocol['activity_selection']
    required = {'method', 'minimum_trades', 'minimum_fresh_anchor_bins',
                'minimum_active_feature_bins'}
    if set(policy) != required or policy['method'] != 'fresh_anchor_then_feature_activity':
        raise ValueError('Explicit activity selection policy required')
    if any(type(policy[k]) is not int or policy[k] < 1 for k in required - {'method'}):
        raise ValueError('Positive integer activity thresholds required')
    if protocol['selection_hours'] != 24:
        raise ValueError('This policy requires a separate first-day selection period')
    f = protocol['forecast']
    if (f['origin_stride_minutes'], f['maximum_reference_staleness_minutes'],
            f['feature_bin_minutes'], f['availability_lag_seconds']) != (30, 30, 15, 60):
        raise ValueError('Unsupported activity grid')
    start = millis(protocol['start_utc'])
    end = start + 86400000
    # First cutoff has a fully observable reference window. The exclusive end
    # ensures ranking cannot use evaluation data or a trade at the next day.
    cutoffs = list(range(start + 1800000, end, 1800000))
    groups = {}
    seen_ids, seen_sequences = set(), set()
    for trade in trades:
        valid_trade(trade, start, end - 1)
        key = (trade['instrument_name'], trade['trade_seq'])
        if trade['trade_id'] in seen_ids or key in seen_sequences:
            raise ValueError('Duplicate preperiod trade')
        seen_ids.add(trade['trade_id']); seen_sequences.add(key)
        if eligible(trade, protocol):
            groups.setdefault(trade['instrument_name'], []).append(trade['timestamp'])
    metrics = {}
    for name, times in groups.items():
        times.sort()
        fresh = active = 0
        for cutoff in cutoffs:
            last = bisect.bisect_right(times, cutoff)
            fresh += bool(last and cutoff - times[last - 1] <= 1800000)
            active += last > bisect.bisect_right(times, cutoff - 900000)
        reasons = []
        for actual, field in [(len(times), 'minimum_trades'),
                              (fresh, 'minimum_fresh_anchor_bins'),
                              (active, 'minimum_active_feature_bins')]:
            if actual < policy[field]:
                reasons.append(field)
        metrics[name] = dict(eligible_trades=len(times), fresh_anchor_bins=fresh,
                             active_feature_bins=active, rejection_reasons=reasons)
    ranked = sorted((name for name, row in metrics.items() if not row['rejection_reasons']),
                    key=lambda name: (-metrics[name]['fresh_anchor_bins'],
                                      -metrics[name]['active_feature_bins'],
                                      -metrics[name]['eligible_trades'], name))
    return dict(ranked_candidates=ranked, metrics=metrics, scheduled_selection_bins=len(cutoffs),
                selection_start_ms=start, selection_end_ms_exclusive=end,
                selection_available_ms=end + f['availability_lag_seconds'] * 1000,
                policy=dict(policy), qualified=False,
                limitation='Preperiod activity only; future liquidity and forecast accuracy unproven. '
                           'Apply creation/expiry metadata checks before choosing contracts.')
