"""Historical marked activity adapter; accepts verified builder rows, not raw feeds.

Coverage assurance is inherited from marked_flow.features.build. Missing keyed
rows/explicit unknown coverage reject admission. No model or prior is mutated.
"""
from dataclasses import asdict
import math
import numpy as np
from STUDIES.market_uncertainty_v1.marked_flow.features import BUCKETS, WINDOW_MS
from STUDIES.market_uncertainty_v1.sv_prototype.historical_inputs import build as base_build
from STUDIES.market_uncertainty_v1.sv_prototype.synthetic import ILLUSTRATIVE_PRIORS


def build(rows, marked_rows, origin, *, ablation="marked_activity", minimum_history=20):
    """P=2 mean, K=24 scale, fixed T=256; marked_rows maps origin to builder output.

    Training-constant columns use scale one: training values are zero, while
    newly observed prediction activity is retained relative to the past mean.
    """
    if ablation not in ('neither', 'pooled_activity', 'marked_activity'):
        raise ValueError('Unknown activity ablation')
    result = base_build(rows, origin, ablation='neither',
                        minimum_history=minimum_history, lookback=256)
    if result['status'] != 'ready':
        return result
    if len(result['training_origins']) != 256:
        return dict(result, status='no_fit', reason='insufficient_fixed_grid_history')
    values = []
    for stamp in result['training_origins'] + [origin]:
        row = marked_rows.get(stamp)
        if (not isinstance(row, dict) or row.get('origin_ms') != stamp
                or row.get('window_start_ms') != stamp-WINDOW_MS
                or row.get('flow_known', True) is not True
                or set(row.get('buckets', {})) != set(BUCKETS)):
            return dict(result, status='no_fit', reason='unknown_marked_coverage', missing_origin=stamp)
        amount = [row['buckets'][b].get('amount') for b in BUCKETS]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in amount):
            return dict(result, status='no_fit', reason='invalid_marked_amount', missing_origin=stamp)
        values.append(np.log1p(amount))
    matrix = np.asarray(values)
    if ablation == 'pooled_activity':
        # Sum native amounts before log1p; never sum log amounts.
        matrix = np.asarray([[math.log1p(math.fsum(marked_rows[t]['buckets'][b]['amount'] for b in BUCKETS))] for t in result['training_origins']+[origin]])
    elif ablation == 'neither':
        matrix = np.empty((257, 0))
    training = matrix[:-1]
    mask = result['data']['observed']
    mean = training[mask].mean(axis=0)
    sd = training[mask].std(axis=0)
    varying = sd > 1e-12
    effective_sd = np.where(varying, sd, 1.)
    transformed = (matrix-mean)/effective_sd
    result['data']['w'] = transformed[:-1]
    result['future']['w'] = transformed[-1]
    result['scaling']['w'] = dict(mean=mean.tolist(), sd=effective_sd.tolist(), raw_sd=sd.tolist(),
                                  active=varying.tolist(), zero_variance_policy='training_centered_scale_one')
    priors = asdict(ILLUSTRATIVE_PRIORS)
    k = matrix.shape[1]
    priors['gamma_sd'] = .03/math.sqrt(k) if k else .03
    result.update(ablation=ablation, bucket_order=list(BUCKETS),
                  suggested_priors=priors,
                  prior_scope='Illustrative independent standardized coefficients: gamma_sd=.03/sqrt(K) for K>0; total prior contribution variance .03^2 at unit second moments, not empirical calibration or a guarantee for correlated covariates. K0 has no gamma coefficients.',
                  coverage_scope='Requires verified marked_flow.features.build outputs and verified historical flat rows; this adapter does not authenticate raw acquisition.',
                  dimensions=dict(T=256, P=2, K=k, q=260+k))
    return result
