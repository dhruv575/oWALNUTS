"""Algebra/target-gradient check only; does not execute the WALNUTS kernel."""
import json,hashlib
from pathlib import Path
import numpy as np,bridgestan as bs
from native_common import LOCAL,model_files
rows=[];rng=np.random.default_rng(940700002)
paths=[LOCAL/'native_transform_probe01']+sorted(p for p in (LOCAL/'native_transform_models01').iterdir() if p.is_dir())
for folder in paths:
    model='arK-arK' if folder.name=='native_transform_probe01' else folder.name
    s=json.loads((folder/'SUMMARY.json').read_text());assert s['passed']
    so,data,_=model_files(model);target=bs.StanModel(str(so),data=data.read_text(),seed=1)
    with np.load(folder/'stored.npz') as arrays:xall=arrays['unconstrained_draw'].copy()
    for c,record in enumerate(s['rows']):
        A=np.asarray(record['A']);mu=np.asarray(record['mu']);C=A@A.T;M=np.linalg.inv(C)
        inverse_error=float(np.linalg.norm(C@M-np.eye(len(C))));assert inverse_error<1e-7
        for eps in [.0001,.001,.01]:
            x=xall[c,50];z=np.linalg.solve(A,x-mu);r=rng.normal(size=len(x));p=np.linalg.solve(A.T,r)
            k_error=float(abs(p@C@p-r@r)/(1+r@r))
            _,g=target.log_density_gradient(x);g=np.asarray(g)
            ph=p+.5*eps*g;xh=x+eps*(C@ph);_,gh=target.log_density_gradient(xh);pf=ph+.5*eps*np.asarray(gh)
            rh=r+.5*eps*(A.T@g);zh=z+eps*rh;xt=mu+A@zh;_,gt=target.log_density_gradient(xt);rf=rh+.5*eps*(A.T@np.asarray(gt))
            q_error=float(np.max(abs(xh-xt))/(1+np.max(abs(xh))))
            p_error=float(np.max(abs(A.T@pf-rf))/(1+np.max(abs(rf))))
            assert max(k_error,q_error,p_error)<1e-8
            rows.append(dict(model=model,chain=c,step_size=eps,kinetic_relative_error=k_error,position_relative_error=q_error,momentum_relative_error=p_error,inverse_error=inverse_error))
out=dict(passed=True,scope=__doc__,rows=rows,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(LOCAL/'METRIC-CONVENTION-CHECK.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(passed=True,checks=len(rows),max_error=max(max(r['kinetic_relative_error'],r['position_relative_error'],r['momentum_relative_error']) for r in rows))))
