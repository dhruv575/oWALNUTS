"""One actual mixed target fit plus measured disk-backed extraction; no import-time work."""
import argparse,json,sys,time,hashlib,gc
from pathlib import Path
PROCESS_STARTED=time.perf_counter();CPU_STARTED=time.process_time()


def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def save(path,value):
    from run import clean
    with Path(path).open('x') as f:json.dump(clean(value),f,indent=2,allow_nan=False)


def verify(plan):
    if any(sha(p)!=v for p,v in plan['bindings'].items()):raise ValueError('Bound source/runtime drift')


def validate_report(report,cell,fixture,plan,raw):
    from continuation_comparison import norm,validate_raw_starts
    from flow_mixed_coordinates import to_mixed
    import numpy as np
    public=cell['backend']=='public'
    if report.get('status')!='completed' or report.get('draws')!=8000 or report.get('parity',{}).get('passed') is not True:raise ValueError('Incomplete full8k/parity record')
    if report.get('seed')!=cell['seed'] or report.get('predictive_seed')!=cell['seed']+130000:raise ValueError('Worker seed differs')
    settings=report['settings']
    if settings['warmup']!=1000 or settings['chains']!=4 or (report['precision_plan']['tiers'] if public else settings['tiers'])!=[8000]:raise ValueError('Fixed-retained policy differs')
    if [a['draws'] for a in report['attempts']]!=[8000]:raise ValueError('Unexpected early-stop/restart path')
    expected_arm='python-pymc-flow-mixed_slopes-continuation' if public else 'numpyro-mixed-slopes-continuation'
    if report.get('model')!='flow' or report.get('coordinates')!='mixed_slopes' or report.get('arm')!=expected_arm:raise ValueError('Wrong worker recipe')
    if public:
        if report['model']!='flow' or settings['block_size']!=32 or settings['threads']!=1:raise ValueError('Wrong public target')
        if report['session_progress_before_close']['completed_transitions']!=[9000]*4:raise ValueError('Public continuation transition mismatch')
        if report['total_target_calls']!=report['session_progress_before_close']['target_calls'] or report['total_target_calls']!=report['warmup_target_calls']+sum(a['added_target_calls'] for a in report['attempts']):raise ValueError('Public callback work mismatch')
    elif report['implementation']!='associative' or settings['target_accept']!=.9 or settings['batch']!=1000:raise ValueError('Wrong strongest reference recipe')
    if report['initial_positions']!=fixture['data']['initial_positions'] or report['hardware_control']['realized_cpus']!=[0]:raise ValueError('Physical starts/affinity differ')
    if report['precision_plan']['names']!=plan['full_gate']['functional_names'] or report['precision_plan']['forecast_rows']!=4 or report['precision_plan']['threshold']!=.02:raise ValueError('Worker precision family differs')
    if not public:
        cps=report['checkpoints']
        if [c['draws_per_chain'] for c in cps]!=list(range(1000,8001,1000)) or len({c['adaptation_sha256'] for c in cps})!=1:raise ValueError('Reference retained adaptation drift')
        for i,c in enumerate(cps):
            if c['start_iterations']!=[1000+i*1000]*4 or c['end_iterations']!=[2000+i*1000]*4:raise ValueError('Reference retained iterations differ')
    actual=norm(report['bindings']);expected=norm(plan['worker_bindings'])
    if public:
        bound=norm(plan['bindings'])
        for name in ['__init__.py','_owalnuts.pyd']:
            key=str((Path(plan['pythonpath'])/'owalnuts'/name).resolve()).casefold()
            expected[key]=bound[key]
    expected[str(Path(cell['fixture']).resolve()).casefold()]=cell['fixture_sha256']
    if any(actual.get(p)!=v for p,v in expected.items()):raise ValueError('Actual worker source/fixture binding mismatch')
    if set(report['evaluation']['canonical_parameter_diagnostics'])!={f'q_{i}' for i in range(1012)} or set(report['evaluation']['functionals'])!=set(plan['full_gate']['functional_names']) or len(report['evaluation']['forecast']['rows'])!=4:raise ValueError('Full diagnostic scope differs')
    validate_raw_starts(raw,fixture['data']['initial_positions'])
    from masked_market_comparison_execute import tail_field
    if public and tail_field(raw,'adapted_metadata')!=report['adapted_metadata']:raise ValueError('Public frozen adaptation differs')
    np.testing.assert_array_equal(np.asarray(tail_field(raw,'sampling_initial_positions')),to_mixed(np.asarray(fixture['data']['initial_positions']),fixture['data']))


