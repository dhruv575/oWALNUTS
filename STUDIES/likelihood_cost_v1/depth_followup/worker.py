import time
START=time.monotonic()
import sys,json,traceback,hashlib
from pathlib import Path
import numpy as np
from targets import Target,SIZES
from native import Native
from sampling import sample
from metrics import assess

CONFIGS={
 'walnuts_full':dict(engine='walnuts',accept=.9,error=1.,kind=0),
 'nuts_full':dict(engine='nuts',accept=.99,mass='diag',kind=0),
 'nuts_lowrank_full':dict(engine='nuts',accept=.99,mass='lowrank',kind=0),
 'nuts_collapsed':dict(engine='nuts',accept=.99,mass='diag',kind=1),
 'nuts_reparam':dict(engine='nuts',accept=.99,mass='diag',kind=2)}
DRAWS=6000

def run(case,config,rep,out):
    case=int(case);rep=int(rep);out=Path(out);out.mkdir(parents=True,exist_ok=False)
    seed=815000000+case*1000000+list(CONFIGS).index(config)*10000+rep*100
    c=CONFIGS[config];owner=None;r=dict(case=case,n=SIZES[case],config=config,rep=rep,seed=seed,draws=DRAWS,import_seconds=time.monotonic()-START)
    try:
        start=time.monotonic();t=Target(SIZES[case],c['kind']);r['data_precompute_seconds']=time.monotonic()-start
        r['data_sha256']=hashlib.sha256(t.X.tobytes()+t.y.tobytes()).hexdigest()
        start=time.monotonic();owner=Native(t);r['compile_seconds']=time.monotonic()-start
        q,info=sample(t,owner,c,seed,DRAWS);r.update(info)
        start=time.monotonic()
        if c['kind']==2:q=t.forward(q)
        r['materialize_seconds']=time.monotonic()-start
        start=time.monotonic();r['metrics']=assess(t,q,info['divergences'],info['depth_hits']);r['diagnostic_seconds']=time.monotonic()-start
        np.savez_compressed(out/'draws.npz',draws=q);r['status']='ok'
    except Exception as e:
        r.update(status='failed',error=repr(e));(out/'ERROR.txt').write_text(traceback.format_exc())
        if owner is not None:r.update(target_calls=int(owner.counter[0]),nonfinite_calls=int(owner.counter[1]))
    r['total_seconds']=time.monotonic()-START
    (out/'RESULT.json').write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')

if __name__=='__main__':run(*sys.argv[1:])
