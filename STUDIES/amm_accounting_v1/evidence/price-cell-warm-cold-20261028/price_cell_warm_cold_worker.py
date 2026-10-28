"""Fixed shifted synthetic target: warm WALNUTS and fresh NUTS."""
import hashlib,json,sys,time
from pathlib import Path
import numpy as np
import arviz as az
import nutpie,owalnuts
from price_cell_fixtures import fixture
from price_cell_native import compile_target
from price_cell_remap import shift


def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    raise TypeError(type(v).__name__)


def run(j,out):
    out=Path(out);out.mkdir(exist_ok=False);root=Path(__file__).resolve().parent
    n,width=[(12,.001),(12,.00001),(250,.001),(250,.00001)][j];base=398131000+16*j
    old=Path('/home/ubuntu/lanes/price-cell-walnuts-20261028/run01')/f'job-{j}'/'fit'
    manifest=json.loads((root/'STATIC-MANIFEST.json').read_text());bindings={}
    for name in ('draws.npz','SAMPLER.json','fixture.npz'):
        h=hashlib.sha256((old/name).read_bytes()).hexdigest()
        assert h==manifest[f'run01/job-{j}/fit/{name}']['sha256'];bindings[str(old/name)]=h
    (out/'INPUTS.json').write_text(json.dumps(bindings,indent=2)+'\n')
    data,_=fixture(n,width);lo=data['lower_cell'];hi=data['upper_cell']
    with np.load(old/'fixture.npz') as f:
        np.testing.assert_array_equal(f['lower'],lo);np.testing.assert_array_equal(f['upper'],hi)
    with np.load(old/'draws.npz') as f:q=f['draws'][:,-1,:].copy()
    saved=json.loads((old/'SAMPLER.json').read_text())
    mass=np.array([c['metadata']['mass_diagonal'] for c in saved['chains']]);steps=np.array([c['metadata']['final_step_size'] for c in saved['chains']])
    value=.003*np.sin(.17*n)+.001*np.sin(.61*n);center=width*np.floor(value/width+.5)
    lower=np.r_[lo[1:],center-width/2];upper=np.r_[hi[1:],center+width/2]
    pos,m,s=shift(q,mass,steps,lo,hi,lower,upper)
    np.savez_compressed(out/'fixture.npz',lower=lower,upper=upper,initial=0.,positions=pos,mass=m,steps=s)
    owner=compile_target(lower,upper,0.)
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    started=time.monotonic()
    with owalnuts.WarmSession(owner.target,owalnuts.WarmState(pos,s,m),seed=base,threads=4,tuning=tuning) as session:chunk=session.refresh(4000)
    warm_seconds=time.monotonic()-started
    np.savez_compressed(out/'warm-draws.npz',draws=chunk.samples)
    (out/'WARM.json').write_text(json.dumps(dict(diagnostics=chunk.diagnostics,metadata=chunk.metadata,work=chunk.work,seed=chunk.seed,target_calls=chunk.target_calls,wall_seconds=warm_seconds),default=serial)+'\n')
    a=chunk.samples
    if a.shape!=(4,4000,3+2*n) or not np.isfinite(a).all():raise ValueError('Warm draw contract')
    warm=az.from_dict(posterior=dict(mu=a[:,:,0],log_sigma=a[:,:,1],beta=a[:,:,2],z=a[:,:,3:3+n],u=a[:,:,3+n:]))
    left=az.summary(warm,round_to='none');left.to_csv(out/'warm-coordinates.csv')
    started=time.monotonic()
    model=nutpie.compile_stan_model(code=(root/'price_cell_sv.stan').read_text(),cleanup=False).with_data(seed=base+9,n=n,lower_cell=lower,upper_cell=upper,initial=0.,rho=.95)
    cold=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=base+8,init_mean=np.r_[2*np.log(.005),np.log(.2),0.,np.zeros(2*n)],save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    cold.to_netcdf(out/'cold.nc');cold_seconds=time.monotonic()-started
    right=az.summary(cold,var_names=['mu','log_sigma','beta','z','u'],round_to='none');right.to_csv(out/'cold-coordinates.csv')
    assert list(left.index)==list(right.index) and len(left)==3+2*n
    table=left.add_prefix('warm_').join(right.add_prefix('cold_'));table['combined_z']=(left['mean']-right['mean'])/np.hypot(left.mcse_mean,right.mcse_mean)
    table.to_csv(out/'comparison.csv');rows={}
    for name,summary in [('warm',left),('cold',right)]:
        bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
        rows[name]=dict(failed_coordinates=summary.index[bad].tolist())
    rows['warm'].update(divergences=sum(int(np.asarray(c['divergent']).sum()) for c in chunk.diagnostics),max_depth_hits=sum(int((np.asarray(c['depth'])>=10).sum()) for c in chunk.diagnostics),seconds=warm_seconds)
    rows['cold'].update(divergences=int(cold.sample_stats.diverging.sum()),max_depth_hits=int(cold.sample_stats['maxdepth_reached'].sum()) if 'maxdepth_reached' in cold.sample_stats else None,seconds=cold_seconds)
    result=dict(index=j,n=n,width=width,methods=rows,max_abs_mean_z=float(abs(table.combined_z).max()),flags_over_4=table.index[abs(table.combined_z)>4].tolist(),scope='Single shifted synthetic window, no market or predictive/economic claim')
    (out/'REPORT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));cold.close()


if __name__=='__main__':run(int(sys.argv[1]),sys.argv[2])
