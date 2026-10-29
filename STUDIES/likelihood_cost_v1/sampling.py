import time
import numpy as np
import owalnuts,nutpie

def sample(t,owner,c,seed,draws):
    owner.counter[:]=0;start=time.monotonic()
    if c['engine']=='walnuts':
        fit=owalnuts.sample(owner.walnuts,dim=t.dim,init=t.initial(),chains=4,threads=1,warmup=750,draws=draws,seed=seed,
            tuning=owalnuts.Tuning(max_depth=10,max_error=c['error']),adaptation=owalnuts.Adaptation(target_accept=c['accept']))
        q=fit.samples;div=int(fit.divergent[:,750:].sum());depth=int((fit.depth[:,750:]>=10).sum())
    else:
        extra={'use_grad_based_mass_matrix':False} if c['mass']=='draw' else {}
        fit=nutpie.sample(owner.nuts,chains=4,cores=1,tune=750,draws=draws,seed=seed,progress_bar=False,save_warmup=False,
            target_accept=c['accept'],maxdepth=10,low_rank_modified_mass_matrix=c['mass']=='lowrank',transform_adapt=False,**extra)
        q=np.asarray(fit.posterior.q.values);div=int(fit.sample_stats.diverging.sum());depth=int(fit.sample_stats.maxdepth_reached.sum());fit.close()
        assert owner.initial_calls==4
    return q,dict(seconds=time.monotonic()-start,target_calls=int(owner.counter[0]),nonfinite_calls=int(owner.counter[1]),divergences=div,depth_hits=depth)
