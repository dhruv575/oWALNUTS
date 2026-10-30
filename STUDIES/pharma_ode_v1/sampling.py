import time
import numpy as np
import owalnuts,nutpie
from backend import Backend

CONFIGS={f'{engine}_{space}_{accept}':dict(engine=engine,space=space,accept=value)
 for engine in ('walnuts','nuts') for space in ('raw','white') for accept,value in [('90',.9),('99',.99)]}

def fit(data,prep,config,seed,draws,warmup):
    c=CONFIGS[config];d=data['P'];starts=np.array(prep['starts']);mode=np.array(prep['mode']);L=np.array(prep['L'])
    if c['space']=='white':
        initial=np.linalg.solve(L,(starts-mode).T).T;b=Backend(data,mode,L,initial)
    else:initial=starts;b=Backend(data,starts=initial)
    b.reset();start=time.monotonic()
    if c['engine']=='walnuts':
        f=owalnuts.sample(b.walnuts,dim=d,init=initial,chains=4,threads=1,warmup=warmup,draws=draws,seed=seed,tuning=owalnuts.Tuning(max_depth=11,max_error=1.),adaptation=owalnuts.Adaptation(target_accept=c['accept']))
        q=f.samples;div=int(f.divergent[:,warmup:].sum());depth=int((f.depth[:,warmup:]>=11).sum())
    else:
        f=nutpie.sample(b.nuts,chains=4,cores=1,tune=warmup,draws=draws,seed=seed,progress_bar=False,save_warmup=False,target_accept=c['accept'],maxdepth=11,low_rank_modified_mass_matrix=False,transform_adapt=False)
        q=np.asarray(f.posterior.q.values);div=int(f.sample_stats.diverging.sum());depth=int(f.sample_stats.maxdepth_reached.sum());f.close();assert b.initial_calls==4
    seconds=time.monotonic()-start;calls,errors=b.counts();b.close()
    if c['space']=='white':q=q@L.T+mode
    return q,dict(seconds=seconds,target_calls=calls,solver_errors=errors,divergences=div,depth_hits=depth)
