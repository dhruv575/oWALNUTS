"""One-shot outer clock; contained cohort timeouts belong to the frozen controller."""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    plan = evidence / 'run' / 'plan.json'
    digest = sha(plan)
    if plan.with_suffix('.sha256').read_text().strip() != digest:
        raise ValueError('Frozen plan sidecar mismatch')
    if any((plan.parent / name).exists() for name in
           ['outer-started.json', 'outer-execution.json', 'execution-summary.json']):
        raise ValueError('Never restart an attempted campaign')
    source = sha(__file__)
    record = dict(plan_sha256=digest, launcher_sha256=source,
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  status='running', qualified=False)
    with (plan.parent / 'outer-started.json').open('x') as handle:
        json.dump(record, handle, indent=2)
    started = time.perf_counter()
    try:
        sys.path.insert(0, str(evidence.parents[1]))
        from persistent_comparison_plan import execute
        execute(plan)
        record['status'] = 'controller_completed'
    except BaseException as exc:
        record.update(status='controller_failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        record.update(outer_seconds=time.perf_counter() - started,
                      launcher_unchanged=sha(__file__) == source,
                      plan_unchanged=sha(plan) == digest,
                      finished_utc=datetime.now(timezone.utc).isoformat(),
                      scope='Controller import, all cohort processes, independent output validation and campaign bookkeeping; excludes this final outer record write.')
        with (plan.parent / 'outer-execution.json').open('x') as handle:
            json.dump(record, handle, indent=2, allow_nan=False)
        print(json.dumps(record), flush=True)


if __name__ == '__main__':
    main()
