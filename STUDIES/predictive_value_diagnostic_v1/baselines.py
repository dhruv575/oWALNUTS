"""Frozen causal baselines. These functions accept observed history only."""
import time
import numpy as np
from scipy.optimize import minimize
from scipy.stats import t

FLOOR = 1e-8

def check_deadline(deadline):
    if deadline is not None and time.monotonic() >= deadline:
        raise TimeoutError('Research deadline reached')

def score_distribution(location, scale, df, observation):
    return dict(logpdf=float(t.logpdf(observation, df, loc=location, scale=scale)),
                pit=float(t.cdf(observation, df, loc=location, scale=scale)))

def nig_ar1(history):
    y = np.asarray(history, dtype=float)
    if len(y) < 20 or not np.isfinite(y).all():
        raise ValueError('NIG requires finite history of at least 20 observations')
    start = max(1, len(y)-256)
    lag, response = y[start-1:-1], y[start:]
    center, sd = float(lag.mean()), float(lag.std(ddof=0))
    if sd <= 1e-12:
        sd = 1.0
    x = np.column_stack((np.ones(len(lag)), (lag-center)/sd))
    forecast = np.array([1., (y[-1]-center)/sd])
    precision = x.T@x + np.eye(2)/100
    mean = np.linalg.solve(precision, x.T@response)
    residual = response-x@mean
    a = 3+len(response)/2
    b = .0002+.5*(residual@residual+mean@mean/100)
    scale = np.sqrt((b/a)*(1+forecast@np.linalg.solve(precision, forecast)))
    return dict(location=float(forecast@mean), scale=float(scale), df=float(2*a),
                training_pairs=len(response), training_start=start,
                lag_center=center, lag_sd=sd)

def objective(theta, standardized):
    """Mean negative t5 log likelihood and analytic standardized gradients."""
    location, log_scale = theta
    scale = np.exp(log_scale)
    residual = standardized-location
    denominator = 5*scale*scale+residual*residual
    value = -np.mean(t.logpdf(standardized, 5, loc=location, scale=scale))
    gradient = np.array([-np.mean(6*residual/denominator),
                         1-np.mean(6*residual*residual/denominator)])
    return float(value), gradient

def fit_t5(history, deadline=None):
    y = np.asarray(history, dtype=float)
    if len(y)<2 or not np.isfinite(y).all():
        raise ValueError('MLE requires finite history')
    center = float(np.median(y))
    unit = max(float(np.std(y, ddof=1)), FLOOR)
    standardized = (y-center)/unit
    lower = float(np.log(FLOOR/unit))
    scales = [max(float(np.std(y,ddof=1))*np.sqrt(3/5), FLOOR),
              max(float(np.median(abs(y-center)))/t.ppf(.75,5), FLOOR)]
    attempts = []
    def fun(theta):
        check_deadline(deadline)
        return objective(theta, standardized)
    for location in [float(y.mean()), center]:
        for scale in scales:
            check_deadline(deadline)
            result = minimize(fun, [(location-center)/unit,np.log(scale/unit)],
                method='L-BFGS-B', jac=True, bounds=[(None,None),(lower,None)],
                options=dict(maxiter=500,maxfun=5000,ftol=1e-12,gtol=1e-8))
            value, gradient = fun(result.x)
            projected = gradient.copy()
            if result.x[1] <= lower+1e-10 and projected[1]>0:
                projected[1] = 0
            eligible = bool(result.success and np.isfinite(result.x).all()
                and np.isfinite(value) and np.isfinite(gradient).all()
                and np.max(abs(projected))<=1e-5)
            attempts.append(dict(eligible=eligible, success=bool(result.success),
                message=str(result.message), nfev=int(result.nfev), nit=int(result.nit),
                mean_nll=float(value+np.log(unit)),
                projected_gradient_inf=float(np.max(abs(projected))),
                location=float(center+unit*result.x[0]),
                scale=float(max(FLOOR,unit*np.exp(result.x[1]))),
                floor_hit=bool(result.x[1]<=lower+1e-10)))
    valid = [i for i,a in enumerate(attempts) if a['eligible']]
    if not valid:
        return dict(status='unavailable', attempts=attempts)
    chosen = min(valid,key=lambda i: (attempts[i]['mean_nll'],i))
    a = attempts[chosen]
    return dict(status='ok', location=a['location'], scale=a['scale'], df=5,
                chosen_start=chosen, floor_hit=a['floor_hit'], attempts=attempts)

def ewma_t5(history, initial_fit):
    y = np.asarray(history,dtype=float)
    if len(y)<250 or initial_fit['status']!='ok':
        return dict(status='unavailable', reason='initial fit unavailable')
    mu, scale = initial_fit['location'], initial_fit['scale']
    variance = (5/3)*scale*scale
    for value in y[250:]:
        variance = .94*variance+.06*(value-mu)**2
    raw_scale = float(np.sqrt(3*variance/5))
    return dict(status='ok', location=mu, scale=max(FLOOR,raw_scale), df=5,
                variance=float(variance), updates=len(y)-250, floor_hit=raw_scale<FLOOR)
