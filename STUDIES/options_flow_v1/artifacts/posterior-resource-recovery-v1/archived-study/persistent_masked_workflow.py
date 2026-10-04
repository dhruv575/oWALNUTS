"""Draft persistent A/B/A masked-flow comparison worker; no automatic launch.

Separate process per backend; changed posteriors always receive fresh adaptation.
"""
import time
STARTED=time.perf_counter()
import copy,json,sys
from pathlib import Path
import numpy as np
from dynamic_masked_target import snapshot,log_density,canonical
from flow_starts import canonical_starts,to_noncentered
from masked_forecast import summarize
from masked_flow_reference import screen
from pymc_continuation_workflow import run_session,bindings,verify_bindings,write_json
from continuation_comparison import sha


def dynamic_model(y,x,mask,rho,nu):
    import numpyro
    import numpyro.distributions as dist
    from numpyro.distributions import constraints
    q=numpyro.sample('q',dist.ImproperUniform(constraints.real,(),(4+2*y.shape[1]+y.shape[0],)))
    numpyro.factor('normalized_target',log_density(q,y,x,mask,rho,nu))


def execute(paths,out,seeds,backend,*,warmup=1000,tiers=(1000,2000,4000,8000),batch=1000):
    invocation_started=time.perf_counter()
    import jax
    jax.config.update('jax_enable_x64',True)
    import jax.numpy as jnp
    from jax.scipy.special import gammaln
    from masked_flow import log_density as independent
    from reference_continuation import adaptation_digest
    from hardware_control import get_affinity
    if backend not in ['numpyro','pymc'] or len(paths)!=3 or len(seeds)!=3 or len(set(seeds))!=3:raise ValueError('Exactly A/B/A with three distinct sampler streams required')
    if any(type(s)!=int or not 0<=s<2**32-130000 for s in seeds) or len(set(seeds+[s+130000 for s in seeds]))!=6:raise ValueError('Seed collisions')
    if warmup<1 or batch<4 or not tiers or any(v%batch for v in tiers) or any(a>=b for a,b in zip(tiers,tiers[1:])):raise ValueError('Invalid full continuation policy')
    fixtures=[json.loads(Path(p).read_text()) for p in paths];snapshots=[snapshot(f['data']) for f in fixtures]
    if snapshots[0][0].shape[1]!=4 or any(s[0].shape!=snapshots[0][0].shape for s in snapshots):raise ValueError('Same T-by4 shape required')
    from pymc_flow_continuation_workflow import validate_fixture
    families=[]
    for f in fixtures:
        _,names,cells=validate_fixture(f,'masked-flow')
        h=f['holdout'];ym=h.get('observation_mask',h.get('y_available'))
        if len(h['x'])!=1 or ym!=[[False]*4] or h['y']!=[[None]*4]:raise ValueError('Exactly one current four-group row without future labels required')
        if 'precision_family' in f and f['precision_family']!=[list(c) for c in cells]:raise ValueError('Fixture precision family differs from available current targets')
        families.append([list(c) for c in cells])
    if fixtures[0]!=fixtures[2] or fixtures[0]==fixtures[1] or snapshots[0][2].sum()==snapshots[1][2].sum():raise ValueError('Exact A return and different B observed count required')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    identity=bindings([*paths,sys.executable,*Path(__file__).parent.glob('*.py')])
    if backend=='pymc':
        import owalnuts
        identity.update(bindings([owalnuts.__file__,Path(owalnuts.__file__).parent/'_owalnuts.pyd']))
    plan=dict(backend=backend,fixtures=[str(Path(p).resolve()) for p in paths],bindings=identity,seeds=seeds,predictive_seeds=[s+130000 for s in seeds],warmup=warmup,tiers=list(tiers),batch=batch,chains=4,fixture_sha256=[sha(p) for p in paths],source_policy='Immutable fixture/source hashes verified before and after each fit',reference_target_accept=.9,cpu_affinity=get_affinity(),qualified=False,policy='Fresh full adaptation each immutable posterior; first passing full precision gate. Process/cache reuse only; CFunc compiles new immutable target each fit.')
    write_json(out/'plan.json',plan);reports=[];fit_costs=[]
    common=to_noncentered(canonical_starts(fixtures[0]['data'],4)[0],fixtures[0]['data'])
    vg=jax.jit(jax.value_and_grad(log_density));reference_values=[];engine=None
    if backend=='numpyro':
        from numpyro.infer import MCMC,NUTS
        engine=MCMC(NUTS(dynamic_model,target_accept_prob=.9,max_tree_depth=10),num_warmup=warmup,num_samples=batch,num_chains=4,chain_method='sequential',progress_bar=False,jit_model_args=True)
    for index,(fixture,host,seed) in enumerate(zip(fixtures,snapshots,seeds)):
        directory=out/f'fit-{index}';directory.mkdir();tick=time.perf_counter();report=dict(status='running',seed=seed,predictive_seed=seed+130000,fit_index=index,qualified=False,attempts=[],backend=backend,fixture=str(Path(paths[index]).resolve()),fixture_sha256=sha(paths[index]),bindings=identity,observed_count=int(host[2].sum()),forecast_cells=families[index],parameter_functionals=names,fresh_adaptation=True,posterior_continuation=False)
        write_json(directory/'report.json',report)
        try:
            verify_bindings(identity);data=fixture['data'];args=tuple(jnp.asarray(a) for a in host);starts=canonical_starts(data,4);initial=to_noncentered(starts,data)
            pt=time.perf_counter();value,gradient=vg(jnp.asarray(common),*args)
            ref,grad=jax.value_and_grad(lambda q:independent(q,data,jnp,gammaln,noncentered=True))(jnp.asarray(common))
            np.testing.assert_allclose(value,ref,rtol=1e-10,atol=1e-8);np.testing.assert_allclose(gradient,grad,rtol=1e-9,atol=1e-7)
            reference_values.append((float(value),np.asarray(gradient)))
            if index==2:
                np.testing.assert_array_equal(reference_values[0][0],reference_values[2][0]);np.testing.assert_array_equal(reference_values[0][1],reference_values[2][1])
            report.update(parity_seconds=time.perf_counter()-pt,common_q=common.tolist(),common_logp=float(value),common_gradient=np.asarray(gradient).tolist(),initial_positions=starts.tolist(),sampling_initial_positions=initial.tolist())
            cells=families[index]
            transport=lambda q:np.asarray(jax.vmap(jax.vmap(lambda z:canonical(z,*args)))(jnp.asarray(q)))
            if backend=='pymc':
                from pymc_flow_continuation_workflow import compile_target,parity
                pt=time.perf_counter();target,compilation=compile_target(data,'masked-flow',32);report['compilation']=compilation;report['compile_seconds']=time.perf_counter()-pt
                pt=time.perf_counter();report['native_parity']=parity(target,data,data,'masked-flow',[common,initial[0]]);report['native_parity_seconds']=time.perf_counter()-pt
                if report['native_parity'].get('passed') is not True:raise ValueError('Native normalized density/gradient parity failed before sampling')
                run_session(target,fixture,starts,directory,seed,warmup,tiers,'noncentered',report,evaluator=summarize,screen=lambda r,threshold:screen(r,4,cells),verify=lambda:verify_bindings(identity),transport=(lambda q:to_noncentered(q,data),transport),raw_filename='raw.json')
            else:
                engine.post_warmup_state=None
                report['warmup_admission']=dict(previous_posterior_state_cleared=True,initial_positions=initial.tolist(),seed=seed)
                pt=time.perf_counter();engine.warmup(jax.random.PRNGKey(seed),*args,init_params={'q':jnp.asarray(initial)},extra_fields=('diverging','num_steps'));jax.block_until_ready(engine.last_state.z)
                report['warmup_seconds']=time.perf_counter()-pt
                report['warmup_iterations']=np.asarray(engine.last_state.i).tolist()
                if not np.all(np.asarray(engine.last_state.i)==warmup):raise ValueError('Fresh adaptation iteration reset failed')
                frozen=adaptation_digest(engine.last_state);chunks=[];divergences=0;checkpoints=[]
                for n in tiers:
                    while len(chunks)*batch<n:
                        if chunks:engine.post_warmup_state=engine.last_state
                        before=engine.post_warmup_state;pt=time.perf_counter();engine.run(before.rng_key,*args,extra_fields=('diverging','num_steps'))
                        chunk=np.asarray(engine.get_samples(group_by_chain=True)['q'])
                        if chunk.shape!=(4,batch,len(common)) or not np.isfinite(chunk).all():raise ValueError('Invalid retained chunk')
                        chunks.append(chunk)
                        if adaptation_digest(engine.last_state)!=frozen or not np.all(np.asarray(engine.last_state.i)==np.asarray(before.i)+batch):raise ValueError('Retained state/adaptation changed')
                        divergences+=int(np.asarray(engine.get_extra_fields()['diverging']).sum());checkpoints.append(dict(draws=len(chunks)*batch,seconds=time.perf_counter()-pt,adaptation_sha256=frozen,start_iterations=np.asarray(before.i).tolist(),end_iterations=np.asarray(engine.last_state.i).tolist()))
                    pt=time.perf_counter();q=transport(np.concatenate(chunks,axis=1));conversion_seconds=time.perf_counter()-pt
                    pt=time.perf_counter();evaluation=summarize(q,fixture,seed+130000);evaluation_seconds=time.perf_counter()-pt
                    report.update(status='completed',evaluation=evaluation,healthy=evaluation['computational_screen_pass'] and divergences==0,retained_divergences=divergences,checkpoints=checkpoints)
                    gate=screen(report,4,cells);report['attempts'].append(dict(draws=n,screen=gate,conversion_seconds=conversion_seconds,evaluation_seconds=evaluation_seconds));report['precision_pass']=gate['pass'];write_json(directory/f'draws-{n}-report.json',report)
                    if gate['pass']:break
                write_json(directory/'raw.json',dict(canonical_draws=q,initial_positions=starts,sampling_initial_positions=initial))
            verify_bindings(identity)
        except Exception as exc:report.update(status='failed',precision_pass=False,error=f'{type(exc).__name__}: {exc}')
        report['fit_seconds_before_final_report_write']=time.perf_counter()-tick
        report['timing_scope']='Fit wall time includes parity, new-target compilation where applicable, fresh adaptation, retained chunks, diagnostics, predictions and raw/tier output; this field excludes this final report write. Cohort fit_costs adds its measured write cost.'
        pt=time.perf_counter();write_json(directory/'report.json',report);write_seconds=time.perf_counter()-pt
        fit_costs.append(dict(fit_index=index,status=report['status'],fit_seconds_including_final_report_write=time.perf_counter()-tick,final_report_write_seconds=write_seconds,report_sha256=sha(directory/'report.json')))
        reports.append(report)
    write_json(out/'cohort.json',dict(expected=3,reports=reports,fit_costs=fit_costs,execute_seconds_before_cohort_write=time.perf_counter()-invocation_started,module_elapsed_seconds_before_cohort_write=time.perf_counter()-STARTED,
        timing_scope='execute_seconds includes this invocation setup and all fit final writes; excludes final cohort serialization and imports before execute. Module elapsed may include caller idle time. External process wrapper is authoritative end-to-end cost.',qualified=False))
    return reports


