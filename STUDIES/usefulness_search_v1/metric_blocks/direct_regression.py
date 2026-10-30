import hashlib,json,time
from pathlib import Path
import numpy as np
import arviz as az
import bridgestan as bs
from scipy.special import gammaln
root=Path(__file__).resolve().parent
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
name='earnings-logearn_interaction'
data_path=models/(name+'.data.json');model_path=models/(name+'_model.so')
reference_path=root.parent/'model01/REFERENCES.json'
paths=[data_path,model_path,models/(name+'.stan'),reference_path,root/'direct_regression.py',root/'DIRECT-PROTOCOL.md']
inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
ref=json.loads(reference_path.read_text())[name];assert ref['passed']
data=json.loads(data_path.read_text());start=time.monotonic()
y=np.log(data['earn']);height=np.asarray(data['height']);male=np.asarray(data['male'])
X=np.column_stack([np.ones(len(y)),height,male,height*male]);n,p=X.shape
assert n>p+1 and np.linalg.matrix_rank(X)==p
Q,R=np.linalg.qr(X,mode='reduced');hat=np.linalg.solve(R,Q.T@y)
residual=y-X@hat;sse=float(residual@residual);alpha=(n-p-1)/2;b=sse/2
Ri=np.linalg.solve(R,np.eye(p));cov=Ri@Ri.T
es2=b/(alpha-1);es=np.sqrt(b)*np.exp(gammaln(alpha-.5)-gammaln(alpha))
exact_mean=np.r_[hat,es];exact_sd=np.r_[np.sqrt(es2*np.diag(cov)),np.sqrt(es2-es**2)]
fit_seconds=time.monotonic()-start
assert np.isfinite(exact_sd).all() and min(exact_sd)>0
def generate(seed,shape):
    rng=np.random.default_rng(seed);sigma=np.sqrt(b/rng.gamma(alpha,1,size=shape))
    beta=hat+sigma[...,None]*(rng.normal(size=(*shape,p))@Ri.T)
    return np.concatenate([beta,sigma[...,None]],axis=-1)
target=bs.StanModel(str(model_path),data=data_path.read_text(),seed=1)
assert target.param_unc_names()==['beta.1','beta.2','beta.3','beta.4','sigma']
test=generate(928500000,(64,));lp=[];analytic=[];errors=[];check_start=time.monotonic()
for row in test:
    beta=row[:p];sigma=row[-1];q=np.r_[beta,np.log(sigma)]
    value,g=target.log_density_gradient(q)
    d=R@(beta-hat);rss=sse+d@d
    expected=-(n-1)*np.log(sigma)-rss/(2*sigma**2)
    grad=np.r_[-R.T@d/sigma**2,-(n-1)+rss/sigma**2]
    lp.append(value);analytic.append(expected);errors.append(float(np.max(np.abs(g-grad)/(1+np.abs(g)))))
diff=np.asarray(lp)-analytic;max_lp=float(np.max(np.abs(diff-diff[0])))
preflight=dict(passed=max_lp<=1e-6 and max(errors)<=1e-7,max_centered_log_density_error=max_lp,
    max_scaled_gradient_error=max(errors),target_calls=64,seconds=time.monotonic()-check_start,
    n=n,p=p,alpha=alpha,b=b,beta_hat=hat.tolist(),exact_mean=exact_mean.tolist(),exact_sd=exact_sd.tolist(),
    fit_seconds=fit_seconds,inputs=inputs)
(root/'PREFLIGHT.json').write_text(json.dumps(preflight,indent=2)+'\n')
assert preflight['passed'],preflight
rows=[]
for seed in range(928500001,928500005):
    t=time.monotonic();draws=generate(seed,(4,8192));seconds=time.monotonic()-t
    np.savez_compressed(root/f'draws-{seed}.npz',draws=draws)
    t=time.monotonic();ds=az.convert_to_dataset({'p':draws});mean=draws.mean((0,1));sd=draws.reshape(-1,p+1).std(0,ddof=1)
    rh=np.asarray(az.rhat(ds,method='rank').p);bulk=np.asarray(az.ess(ds,method='bulk').p);tail=np.asarray(az.ess(ds,method='tail').p);mcse=np.asarray(az.mcse(ds,method='mean').p)
    z=np.abs(mean-ref['mean'])/np.sqrt(mcse**2+np.array(ref['mcse'])**2)
    delta=np.abs(mean-ref['mean'])/ref['sd'];sd_error=np.abs(sd/ref['sd']-1)
    exact_delta=np.abs(mean-exact_mean)/exact_sd;exact_sd_error=np.abs(sd/exact_sd-1)
    passed=rh.max()<=1.01 and min(bulk.min(),tail.min())>=400 and z.max()<=4.5 and delta.max()<=.1 and sd_error.max()<=.1 and exact_delta.max()<=.05 and exact_sd_error.max()<=.05
    rows.append(dict(seed=seed,passed=bool(passed),rank_rhat=rh.tolist(),bulk_ess=bulk.tolist(),tail_ess=tail.tolist(),
        mean=mean.tolist(),sd=sd.tolist(),mcse=mcse.tolist(),reference_z=z.tolist(),reference_mean_error_sd=delta.tolist(),reference_sd_error=sd_error.tolist(),exact_mean_error_sd=exact_delta.tolist(),exact_sd_error=exact_sd_error.tolist(),
        fit_seconds_charged=fit_seconds,generation_seconds=seconds,diagnostic_seconds=time.monotonic()-t,sampling_target_calls=0))
result=dict(passed=all(r['passed'] for r in rows),rows=rows,preflight=preflight,
    unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in inputs.items()))
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
