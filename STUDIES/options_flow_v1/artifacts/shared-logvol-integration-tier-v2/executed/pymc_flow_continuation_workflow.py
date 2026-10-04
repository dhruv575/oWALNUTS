"""Public CFunc flow continuation, with explicit dense/masked model contracts."""
import time
STARTED=time.perf_counter()
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback
import numpy as np
from pymc_continuation_workflow import bindings,verify_bindings,write_json,run_session


def validate_fixture(fixture,model):
    data=fixture['data']
    if model=='flow':
        if 'observation_mask' in data:raise ValueError('Dense flow cannot silently ignore an observation mask')
        from model import validate
        y,x=validate(data);transport_data=data
    elif model=='masked-flow':
        from masked_flow import validate
        y,x,mask=validate(data)
        transport_data=dict(data,y=np.where(mask,y,0.).tolist(),x=np.where(mask,x,0.).tolist())
    else:raise ValueError('Unknown flow model')
    future=fixture.get('holdout')
    if not isinstance(future,dict):raise ValueError('Explicit forecast holdout is required')
    fy=np.asarray(future.get('y'),dtype=float);fx=np.asarray(future.get('x'),dtype=float)
    if fy.ndim!=2 or fy.shape!=fx.shape or fy.shape[0]<1 or fy.shape[1]!=y.shape[1]:
        raise ValueError('Holdout requires matching nonempty H-by-G y and x')
    if model=='flow':
        if any(key in future for key in ['observation_mask','y_available','x_available']):raise ValueError('Dense flow cannot silently ignore future availability masks')
        if not np.isfinite(fy).all() or not np.isfinite(fx).all():raise ValueError('Dense holdout must be finite')
        forecast_family=fy.size
    else:
        xm=np.asarray(future.get('x_available'))
        ym=np.asarray(future.get('y_available',future.get('observation_mask')))
        if 'y_available' in future and 'observation_mask' in future and not np.array_equal(future['y_available'],future['observation_mask']):raise ValueError('Conflicting future outcome masks')
        if xm.shape!=fx.shape or ym.shape!=fy.shape or xm.dtype!=np.bool_ or ym.dtype!=np.bool_:raise ValueError('Masked forecast requires explicit matching boolean x/y availability')
        if not np.isfinite(fx[xm]).all() or not np.isfinite(fy[ym]).all():raise ValueError('Available future values must be finite')
        grid=np.asarray(future.get('grid_index'));h=len(fy);t=len(y)
        if grid.shape!=(h,) or not np.issubdtype(grid.dtype,np.integer) or not (np.array_equal(grid,np.arange(h)) or np.array_equal(grid,np.arange(t,t+h))):raise ValueError('Future grid must preserve every regular latent step')
        forecast_family=[(int(i)+1,int(j)) for i,j in zip(*np.nonzero(xm))]
        if not forecast_family:raise ValueError('At least one declared available-covariate forecast cell is required')
    names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']
    for group in range(y.shape[1]):names.extend([f'alpha_{group}',f'beta_{group}'])
    return transport_data,names,forecast_family


def strict_screen(report,threshold,names,forecast_rows):
    from precision_tiers import precision_screen
    evaluation=report.get('evaluation',{})
    if set(evaluation.get('functionals',{}))!=set(names):
        raise ValueError('Physical functional set differs from the declared complete flow gate')
    if isinstance(forecast_rows,list):
        from masked_forecast import precision_forecast_screen
        # Parameter health/precision and exact frozen available-x forecast family
        # remain separate; missing labels never remove precision requirements.
        parameter_report=dict(report,evaluation={k:v for k,v in evaluation.items() if k!='forecast'})
        parameters=precision_screen(parameter_report,threshold,names=names,require_forecast=False)
        forecast=precision_forecast_screen(evaluation.get('forecast',{}),forecast_rows,threshold)
        ratios={**parameters['ratios'],**{f'forecast_{k}':v for k,v in forecast['ratios'].items()}}
        return dict(**{'pass':parameters['pass'] and forecast['pass']},reasons=parameters['reasons']+forecast['reasons'],
            ratios=ratios,max_endpoint_mcse_over_width=max(ratios.values(),default=None),threshold=threshold,
            parameter_functionals=names,forecast_rows=len(forecast_rows),forecast_expected_cells=forecast_rows,
            parameter_screen=parameters,forecast_screen=forecast,qualified=False)
    if len(evaluation.get('forecast',{}).get('rows',[]))!=forecast_rows:
        raise ValueError('Observed forecast row count differs from the declared gate')
    return precision_screen(report,threshold,names=names,require_forecast=True)


def validate_likelihood_variant(model,block_size,coordinates,variant):
    if variant not in ('pymc_student_t','shared_logvol_student_t_v1'):raise ValueError('Unknown likelihood variant')
    if variant!='pymc_student_t' and (model!='flow' or coordinates!='mixed_slopes' or block_size!=32):raise ValueError('Candidate likelihood requires dense flow, mixed slopes and block32')

