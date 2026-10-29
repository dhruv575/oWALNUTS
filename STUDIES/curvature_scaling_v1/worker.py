import time
START=time.monotonic()
import sys,json,traceback
from pathlib import Path
import numpy as np
import owalnuts,nutpie
from targets import Target,CASES
from native import Native
from metrics import assess

CONFIGS={}
for a in (.9,.99):
    for e in (.1,1.,10.):CONFIGS[f'w{a:g}_e{e:g}']=dict(engine='walnuts',accept=a,error=e)
    for mass in ('diag','draw','lowrank'):CONFIGS[f'n{a:g}_{mass}']=dict(engine='nuts',accept=a,mass=mass)
DEFAULT='w0.99_e1';REPARAM='n0.99_diag_reparam'
CONFIGS[REPARAM]=dict(engine='nuts',accept=.99,mass='diag',reparam=True)
BUDGETS=[3000,6000]

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

def run(phase,case,config,rep,draws,out):
    case=int(case);rep=int(rep);draws=int(draws);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    seed=(715000000 if phase=='calibrate' else 725000000)+case*1000000+list(CONFIGS).index(config)*10000+rep*100+BUDGETS.index(draws)
    c=CONFIGS[config];dim,b=CASES[case];owner=None
    r=dict(phase=phase,case=case,dim=dim,curvature=b,config=config,rep=rep,draws=draws,seed=seed,import_seconds=time.monotonic()-START)
    try:
        start=time.monotonic();target=Target(dim,b);sample_target=Target(dim,0.) if c.get('reparam') else target
        owner=Native(sample_target);r['setup_seconds']=time.monotonic()-start
        q,info=sample(sample_target,owner,c,seed,draws);r.update(info)
        start=time.monotonic()
        if c.get('reparam'):q=target.forward(q)
        r['materialize_seconds']=time.monotonic()-start
        start=time.monotonic();r['metrics']=assess(target,q,info['divergences'],info['depth_hits']);r['diagnostic_seconds']=time.monotonic()-start
        np.savez_compressed(out/'draws.npz',draws=q);r['status']='ok'
    except Exception as e:
        r.update(status='failed',error=repr(e));(out/'ERROR.txt').write_text(traceback.format_exc())
        if owner is not None:r.update(target_calls=int(owner.counter[0]),nonfinite_calls=int(owner.counter[1]))
    r['total_seconds']=time.monotonic()-START
    (out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':run(*sys.argv[1:])
