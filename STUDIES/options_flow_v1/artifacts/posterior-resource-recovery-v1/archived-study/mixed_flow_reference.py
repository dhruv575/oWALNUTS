"""Optional dense mixed-slope NumPyro continuation; mandatory normalized parity."""
import time
STARTED=time.perf_counter()
import argparse
import json
from pathlib import Path
import sys
import traceback
import numpy as np
from pymc_continuation_workflow import bindings,verify_bindings,write_json


def execute(fixture_path,out,seed,warmup=1000,chains=4,tiers=(1000,2000,4000,8000),batch=1000,target_accept=.9,implementation='sequential'):
    import jax
    jax.config.update('jax_enable_x64',True)
    from reference_continuation import ContinuedReference
    from flow_starts import canonical_starts
    from flow_mixed_coordinates import to_mixed,to_canonical,jax_log_density,normalized_parity
    from pymc_flow_continuation_workflow import validate_fixture,strict_screen
    from evaluate import summarize
    out=Path(out);out.mkdir(parents=True,exist_ok=False);fixture_path=Path(fixture_path).resolve()
    identity=bindings([fixture_path,Path(sys.executable),*Path(__file__).parent.glob('*.py')])
    report=dict(status='running',qualified=False,model='flow',coordinates='mixed_slopes',
        arm='numpyro-mixed-slopes-continuation',implementation=implementation,seed=seed,predictive_seed=seed+130000,bindings=identity,
        settings=dict(implementation=implementation,warmup=warmup,chains=chains,tiers=list(tiers),batch=batch,target_accept=target_accept),attempts=[])
    write_json(out/'started.json',report);engine=None
    def emit(stage,event,draws=None):
        with (out/'phase-events.jsonl').open('a') as handle:
            handle.write(json.dumps(dict(stage=stage,event=event,draws=draws,seconds=time.perf_counter()-STARTED,cpu_seconds=time.process_time()))+'\n')
    try:
        if implementation not in ['sequential','associative']:raise ValueError('Unknown mixed reference implementation')
        if implementation=='associative':
            from flow_mixed_associative import jax_log_density,normalized_parity
        if isinstance(seed,bool) or not isinstance(seed,int) or not 0<=seed<2**32-130000:raise ValueError('Invalid chain/predictive seed')
        if chains<4 or warmup<1 or batch<4 or not tiers or any(v<4 or v%batch for v in tiers) or any(b<=a for a,b in zip(tiers,tiers[1:])):raise ValueError('Invalid counts/tiers')
        fixture=json.loads(fixture_path.read_text());data=fixture['data'];_,names,cells=validate_fixture(fixture,'flow')
        starts=canonical_starts(data,chains);sampling_starts=to_mixed(starts,data)
        np.testing.assert_allclose(to_canonical(sampling_starts,data),starts,rtol=1e-12,atol=1e-12)
        report.update(initial_positions=starts.tolist(),sampling_initial_positions=sampling_starts.tolist(),
            precision_plan=dict(names=names,forecast_rows=cells,threshold=.02,tiers=list(tiers)))
        from hardware_control import get_affinity
        report['hardware_control']=dict(realized_cpus=list(get_affinity()))
        emit('parity','start');tick=time.perf_counter()
        report['parity']=normalized_parity(data,[sampling_starts[0],sampling_starts[-1],sampling_starts[0]+np.random.default_rng(818).normal(0,.01,starts.shape[1])])
        if report['parity'].get('passed') is not True:raise ValueError('Normalized parity did not pass')
        report['parity_seconds']=time.perf_counter()-tick;emit('parity','end');verify_bindings(identity)
        engine=ContinuedReference(lambda u:-jax_log_density(u,data),sampling_starts,seed,warmup,batch,target_accept)
        emit('adapt','start');tick=time.perf_counter()
        try:engine.adapt()
        finally:report['adapt_seconds']=time.perf_counter()-tick
        emit('adapt','end');write_json(out/'report.json',report)
        for retained in tiers:
            attempt=dict(draws=retained,status='running');report['attempts'].append(attempt);tick=time.perf_counter()
            write_json(out/'report.json',report)
            try:
                verify_bindings(identity);emit('batch','start',retained);sampling_tick=time.perf_counter()
                try:
                    while len(engine.chunks)*batch<retained:engine.append()
                finally:attempt['sampling_seconds']=time.perf_counter()-sampling_tick
                emit('batch','end',retained);emit('evaluation','start',retained)
                q=to_canonical(engine.samples,data);evaluation=summarize(q,fixture,predictive_seed=seed+130000)
                fit=dict(status='completed',draws=retained,evaluation=evaluation,retained_divergences=engine.divergences,
                    healthy=evaluation['computational_screen_pass'] and engine.divergences==0,checkpoints=engine.checkpoints.copy())
                gate=strict_screen(fit,.02,names,cells);emit('evaluation','end',retained)
                verify_bindings(identity);emit('serialization','start',retained)
                write_json(out/f'draws-{retained}-report.json',fit)
                write_json(out/f'draws-{retained}-raw.json',dict(canonical_draws=q,sampling_initial_positions=sampling_starts,initial_positions=starts))
                attempt.update(status='completed',screen=gate);report.update(fit,status='running',precision_pass=gate['pass'])
                emit('serialization','end',retained)
            except Exception as exc:
                attempt.update(status='failed',error=str(exc));raise
            finally:
                attempt['seconds_including_evaluation_and_serialization']=time.perf_counter()-tick
                write_json(out/'report.json',report)
            if gate['pass']:break
        verify_bindings(identity);report['status']='completed'
    except Exception as exc:
        report.update(status='failed',precision_pass=False,error=str(exc),traceback=traceback.format_exc())
    if engine is not None:report['checkpoints']=engine.checkpoints
    report['end_to_end_seconds']=time.perf_counter()-STARTED
    report['total_sampling_seconds']=report.get('adapt_seconds',0)+sum(v.get('sampling_seconds',0) for v in report['attempts'])
    emit('worker','terminal');write_json(out/'report.json',report)
    write_json(out/'invocation-timing.json',dict(seconds_including_imports_and_report=time.perf_counter()-STARTED))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--seed',type=int,required=True)
    parser.add_argument('--warmup',type=int,default=1000);parser.add_argument('--chains',type=int,default=4)
    parser.add_argument('--tiers',type=int,nargs='+',default=[1000,2000,4000,8000]);parser.add_argument('--batch',type=int,default=1000);parser.add_argument('--target-accept',type=float,default=.9)
    parser.add_argument('--implementation',choices=['sequential','associative'],default='sequential')
    args=parser.parse_args();result=execute(args.fixture,args.out,args.seed,args.warmup,args.chains,args.tiers,args.batch,args.target_accept,args.implementation)
    raise SystemExit(0 if result.get('precision_pass') else 2)

