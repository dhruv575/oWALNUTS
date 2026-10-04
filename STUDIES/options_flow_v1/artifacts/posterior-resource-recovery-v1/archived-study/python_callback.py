"""Exploratory public Python/JAX workflow; callback cost is part of sampling.

Use the source-built isolated environment. This is distinct from the Rust
generic-autodiff arm and records extension identity, not build attestation.
"""
import time
STARTED = time.perf_counter()
import argparse
import hashlib
import json
from pathlib import Path
import traceback

import numpy as np
import jax
import jax.numpy as jnp
from jax.scipy.special import gammaln
import owalnuts
import owalnuts._owalnuts as extension

from run import clean


def target_and_starts(fixture, model, chains):
    data = fixture['data']
    if model == 'flow':
        from model import validate
        from flow_starts import canonical_starts, to_noncentered
        from optimized_reference import noncentered_log_density, canonical_noncentered
        validate(data)
        initial = canonical_starts(data, chains)
        starts = to_noncentered(initial, data)
        logp = lambda q: noncentered_log_density(q, data)
        canonical = lambda q: np.asarray(jax.vmap(jax.vmap(lambda v: canonical_noncentered(v, data)))(jnp.asarray(q)))
    else:
        from local_level import validate, log_density
        validate(data)
        initial = np.asarray([np.r_[np.asarray(data['y'])+(c-(chains-1)/2)*.02,
            np.log(.08)+(c-(chains-1)/2)*.02, np.log(.12)-(c-(chains-1)/2)*.02]
            for c in range(chains)])
        starts = initial.copy()
        logp = lambda q: log_density(q, data, jnp, gammaln)
        canonical = lambda q: np.asarray(q)
    return owalnuts.from_jax(logp), starts, initial, canonical


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model', choices=['flow', 'local_level'], required=True)
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--warmup', type=int, default=1000)
    p.add_argument('--draws', type=int, default=1000)
    p.add_argument('--chains', type=int, default=4)
    a = p.parse_args()
    if min(a.warmup, a.draws, a.chains) < 1:
        p.error('Positive sampling settings required')
    a.out.mkdir(parents=True, exist_ok=False)
    report_path = a.out/'python-jax-report.json'
    fixture = json.loads(a.fixture.read_text())
    report = dict(status='running', phase='exploratory', qualified=False,
        arm='python-jax', model=a.model, seed=a.seed,
        fixture_sha256=hashlib.sha256(a.fixture.read_bytes()).hexdigest(),
        settings=dict(warmup=a.warmup, draws=a.draws, chains=a.chains,
                      chain_execution='sequential', threads=1),
        extension_path=extension.__file__,
        extension_sha256=hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest(),
        build_attestation=False,
        source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in Path(__file__).parent.glob('*.py')},
        software=dict(jax=jax.__version__, algorithm_revision=owalnuts.ALGORITHM_REVISION))
    report_path.write_text(json.dumps(report, indent=2))
    try:
        target, starts, initial, canonical = target_and_starts(fixture, a.model, a.chains)
        ts = time.perf_counter()
        value, gradient = target(starts[0])
        if not np.isfinite(value) or not np.isfinite(gradient).all():
            raise ValueError('Nonfinite initial density or gradient')
        compile_seconds = time.perf_counter()-ts
        ts = time.perf_counter()
        result = owalnuts.sample(target, dim=starts.shape[1], init=starts,
            chains=a.chains, warmup=a.warmup, draws=a.draws, seed=a.seed, threads=1)
        sampling_seconds = time.perf_counter()-ts
        q = canonical(result.samples)
        if q.shape != (a.chains, a.draws, starts.shape[1]) or not np.isfinite(q).all():
            raise ValueError('Invalid posterior output shape/values')
        if a.model == 'flow':
            from evaluate import summarize
            evaluation = summarize(q, fixture, a.seed+130000)
        else:
            from run_local_level import evaluate
            evaluation = evaluate(q, fixture, a.seed+130000)
        health = result.health()
        raw = dict(arm='python-jax', seed=a.seed, initial_positions=initial.tolist(),
                   canonical_draws=q.tolist(), sampler_health=health)
        (a.out/'python-jax-raw.json').write_text(json.dumps(clean(raw), allow_nan=False))
        report.update(status='completed', evaluation=evaluation,
            retained_divergences=health['divergences'], sampler_health=health,
            healthy=evaluation['computational_screen_pass'] and health['divergences']==0,
            first_density_call_including_compilation_seconds=compile_seconds,
            sampling_including_callback_seconds=sampling_seconds,
            target_calls=result.target_calls,
            end_to_end_seconds=time.perf_counter()-STARTED)
    except Exception as exc:
        report.update(status='failed', error=str(exc), traceback=traceback.format_exc(),
                      end_to_end_seconds=time.perf_counter()-STARTED)
    report_path.write_text(json.dumps(clean(report), indent=2, allow_nan=False))
    (a.out/'invocation-timing.json').write_text(json.dumps(
        dict(seconds_including_imports_and_report=time.perf_counter()-STARTED)))
    print(json.dumps({k:report.get(k) for k in ('status','healthy','end_to_end_seconds')}))
    return int(report['status'] != 'completed')


if __name__ == '__main__':
    raise SystemExit(main())
