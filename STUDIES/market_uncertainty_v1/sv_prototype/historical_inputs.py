"""SV admission for verified event-time/bar-close rows, not receipt evidence.

The historical_evaluation producer verifies raw acquisition and bar timing.
This adapter checks causal selection and preserves the complete latent grid.
Priors apply to training-standardized coefficients; returns stay in native units.
"""
import math
import numpy as np

HALF = 1_800_000
ARMS = ('neither', 'mean', 'scale', 'both')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def build(rows, origin, *, ablation, minimum_history, lookback):
    if type(origin) is not int or ablation not in ARMS:
        raise ValueError('Integer historical origin and named ablation required')
    if any(type(v) is not int or v < 1 for v in (minimum_history, lookback)):
        raise ValueError('Positive explicit history and lookback required')
    times = [r['origin_ms'] for r in rows]
    if any(type(v) is not int for v in times) or times != sorted(set(times)) or origin not in times:
        raise ValueError('Distinct ordered historical origins required')
    index = times.index(origin)
    start = max(0, index-lookback)
    selected = rows[start:index]
    grid = times[start:index+1]
    result = dict(status='no_fit', qualified=False, origin_ms=origin,
                  ablation=ablation, minimum_history=minimum_history, lookback=lookback,
                  estimand='retrospective event-time flow and next bar-close log return')
    if any(b-a != HALF for a, b in zip(grid, grid[1:])):
        return dict(result, reason='missing_scheduled_grid_rows')
    current = rows[index]
    if not finite(current.get('bar_close')) or current['bar_close'] <= 0:
        return dict(result, reason='missing_forecast_anchor')
    if not selected:
        return dict(result, reason='insufficient_mature_history', training_count=0)
    meanflow = ablation in ('mean', 'both')
    scaleflow = ablation in ('scale', 'both')

    def design(row):
        lag = row.get('lag_return')
        x = [1., lag if finite(lag) else float('nan')]
        amount, signed = row.get('total_amount'), row.get('signed_amount')
        known = (row.get('flow_known') is True and finite(amount) and finite(signed)
                 and amount >= 0 and abs(signed) <= amount+1e-10)
        if known:
            imbalance = signed/amount if amount else 0.
            mean = [imbalance, math.log1p(amount)]
            scale = [abs(imbalance), math.log1p(amount)]
        else:
            mean = scale = [float('nan'), float('nan')]
        return x+(mean if meanflow else []), scale if scaleflow else []

    X, W, y, observed = [], [], [], []
    for row in selected:
        available = row.get('label_available_ms')
        if available is not None and (type(available) is not int or available < row['origin_ms']+HALF):
            raise ValueError('Label availability precedes its horizon')
        eligible = available is not None and available <= origin
        value = row.get('log_bar_close_return') if eligible else None
        if eligible and not finite(value):
            raise ValueError('Mature label must be finite')
        x, w = design(row)
        eligible = eligible and bool(np.isfinite(x).all())
        X.append(x); W.append(w); y.append(value if eligible else float('nan')); observed.append(eligible)
    xn, wn = design(current)  # Current and future outcomes are never inspected.
    X, W = np.asarray(X), np.asarray(W).reshape(len(selected), -1)
    mask = np.asarray(observed, dtype=bool)
    result['training_count'] = int(mask.sum())
    if scaleflow and not np.isfinite(W).all():
        return dict(result, reason='unknown_scale_covariates')
    if not np.isfinite(xn).all() or not np.isfinite(wn).all():
        return dict(result, reason='unknown_forecast_covariates')
    if mask.sum() < minimum_history:
        return dict(result, reason='insufficient_mature_history')

    def scale(a, future, skip):
        mean = a[mask, skip:].mean(axis=0)
        sd = a[mask, skip:].std(axis=0)
        sd = np.where(sd > 1e-12, sd, 1.)
        out = a.copy(); out[:, skip:] = (a[:, skip:]-mean)/sd
        nxt = np.asarray(future, dtype=float).copy(); nxt[skip:] = (nxt[skip:]-mean)/sd
        return out, nxt, dict(mean=mean.tolist(), sd=sd.tolist())

    X, xn, sx = scale(X, xn, 1)
    W, wn, sw = scale(W, wn, 0)
    return dict(result, status='ready', training_origins=grid[:-1],
                data=dict(y=np.asarray(y), x=X, w=W, observed=mask),
                future=dict(x=xn, w=wn), scaling=dict(x=sx, w=sw))