def compile_target(data,model,block_size,coordinates='noncentered',likelihood_variant='pymc_student_t'):
    validate_likelihood_variant(model,block_size,coordinates,likelihood_variant)
    if coordinates=='mixed_slopes':
        if model!='flow':raise ValueError('Mixed slopes currently support dense flow only')
        import owalnuts
        from flow_mixed_coordinates import build_model
        tick=time.perf_counter();target,dimension,initial,names,_=owalnuts.from_pymc(build_model(data,block_size,likelihood_variant=likelihood_variant),gil_free=True)
        if names!=['q'] or dimension!=4+2*len(data['y'][0])+len(data['y']):raise ValueError('Unexpected mixed flow layout')
        metadata=dict(compile_seconds=time.perf_counter()-tick,dimension=dimension,names=names,initial=initial.tolist(),block_size=block_size,coordinates=coordinates)
        if likelihood_variant!='pymc_student_t':metadata['likelihood_variant']=likelihood_variant
        return target,metadata
    if coordinates!='noncentered':raise ValueError('Unknown flow coordinates')
    if model=='flow':
        from pymc_flow_workflow import compile_target as compile_dense
        return compile_dense(data,block_size)
    if model!='masked-flow':raise ValueError('Unknown flow model')
    from masked_flow import validate
    from masked_flow_pymc import compile_target as compile_masked
    y,_,mask=validate(data);tick=time.perf_counter()
    target,dimension,initial,names,_=compile_masked(data,block_size)
    if dimension!=4+2*y.shape[1]+y.shape[0] or names!=['q']:raise ValueError('Unexpected masked flow layout')
    return target,dict(compile_seconds=time.perf_counter()-tick,dimension=dimension,names=names,
        initial=initial.tolist(),block_size=block_size,observed_count=int(mask.sum()),
        data_policy='Observed-only likelihood; regular latent grid; finite placeholders used only for coordinate transport',
        missingness_assumption='Conditional on observation pattern; selection mechanism not modeled')


