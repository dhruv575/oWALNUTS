import hashlib,json
from pathlib import Path
import numpy as np
import bridgestan as bs
from native_common import model_files
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'transport_gradient_audit01';r.mkdir(exist_ok=False);rows=[]
for name in ['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
    so,data,source=model_files(name);target=bs.StanModel(str(so),data=data.read_text(),seed=1);path=l/'native_prefix02'/name/'long.npz'
    with np.load(path) as z:q=z['sample_stats__unconstrained_draw'][:,100:];g=z['sample_stats__gradient'][:,100:]
    errors=[];points=[]
    for chain in range(4):
        for index in [0,999,1999]:
            lp,actual=target.log_density_gradient(q[chain,index]);relative=float(np.max(abs(actual-g[chain,index]))/(1+np.max(abs(actual))));errors.append(relative);points.append(dict(chain=chain,index=index,position=q[chain,index].tolist(),stored=g[chain,index].tolist(),actual=actual.tolist(),log_density=float(lp),relative_error=relative))
    row=dict(model=name,passed=max(errors)<1e-8,max_relative_error=max(errors),target_gradient_calls=12,points=points,inputs={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [so,data,source,path]});rows.append(row);print(json.dumps(dict(model=name,passed=row['passed'],max_relative_error=max(errors))),flush=True)
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,target_gradient_calls=72),indent=2,allow_nan=False)+'\n')
