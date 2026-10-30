import time
START=time.monotonic()
import sys,json,traceback
from pathlib import Path
import numpy as np
from backend import Backend,ROOT
from sampling import CONFIGS,fit
from features import features,summarize,predictions,heldout

CASES=['stan_public','theoph_1','theoph_2','theoph_3','linear_1','linear_2','linear_3']

def run(phase,case,config,rep,out):
    rep=int(rep);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    data=json.loads((ROOT/'data'/f'{case}.json').read_text());prep=json.loads((ROOT/'prepared'/f'{case}.json').read_text());meta=json.loads((ROOT/'data/CASES.json').read_text())[case]
    seed={'calibrate':845000000,'reference':855000000,'validate':865000000,'laplace':875000000}[phase]+CASES.index(case)*100000+rep*1000+(list(CONFIGS).index(config) if config in CONFIGS else 99)
    draws,warmup={'calibrate':(1000,750),'reference':(6000,1500),'validate':(2000,1000),'laplace':(4000,0)}[phase]
    r=dict(phase=phase,case=case,config=config,rep=rep,seed=seed,draws=draws,warmup=warmup,import_seconds=time.monotonic()-START)
    try:
        if phase=='laplace':
            if not prep['laplace_valid']:raise ValueError('Laplace Hessian or MAP failed')
            start=time.monotonic();q=np.random.default_rng(seed).normal(size=(4,draws,data['P']))@np.array(prep['L']).T+np.array(prep['mode']);r.update(seconds=time.monotonic()-start+prep['seconds'],target_calls=None,solver_errors=0,divergences=0,depth_hits=0)
        else:q,info=fit(data,prep,config,seed,draws,warmup);r.update(info)
        start=time.monotonic();b=Backend(data);pred=predictions(b,q);b.close()
        f=features(q.reshape(-1,data['P']),pred.reshape(-1,data['Npred']),meta['threshold']).reshape(4,draws,-1)
        r['summary']=summarize(f,r['divergences'],r['depth_hits']);r['heldout']=heldout(q,pred,meta['holdout_concentration']);r['diagnostic_seconds']=time.monotonic()-start
        np.savez_compressed(out/'draws.npz',q=q,pred=pred);r['status']='ok'
    except Exception as e:r.update(status='failed',error=repr(e));(out/'ERROR.txt').write_text(traceback.format_exc())
    r['worker_seconds']=time.monotonic()-START
    r['shared_preparation_seconds']=prep['seconds']
    r['total_seconds']=r['worker_seconds']+prep['seconds']
    (out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':run(*sys.argv[1:])
