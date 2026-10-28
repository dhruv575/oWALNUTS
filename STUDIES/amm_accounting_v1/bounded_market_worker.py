"""Both fixed samplers per causal market cell; preserve independent failures."""
import hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import arviz as az
from bounded_market_common import cell,physical_draws,differences
from bounded_logspace_native import compile_target
from resource_monitor import execute

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'predictive_value_diagnostic_v1'))
import predictive_density

def serial(v):
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,np.generic):return v.item()
    raise TypeError(type(v).__name__)
def write(p,value):p.write_text(json.dumps(value,default=serial,indent=2,allow_nan=False)+'\n')
def failed(summary):
    bad=(~np.isfinite(summary[['r_hat','ess_bulk','ess_tail']]).all(axis=1))|(summary.r_hat>1.01)|(summary.ess_bulk<400)|(summary.ess_tail<400)
    return summary.index[bad].tolist()
def initial(cap,n):
    gap=np.log(cap/.2);eta=gap+np.log(-np.expm1(-gap))
    return np.r_[2*np.log(.005),eta,0.,np.zeros(n)]
def stack(group):return np.concatenate([group.mu.values[:,:,None],group.eta.values[:,:,None],group.b.values[:,:,None],group.z.values],axis=-1)

def nuts(y,cap,seed,out):
    import nutpie
    start=time.monotonic()
    model=nutpie.compile_stan_model(code=(HERE/'bounded_scale_rescaled.stan').read_text(),cleanup=False).with_data(seed=seed+1,n=len(y),y=y,cap=cap,rho=.95)
    setup=time.monotonic()-start;stamp=time.monotonic()
    data=nutpie.sample(model,chains=4,cores=4,tune=2000,draws=4000,seed=seed,init_mean=initial(cap,len(y)),save_warmup=True,progress_bar=False,target_accept=.9,maxdepth=10,low_rank_modified_mass_matrix=False,transform_adapt=False)
    sampling=time.monotonic()-stamp;stamp=time.monotonic();samples=stack(data.posterior);warmup=stack(data.warmup_posterior)
    extras={'stat_'+k:v.values for k,v in data.sample_stats.data_vars.items()}
    extras.update({'warmup_stat_'+k:v.values for k,v in data.warmup_sample_stats.data_vars.items()})
    np.savez_compressed(out/'draws.npz',draws=samples,warmup=warmup,**extras)
    report=dict(divergences=int(data.sample_stats.diverging.sum()),depth_hits=int(data.sample_stats.maxdepth_reached.sum()),warmup_divergences=int(data.warmup_sample_stats.diverging.sum()),setup_seconds=setup,sampling_seconds=sampling,serialization_seconds=time.monotonic()-stamp)
    data.close();return samples,report

def walnuts(y,cap,seed,out):
    import owalnuts
    start=time.monotonic();owner=compile_target(y,cap)
    tuning=owalnuts.Tuning(step_size=.5,max_depth=10,min_micro_steps=1,max_refinement_levels=8,max_error=1.,divergence_threshold=1000.,u_turn_rule='momentum_sum',exhaustion_rule='stop')
    adaptation=owalnuts.Adaptation(target_accept=.9,adapt_step_size=True,adapt_mass=True,metric_regularization='stan',trapped_chain_restart=True)
    setup=time.monotonic()-start;stamp=time.monotonic()
    result=owalnuts.sample(owner.target,owner.dimension,init=np.tile(initial(cap,len(y)),(4,1)),chains=4,warmup=2000,draws=4000,seed=seed+4,threads=4,tuning=tuning,adaptation=adaptation,admit_worst_case=True)
    sampling=time.monotonic()-stamp;stamp=time.monotonic();samples=result.samples
    assert result.divergent.shape==(4,6000) and result.depth.shape==(4,6000)
    np.savez_compressed(out/'draws.npz',draws=samples,divergent=result.divergent,depth=result.depth)
    write(out/'SAMPLER.json',dict(config=result.config,chains=result.chains,warnings=result.chain_warnings(),algorithm_revision=result.algorithm_revision,target_calls=result.target_calls,target_recoverable_failures=result.target_recoverable_failures,wall_seconds=result.wall_seconds))
    return samples,dict(divergences=int(result.divergent[:,2000:].sum()),depth_hits=int((result.depth[:,2000:]>=10).sum()),warmup_divergences=int(result.divergent[:,:2000].sum()),target_recoverable_failures=result.target_recoverable_failures,setup_seconds=setup,sampling_seconds=sampling,serialization_seconds=time.monotonic()-stamp)

