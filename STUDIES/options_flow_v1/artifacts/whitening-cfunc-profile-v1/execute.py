"""Frozen sequential target-only feasibility profile; no MCMC speed claim."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with path.open('x', encoding='utf-8') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def snapshot():
    previous = json.loads((HERE.parent / 'local-conditional-whitening-v2/plan.json').read_text())
    paths = list(ROOT.glob('*.py')) + [Path(p) for p in previous['bound_files']]
    paths += [Path(__file__), Path(sys.executable)]
    return {str(p.resolve()): sha(p) for p in paths}


def main():
    plan = dict(phase='target-only-exploratory', qualified=False,
                periods=[32, 128, 512, 1000], blocks=5, calls_per_block=300,
                cpus=[0], timeout_seconds_per_cell=600, source=snapshot(),
                cache_policy='Existing compiler caches retained; fresh process per length.',
                scope='Value/gradient target cost and scaling only; no sampler speed claim.')
    write(HERE / 'plan.json', plan)
    digest = sha(HERE / 'plan.json')
    (HERE / 'plan.sha256').write_text(digest + '\n')
    outcomes = []
    for n in plan['periods']:
        if snapshot() != plan['source'] or sha(HERE / 'plan.json') != digest:
            raise RuntimeError('Frozen profile inputs changed')
        command = [sys.executable, str(ROOT / 'hardware_control.py'), '--cpus', '0',
                   '--timeout', '600', '--record', str(HERE / f't{n}-affinity.json'),
                   '--', sys.executable, str(ROOT / 'profile_whitening_cfunc.py'),
                   '--periods', str(n), '--out', str(HERE / f't{n}.json'),
                   '--blocks', '5', '--calls-per-block', '300']
        write(HERE / f't{n}-started.json', dict(command=command, plan_sha256=digest))
        start = time.perf_counter()
        with (HERE / f't{n}.log').open('x') as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        outcome = dict(periods=n, returncode=result.returncode,
                       controller_seconds=time.perf_counter()-start,
                       source_unchanged=snapshot() == plan['source'], plan_sha256=digest)
        write(HERE / f't{n}-terminal.json', outcome)
        outcomes.append(outcome)
        print(json.dumps(outcome), flush=True)
        if not outcome['source_unchanged']:
            raise RuntimeError('Source changed during profile')
    write(HERE / 'summary.json', dict(qualified=False, outcomes=outcomes))


if __name__ == '__main__':
    main()
