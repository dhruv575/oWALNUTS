"""Bounded candidate: iid rejection reference versus four-chain NUTS."""
import json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie
from bounded_scale_rejection import draw


def run(j,out):
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic();cap=(.5,1.,2.)[j];base=398133000+3*j
    reference=draw(cap,0.,1000000,base);np.savez_compressed(out/'reference.npz',draws=reference)
    (out/'REFERENCE.json').write_text(json.dumps(dict(cap=cap,proposals=1000000,accepted=len(reference),seed=base,elapsed_seconds=time.monotonic()-start),indent=2)+'\n')
    if len(reference)<1000:raise ValueError('Insufficient iid reference; preserved without replacement')
    model=nutpie.compile_stan_model(code=Path(__file__).with_name('bounded_scale_sv.stan').read_text(),cleanup=False).with_data(seed=base+2,n=1,y=np.array([0.]),cap=cap,rho=.95)
    gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap))
    trace=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=base+1,init_mean=np.array([2*np.log(.005),eta,0.,0.]),save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    trace.to_netcdf(out/'trace.nc');summary=az.summary(trace,var_names=['mu','eta','beta','z'],round_to='none')
    if list(summary.index)!=['mu','eta','beta','z[0]']:raise ValueError('Coordinate contract')
    summary['reference_mean']=reference.mean(axis=0);summary['reference_mcse']=reference.std(axis=0,ddof=1)/np.sqrt(len(reference))
    summary['combined_z']=(summary['mean']-summary.reference_mean)/np.hypot(summary.mcse_mean,summary.reference_mcse)
    for probability in (.05,.5,.95):summary[f'reference_q{probability}']=np.quantile(reference,probability,axis=0)
    summary.to_csv(out/'coordinates.csv')
    bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
    result=dict(index=j,cap=cap,accepted=len(reference),failed_coordinates=summary.index[bad].tolist(),divergences=int(trace.sample_stats.diverging.sum()),max_depth_hits=int(trace.sample_stats.maxdepth_reached.sum()) if 'maxdepth_reached' in trace.sample_stats else None,max_abs_mean_z=float(abs(summary.combined_z).max()),flags_over_4=summary.index[abs(summary.combined_z)>4].tolist(),elapsed_seconds=time.monotonic()-start,scope='One-observation synthetic posterior comparison only')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True);trace.close()


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
