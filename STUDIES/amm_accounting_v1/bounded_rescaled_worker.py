import json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie

def run(j,out):
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic()
    cap=[.5,1.,2.][j];base=398136000+16*j;n=12
    model=nutpie.compile_stan_model(code=Path(__file__).with_name('bounded_scale_rescaled.stan').read_text(),cleanup=False).with_data(seed=base+1,n=n,y=np.zeros(n),cap=cap,rho=.95)
    compile_seconds=time.monotonic()-start;gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap));stamp=time.monotonic()
    data=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=base,init_mean=np.r_[2*np.log(.005),eta,0.,np.zeros(n)],save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    sample_seconds=time.monotonic()-stamp;data.to_netcdf(out/'nuts.nc')
    summary=az.summary(data,var_names=['mu','log_sigma','beta','z','b'],round_to='none');summary.to_csv(out/'coordinates.csv')
    bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
    failures=summary.index[bad].tolist()
    report=dict(index=j,cap=cap,n=n,seed=base,model_seed=base+1,failed_physical_coordinates=[s for s in failures if s!='b'],failed_b='b' in failures,divergences=int(data.sample_stats.diverging.sum()),depth_hits=int(data.sample_stats.maxdepth_reached.sum()),chain_median_mean_h=np.median(data.posterior.h.values.mean(axis=-1),axis=1).tolist(),chain_median_log_sigma=np.median(data.posterior.log_sigma.values,axis=1).tolist(),timing=dict(compile=compile_seconds,sampling=sample_seconds,total=time.monotonic()-start),scope='Exact coordinate-change exploration; no independently qualified reference')
    data.close();(out/'REPORT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)

if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
