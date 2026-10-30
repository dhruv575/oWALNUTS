import hashlib,json,time
from pathlib import Path
import numpy as np
from fisher_high_precision import covariance_from_samples
from fisher_dense import covariance_from_scores
root=Path(__file__).resolve().parent;rng=np.random.default_rng(928900000);rows=[];raw=[];start=time.monotonic()
for d in [2,5,10]:
    for condition in [1.,100.,10000.]:
        q,_=np.linalg.qr(rng.normal(size=(d,d)));true=(q*np.geomspace(1,condition,d))@q.T
        precision=np.linalg.inv(true);x=rng.normal(size=(128,d))*np.geomspace(1e-3,1e3,d)
        scores=-x@precision;c=np.cov(x,rowvar=False);g=np.cov(scores,rowvar=False);perm=rng.permutation(d)
        record=dict(d=d,condition=condition);item=dict(true=true.tolist(),positions=x.tolist(),scores=scores.tolist(),permutation=perm.tolist())
        try:
            s=covariance_from_samples(x,scores);err=float(np.linalg.norm(s-true)/np.linalg.norm(true));res=float(np.linalg.norm(s@g@s-c)/np.linalg.norm(c))
            sp=covariance_from_samples(x[:,perm],scores[:,perm]);pe=float(np.linalg.norm(sp-s[np.ix_(perm,perm)])/np.linalg.norm(s))
            record.update(passed=err<=1e-6 and res<=1e-8 and pe<=1e-6,error=err,residual=res,permutation_error=pe);item['estimated']=s.tolist()
        except (ValueError,np.linalg.LinAlgError) as exc:record.update(passed=False,exception=str(exc))
        rows.append(record);raw.append(item)
for d in [2,5,10]:
    x=rng.normal(size=(128,d));y=rng.normal(size=(128,d))
    a=covariance_from_samples(x,y);b=covariance_from_scores(np.cov(x,rowvar=False),np.cov(y,rowvar=False))
    err=float(np.linalg.norm(a-b)/np.linalg.norm(b));rows.append(dict(test='ordinary_parity',d=d,error=err,passed=err<=1e-10))
for name,x,y,gamma in [('singular',np.zeros((10,3)),np.ones((10,3)),0),('nonfinite',np.full((10,3),np.nan),np.ones((10,3)),0),('negative_gamma',np.eye(3),np.eye(3),-1)]:
    try:covariance_from_samples(x,y,gamma);passed=False
    except (ValueError,np.linalg.LinAlgError):passed=True
    rows.append(dict(test=name,passed=passed))
s=covariance_from_samples(np.zeros((10,3)),np.zeros((10,3)),.001)
err=float(np.linalg.norm(s-np.eye(3)));rows.append(dict(test='regularized_singular',error=err,passed=err<=1e-8))
result=dict(passed=all(r['passed'] for r in rows),rows=rows,seconds=time.monotonic()-start,target_calls=0,
 inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [root/'fisher_high_precision.py',root/'fisher_dense.py',root/'test_fisher_high_precision.py',root/'FISHER-HIGH-PRECISION-PREFLIGHT.md']})
(root/'RAW.json').write_text(json.dumps(raw,indent=2)+'\n');(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if not result['passed']:raise SystemExit(1)

