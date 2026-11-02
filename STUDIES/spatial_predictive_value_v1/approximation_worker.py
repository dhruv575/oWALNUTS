from common import *
import time
os.environ['XDG_CACHE_HOME']=str(BASE/'cache-approximation')
import arviz as az
from scipy.special import logsumexp
from scipy.stats import multivariate_t
def main():
    verify_freeze();out=BASE/'approximation_repair01';out.mkdir(exist_ok=False);start=time.perf_counter();target=Native(data())
    original=json.loads((BASE/'training/APPROXIMATION.json').read_text());best=min(original['starts'],key=lambda r:r['fun']);q=np.array(best['mode']);steps=[]
    def objective(x):
        try:v,g=target.value(x);return -v,-g
        except ValueError:return np.inf,np.zeros(205)
    def hessian(x):
        basis=np.eye(205)*1e-4;H=np.column_stack([(objective(x+e)[1]-objective(x-e)[1])/2e-4 for e in basis]);return (H+H.T)/2
    for iteration in range(20):
        value,g=objective(q);H=hessian(q);eigen=np.linalg.eigvalsh(H);steps.append(dict(iteration=iteration,value=value,gradient_max=float(max(abs(g))),minimum_eigenvalue=float(eigen.min())))
        if max(abs(g))<=1e-3 or eigen.min()<=0:break
        step=np.linalg.solve(H,g)
        for backtrack in range(20):
            candidate=q-step*2.**(-backtrack)
            if objective(candidate)[0]<=value+1e-10:q=candidate;break
        else:break
    value,g=objective(q);H=hessian(q);valid=bool(max(abs(g))<=1e-3 and np.linalg.eigvalsh(H).min()>0)
    result=dict(valid=valid,iterations=steps,gradient_max=float(max(abs(g))),seconds=time.perf_counter()-start)
    if not valid:write(out/'APPROXIMATION.json',result);target.close();return
    cov=np.linalg.inv(H);L=np.linalg.cholesky(cov);np.savez_compressed(out/'LAPLACE-FIT.npz',mode=q,cov=cov)
    rng=np.random.default_rng(955000010);draws=q+rng.normal(size=(8192,205))@L.T;np.savez_compressed(out/'LAPLACE-DRAWS.npz',q=draws)
    rows=[]
    for seed in [955000011,955000012]:
        rng=np.random.default_rng(seed);z=rng.normal(size=(8192,205));heavy=rng.random(8192)<.1;z[heavy]*=1.5/np.sqrt(rng.chisquare(8,size=heavy.sum())[:,None]/8)
        draws=q+z@L.T;normal=-.5*np.sum(z*z,1)-.5*205*np.log(2*np.pi)-np.log(np.diag(L)).sum();heavy_lp=multivariate_t(loc=q,shape=2.25*cov,df=8).logpdf(draws)
        proposal=np.logaddexp(np.log(.9)+normal,np.log(.1)+heavy_lp);lp=np.array([-objective(row)[0] for row in draws]);lw=lp-proposal;_,k=az.psislw(lw);w=np.exp(lw-logsumexp(lw));ess=float(1/(w@w))
        np.savez_compressed(out/f'IMPORTANCE-{seed}.npz',q=draws,logweights=lw);rows.append(dict(seed=seed,pareto_k=float(k),ess=ess,nonfinite_targets=int((~np.isfinite(lp)).sum()),passed=bool(k<.7 and ess>=1000)))
    result.update(importance=rows,correction_qualified=all(r['passed'] for r in rows),seconds=time.perf_counter()-start,target_calls=target.counts()[0]);write(out/'APPROXIMATION.json',result);target.close();verify_freeze();print(json.dumps(result),flush=True)
if __name__=='__main__':main()
