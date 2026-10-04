"""Cheap no-flow forecast baseline for utility checks, distinct from sampler controls.

Uses per-group training empirical quantiles. It is deliberately transparent and
has no claimed conditional coverage guarantee under time dependence or shifts.
"""
import numpy as np


def empirical_forecast(fixture, alpha=.1):
    if not 0 < alpha < 1:
        raise ValueError('alpha must be in (0,1)')
    training=np.asarray(fixture['data']['y'],float)
    future=np.asarray(fixture['holdout']['y'],float)
    if training.ndim==1: training=training[:,None]
    if future.ndim==1: future=future[:,None]
    if (training.ndim!=2 or future.ndim!=2 or len(training)<2 or not len(future)
            or training.shape[1]!=future.shape[1]
            or not np.isfinite(training).all() or not np.isfinite(future).all()):
        raise ValueError('Require finite matching training/holdout panels')
    lower,upper=np.quantile(training,[alpha/2,1-alpha/2],axis=0)
    rows=[]
    for h,y in enumerate(future,1):
        for g,observed in enumerate(y):
            lo,hi=lower[g],upper[g]
            score=hi-lo+2/alpha*(max(lo-observed,0)+max(observed-hi,0))
            rows.append(dict(horizon=h,group=g,lower=float(lo),upper=float(hi),
                observed=float(observed),covered=bool(lo<=observed<=hi),
                width=float(hi-lo),interval_score=float(score)))
    return dict(name='training_empirical_no_flow',alpha=alpha,rows=rows,
        coverage=float(np.mean([r['covered'] for r in rows])),
        mean_interval_score=float(np.mean([r['interval_score'] for r in rows])),
        limitation='Descriptive baseline; no iid or conditional coverage claim. Paired uncertainty requires independent datasets or origin blocks.')
