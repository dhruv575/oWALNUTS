"""Fixed nine-case WALNUTS comparison in admitted exact rescaled coordinates."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import owalnuts
from bounded_rescaled_native import compile_target

def serial(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    raise TypeError(type(value).__name__)

def run(index,out):
    if index not in range(9):raise ValueError('Fixed fit index')
    cap=[.5,1.,2.][index//3];case=index%3;n=12 if case==0 else 250
    y=np.zeros(n) if case==0 else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n))
    if case==1:y[[0,125]]=0.
    if case==2 and len(np.unique(y))!=n:raise ValueError('Distinct fixture')
    out=Path(out);out.mkdir(exist_ok=False);started=time.monotonic()
    np.savez_compressed(out/'fixture.npz',y=y,cap=cap,rho=.95)
    owner=compile_target(y,cap)
    import owalnuts._owalnuts as native
    runtime={str(Path(m.__file__).resolve()):hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (owalnuts,native)}
    (out/'RUNTIME.json').write_text(json.dumps(dict(files=runtime,python=sys.version,snapshot_sha256=owner.snapshot_sha256),indent=2)+'\n')
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    adaptation=owalnuts.Adaptation(target_accept=.9,adapt_step_size=True,adapt_mass=True,metric_regularization='stan',trapped_chain_restart=True)
    gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap))
    initial=np.tile(np.r_[2*np.log(.005),eta,0.,np.zeros(n)],(4,1));setup=time.monotonic()-started;stamp=time.monotonic()
    result=owalnuts.sample(owner.target,owner.dimension,init=initial,chains=4,warmup=2000,draws=4000,seed=398139000+16*index,threads=4,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
    sample_seconds=time.monotonic()-stamp;s=result.samples
    if s.shape!=(4,4000,3+n) or not np.isfinite(s).all():raise ValueError('Draw shape/finiteness')
    if result.divergent.shape!=(4,6000) or result.depth.shape!=(4,6000):raise ValueError('Diagnostic phase shape')
    np.savez_compressed(out/'draws.npz',draws=s,divergent=result.divergent,depth=result.depth)
    details=dict(config=result.config,chains=result.chains,warnings=result.chain_warnings(),algorithm_revision=result.algorithm_revision,target_calls=result.target_calls,target_recoverable_failures=result.target_recoverable_failures,wall_seconds=result.wall_seconds)
    (out/'SAMPLER.json').write_text(json.dumps(details,default=serial)+'\n')
    l=np.log(cap)-np.logaddexp(0.,s[:,:,1]);weights=np.ones(n)/n
    for i in range(n-1,0,-1):weights[i-1]+=.95*weights[i]
    weights[0]/=np.sqrt(1-.95**2)
    hbar=s[:,:,0]+np.exp(l)*(s[:,:,3:]@weights);beta=np.exp(hbar/2)*s[:,:,2]
    trace=az.from_dict(posterior=dict(mu=s[:,:,0],log_sigma=l,beta=beta,z=s[:,:,3:],b=s[:,:,2]))
    summary=az.summary(trace,round_to='none');summary.to_csv(out/'coordinates.csv')
    bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
    failures=summary.index[bad].tolist()
    r=dict(index=index,cap=cap,case=case,n=n,failed_physical_coordinates=[x for x in failures if x!='b'],failed_b='b' in failures,divergences=int(result.divergent[:,2000:].sum()),warmup_divergences=int(result.divergent[:,:2000].sum()),max_depth_hits=int((result.depth[:,2000:]>=10).sum()),timing=dict(setup=setup,sampling=sample_seconds,total=time.monotonic()-started),target_calls=result.target_calls,scope='Synthetic fixed WALNUTS panel; all failures retained; no predictive or economic claim')
    (out/'REPORT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)

if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
