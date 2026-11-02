import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
from backend import *
import time
from scipy.optimize import minimize
def main():
    out=BASE/'laplace';out.mkdir(exist_ok=False)
    for index,case in enumerate(['weak','mixed']):
        start=time.perf_counter();data=json.loads((BASE/(case+'.json')).read_text());reference=json.loads((BASE/'references'/(case+'.json')).read_text());b=Backend(data,'noncentered')
        def objective(q):
            try:v,g=b.value(q);return -v,-g
            except ValueError:return np.inf,np.zeros(14)
        fit=minimize(objective,b.starts[2],jac=True,method='BFGS',options={'gtol':1e-7,'maxiter':2000});basis=np.eye(14)*1e-4
        H=np.column_stack([(objective(fit.x+d)[1]-objective(fit.x-d)[1])/2e-4 for d in basis]);H=(H+H.T)/2
        valid=bool(max(abs(objective(fit.x)[1]))<=1e-4 and np.linalg.eigvalsh(H).min()>0);result=dict(valid=valid,mode=fit.x.tolist(),gradient_max=float(max(abs(fit.jac))),minimum_eigenvalue=float(np.linalg.eigvalsh(H).min()))
        if valid:
            q=np.random.default_rng(956300001+index).multivariate_normal(fit.x,np.linalg.inv(H),8192);f=features(to_physical(q,data,'noncentered'));mean=f.mean(0);sd=f.std(0,ddof=1);err=abs(mean-reference['mean']);refsd=np.array(reference['sd'])
            result.update(mean=mean.tolist(),sd=sd.tolist(),max_mean_error_sd=float(max(err[:26]/refsd[:26])),probability_errors=err[26:].tolist(),mean_fidelity_pass=bool(max(err[:26]/refsd[:26])<=.05 and max(err[26:])<=.02))
            np.savez_compressed(out/(case+'.npz'),q=q)
        result['seconds']=time.perf_counter()-start;b.close();(out/(case+'.json')).write_text(json.dumps(result,indent=2,allow_nan=False));print(json.dumps(dict(case=case,**result)),flush=True)
if __name__=='__main__':main()
