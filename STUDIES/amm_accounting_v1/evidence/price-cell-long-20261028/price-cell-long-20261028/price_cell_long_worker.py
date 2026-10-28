"""One fixed long-window stress fit; external monitor owns resources."""
import json,sys,time,hashlib
from pathlib import Path
import numpy as np
import arviz as az
import nutpie
from price_cell_fixtures import fixture


def run(index,out):
    n,width=[(12,.001),(12,.00001),(250,.001),(250,.00001)][index]
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic()
    data,latent=fixture(n,width)
    np.savez_compressed(out/'fixture.npz',latent=latent,lower=data['lower_cell'],upper=data['upper_cell'])
    source=Path(__file__).with_name('price_cell_sv.stan')
    model=nutpie.compile_stan_model(code=source.read_text(),cleanup=False).with_data(seed=398124001+2*index,**data)
    trace=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=398124000+2*index,
        init_mean=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)],save_warmup=True,
        progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    trace.to_netcdf(out/'trace.nc')
    summary=az.summary(trace,var_names=['mu','log_sigma','beta','z','u'],round_to='none')
    assert len(summary)==3+2*n
    summary.to_csv(out/'coordinates.csv')
    divergent=int(trace.sample_stats['diverging'].sum())
    finite=np.isfinite(summary[['r_hat','ess_bulk','ess_tail']].to_numpy()).all()
    passed=finite and bool((summary.r_hat<=1.01).all() and (summary.ess_bulk>=400).all() and (summary.ess_tail>=400).all()) and divergent==0
    stats=list(trace.sample_stats.data_vars)
    depth_name=next((x for x in ['tree_depth','depth'] if x in stats),None)
    result=dict(index=index,n=n,width=width,dimensions=3+2*n,divergences=divergent,diagnostic_pass=bool(passed),sample_stats=stats,max_depth_hits=None if depth_name is None else int((trace.sample_stats[depth_name]>=10).sum()),elapsed_seconds=time.monotonic()-start,stan_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),scope='Synthetic geometry readiness only; no independent long-window fidelity claim')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n')
    trace.close();print(json.dumps(result),flush=True)


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
