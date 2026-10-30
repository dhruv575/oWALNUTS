import hashlib,json
from pathlib import Path
import numpy as np
from scipy.special import polygamma
root=Path(__file__).resolve().parent
path=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models/earnings-logearn_interaction.data.json')
data=json.loads(path.read_text());y=np.log(data['earn']);h=np.asarray(data['height']);m=np.asarray(data['male'])
X=np.column_stack([np.ones(len(y)),h,m,h*m]);Q,R=np.linalg.qr(X,mode='reduced');hat=np.linalg.solve(R,Q.T@y)
res=y-X@hat;alpha=(len(y)-5)/2;b=float(res@res)/2;Ri=np.linalg.solve(R,np.eye(4))
exact=np.zeros((5,5));exact[:4,:4]=b/(alpha-1)*(Ri@Ri.T);exact[4,4]=float(polygamma(1,alpha))/4
precision=np.linalg.inv(exact);rows=[]
summary=json.loads((root/'SUMMARY.json').read_text());assert summary['unchanged']
inputs={str(path):hashlib.sha256(path.read_bytes()).hexdigest()}
for seed in range(928600001,928600017):
    p=root/f'{seed}-MATRICES.json'
    if not p.exists():continue
    inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();mat=json.loads(p.read_text())
    for arm in ['fixed_diag','empirical','curvature']:
        c=np.diag(mat['variances']) if arm=='fixed_diag' else np.asarray(mat[arm])
        l=np.linalg.cholesky(c);w=l.T@precision@l;e=np.linalg.eigvalsh((w+w.T)/2)
        result=next(r for r in summary['rows'] if r['seed']==seed and r['arm']==arm)
        rows.append(dict(seed=seed,arm=arm,passed=result['passed'],condition_proxy=float(e[-1]/e[0]),
            marginal_variance_ratios=(np.diag(c)/np.diag(exact)).tolist(),bulk=result.get('functionals',{}).get('bulk'),
            selection=mat['selection'] if arm=='curvature' else None))
out=dict(exact_unconstrained_covariance=exact.tolist(),inputs=inputs,rows=rows,
    interpretation='Post-hoc geometry diagnostic only; no changed gate or demonstrated causal attribution.')
(root/'DIAGNOSIS.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(rows))
