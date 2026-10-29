import time
import numpy as np
import owalnuts,nutpie
from nutpie.compiled_pyfunc import from_pyfunc

CONFIGS={**{f'walnuts_{v}':dict(engine='walnuts',accept=a,lowrank=False) for v,a in [('80',.8),('90',.9),('99',.99)]},
    **{f'nuts_{v}':dict(engine='nuts',accept=a,lowrank=False) for v,a in [('80',.8),('90',.9),('99',.99)]},
    'nuts_lowrank90':dict(engine='nuts',accept=.9,lowrank=True)}


def fit(target,config,seed,draws,warmup=750):
    c=CONFIGS[config];target.calls=0;target.nonfinite=0;start=time.monotonic()
    if c['engine']=='walnuts':
        result=owalnuts.sample(target,dim=target.dim,init=target.initial(),chains=4,threads=1,warmup=warmup,draws=draws,seed=seed,
            tuning=owalnuts.Tuning(max_depth=10),adaptation=owalnuts.Adaptation(target_accept=c['accept']))
        q=result.samples;div=int(result.divergent[:,warmup:].sum());depth=int((result.depth[:,warmup:]>=10).sum())
    else:
        starts=iter(target.initial());initial_count=[0]
        def initial(seed):initial_count[0]+=1;return next(starts).copy()
        compiled=from_pyfunc(target.dim,lambda:target,lambda *args:lambda q:{'x':np.array(q)},[np.dtype('float64')],[(target.dim,)],['x'],make_initial_point_fn=initial)
        result=nutpie.sample(compiled,chains=4,cores=1,tune=warmup,draws=draws,seed=seed,progress_bar=False,save_warmup=False,target_accept=c['accept'],maxdepth=10,low_rank_modified_mass_matrix=c['lowrank'],transform_adapt=False)
        q=np.asarray(result.posterior.x.values);div=int(result.sample_stats.diverging.sum());depth=int(result.sample_stats.maxdepth_reached.sum())
        result.close()
        if initial_count[0]!=4:raise ValueError('Unexpected initialization count')
    return q,dict(seconds=time.monotonic()-start,target_calls=target.calls,nonfinite_calls=target.nonfinite,divergences=div,depth_hits=depth,
        config=config,warmup=warmup,draws=draws,engine=c['engine'])
