"""Fixed native WALNUTS sampling panel; external monitor owns resource limits."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import owalnuts
from price_cell_fixtures import fixture
from price_cell_native import compile_target


def serial(value):
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    raise TypeError(type(value).__name__)


def run(index,out):
    n,width=[(12,.001),(12,.00001),(250,.001),(250,.00001)][index]
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic()
    data,latent=fixture(n,width)
    np.savez_compressed(out/'fixture.npz',latent=latent,lower=data['lower_cell'],upper=data['upper_cell'])
    owner=compile_target(data['lower_cell'],data['upper_cell'],data['initial'],data['rho'])
    import owalnuts._owalnuts as native
    runtime={str(Path(m.__file__).resolve()):hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (owalnuts,native)}
    (out/'RUNTIME.json').write_text(json.dumps(dict(files=runtime,python=sys.version,snapshot_sha256=owner.snapshot_sha256),indent=2)+'\n')
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    adaptation=owalnuts.Adaptation(target_accept=.9,adapt_step_size=True,adapt_mass=True,metric_regularization='stan',trapped_chain_restart=True)
    initial=np.tile(np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)],(4,1))
    result=owalnuts.sample(owner.target,owner.dimension,init=initial,chains=4,warmup=2000,draws=4000,seed=398129000+index,threads=4,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
    np.savez_compressed(out/'draws.npz',draws=result.samples)
    details=dict(config=result.config,chains=result.chains,warnings=result.chain_warnings(),algorithm_revision=result.algorithm_revision,target_calls=result.target_calls,target_recoverable_failures=result.target_recoverable_failures,wall_seconds=result.wall_seconds)
    (out/'SAMPLER.json').write_text(json.dumps(details,default=serial)+'\n')
    samples=result.samples
    if samples.shape!=(4,4000,3+2*n) or not np.isfinite(samples).all():raise ValueError('Draw shape/finiteness')
    trace=az.from_dict(posterior=dict(mu=samples[:,:,0],log_sigma=samples[:,:,1],beta=samples[:,:,2],z=samples[:,:,3:3+n],u=samples[:,:,3+n:]))
    summary=az.summary(trace,round_to='none');summary.to_csv(out/'coordinates.csv')
    if len(summary)!=3+2*n:raise ValueError('Coordinate omission')
    if result.divergent.shape!=(4,6000) or result.depth.shape!=(4,6000):raise ValueError('Diagnostic shape')
    divergent=int(result.divergent[:,2000:].sum())
    finite=bool(np.isfinite(summary[['r_hat','ess_bulk','ess_tail']].to_numpy()).all())
    passed=finite and bool((summary.r_hat<=1.01).all() and (summary.ess_bulk>=400).all() and (summary.ess_tail>=400).all()) and divergent==0
    report=dict(index=index,n=n,width=width,dimensions=3+2*n,diagnostic_pass=passed,divergences=divergent,warmup_divergences=int(result.divergent[:,:2000].sum()),max_depth_hits=int((result.depth[:,2000:]>=10).sum()),elapsed_seconds=time.monotonic()-start,target_calls=result.target_calls,scope='Synthetic WALNUTS sampling readiness; no market or economic claim')
    (out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
