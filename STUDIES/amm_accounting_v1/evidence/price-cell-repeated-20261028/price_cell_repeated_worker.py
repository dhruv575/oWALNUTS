"""Three successive warm updates with independently seeded cold references."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie,owalnuts
from price_cell_fixtures import fixture
from price_cell_native import compile_target
from price_cell_remap import shift
from price_cell_warm_cold_worker import serial


def run(path,out):
    start=time.monotonic();out=Path(out);out.mkdir(exist_ok=False);root=Path(__file__).resolve().parent
    j=2+path//2;n=250;width=(.001,.00001)[path//2];base=398132000+100*path
    old=Path('/home/ubuntu/lanes/price-cell-walnuts-20261028/run01')/f'job-{j}'/'fit'
    manifest=json.loads((root/'STATIC-MANIFEST.json').read_text());bindings={}
    for name in ('draws.npz','SAMPLER.json','fixture.npz'):
        h=hashlib.sha256((old/name).read_bytes()).hexdigest();assert h==manifest[f'run01/job-{j}/fit/{name}']['sha256'];bindings[str(old/name)]=h
    (out/'INPUTS.json').write_text(json.dumps(bindings,indent=2)+'\n')
    data,_=fixture(n,width);lo=data['lower_cell'];hi=data['upper_cell']
    with np.load(old/'fixture.npz') as f:
        np.testing.assert_array_equal(f['lower'],lo);np.testing.assert_array_equal(f['upper'],hi)
    with np.load(old/'draws.npz') as f:q=f['draws'][:,-1,:].copy()
    saved=json.loads((old/'SAMPLER.json').read_text());mass=np.array([c['metadata']['mass_diagonal'] for c in saved['chains']]);steps=np.array([c['metadata']['final_step_size'] for c in saved['chains']])
    loading_seconds=time.monotonic()-start
    stamp=time.monotonic();compiled=nutpie.compile_stan_model(code=(root/'price_cell_sv.stan').read_text(),cleanup=False);stan_compile_seconds=time.monotonic()-stamp
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    session=None;owners=[];results=[]
    try:
        for update in range(3):
            folder=out/f'update-{update}';folder.mkdir();timing={};stamp=time.monotonic()
            t=n+update;value=.003*np.sin(.17*t)+.001*np.sin(.61*t);center=width*np.floor(value/width+.5)
            lower=np.r_[lo[1:],center-width/2];upper=np.r_[hi[1:],center+width/2]
            pos,m,s=shift(q,mass,steps,lo,hi,lower,upper)
            np.savez_compressed(folder/'fixture.npz',lower=lower,upper=upper,initial=0.,positions=pos,mass=m,steps=s)
            timing['remap_and_fixture_save']=time.monotonic()-stamp;stamp=time.monotonic()
            owner=compile_target(lower,upper,0.);owners.append(owner);timing['native_compile']=time.monotonic()-stamp;stamp=time.monotonic()
            state=owalnuts.WarmState(pos,s,m)
            if session is None:session=owalnuts.WarmSession(owner.target,state,seed=base,threads=4,tuning=tuning)
            else:session.retarget(owner.target,state)
            timing['session_create_or_retarget']=time.monotonic()-stamp;stamp=time.monotonic()
            chunk=session.refresh(1024);timing['warm_sampling']=time.monotonic()-stamp
            assert chunk.seed==base+4*update and chunk.call_index==update
            state=session.state();q=state.positions.copy();mass=state.mass_diagonal.copy();steps=state.step_sizes.copy();lo=lower;hi=upper
            stamp=time.monotonic();np.savez_compressed(folder/'warm-draws.npz',draws=chunk.samples)
            (folder/'WARM.json').write_text(json.dumps(dict(diagnostics=chunk.diagnostics,metadata=chunk.metadata,work=chunk.work,seed=chunk.seed,target_calls=chunk.target_calls),default=serial)+'\n');timing['warm_serialize']=time.monotonic()-stamp
            a=chunk.samples
            if a.shape!=(4,1024,503) or not np.isfinite(a).all():raise ValueError('Warm draw contract')
            stamp=time.monotonic();left=az.summary(az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:253],u=a[:,:,253:])),round_to='none');left.to_csv(folder/'warm-coordinates.csv');timing['warm_summary']=time.monotonic()-stamp
            stamp=time.monotonic();model=compiled.with_data(seed=base+41+2*update,n=n,lower_cell=lower,upper_cell=upper,initial=0.,rho=.95);timing['cold_bind']=time.monotonic()-stamp;stamp=time.monotonic()
            cold=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=base+40+2*update,init_mean=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(500)],save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
            timing['cold_adapt_and_sample']=time.monotonic()-stamp;stamp=time.monotonic();cold.to_netcdf(folder/'cold.nc');timing['cold_serialize']=time.monotonic()-stamp;stamp=time.monotonic()
            right=az.summary(cold,var_names=['mu','log_sigma','beta','z','u'],round_to='none');right.to_csv(folder/'cold-coordinates.csv');timing['cold_summary']=time.monotonic()-stamp
            assert list(left.index)==list(right.index) and len(left)==503
            table=left.add_prefix('warm_').join(right.add_prefix('cold_'));table['combined_z']=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean);table.to_csv(folder/'comparison.csv');methods={}
            for name,summary in [('warm',left),('cold',right)]:
                bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
                methods[name]=dict(failed_coordinates=summary.index[bad].tolist())
            methods['warm'].update(divergences=sum(int(np.asarray(c['divergent']).sum()) for c in chunk.diagnostics),max_depth_hits=sum(int((np.asarray(c['depth'])>=10).sum()) for c in chunk.diagnostics))
            methods['cold'].update(divergences=int(cold.sample_stats.diverging.sum()),max_depth_hits=int(cold.sample_stats['maxdepth_reached'].sum()) if 'maxdepth_reached' in cold.sample_stats else None)
            result=dict(path=path,update=update,width=width,methods=methods,timing=timing,max_abs_mean_z=float(abs(table.combined_z).max()),flags_over_4=table.index[abs(table.combined_z)>4].tolist())
            (folder/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');results.append(result);print(json.dumps(result),flush=True);cold.close()
    finally:
        if session is not None:session.close()
    (out/'REPORT.json').write_text(json.dumps(dict(path=path,loading_seconds=loading_seconds,stan_compile_seconds=stan_compile_seconds,total_seconds=time.monotonic()-start,updates=results),indent=2)+'\n')


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
