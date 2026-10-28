"""Nine fixed geometry cases; preserve NUTS and independently blocked slice."""
import concurrent.futures,json,multiprocessing,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie
from bounded_scale_slice import transition,physical


def fixture(j):
    cap=(.5,1.,2.)[j//3];case=j%3;n=12 if case==0 else 250
    y=np.zeros(n) if case==0 else .003*np.sin(.17*np.arange(n))+.001*np.cos(.61*np.arange(n))
    if case==1:y[[0,125]]=0.
    if case==2 and len(np.unique(y))!=n:raise ValueError('Distinct fixture requirement')
    return cap,y


def chain(args):
    j,c,out=args;cap,y=fixture(j);rng=np.random.default_rng(398135000+16*j+4+c)
    state=np.zeros(3+len(y));values=[];work=[];start=time.monotonic()
    for tick in range(5000):
        state,calls=transition(state,y,cap,rng);values.append(physical(state,cap));work.append(calls)
    a=np.asarray(values);p=Path(out)/f'slice-{c}.npz'
    if a.shape!=(5000,3+len(y)) or not np.isfinite(a).all():raise ValueError('Slice shape/finiteness')
    np.savez_compressed(p,warmup=a[:1000],draws=a[1000:],work=np.asarray(work))
    result=dict(chain=c,seed=398135000+16*j+4+c,elapsed_seconds=time.monotonic()-start,proposal_evaluations=int(sum(work)))
    (Path(out)/f'slice-{c}.json').write_text(json.dumps(result,indent=2)+'\n');return result


def run(j,out):
    out=Path(out);out.mkdir(exist_ok=False);start=time.monotonic();cap,y=fixture(j);n=len(y);base=398135000+16*j
    np.savez_compressed(out/'fixture.npz',y=y,cap=cap,rho=.95)
    model=nutpie.compile_stan_model(code=Path(__file__).with_name('bounded_scale_sv.stan').read_text(),cleanup=False).with_data(seed=base+1,n=n,y=y,cap=cap,rho=.95)
    compile_seconds=time.monotonic()-start;gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap));stamp=time.monotonic()
    cold=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=base,init_mean=np.r_[2*np.log(.005),eta,0.,np.zeros(n)],save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    nuts_seconds=time.monotonic()-stamp;cold.to_netcdf(out/'nuts.nc')
    right=az.summary(cold,var_names=['mu','log_sigma','beta','z'],round_to='none');right.to_csv(out/'nuts-coordinates.csv')
    nuts_diagnostics=dict(divergences=int(cold.sample_stats.diverging.sum()),max_depth_hits=int(cold.sample_stats.maxdepth_reached.sum()) if 'maxdepth_reached' in cold.sample_stats else None)
    cold.close();stamp=time.monotonic()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4,mp_context=multiprocessing.get_context('spawn')) as pool:chains=list(pool.map(chain,[(j,c,str(out)) for c in range(4)]))
    slice_seconds=time.monotonic()-stamp;arrays=[]
    for c in range(4):
        with np.load(out/f'slice-{c}.npz') as f:arrays.append(f['draws'])
    a=np.stack(arrays);left=az.summary(az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:])),round_to='none');left.to_csv(out/'slice-coordinates.csv')
    assert list(left.index)==list(right.index) and len(left)==3+n
    table=left.add_prefix('slice_').join(right.add_prefix('nuts_'));table['combined_z']=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean);table.to_csv(out/'comparison.csv')
    methods={}
    for name,summary in [('slice',left),('nuts',right)]:
        bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
        methods[name]=dict(failed_coordinates=summary.index[bad].tolist())
    methods['nuts'].update(nuts_diagnostics)
    r=dict(index=j,cap=cap,case=j%3,n=n,methods=methods,max_abs_mean_z=float(abs(table.combined_z).max()),flags_over_4=table.index[abs(table.combined_z)>4].tolist(),chains=chains,timing=dict(compile=compile_seconds,nuts_sample=nuts_seconds,slice_with_process_startup=slice_seconds,total=time.monotonic()-start),scope='Synthetic candidate geometry; failed diagnostics preclude reference qualification')
    (out/'REPORT.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r),flush=True)


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
