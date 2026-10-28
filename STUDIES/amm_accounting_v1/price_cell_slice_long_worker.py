"""Fixed long-window independent sampler panel, one chain per invocation."""
import json,sys,time
from pathlib import Path
import numpy as np
from price_cell_slice import transition,physical
from price_cell_fixtures import fixture


def run(index,out):
    if index not in range(16):raise ValueError('Fixed chain index')
    out=Path(out);out.mkdir(exist_ok=False);rng=np.random.default_rng(398126000+index)
    n,width=[(12,.001),(12,.00001),(250,.001),(250,.00001)][index//4]
    data,_=fixture(n,width);lower=data['lower_cell'];upper=data['upper_cell']
    c=np.zeros(3+n);x=(lower+upper)/2;rows=[];counts=[];start=time.monotonic()
    for tick in range(5000):
        c,x,work=transition(c,x,lower,upper,rng)
        u=np.log(x-lower)-np.log(upper-x)
        rows.append(np.r_[physical(c),u]);counts.append([work['slice_evaluations'],work['price_proposals']])
    np.savez_compressed(out/'draws.npz',warmup=np.asarray(rows[:1000]),draws=np.asarray(rows[1000:]),work=np.asarray(counts))
    result=dict(index=index,fixture=index//4,n=n,width=width,seed=398126000+index,warmup=1000,retained=4000,slice_evaluations=int(np.sum(np.asarray(counts)[:,0])),price_proposals=int(np.sum(np.asarray(counts)[:,1])),elapsed_seconds=time.monotonic()-start)
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
