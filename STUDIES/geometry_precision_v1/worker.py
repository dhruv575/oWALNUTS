import time
START=time.monotonic()
import sys,json,traceback
from pathlib import Path
import numpy as np
from targets import Target,NAMES
from sampling import fit,CONFIGS
from metrics import assess


def write(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def run(name,config,rep,draws,phase,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=False);rep=int(rep);draws=int(draws)
    ci=list(CONFIGS).index(config);ni=NAMES.index(name)
    seed={'pilot':605000000,'calibrate':615000000,'test':625000000}[phase]+ni*100000+ci*10000+rep*100+{250:0,1000:1,3000:2}[draws]
    write(out/'START.json',dict(name=name,config=config,rep=rep,draws=draws,phase=phase,seed=seed))
    result=dict(name=name,config=config,rep=rep,draws=draws,phase=phase,seed=seed,runtime_import_seconds=time.monotonic()-START)
    try:
        start=time.monotonic();t=Target(name);result['target_setup_seconds']=time.monotonic()-start
        q,info=fit(t,config,seed,draws);result.update(info)
        stamp=time.monotonic();result['metrics']=assess(t,q,info['divergences'],info['depth_hits']);result['diagnostic_seconds']=time.monotonic()-stamp
        np.savez_compressed(out/'draws.npz',draws=q)
        result['status']='ok'
    except Exception as exc:
        result.update(status='failed',error=repr(exc));(out/'ERROR.txt').write_text(traceback.format_exc())
    result['total_seconds']=time.monotonic()-START;write(out/'RESULT.json',result)
    print(json.dumps({k:result.get(k) for k in ['name','config','rep','draws','status','total_seconds']}),flush=True)


if __name__=='__main__':run(*sys.argv[1:])
