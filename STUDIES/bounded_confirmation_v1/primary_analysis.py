"""Frozen primary endpoint calculation; call only after complete study admission.

This module does not load study outcomes or implement secondary descriptive
analyses. All three paired columns use identical circular-block resamples.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'amm_accounting_v1'))
from confirmation_calendar import schedule
from confirmation_bootstrap import summarize
from analysis_gate import assess


def analyze(calendar, reports):
    if calendar != schedule()['cells']:
        raise ValueError('Calendar differs from frozen schedule')
    reports = list(reports)
    admission = assess(calendar, reports)
    if not admission['primary_analysis_admitted']:
        return dict(admission=admission, status='not_admitted', months=None,
                    predictive_confirmation=False, predictive_functional_equivalence=False)
    by_index = {r['index']: r for r in reports}
    months = []
    for month_index, (month, n) in enumerate([('2025-09', 1440), ('2025-10', 1488)]):
        rows = []
        for cell in calendar:
            if cell['month'] != month or not cell['primary']:
                continue
            comparisons = {c['baseline']: c for c in by_index[cell['index']]['comparisons']}
            rolling, ewma = (comparisons[b] for b in ['rolling_t5', 'ewma_t5'])
            if abs(rolling['inference'] - ewma['inference']) > 1e-10:
                raise ValueError('Sampler contrast depends on baseline')
            rows.append([rolling['model'], ewma['model'], rolling['inference']])
        scores = np.asarray(rows)
        if scores.shape != (n, 3):
            raise ValueError('Primary month denominator')
        blocks = []
        for offset, block in enumerate([96, 48, 336]):
            result = summarize(scores, n, block, 398300000 + 3 * month_index + offset)
            result['predictive_pass'] = all(
                result['mean'][i] > .01 and result['lower_9875'][i] > 0 for i in range(2))
            lower, upper = result['interval_95'][2]
            result['functional_equivalence_pass'] = lower > -.01 and upper < .01
            blocks.append(result)
        months.append(dict(month=month, n=n, columns=['nuts_minus_rolling_t5',
            'nuts_minus_ewma_t5', 'walnuts_minus_nuts'],
            median=np.median(scores, axis=0).tolist(),
            positive_fraction=(scores > 0).mean(axis=0).tolist(), blocks=blocks))
    predictive = [all(m['blocks'][i]['predictive_pass'] for m in months) for i in range(3)]
    equivalence = [all(m['blocks'][i]['functional_equivalence_pass'] for m in months) for i in range(3)]
    return dict(admission=admission, status='analyzed', months=months,
                predictive_confirmation=predictive[0],
                predictive_functional_equivalence=equivalence[0],
                block_sensitivity_changes_predictive_conclusion=any(x != predictive[0] for x in predictive[1:]),
                block_sensitivity_changes_equivalence_conclusion=any(x != equivalence[0] for x in equivalence[1:]),
                scope='Primary predictive endpoints only; not full posterior equivalence, decision value, profitability, or publication readiness')