def analyze(samples,cap,label,out,report):
    assert samples.shape==(4,4000,253) and np.isfinite(samples).all()
    stamp=time.monotonic();values,joint=physical_draws(samples,cap)
    summary=az.summary(az.from_dict(posterior=values),round_to='none');summary.to_csv(out/'coordinates.csv')
    np.savez_compressed(out/'joint.npz',draws=joint)
    report.update(status='sampled',failed_physical_coordinates=[v for v in failed(summary) if v!='b'],failed_b='b' in failed(summary),diagnostics_seconds=time.monotonic()-stamp)
    try:
        stamp=time.monotonic();pred=predictive_density.evaluate_observation(joint,label,deadline=time.monotonic()+60)
        density=pred['density_mcse']['scaled_density'];pit=pred['pit_by_chain_draw']
        np.savez_compressed(out/'predictive.npz',logpdf=pred['logpdf_by_chain_draw'],pit=pit,scaled_density=density)
        functional=az.summary(az.from_dict(posterior=dict(density=density,pit=pit)),round_to='none');functional.to_csv(out/'functionals.csv')
        report['prediction']=dict(status='ok',logpdf=pred['logpdf'],pit=pred['pit'],logpdf_mcse=float(functional.loc['density','mcse_mean']/density.mean()),pit_mcse=float(functional.loc['pit','mcse_mean']),failed_functionals=failed(functional),numerical=pred['numerical'],elapsed_seconds=time.monotonic()-stamp)
    except Exception as exc:
        (out/'PREDICTION-ERROR.txt').write_text(traceback.format_exc())
        report['prediction']=dict(status='failed',error=repr(exc))
    report['qualified']=bool(not report['failed_physical_coordinates'] and not report['failed_b'] and report['divergences']==0 and report['depth_hits']==0 and report['prediction']['status']=='ok' and not report['prediction']['failed_functionals'])
    return report

def load_fixture(index,fixtures):
    fixture_index,cap,seed=cell(index);fixtures=Path(fixtures)
    row=json.loads((fixtures/'FIXTURES.json').read_text())[fixture_index];assert row['index']==fixture_index
    p=fixtures/row['fixture'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    with np.load(p) as f:y=f['window'].copy();assert np.array_equal(y,f['history'][-250:])
    labels=json.loads((fixtures/'LABELS.json').read_text());assert labels[fixture_index]['index']==fixture_index
    return row,y,labels[fixture_index]['label'],cap,seed

def run_method(name,index,fixtures,out):
    row,y,label,cap,seed=load_fixture(index,fixtures);folder=Path(out)
    if (folder/'REPORT.json').exists():raise FileExistsError('Method already recorded')
    try:
        samples,report={'nuts':nuts,'walnuts':walnuts}[name](y,cap,seed,folder)
        report=analyze(samples,cap,label,folder,report)
    except Exception as exc:
        (folder/'ERROR.txt').write_text(traceback.format_exc());report=dict(status='failed',qualified=False,error=repr(exc))
    write(folder/'REPORT.json',report)

def run(index,fixtures,out):
    fixture_index,cap,seed=cell(index);fixtures=Path(fixtures);out=Path(out);out.mkdir(exist_ok=False)
    inventory=json.loads((fixtures/'FIXTURES.json').read_text());row=inventory[fixture_index];assert row['index']==fixture_index
    p=fixtures/row['fixture'];assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
    with np.load(p) as f:y=f['window'].copy();assert np.array_equal(y,f['history'][-250:])
    labels=json.loads((fixtures/'LABELS.json').read_text());assert labels[fixture_index]['index']==fixture_index
    label=labels[fixture_index]['label'];reports={};start=time.monotonic()
    for name,engine in [('nuts',nuts),('walnuts',walnuts)]:
        folder=out/name;folder.mkdir()
        receipt=execute([sys.executable,str(Path(__file__).resolve()),'--method',name,str(index),str(fixtures),str(folder)],str(HERE),400,folder,4*1024**3,96*1024**2,folder/'worker.log',ownership_env='OWALNUTS_BOUNDED_MARKET_METHOD',output_scan_interval=2,utilization_path=folder/'utilization.jsonl',phase_reserved_cores={'startup':4})
        write(folder/'SUPERVISION.json',receipt)
        if not receipt.get('group_drained'):raise RuntimeError('Method group failed to drain')
        if (folder/'REPORT.json').exists():report=json.loads((folder/'REPORT.json').read_text())
        else:report=dict(status='failed',qualified=False,error='Method did not produce a report',supervision=receipt)
        if receipt.get('exit_code')!=0:report.update(status='failed',qualified=False,supervision=receipt)
        reports[name]=report
    baseline=[r for r in json.loads((fixtures/'BASELINES.json').read_text()) if r['index']==fixture_index];assert len(baseline)==3
    comparisons=[]
    if all(r.get('prediction',{}).get('status')=='ok' for r in reports.values()):
        for b in baseline:
            comparisons.append(dict(baseline=b['method'],qualified=all(r['qualified'] for r in reports.values()),**differences(reports['nuts']['prediction']['logpdf'],reports['walnuts']['prediction']['logpdf'],b['score']['logpdf'])))
    result=dict(index=index,fixture=row,cap=cap,seed=seed,methods=reports,comparisons=comparisons,total_seconds=time.monotonic()-start,scope='Previously examined development origins; no holdout or profit claim')
    write(out/'REPORT.json',result);print(json.dumps(dict(index=index,qualified={k:v['qualified'] for k,v in reports.items()},statuses={k:v['status'] for k,v in reports.items()})),flush=True)

if __name__=='__main__':
    if sys.argv[1]=='--method':run_method(sys.argv[2],int(sys.argv[3]),sys.argv[4],sys.argv[5])
    else:run(int(sys.argv[1]),sys.argv[2],sys.argv[3])
