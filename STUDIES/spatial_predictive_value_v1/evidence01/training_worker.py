from common import *
import time,itertools
os.environ['XDG_CACHE_HOME']=str(BASE/'cache-training')
import arviz as az
from scipy.optimize import minimize
from scipy.linalg import solve_triangular
from scipy.special import logsumexp
from scipy.stats import multivariate_t
def stats(v):
    ds=az.convert_to_dataset({'p':v})
    st={k:np.asarray(fn(ds).p) for k,fn in [('rhat',lambda d:az.rhat(d,method='rank')),('bulk',lambda d:az.ess(d,method='bulk')),('tail',lambda d:az.ess(d,method='tail')),('mcse',lambda d:az.mcse(d,method='mean'))]}
    st.update(mean=v.mean((0,1)),sd=v.reshape(-1,405).std(0,ddof=1));return st
def reference(out):
    model=GridGP(data());groups=[];arrays=[];records=[]
    for root in GP_PATHS+WAL_PATHS:
        d=json.loads((root/'SUMMARY.json').read_text());st={k:np.array(v) for k,v in d['stats'].items()}
        if root in GP_PATHS:
            v=physical(np.load(root/'DRAWS.npz')['q'],model);fresh=stats(v)
            assert all(np.allclose(st[k],fresh[k],rtol=1e-10,atol=1e-10) for k in fresh)
            arrays.append(v[:,::2].copy());del v
        else:arrays.append(np.load(root/'FUNCTIONALS.npz')['values'])
        passed=all(np.isfinite(v).all() for v in st.values()) and max(st['rhat'])<=1.01 and min(st['bulk'])>=1000 and min(st['tail'])>=1000 and d['divergences']==0
        groups.append(st);records.append(dict(source=str(root),passed=bool(passed),min_bulk=float(min(st['bulk'])),min_tail=float(min(st['tail'])),max_rhat=float(max(st['rhat']))))
    pairs=[]
    for i,j in itertools.combinations(range(4),2):
        a,b=groups[i],groups[j];delta=abs(a['mean']-b['mean']);sd=(a['sd']+b['sd'])/2
        row=dict(a=i,b=j,max_z=float(max(delta/np.sqrt(a['mcse']**2+b['mcse']**2))),max_mean_sd=float(max(delta/sd)),max_relative_sd=float(max(abs(a['sd']-b['sd'])/sd)))
        row['passed']=row['max_z']<=4 and row['max_mean_sd']<=.05 and row['max_relative_sd']<=.1;pairs.append(row)
    combined=stats(np.concatenate(arrays));checks=dict(groups=all(r['passed'] for r in records),pairs=all(r['passed'] for r in pairs),finite=all(np.isfinite(v).all() for v in combined.values()),rhat=max(combined['rhat'])<=1.01,bulk=min(combined['bulk'])>=4000,tail=min(combined['tail'])>=2000,mcse=max(combined['mcse']/combined['sd'])<=.02)
    result=dict(passed=bool(all(checks.values())),checks={k:bool(v) for k,v in checks.items()},groups=records,pairs=pairs,combined={k:v.tolist() for k,v in combined.items()},scope='New mixed-engine training reference; historical failed reference unchanged')
    write(out/'REFERENCE.json',result);return result
def approximation(out):
    start=time.perf_counter();target=Native(data());terrain=json.loads((BASE/'inputs/TERRAIN.json').read_text());starts=[]
    def objective(q):
        try:v,g=target.value(q);return -v,-g
        except ValueError:return np.inf,np.zeros(205)
    for alpha in [-1.,0.,1.]:
        q=np.zeros(205);q[1]=alpha;q[2:5]=np.array(terrain['mode'])/np.array(data()['coef_scale'])
        fit=minimize(objective,q,jac=True,method='L-BFGS-B',options={'maxiter':2000,'ftol':1e-12,'gtol':1e-6,'maxls':50})
        starts.append(dict(alpha_start=alpha,success=bool(fit.success),message=str(fit.message),fun=float(fit.fun),gradient_max=float(max(abs(fit.jac))),iterations=int(fit.nit),mode=fit.x.tolist()))
    chosen=min(starts,key=lambda r:r['fun']);mode=np.array(chosen['mode']);basis=np.eye(205)*1e-4
    H=np.column_stack([(objective(mode+e)[1]-objective(mode-e)[1])/2e-4 for e in basis]);H=(H+H.T)/2;ev=np.linalg.eigvalsh(H)
    valid=np.isfinite(H).all() and ev.min()>0 and chosen['gradient_max']<=1e-3
    result=dict(valid=bool(valid),starts=starts,min_hessian_eigenvalue=float(ev.min()),seconds=time.perf_counter()-start)
    if not valid:write(out/'APPROXIMATION.json',result);target.close();return result
    cov=np.linalg.inv(H);L=np.linalg.cholesky(cov);np.savez_compressed(out/'LAPLACE-FIT.npz',mode=mode,cov=cov)
    rng=np.random.default_rng(955000010);q=mode+rng.normal(size=(8192,205))@L.T;np.savez_compressed(out/'LAPLACE-DRAWS.npz',q=q)
    results=[]
    for seed in [955000011,955000012]:
        rng=np.random.default_rng(seed);z=rng.normal(size=(8192,205));heavy=rng.random(8192)<.1;z[heavy]*=1.5/np.sqrt(rng.chisquare(8,size=heavy.sum())[:,None]/8)
        q=mode+z@L.T;normal=-.5*np.sum(z*z,1)-.5*205*np.log(2*np.pi)-np.log(np.diag(L)).sum()
        heavy_lp=multivariate_t(loc=mode,shape=2.25*cov,df=8).logpdf(q)
        proposal=np.logaddexp(np.log(.9)+normal,np.log(.1)+heavy_lp)
        lp=np.array([-objective(row)[0] for row in q]);lw=lp-proposal;_,k=az.psislw(lw);w=np.exp(lw-logsumexp(lw));ess=float(1/(w@w))
        np.savez_compressed(out/f'IMPORTANCE-{seed}.npz',q=q,logweights=lw)
        results.append(dict(seed=seed,pareto_k=float(k),ess=ess,nonfinite_targets=int((~np.isfinite(lp)).sum()),passed=bool(k<.7 and ess>=1000)))
    result.update(importance=results,correction_qualified=all(r['passed'] for r in results),seconds=time.perf_counter()-start,target_calls=target.counts()[0]);write(out/'APPROXIMATION.json',result);target.close();return result
if __name__=='__main__':
    verify_freeze();out=BASE/'training';out.mkdir(exist_ok=False);start=time.perf_counter()
    ref=reference(out);approx=approximation(out);verify_freeze()
    write(out/'SUMMARY.json',dict(reference_passed=ref['passed'],approximation_valid=approx['valid'],seconds=time.perf_counter()-start));print(json.dumps(dict(reference=ref['passed'],approximation=approx['valid'])),flush=True)
