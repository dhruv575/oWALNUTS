"""Exploratory local-model precision worker using the public CFunc session.

One adaptation, incremental retained draws, and completed-request telemetry.
The session retains bounded full history; this is not a streaming-memory API.
"""
import time
STARTED = time.perf_counter()
import argparse
import hashlib
import json
from pathlib import Path
import traceback
import numpy as np


def bindings(paths):
    return {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}


def verify_bindings(expected):
    if bindings(expected) != expected:
        raise RuntimeError('Source, extension or fixture changed during invocation')


def plain(value):
    if isinstance(value, np.ndarray):
        # Numeric tolist() already creates native scalar values in C. Avoid
        # recursively revisiting millions of finite posterior coordinates.
        native = value.tolist()
        if value.dtype.kind in 'biu': return native
        if value.dtype.kind == 'f' and np.isfinite(value).all(): return native
        return plain(native)
    if isinstance(value, np.generic): return plain(value.item())
    if isinstance(value, dict): return {str(k): plain(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)): return [plain(v) for v in value]
    if isinstance(value, float) and not np.isfinite(value): return None
    return value


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(plain(value), indent=2, allow_nan=False))
    temporary.replace(path)


def run_session(target, fixture, starts, out, seed, warmup, tiers, coordinates,
                report, session_factory=None, evaluator=None, screen=None, verify=lambda: None,
                emit=lambda *args: None, checkpoint=lambda report: None, transport=None,
                raw_filename='python-pymc-raw.json'):
    """Persist each attempted tier, including failures; injectable seams test transport."""
    import owalnuts
    from pymc_workflow import coordinate_transport
    from run_local_level import evaluate
    from precision_tiers import precision_screen
    factory = session_factory or owalnuts.start_session
    evaluator = evaluator or evaluate
    screen = screen or precision_screen
    if not tiers or any(n < 4 for n in tiers) or any(b <= a for a, b in zip(tiers, tiers[1:])):
        raise ValueError('Strictly increasing retained tiers >=4 required')
    to_sampling, to_canonical = transport or coordinate_transport(fixture['data'], coordinates)
    sampling_starts = to_sampling(starts)
    report.update(status='running', attempts=[], coordinates=coordinates, initial_positions=starts.tolist(),
                  sampling_initial_positions=sampling_starts.tolist())
    session = None
    chunks = []
    diagnostics = []
    previous = 0
    calls = 0
    try:
        verify(); emit('admission', 'start', None)
        tick = time.perf_counter()
        try:
            session = factory(target, init=sampling_starts, chains=len(starts), warmup=warmup,
                              max_draws=tiers[-1], seed=seed, threads=1)
        finally:
            report['admission_seconds'] = time.perf_counter() - tick
        emit('admission', 'end', None)
        emit('adapt', 'start', None); tick = time.perf_counter(); cpu = time.process_time()
        try:
            adapted = session.adapt()
        finally:
            report.update(adapt_seconds=time.perf_counter()-tick, adapt_cpu_seconds=time.process_time()-cpu)
        report.update(warmup_diagnostics=adapted.diagnostics, warmup_work=adapted.cumulative_work,
                      initialization_target_calls=adapted.initialization_target_calls,
                      warmup_target_calls=adapted.target_calls)
        calls += adapted.target_calls
        frozen = json.dumps(plain(adapted.metadata), sort_keys=True)
        report['adapted_metadata'] = adapted.metadata
        emit('adapt', 'end', None); verify()
        checkpoint(report)
        for tier in tiers:
            attempt = dict(draws=tier, added_draws=tier-previous, status='running')
            report['attempts'].append(attempt)
            fit_dir = Path(out)/f'draws-{tier}'; fit_dir.mkdir()
            write_json(fit_dir/'attempt.json', attempt)
            checkpoint(report)
            tick = time.perf_counter(); cpu = time.process_time()
            try:
                verify(); emit('batch', 'start', tier)
                try:
                    chunk = session.draw(tier-previous)
                finally:
                    attempt.update(sampling_seconds=time.perf_counter()-tick, sampling_cpu_seconds=time.process_time()-cpu)
                emit('batch', 'end', tier)
                if (chunk.retained_start, chunk.retained_end) != (previous, tier):
                    raise RuntimeError('Noncontiguous retained draw prefix')
                if json.dumps(plain(chunk.metadata), sort_keys=True) != frozen:
                    raise RuntimeError('Adapted metric or tuning changed during retained sampling')
                calls += chunk.target_calls
                if calls != chunk.cumulative_target_calls:
                    raise RuntimeError('Callback accounting does not reconcile')
                chunks.append(np.asarray(chunk.samples)); diagnostics.append(chunk.diagnostics)
                q = to_canonical(np.concatenate(chunks, axis=1))
                if q.shape != (len(starts), tier, starts.shape[1]) or not np.isfinite(q).all():
                    raise RuntimeError('Invalid canonical draw transport')
                divergences = sum(int(np.count_nonzero(c['divergent'])) for d in diagnostics for c in d)
                emit('evaluation', 'start', tier); evaluation_start = time.perf_counter()
                evaluation = evaluator(q, fixture, seed+130000)
                fit = dict(status='completed', draws=tier, evaluation=evaluation,
                           evaluation_seconds=time.perf_counter()-evaluation_start,
                           retained_divergences=divergences,
                           healthy=evaluation['computational_screen_pass'] and divergences == 0,
                           target_calls=chunk.cumulative_target_calls,
                           cumulative_work=chunk.cumulative_work)
                emit('evaluation', 'end', tier)
                result = screen(fit, .02)
                verify(); emit('serialization', 'start', tier)
                write_json(fit_dir/raw_filename, dict(canonical_draws=q, coordinates=coordinates,
                           retained_chunk_diagnostics=diagnostics, cumulative_work=chunk.cumulative_work,
                           adapted_metadata=chunk.metadata,sampling_initial_positions=sampling_starts,
                           initial_positions=starts))
                write_json(fit_dir/'fit-report.json', fit)
                attempt.update(status='completed', screen=result, added_target_calls=chunk.target_calls,
                               cumulative_target_calls=chunk.cumulative_target_calls)
                report.update(fit, status='running', precision_pass=result['pass'])
                emit('serialization', 'end', tier)
                previous = tier
            except Exception as exc:
                attempt.update(status='failed', error=str(exc))
                raise
            finally:
                attempt['seconds_including_evaluation_and_serialization'] = time.perf_counter()-tick
                attempt['cpu_seconds_including_evaluation_and_serialization'] = time.process_time()-cpu
                write_json(fit_dir/'attempt.json', attempt)
                checkpoint(report)
            if result['pass']: break
        verify()
        report.update(status='completed', total_target_calls=calls)
    except Exception as exc:
        report.update(status='failed', precision_pass=False, error=str(exc), traceback=traceback.format_exc())
    finally:
        if session is not None:
            cleanup_errors=[]
            try:
                report['session_progress_before_close'] = session.progress()
                report['total_target_calls'] = report['session_progress_before_close']['target_calls']
            except Exception as exc:
                cleanup_errors.append('progress before close: '+str(exc))
            try: session.close()
            except Exception as exc: cleanup_errors.append('close: '+str(exc))
            try: report['session_progress_after_close'] = session.progress()
            except Exception as exc: cleanup_errors.append('progress after close: '+str(exc))
            if cleanup_errors:
                report.update(status='failed', precision_pass=False, cleanup_errors=cleanup_errors)
        report['total_sampling_seconds'] = report.get('adapt_seconds',0)+sum(a.get('sampling_seconds',0) for a in report['attempts'])
        checkpoint(report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path, required=True); parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--seed', type=int, required=True); parser.add_argument('--warmup', type=int, default=1000)
    parser.add_argument('--chains', type=int, default=4); parser.add_argument('--tiers', type=int, nargs='+', default=[1000,2000,4000,8000])
    parser.add_argument('--coordinates', choices=['centered','observation_residual','conditional_whitening'], default='centered')
    args = parser.parse_args()
    if args.warmup < 1 or args.chains < 4: parser.error('Positive warmup and at least four chains required')
    import owalnuts
    import sys
    import owalnuts._owalnuts as extension
    from pymc_workflow import compile_target, parity, canonical_starts, coordinate_transport
    args.out.mkdir(parents=True, exist_ok=False)
    root=Path(__file__).resolve().parents[2]
    identity = bindings([args.fixture, Path(sys.executable), Path(owalnuts.__file__), Path(extension.__file__),
                         root/'Cargo.toml',root/'Cargo.lock', *root.joinpath('src').rglob('*.rs'),
                         root/'integrations/python/Cargo.toml',root/'integrations/python/Cargo.lock',
                         *root.joinpath('integrations/python/src').rglob('*.rs'),
                         *Path(__file__).parent.glob('*.py')])
    report = dict(status='running', qualified=False, phase='exploratory', model='local_level',
                  arm='python-pymc-cfunc-continuation', coordinates=args.coordinates, seed=args.seed,
                  bindings=identity, settings=dict(warmup=args.warmup, chains=args.chains, threads=1),
                  precision_plan=dict(tiers=args.tiers, threshold=.02, policy='One adaptation; exact retained prefix; frozen metric; all costs charged'),
                  predictive_seed=args.seed+130000, progress_semantics='Completed-request snapshots, not live counters')
    report['software']=dict(python=sys.version,algorithm_revision=owalnuts.ALGORITHM_REVISION,numpy=np.__version__)
    write_json(args.out/'started.json', report)
    def emit(stage,event,draws):
        with (args.out/'phase-events.jsonl').open('a') as f:
            f.write(json.dumps(dict(stage=stage,event=event,draws=draws,seconds=time.perf_counter()-STARTED,cpu_seconds=time.process_time()))+'\n')
    try:
        fixture=json.loads(args.fixture.read_text()); starts=canonical_starts(fixture['data'],args.chains)
        emit('compile','start',None); target,metadata=compile_target(fixture['data'],args.coordinates)
        report['compilation']=metadata; emit('compile','end',None)
        positions=coordinate_transport(fixture['data'],args.coordinates)[0](starts)
        emit('parity','start',None); tick=time.perf_counter()
        report['parity']=parity(target,fixture['data'],[positions[0],positions[-1],positions[0]+np.random.default_rng(818).normal(0,.01,positions.shape[1])],args.coordinates)
        if report['parity'].get('passed') is not True: raise RuntimeError('Independent runtime parity did not pass')
        report['parity_seconds']=time.perf_counter()-tick; emit('parity','end',None)
        run_session(target,fixture,starts,args.out,args.seed,args.warmup,args.tiers,args.coordinates,report,
                    verify=lambda:verify_bindings(identity),emit=emit,
                    checkpoint=lambda r:write_json(args.out/'python-pymc-report.json',r))
    except Exception as exc:
        report.update(status='failed',precision_pass=False,error=str(exc),traceback=traceback.format_exc())
    report['end_to_end_seconds']=time.perf_counter()-STARTED
    emit('worker','terminal',None)
    write_json(args.out/'python-pymc-report.json',report)
    write_json(args.out/'invocation-timing.json',dict(seconds_including_imports_and_report=time.perf_counter()-STARTED))
    return int(report['status']!='completed' or not report.get('precision_pass',False))


if __name__ == '__main__': raise SystemExit(main())