def run(plan_path,cell_id):
    plan=json.loads(Path(plan_path).read_text());cell=next(c for c in plan['cells'] if c['id']==cell_id)
    sys.path.insert(0,plan['study']);from reference_bank_allocation import memory_limit,peak_memory
    from hardware_control import get_affinity
    out=Path(cell['out']);out.mkdir(parents=True,exist_ok=False);tick=PROCESS_STARTED;cpu=CPU_STARTED
    result=dict(status='failed',qualified=False,cell_id=cell_id,backend=cell['backend'],posterior_sha256=plan['posterior_sha256'])
    guard=None;phase='admission';phase_tick=time.perf_counter()
    try:
        # Install the fixed cap before admission helpers can import numerical modules.
        if plan.get('memory_bytes')!=8*1024**3:raise ValueError('Unexpected memory policy')
        guard=memory_limit(plan['memory_bytes'])
        from .controller import verify_frozen
        original_plan_sha=sha(plan_path);validated=verify_frozen(plan_path,original_plan_sha)
        if validated!=plan or cell not in validated['cells']:raise ValueError('Worker cell/plan identity differs')
        import numpy as np
        verify(plan)
        if get_affinity()!=[0]:raise ValueError('RequiredCPU0affinity not realized')
        fixture=json.loads(Path(cell['fixture']).read_text())
        if sha(cell['fixture'])!=cell['fixture_sha256']:raise ValueError('Fixture drift')
        fit=out/'fit';fit_tick=time.perf_counter();phase='sampler';phase_tick=fit_tick
        if cell['backend']=='public':
            from pymc_flow_continuation_workflow import main
            sys.argv=['resource-worker','--fixture',cell['fixture'],'--out',str(fit),'--seed',str(cell['seed']),'--warmup','1000','--chains','4','--tiers','8000','--model','flow','--coordinates','mixed_slopes','--block-size','32','--expected-cpus','0']
            code=main();rp=fit/'python-pymc-flow-report.json';raw=fit/'draws-8000'/'python-pymc-flow-raw.json'
        else:
            from mixed_flow_reference import execute
            report=execute(cell['fixture'],fit,cell['seed'],warmup=1000,chains=4,tiers=(8000,),batch=1000,target_accept=.9,implementation='associative')
            code=0 if report.get('precision_pass') else 2;rp=fit/'report.json';raw=fit/'draws-8000-raw.json'
        result.update(sampler_seconds=time.perf_counter()-fit_tick,sampler_returncode=code,worker_report_sha256=sha(rp))
        phase='adapter';phase_tick=time.perf_counter();report=json.loads(rp.read_text());validate_report(report,cell,fixture,plan,raw);verify(plan)
        # Drop any Python worker return object; JSON is never decoded for raw draws.
        gc.collect();from .stream_extract import extract
        phase='extraction';phase_tick=time.perf_counter()
        extraction=extract(raw,out/'extracted',chains=4,draws=8000,dimension=1012,rho=fixture['data']['rho'],x_next=fixture['holdout']['x'][0][0])
        flags=extraction.pop('divergence_arrays');result['extraction']=extraction
        extraction['canonical_sha256']=sha(out/'extracted'/'canonical.npy');extraction['compact_sha256']=sha(out/'extracted'/'compact.npz')
        q=np.load(out/'extracted'/'canonical.npy',mmap_mode='r');compact=np.load(out/'extracted'/'compact.npz')
        from evaluate import summarize
        from pymc_flow_continuation_workflow import strict_screen
        from predictive_cdf import PredictiveMixture
        names=['beta_bar','tau','mu_h','sigma_h','h_terminal','h_mean']+[p+str(g) for g in range(4) for p in ['alpha_','beta_']]
        result['checkpoints']=[]
        for n in [4000,8000]:
            phase=f'diagnostics-{n}';phase_tick=time.perf_counter();ct=phase_tick;evaluation=summarize(q[:,:n],fixture,cell['seed']+130000)
            if cell['backend']=='public':
                if len(flags)!=4 or any(len(v)!=8000 for v in flags):raise ValueError('Public raw divergence shape differs')
                divergences=sum(sum(v[:n]) for v in flags)
            else:
                matches=[c for c in report['checkpoints'] if c['draws_per_chain']==n]
                if len(matches)!=1:raise ValueError('Reference prefix telemetry missing')
                divergences=matches[0]['retained_divergences_total']
            fit_report=dict(status='completed',draws=n,evaluation=evaluation,retained_divergences=divergences,healthy=evaluation['computational_screen_pass'] and divergences==0)
            ds=[*evaluation['functionals'].values(),*evaluation['canonical_parameter_diagnostics'].values()]
            finite_healthy=all(np.isfinite([d['rhat'],d['bulk_ess'],d['tail_ess']]).all() and 0<d['rhat']<=1.01 and min(d['bulk_ess'],d['tail_ess'])>=400 for d in ds)
            fit_report['healthy']=bool(finite_healthy and divergences==0)
            screen=strict_screen(fit_report,.02,names,4)
            save(out/f'checkpoint-{n}.json',dict(fit_report,screen=screen));diagnostic_seconds=time.perf_counter()-ct
            phase=f'predictive-cdf-{n}';phase_tick=time.perf_counter();pt=phase_tick;count=4*n
            mix=PredictiveMixture('flow',compact['cdf_location'][:,:n].reshape(-1),compact['cdf_future_mean'][:,:n].reshape(-1),compact['cdf_future_sd'][:,:n].reshape(-1),np.zeros(count),np.full(count,1/count),fixture['data']['nu'],2048,dict(group=0,x_next=fixture['holdout']['x'][0][0],horizon=1))
            quantiles=mix.quantiles();save(out/f'predictive-cdf-{n}.json',quantiles)
            result['checkpoints'].append(dict(draws=n,full_gate_pass=screen['pass'],diagnostic_seconds=diagnostic_seconds,predictive_cdf_seconds=time.perf_counter()-pt,predictive_cdf=quantiles,checkpoint_sha256=sha(out/f'checkpoint-{n}.json'),predictive_cdf_sha256=sha(out/f'predictive-cdf-{n}.json')))
        result.update(status='resource_completed',accuracy_qualified=False,reference_bank_resolved=False,resource_only=True)
        verify(plan);verify_frozen(plan_path,original_plan_sha)
    except Exception as exc:result.update(error=f'{type(exc).__name__}: {exc}')
    finally:
        result['last_phase']=phase;result['last_phase_elapsed_seconds']=time.perf_counter()-phase_tick
        if phase=='sampler' and 'sampler_seconds' not in result:result['sampler_seconds']=result['last_phase_elapsed_seconds']
        result.update(process_cpu_seconds_before_final_report=time.process_time()-cpu,worker_seconds_before_final_report=time.perf_counter()-tick,resources=peak_memory(),memory_cap_bytes=plan['memory_bytes'],resource_scope='Current worker process peak memory and CPU; excludes compiler-child aggregate CPU/memory. External contained elapsed includes child work and final output.')
        save(out/'resource-result.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--cell',required=True);a=p.parse_args();r=run(a.plan,a.cell);raise SystemExit(0 if r['status']=='resource_completed' else 2)
