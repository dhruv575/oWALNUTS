import hashlib,json,time
from pathlib import Path
import numpy as np
from fisher_dense import covariance_from_scores
root=Path(__file__).resolve().parent;rng=np.random.default_rng(928900000);rows=[];raw=[];start=time.monotonic()
for d in [2,5,10]:
    for condition in [1.,100.,10000.]:
        q,_=np.linalg.qr(rng.normal(size=(d,d)));true=(q*np.geomspace(1,condition,d))@q.T
        precision=np.linalg.inv(true);x=rng.normal(size=(128,d))*np.geomspace(1e-3,1e3,d)
        scores=-x@precision;c=np.cov(x,rowvar=False);g=np.cov(scores,rowvar=False)
        record=dict(d=d,condition=condition)
        try:
            s=covariance_from_scores(c,g);err=float(np.linalg.norm(s-true)/np.linalg.norm(true));res=float(np.linalg.norm(s@g@s-c)/np.linalg.norm(c))
            perm=rng.permutation(d);sp=covariance_from_scores(c[np.ix_(perm,perm)],g[np.ix_(perm,perm)])
            pe=float(np.linalg.norm(sp-s[np.ix_(perm,perm)])/np.linalg.norm(s))
            record.update(passed=err<=1e-6 and res<=1e-8 and pe<=1e-6,error=err,residual=res,permutation_error=pe)
            raw.append(dict(d=d,condition=condition,true=true.tolist(),position_covariance=c.tolist(),score_covariance=g.tolist(),estimated=s.tolist()))
        except (ValueError,np.linalg.LinAlgError) as exc:
            record.update(passed=False,exception=str(exc));raw.append(dict(d=d,condition=condition,true=true.tolist(),position_covariance=c.tolist(),score_covariance=g.tolist()))
        rows.append(record)
singular=np.diag([1.,0.,0.]);identity=np.eye(3)
for name,c,g in [('singular',singular,identity),('indefinite',np.diag([1.,-1.,1.]),identity)]:
    try:covariance_from_scores(c,g);passed=False
    except (ValueError,np.linalg.LinAlgError):passed=True
    rows.append(dict(test=name,passed=passed))
try:
    gamma=.001;s=covariance_from_scores(singular,singular,gamma);a=singular+gamma*identity
    residual=float(np.linalg.norm(s@a@s-a)/np.linalg.norm(a));rows.append(dict(test='regularized_singular',passed=residual<=1e-8,residual=residual))
except (ValueError,np.linalg.LinAlgError) as exc:rows.append(dict(test='regularized_singular',passed=False,exception=str(exc)))
result=dict(passed=all(r['passed'] for r in rows),rows=rows,seconds=time.monotonic()-start,target_calls=0,
    inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'fisher_dense.py',root/'test_fisher_dense.py',root/'FISHER-PREFLIGHT.md']})
(root/'RAW.json').write_text(json.dumps(raw,indent=2)+'\n');(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if not result['passed']:raise SystemExit(1)
