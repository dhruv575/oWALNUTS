"""Fixed T1 independent sampler preflight, one chain per invocation."""
import json,sys,time
from pathlib import Path
import numpy as np
from price_cell_slice import transition,physical


def run(index,out):
    if index not in range(4):raise ValueError('Fixed chain index')
    out=Path(out);out.mkdir(exist_ok=False);rng=np.random.default_rng(398125000+index)
    c=np.zeros(4);x=np.zeros(1);rows=[];counts=[];start=time.monotonic()
    for tick in range(5000):
        c,x,work=transition(c,x,[-.0005],[.0005],rng)
        u=np.log(x+.0005)-np.log(.0005-x)
        rows.append(np.r_[physical(c),u]);counts.append([work['slice_evaluations'],work['price_proposals']])
    np.savez_compressed(out/'draws.npz',warmup=np.asarray(rows[:1000]),draws=np.asarray(rows[1000:]),work=np.asarray(counts))
    result=dict(index=index,seed=398125000+index,warmup=1000,retained=4000,slice_evaluations=int(np.sum(np.asarray(counts)[:,0])),price_proposals=int(np.sum(np.asarray(counts)[:,1])),elapsed_seconds=time.monotonic()-start)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