def parity(target,data,transport_data,model,points,coordinates='noncentered'):
    if coordinates=='mixed_slopes':
        if model!='flow':raise ValueError('Mixed slopes currently support dense flow only')
        from flow_mixed_coordinates import normalized_parity
        return normalized_parity(data,points,target)
    if coordinates!='noncentered':raise ValueError('Unknown flow coordinates')
    if model=='flow':
        from pymc_flow_workflow import parity as dense_parity
        return dense_parity(target,data,points)
    from masked_flow import log_density
    from pymc_flow_workflow import to_canonical
    from pymc_workflow import evaluate_cfunc
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    vg=jax.jit(jax.value_and_grad(lambda u:log_density(u,data,jnp,gammaln,noncentered=True)))
    rows=[]
    for u in points:
        value,gradient=evaluate_cfunc(target,u);reference,reference_gradient=vg(jnp.asarray(u))
        centered=log_density(to_canonical(u,transport_data),data)+len(data['y'])*u[3]-.5*np.log1p(-data['rho']**2)
        np.testing.assert_allclose(value,reference,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(value,centered,rtol=1e-10,atol=1e-8)
        np.testing.assert_allclose(gradient,reference_gradient,rtol=1e-9,atol=1e-8)
        if not np.isfinite(value) or not np.isfinite(gradient).all():raise ValueError('Nonfinite parity point')
        rows.append(dict(value_error=abs(value-float(reference)),gradient_max_error=float(np.max(np.abs(gradient-np.asarray(reference_gradient)))),
                         point_sha256=hashlib.sha256(np.asarray(u,dtype=np.float64).tobytes()).hexdigest()))
    return dict(passed=True,cases=rows,independent_normalized_centered_check=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--fixture',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--warmup',type=int,default=1000)
    p.add_argument('--chains',type=int,default=4);p.add_argument('--tiers',type=int,nargs='+',default=[1000,2000,4000,8000])
    p.add_argument('--model',choices=['flow','masked-flow'],default='flow');p.add_argument('--block-size',type=int,choices=[0,16,32],default=32)
    p.add_argument('--coordinates',choices=['noncentered','mixed_slopes'],default='noncentered')
    p.add_argument('--likelihood-variant',choices=['pymc_student_t','shared_logvol_student_t_v1'],default='pymc_student_t')
    p.add_argument('--expected-cpus');a=p.parse_args()
    try:validate_likelihood_variant(a.model,a.block_size,a.coordinates,a.likelihood_variant)
    except ValueError as exc:p.error(str(exc))
    if a.chains<4 or a.warmup<1 or not a.tiers or any(v<4 for v in a.tiers) or any(b<=v for v,b in zip(a.tiers,a.tiers[1:])):
        p.error('At least four chains, positive warmup and strictly increasing tiers >=4 required')
    if a.coordinates=='mixed_slopes' and a.model!='flow':p.error('Mixed slopes currently support dense flow only')
    import owalnuts
    import owalnuts._owalnuts as extension
    from flow_starts import canonical_starts,to_noncentered
    from pymc_flow_workflow import to_canonical
    if a.model=='masked-flow':from masked_forecast import summarize
    else:from evaluate import summarize
    from hardware_control import get_affinity,parse_cpus
    a.out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    identity=bindings([a.fixture,Path(sys.executable),Path(owalnuts.__file__),Path(extension.__file__),
        root/'Cargo.toml',root/'Cargo.lock',*root.joinpath('src').rglob('*.rs'),
        root/'integrations/python/Cargo.toml',root/'integrations/python/Cargo.lock',
        *root.joinpath('integrations/python/src').rglob('*.rs'),*Path(__file__).parent.glob('*.py')])
    report=dict(status='running',qualified=False,phase='exploratory',model=a.model,
        arm='python-pymc-'+a.model+'-'+a.coordinates+'-continuation',coordinates=a.coordinates,seed=a.seed,bindings=identity,
        settings=dict(chains=a.chains,warmup=a.warmup,threads=1,block_size=a.block_size),
        predictive_seed=a.seed+130000,software=dict(python=sys.version,numpy=np.__version__,algorithm_revision=owalnuts.ALGORITHM_REVISION))
    if a.likelihood_variant!='pymc_student_t':
        report['likelihood_variant']=a.likelihood_variant;report['settings']['likelihood_variant']=a.likelihood_variant
        report['arm']+='-'+a.likelihood_variant
    write_json(a.out/'started.json',report)
    def emit(stage,event,draws):
        with (a.out/'phase-events.jsonl').open('a') as f:
            f.write(json.dumps(dict(stage=stage,event=event,draws=draws,seconds=time.perf_counter()-STARTED,cpu_seconds=time.process_time()))+'\n')
    try:
        realized=list(get_affinity());report['hardware_control']=dict(realized_cpus=realized,expected_cpus=a.expected_cpus)
        if a.expected_cpus is not None and sorted(realized)!=sorted(parse_cpus(a.expected_cpus)):raise ValueError('Inherited CPU affinity mismatch')
        fixture=json.loads(a.fixture.read_text());data=fixture['data']
        transport_data,names,forecast_rows=validate_fixture(fixture,a.model)
        report['precision_plan']=dict(tiers=a.tiers,threshold=.02,names=names,
            forecast_rows=len(forecast_rows) if isinstance(forecast_rows,list) else forecast_rows,
            forecast_expected_cells=forecast_rows if isinstance(forecast_rows,list) else None,
            forecast_scope='Fixed-origin scenario conditional on supplied future covariates; labels score only; not an operational future-flow claim',
            policy='One adaptation; exact retained prefix; all canonical health; every physical functional and observed forecast')
        if a.coordinates=='mixed_slopes':
            from flow_mixed_coordinates import to_mixed as forward,to_canonical as backward
        else:forward,backward=to_noncentered,to_canonical
        starts=canonical_starts(transport_data,a.chains);sampling_starts=forward(starts,transport_data)
        np.testing.assert_allclose(backward(sampling_starts,transport_data),starts,rtol=1e-12,atol=1e-12)
        emit('compile','start',None);target,metadata=compile_target(data,a.model,a.block_size,a.coordinates,a.likelihood_variant)
        report['compilation']=metadata;emit('compile','end',None)
        emit('parity','start',None);tick=time.perf_counter()
        report['parity']=parity(target,data,transport_data,a.model,[sampling_starts[0],sampling_starts[-1],
            sampling_starts[0]+np.random.default_rng(818).normal(0,.01,starts.shape[1])],a.coordinates)
        if report['parity'].get('passed') is not True:raise RuntimeError('Independent runtime parity failed')
        report['parity_seconds']=time.perf_counter()-tick;emit('parity','end',None)
        run_session(target,fixture,starts,a.out,a.seed,a.warmup,a.tiers,a.coordinates,report,
            evaluator=lambda q,f,seed:summarize(q,f,predictive_seed=seed),
            screen=lambda r,t:strict_screen(r,t,names,forecast_rows),
            transport=(lambda q:forward(q,transport_data),lambda q:backward(q,transport_data)),
            raw_filename='python-pymc-flow-raw.json',verify=lambda:verify_bindings(identity),emit=emit,
            checkpoint=lambda r:write_json(a.out/'python-pymc-flow-report.json',r))
    except Exception as exc:
        report.update(status='failed',precision_pass=False,error=str(exc),traceback=traceback.format_exc())
    report['end_to_end_seconds']=time.perf_counter()-STARTED;emit('worker','terminal',None)
    write_json(a.out/'python-pymc-flow-report.json',report)
    write_json(a.out/'invocation-timing.json',dict(seconds_including_imports_and_report=time.perf_counter()-STARTED))
    return int(report['status']!='completed' or not report.get('precision_pass',False))


if __name__=='__main__':raise SystemExit(main())
