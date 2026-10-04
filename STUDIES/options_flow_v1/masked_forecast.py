"""Masked-label forecast evaluation on every scheduled latent time step.

Future x is a declared scenario, not a claim it was known at the training cutoff.
Labels affect scoring only. Missing x yields an explicit unavailable forecast.
"""
import math
import numpy as np
import arviz as az
from evaluate import summarize as posterior_summary
from model import functionals
from masked_flow import validate


def forecast(draws,data,future,predictive_seed=719):
    y_train,_,_=validate(data);t,g=y_train.shape
    q=np.asarray(draws,dtype=float)
    if q.ndim!=3 or q.shape[-1]!=4+2*g+t or q.shape[0]<2 or q.shape[1]<4 or not np.isfinite(q).all():raise ValueError('Finite canonical chain/draw/parameter array with exact dimension required')
    x=np.asarray(future['x'],dtype=float);y=np.asarray(future['y'],dtype=float)
    xm=np.asarray(future['x_available'])
    if 'y_available' in future and 'observation_mask' in future and future['y_available']!=future['observation_mask']:raise ValueError('Conflicting future outcome masks')
    ym=np.asarray(future['y_available'] if 'y_available' in future else future['observation_mask'])
    if x.ndim!=2 or x.shape[1]!=g or len(x)<1 or y.shape!=x.shape or xm.shape!=x.shape or ym.shape!=x.shape:raise ValueError('Future x/y and masks require exact common H-by-G shape')
    if xm.dtype!=np.bool_ or ym.dtype!=np.bool_:raise ValueError('Explicit boolean future availability masks required')
    if not np.isfinite(x[xm]).all() or not np.isfinite(y[ym]).all():raise ValueError('Available future values must be finite')
    grid=np.asarray(future['grid_index'])
    if grid.shape!=(len(x),) or not np.issubdtype(grid.dtype,np.integer) or not (np.array_equal(grid,np.arange(t,t+len(x))) or np.array_equal(grid,np.arange(len(x)))):raise ValueError('Future grid must enumerate every regular latent step, either relative or continuing training')
    safe_x=np.where(xm,x,0.)
    vals=functionals(q,g);rng=np.random.default_rng(predictive_seed)
    h=q[...,-1].copy();mu=q[...,2];sigma=np.exp(q[...,3]);rows=[]
    for index in range(len(x)):
        h=mu+data['rho']*(h-mu)+sigma*rng.normal(size=h.shape)
        location=np.stack([vals[f'alpha_{j}']+vals[f'beta_{j}']*safe_x[index,j] for j in range(g)],axis=-1)
        # Draw every group at every time, even unavailable cells. This keeps
        # later forecasts invariant to changes in the missingness pattern.
        prediction=location+np.exp(h[...,None]/2)*rng.standard_t(data['nu'],size=location.shape)
        for j in range(g):
            row=dict(horizon=index+1,grid_index=int(grid[index]),group=j,forecast_available=bool(xm[index,j]),
                target_observed=bool(ym[index,j]),observed=float(y[index,j]) if ym[index,j] else None,
                lower=None,upper=None,width=None,endpoint_mcse=None,covered=None,interval_score=None)
            if not xm[index,j]:row['unavailable_reason']='Future covariate unavailable; no zero-feature forecast substituted'
            else:
                values=prediction[...,j]
                if not np.isfinite(values).all():raise ValueError('Nonfinite posterior predictive simulation')
                lo,hi=np.quantile(values,[.05,.95]);row.update(lower=float(lo),upper=float(hi),width=float(hi-lo),
                    endpoint_mcse=[float(az.mcse(values,method='quantile',prob=p)) for p in [.05,.95]])
                if ym[index,j]:
                    observed=y[index,j];row.update(covered=bool(lo<=observed<=hi),interval_score=float(hi-lo+20*max(lo-observed,0)+20*max(observed-hi,0)))
            rows.append(row)
    scored=[r for r in rows if r['forecast_available'] and r['target_observed']]
    return dict(kind='Fixed-origin scenario conditional on supplied future covariates; no held-out label updates',operational_forecast_qualified=False,
        predictive_seed=predictive_seed,rows=rows,scheduled_cells=len(rows),available_forecast_cells=int(xm.sum()),
        observed_target_cells=int(ym.sum()),scored_cells=len(scored),unavailable_forecast_cells=int((~xm).sum()),
        coverage=float(np.mean([r['covered'] for r in scored])) if scored else None,
        mean_interval_score=float(np.mean([r['interval_score'] for r in scored])) if scored else None,
        predictive_mcse_note='Posterior autocorrelation plus one simulated future state/Student-t outcome per draw; observation selection is not modeled',
        coverage_scope='Conditional on observed eligible future trades and available covariates; all scheduled denominators remain explicit')


def summarize(draws,fixture,predictive_seed=719):
    # Reuse exactly the existing posterior diagnostic family, without allowing
    # its dense zip-based predictor to see masked labels or truncate horizons.
    data=fixture['data'];y,_,_=validate(data);q=np.asarray(draws)
    if q.ndim!=3 or q.shape[-1]!=4+2*y.shape[1]+len(y):raise ValueError('Canonical dimension mismatch')
    stripped={k:v for k,v in fixture.items() if k!='holdout'}
    result=posterior_summary(q,stripped,predictive_seed)
    if 'holdout' in fixture:result['forecast']=forecast(q,data,fixture['holdout'],predictive_seed)
    return result


def precision_forecast_screen(forecast_result,expected_cells,relative_mcse=.02):
    """Require an externally frozen exact available-x cell family, irrespective of y."""
    if not math.isfinite(relative_mcse) or not 0<relative_mcse<1:raise ValueError('Invalid precision threshold')
    expected=[tuple(cell) for cell in expected_cells]
    if not expected or len(set(expected))!=len(expected):raise ValueError('Explicit unique precision cells required')
    rows=forecast_result['rows'];indexed={(r['horizon'],r['group']):r for r in rows}
    reasons=[];ratios={}
    if len(indexed)!=len(rows):reasons.append('Duplicate forecast cells')
    available={key for key,row in indexed.items() if row['forecast_available']}
    if set(expected)!=available:reasons.append('Actual available-x forecast family differs from frozen precision family')
    for key in expected:
        row=indexed.get(key)
        if row is None or not row['forecast_available']:reasons.append(f'Unavailable expected forecast: {key}');continue
        width=row['width'];errors=row['endpoint_mcse']
        if not math.isfinite(width) or width<=0 or len(errors)!=2 or any(not math.isfinite(v) or v<0 for v in errors):reasons.append(f'Invalid interval precision: {key}');continue
        ratio=max(errors)/width;ratios[str(key)]=ratio
        if ratio>relative_mcse:reasons.append(f'Endpoint precision failed: {key}')
    return {'pass':not reasons,'passed':not reasons,'reasons':reasons,'ratios':ratios,'expected_cells':expected,'threshold':relative_mcse,'qualified':False}
