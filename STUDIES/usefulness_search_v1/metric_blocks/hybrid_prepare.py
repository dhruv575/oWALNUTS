import hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import bridgestan as bs
from fisher_high_precision import covariance_from_samples
from hybrid_gate import evaluate
from selector_full_shape import select
inp=json.loads(Path(sys.argv[1]).read_text());pilot=Path(inp['pilot']);raw=pilot.read_bytes();p=json.loads(raw)
target=bs.StanModel(inp['model'],data=Path(inp['data']).read_text(),seed=1)
x=np.array(p['draws']);flat=x.reshape(-1,x.shape[-1]);d=x.shape[-1]
def install(c):
    m=np.linalg.inv(c);m=(m+m.T)/2
    assert np.isfinite(m).all() and np.linalg.eigvalsh(m).min()>0 and np.linalg.norm(c@m-np.eye(d))<=1e-7
    return m.tolist()
t=time.monotonic();scores=np.array([target.log_density_gradient(q)[1] for q in flat]);score_seconds=time.monotonic()-t
t=time.monotonic();gate=evaluate(x,scores.reshape(x.shape));gate_seconds=time.monotonic()-t
t=time.monotonic();fisher=None;fisher_error=None
try:
    fc=covariance_from_samples(flat,scores);fisher=install(fc)
except Exception:fisher_error=traceback.format_exc()
fisher_seconds=time.monotonic()-t
t=time.monotonic();coarse=[];fine=[];calls=0
for chain in x:
    for q in chain[[0,24,49,99]]:
        matrices=[]
        for step in [1e-4,5e-5]:
            h=np.empty((d,d))
            for j in range(d):
                delta=np.eye(d)[j]*step*(1+abs(q[j]))
                _,gp=target.log_density_gradient(q+delta);_,gm=target.log_density_gradient(q-delta);calls+=2
                h[:,j]=-(np.asarray(gp)-np.asarray(gm))/(2*delta[j])
            matrices.append(h)
        coarse.append(matrices[0]);fine.append(matrices[1])
v=np.maximum(x.var(axis=1,ddof=1).mean(0),1e-8);c,selection=select(coarse,fine,v);v4=install(c)
probe_seconds=time.monotonic()-t
branch='fisher' if gate['use_fisher'] and fisher is not None else ('v4' if selection['blocks'] else 'auto')
r=dict(fisher_mass=fisher,fisher_error=fisher_error,v4_mass=v4,selection=selection,gate=gate,branch=branch,
    scores=scores.tolist(),coarse=np.array(coarse).tolist(),fine=np.array(fine).tolist(),variances=v.tolist(),
    score_calls=len(flat),probe_calls=calls,score_seconds=score_seconds,gate_seconds=gate_seconds,
    fisher_seconds=fisher_seconds,probe_seconds=probe_seconds,pilot_sha256=hashlib.sha256(raw).hexdigest())
Path(sys.argv[2]).write_text(json.dumps(r,indent=2,allow_nan=False)+'\n')
