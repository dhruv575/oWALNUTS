import json,sys,time
from pathlib import Path
import numpy as np
from bounded_rescaled_slice import transition,physical


def run(index,out):
    if index not in range(12):raise ValueError('Fixed chain index')
    out=Path(out);out.mkdir(exist_ok=False);cap=(.5,1.,2.)[index//4]
    rng=np.random.default_rng(398137000+index);state=np.zeros(15);rows=[];work=[];start=time.monotonic()
    for tick in range(5000):
        state,calls=transition(state,np.zeros(12),cap,rng)
        rows.append(physical(state,cap)[0]);work.append(calls)
    values=np.asarray(rows)
    if values.shape!=(5000,15) or not np.isfinite(values).all():raise ValueError('Draw contract')
    np.savez_compressed(out/'draws.npz',warmup=values[:1000],draws=values[1000:],work=np.asarray(work))
    result=dict(index=index,cap=cap,seed=398137000+index,warmup=1000,retained=4000,proposal_evaluations=int(sum(work)),elapsed_seconds=time.monotonic()-start)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
