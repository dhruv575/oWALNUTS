import hashlib,json,time
from pathlib import Path
import numpy as np
import bridgestan as bs
from scipy.integrate import quad_vec
from scipy.optimize import minimize_scalar

root=Path(__file__).resolve().parent
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
name='sblrc-blr'
paths=[models/(name+'.data.json'),models/(name+'.stan'),models/(name+'_model.so'),
       root.parent/'broad01/REFERENCES.json',root/'collapsed_regression.py',root/'COLLAPSED-PROTOCOL.md']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
data=json.loads(paths[0].read_text());ref=json.loads(paths[3].read_text())[name];assert ref['passed']
start=time.monotonic();X=np.asarray(data['X']);y=np.asarray(data['y']);n,p=X.shape
U,s,Vt=np.linalg.svd(X,full_matrices=False);assert len(s)==p and min(s)>max(s)*1e-12
z=U.T@y;res=y-U@z;rss=float(res@res);V=Vt.T
def conditional(t):
    ss=np.exp(2*t);den=ss+100*s*s
    mean=V@(100*s*z/den);var=(V*V)@(100*ss/den)
    return mean,var
def logmarginal(t):
    ss=np.exp(2*t);den=ss+100*s*s
    return -.5*((n-p)*2*t+np.log(den).sum()+rss/ss+(z*z/den).sum())-ss/200+t
opt=minimize_scalar(lambda t:-logmarginal(t),bounds=(-20,20),method='bounded')
assert opt.success and -19<opt.x<19
mode=float(opt.x);peak=logmarginal(mode);setup=time.monotonic()-start
records=[]
for radius in [12,16]:
    calls=[0]
    def integrand(t):
        calls[0]+=1;m,v=conditional(t);sig=np.exp(t)
        return np.exp(logmarginal(t)-peak)*np.r_[1,m,sig,v+m*m,sig*sig]
    t0=time.monotonic();value,error=quad_vec(integrand,mode-radius,mode+radius,epsabs=1e-10,epsrel=1e-10)
    mean=value[1:p+2]/value[0];sd=np.sqrt(value[p+2:]/value[0]-mean*mean)
    records.append(dict(radius=radius,mean=mean.tolist(),sd=sd.tolist(),relative_error=float(error/np.linalg.norm(value)),
        evaluations=calls[0],seconds=time.monotonic()-t0,boundary_relative_density=[float(np.exp(logmarginal(mode+a)-peak)) for a in [-radius,radius]]))
target=bs.StanModel(str(paths[2]),data=paths[0].read_text(),seed=1)
assert target.param_unc_names()==[f'beta.{i+1}' for i in range(p)]+['sigma']
rng=np.random.default_rng(929200000);diff=[];graderr=[]
for i in range(64):
    t=mode+rng.uniform(-.5,.5);ss=np.exp(2*t);den=ss+100*s*s
    mean,_=conditional(t);beta=mean+V@(np.sqrt(100*ss/den)*rng.normal(size=p))
    q=np.r_[beta,t];lp,g=target.log_density_gradient(q);r=y-X@beta
    analytic=-beta@beta/200-ss/200-(n-1)*t-r@r/(2*ss)
    gradient=np.r_[-beta/100+X.T@r/ss,-ss/100-(n-1)+r@r/ss]
    diff.append(float(lp-analytic));graderr.append(float(np.max(np.abs(g-gradient)/(1+np.abs(g)))))
density_error=float(np.max(np.abs(np.asarray(diff)-diff[0])))
mean=np.asarray(records[-1]['mean']);sd=np.asarray(records[-1]['sd']);rsd=np.asarray(ref['sd'])
zerr=np.abs(mean-ref['mean'])/ref['mcse'];delta=np.abs(mean-ref['mean'])/rsd;sderr=np.abs(sd/rsd-1)
agreement=max(np.max(np.abs(np.asarray(records[0][k])-records[1][k])/rsd) for k in ['mean','sd'])
passed=density_error<=1e-6 and max(graderr)<=1e-7 and agreement<=1e-7 and max(r['relative_error'] for r in records)<=1e-7 and max(zerr)<=4.5 and max(delta)<=.1 and max(sderr)<=.1
result=dict(passed=bool(passed),n=n,p=p,mode=mode,setup_seconds=setup,quadratures=records,
    moment_agreement_reference_sd=float(agreement),density_error=density_error,scaled_gradient_error=max(graderr),
    reference_z=zerr.tolist(),reference_mean_error_sd=delta.tolist(),reference_sd_error=sderr.tolist(),
    target_validation_calls=64,inputs=hashes,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()),
    limitation='Numerical moments only; no IID sampler, rigorous tail bound, or sampling speed claim.')
(root/'SUMMARY.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
