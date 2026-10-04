"""Exploratory time to interval precision with one NumPyro warmup and continuation.

Fixed-size retained batches reuse compilation and frozen adaptation. Every
batch, diagnostic check and serialization is charged. This is a different
execution policy from precision_tiers.py and must be labeled as such.
"""
import time
STARTED = time.perf_counter()
import argparse
import hashlib
import json
import datetime
from pathlib import Path
import traceback

import numpy as np
import jax
import jax.numpy as jnp
from jax.scipy.special import gammaln
from reference_continuation import ContinuedReference
from precision_tiers import precision_screen
from run import clean


def local_configuration(data,chains,coordinates='centered'):
    from local_level import validate,log_density
    from local_observation_residual import canonical_starts,to_residual,to_canonical,log_density as residual_density
    validate(data)
    initial=canonical_starts(data,chains)
    if coordinates == 'centered':
        return initial,initial.copy(),lambda q:-log_density(q,data,jnp,gammaln),lambda q:q
    if coordinates == 'observation_residual':
        return initial,to_residual(initial,data),lambda q:-residual_density(q,data,jnp),lambda q:to_canonical(q,data)
    if coordinates == 'conditional_whitening':
        from local_conditional_whitening import to_whitened,to_canonical as guide_canonical,jax_log_density
        return initial,to_whitened(initial,data),lambda q:-jax_log_density(q,data),lambda q:guide_canonical(q,data)
    raise ValueError('Unknown local coordinates')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fixture', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--model', choices=['flow','local_level'], required=True)
    p.add_argument('--coordinates',choices=['centered','observation_residual','conditional_whitening'],default='centered',help='Local-level coordinates; flow retains historical process-noncentered recipe')
    p.add_argument('--seed', type=int, required=True)
    p.add_argument('--warmup', type=int, default=1000)
    p.add_argument('--target-accept',type=float,default=.8)
    p.add_argument('--chains', type=int, default=4)
    p.add_argument('--batch-size', type=int, default=1000)
    p.add_argument('--tiers', type=int, nargs='+', default=[1000,2000,4000,8000])
    a = p.parse_args()
    if not np.isfinite(a.target_accept) or not 0 < a.target_accept < 1:p.error('--target-accept must be finite and strictly between zero and one')
    if a.model == 'flow' and a.coordinates != 'centered':p.error('Observation residual coordinates support local_level only')
    if (min(a.warmup,a.chains,a.batch_size)<1 or not a.tiers
            or any(v<a.batch_size or v%a.batch_size for v in a.tiers)
            or any(b<=c for c,b in zip(a.tiers,a.tiers[1:]))):
        p.error('Positive settings and increasing tiers divisible by batch size required')
    a.out.mkdir(parents=True, exist_ok=False)
    def phase(event,**details):
        record=dict(event=event,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    elapsed_seconds=time.perf_counter()-STARTED,**details)
        with (a.out/'phase-events.jsonl').open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(record)+'\n');handle.flush()
        print(json.dumps(record),flush=True)
    phase('worker_configuring')
    fixture = json.loads(a.fixture.read_text())
    data = fixture['data']
    coordinate_label='noncentered' if a.model=='flow' else a.coordinates
    arm='numpyro-continuation' if a.coordinates=='centered' else 'numpyro-continuation-'+a.coordinates.replace('_','-')
    plan = dict(model=a.model,coordinates=coordinate_label,arm=arm, seed=a.seed, warmup=a.warmup, chains=a.chains,
        target_accept=a.target_accept,batch_size=a.batch_size, tiers=a.tiers, relative_mcse=.02,
        fixture_sha256=hashlib.sha256(a.fixture.read_bytes()).hexdigest(),
        source_sha256={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                       for f in Path(__file__).parent.glob('*.py')},
        execution='One full warmup; fixed retained batches continue chain state with frozen step size and metric',
        phase='exploratory', qualified=False)
    (a.out/'plan.json').write_text(json.dumps(plan, indent=2))
    report_path = a.out/'numpyro-continuation-report.json'
    report_path.write_text(json.dumps(dict(status='running', phase='exploratory', plan=plan)))
    attempts = []
    try:
        if a.model == 'flow':
            from model import validate
            from flow_starts import canonical_starts, to_noncentered
            from optimized_reference import noncentered_log_density, canonical_noncentered
            from evaluate import summarize as evaluate
            validate(data)
            initial = canonical_starts(data,a.chains)
            starts = to_noncentered(initial,data)
            potential = lambda q: -noncentered_log_density(q,data)
            canonical = lambda q: np.asarray(jax.vmap(jax.vmap(lambda v:canonical_noncentered(v,data)))(q))
        else:
            from run_local_level import evaluate
            initial,starts,potential,canonical=local_configuration(data,a.chains,a.coordinates)
        phase('sampler_constructing')
        sampler = ContinuedReference(potential, starts, a.seed, a.warmup,a.batch_size,target_accept=a.target_accept)
        phase('adapt_begin')
        sampler.adapt()
        phase('adapt_end')
        passed = False
        for tier in a.tiers:
            while len(sampler.chunks)*a.batch_size < tier:
                phase('batch_begin',batch=len(sampler.chunks)+1)
                sampler.append()
                phase('batch_end',batch=len(sampler.chunks))
            phase('evaluation_begin',tier=tier)
            q = canonical(sampler.samples)
            evaluation = evaluate(q,fixture,a.seed+130000)
            phase('evaluation_end',tier=tier)
            report = dict(arm=arm,coordinates=coordinate_label,status='completed',phase='exploratory',
                qualified=False,seed=a.seed,settings=dict(target_accept=a.target_accept,warmup=a.warmup,draws=tier,chains=a.chains),
                fixture_sha256=plan['fixture_sha256'],source_sha256=plan['source_sha256'],
                evaluation=evaluation,retained_divergences=sampler.divergences,
                healthy=evaluation['computational_screen_pass'] and sampler.divergences==0,
                warmup_seconds=sampler.warmup_seconds,checkpoints=sampler.checkpoints.copy(),
                warmup_cpu_seconds=sampler.warmup_cpu_seconds,
                end_to_end_seconds=time.perf_counter()-STARTED)
            screen = precision_screen(report)
            (a.out/f'draws-{tier}-report.json').write_text(json.dumps(clean(report),indent=2,allow_nan=False))
            attempts.append(dict(draws=tier,screen=screen,
                cumulative_seconds_including_tier_report=time.perf_counter()-STARTED))
            print(tier,screen['pass'],screen['max_endpoint_mcse_over_width'],flush=True)
            if screen['pass']:
                passed=True
                break
        (a.out/'numpyro-continuation-raw.json').write_text(json.dumps(clean(dict(
            canonical_draws=q.tolist(),initial_positions=initial.tolist(),
            sampling_initial_positions=starts.tolist(),coordinates=coordinate_label,
            seed=a.seed,checkpoints=sampler.checkpoints)),allow_nan=False))
        report.update(plan=plan,attempts=attempts,precision_pass=passed,
                      end_to_end_seconds=time.perf_counter()-STARTED)
    except Exception as exc:
        phase('worker_error',error=f'{type(exc).__name__}: {exc}')
        report=dict(status='failed',phase='exploratory',qualified=False,plan=plan,
                    error=str(exc),traceback=traceback.format_exc(),attempts=attempts,
                    end_to_end_seconds=time.perf_counter()-STARTED)
    report_path.write_text(json.dumps(clean(report),indent=2,allow_nan=False))
    phase('worker_terminal',status=report.get('status'),precision_pass=report.get('precision_pass',False))
    (a.out/'invocation-timing.json').write_text(json.dumps(dict(
        seconds_including_imports_and_output=time.perf_counter()-STARTED,
        precision_pass=report.get('precision_pass',False),qualified=False)))
    return 0 if report.get('precision_pass') else 2


if __name__ == '__main__': raise SystemExit(main())
