"""Independent diagnostics and forecast evaluation; failures remain visible."""
import numpy as np
import arviz as az
from model import functionals


def summarize(draws, fixture, predictive_seed=719):
    draws=np.asarray(draws,float)
    if draws.ndim!=3 or draws.shape[0]<2 or draws.shape[1]<4 or not np.isfinite(draws).all():
        raise ValueError('Need finite chain x draw x parameter array, >=2 chains and >=4 draws')
    g=len(fixture['data']['x'][0]); vals=functionals(draws,g); result={}
    truth=functionals(np.asarray(fixture['truth']),g) if 'truth' in fixture else {}
    for name,v in vals.items():
        result[name]={'mean':float(v.mean()),'sd':float(v.std()),
          'rhat':float(az.rhat(v,method='rank')),'bulk_ess':float(az.ess(v,method='bulk')),
          'tail_ess':float(az.ess(v,method='tail',prob=(.05,.95))),'mean_mcse':float(az.mcse(v,method='mean')),
          'interval_90':np.quantile(v,[.05,.95]).tolist(),
          'endpoint_mcse':[float(az.mcse(v,method='quantile',prob=p)) for p in [.05,.95]]}
        if name in truth:
            result[name]['truth']=float(truth[name])
            # Raw correlated ranks are descriptive only; qualification requires ESS-aware SBC handling.
            result[name]['raw_rank_fraction']=float((v<truth[name]).mean())
            result[name]['covers_truth_90']=bool(np.quantile(v,.05)<=truth[name]<=np.quantile(v,.95))
    parameter_checks={f'q_{j}':{'rhat':float(az.rhat(draws[...,j],method='rank')),
                      'bulk_ess':float(az.ess(draws[...,j],method='bulk')),
                      'tail_ess':float(az.ess(draws[...,j],method='tail',prob=(.05,.95)))} for j in range(draws.shape[-1])}
    health=all(d['rhat']<=1.01 and d['bulk_ess']>=400 and d['tail_ess']>=400 for d in list(result.values())+list(parameter_checks.values()))
    out={'functionals':result,'diagnostic_gate':health,'chain_count':draws.shape[0],
         'computational_screen_pass':draws.shape[0]>=4 and health,'canonical_parameter_diagnostics':parameter_checks}
    if 'holdout' in fixture:
        rng=np.random.default_rng(predictive_seed); data=fixture['data']; future=fixture['holdout']
        h=draws[...,-1].copy(); mu=draws[...,2]; sig=np.exp(draws[...,3]); rows=[]
        for horizon,(x,y) in enumerate(zip(future['x'],future['y']),1):
            h=mu+data['rho']*(h-mu)+sig*rng.normal(size=h.shape)
            location=np.stack([vals[f'alpha_{j}']+vals[f'beta_{j}']*x[j] for j in range(g)],axis=-1)
            pred=location+np.exp(h[...,None]/2)*rng.standard_t(data['nu'],size=location.shape)
            for j in range(g):
                v=pred[...,j]; lo,hi=np.quantile(v,[.05,.95]); observed=y[j]
                interval_score=hi-lo+20*max(lo-observed,0)+20*max(observed-hi,0)
                rows.append({'horizon':horizon,'group':j,'observed':observed,'lower':float(lo),'upper':float(hi),
                  'covered':bool(lo<=observed<=hi),'width':float(hi-lo),'interval_score':float(interval_score),
                  'endpoint_mcse':[float(az.mcse(v,method='quantile',prob=p)) for p in [.05,.95]]})
        out['forecast']={'kind':'fixed-origin multi-horizon conditional on supplied covariates; no holdout outcome updates',
                         'predictive_mcse_note':'Includes one nested future-path and Student-t draw per posterior draw; endpoint MCSE combines posterior autocorrelation and nested Monte Carlo noise.',
                         'operational_forecast_qualified':False,'rows':rows,'coverage':float(np.mean([r['covered'] for r in rows])),
                         'mean_interval_score':float(np.mean([r['interval_score'] for r in rows])),
                         'coverage_uncertainty':'No iid binomial interval: horizons/groups share latent state; use independent datasets or origin blocks.'}
    return out
