"""Separate bounded live SV schedule; missed origins are never replayed."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import issue as issuer

HORIZON = 1_800_000_000_000
WINDOW = 900_000_000_000
LAG = 60_000_000_000


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)


def run(capture, out, config, *, capture_end_ns, max_origins=96,
        deadline_seconds=172800, minimum_free_bytes=12*1024**3,
        clock=time.monotonic_ns, utc=time.time_ns, sleep=time.sleep,
        issue_fn=None):
    capture, out = Path(capture).resolve(), Path(out).resolve()
    if out == capture or capture in out.parents:
        raise ValueError('Scheduler output must be outside capture')
    if type(max_origins) is not int or not 1 <= max_origins <= 96:
        raise ValueError('At most 96 planned origins')
    if not 0 < deadline_seconds <= 172800 or type(capture_end_ns) is not int:
        raise ValueError('Invalid time budget')
    if type(minimum_free_bytes) is not int or minimum_free_bytes < 1:
        raise ValueError('Positive disk floor required')
    with (capture/'receipts.jsonl').open() as stream:
        first = json.loads(stream.readline())['receipt_monotonic_ns']
    if type(first) is not int or not first < capture_end_ns <= first+172800_000_000_000:
        raise ValueError('Capture end outside 48-hour bound')
    origins = list(range(first+WINDOW, capture_end_ns-HORIZON+1, HORIZON))[:max_origins]
    streams = config['origin_streams']
    if set(streams) != {str(o) for o in origins}:
        raise ValueError('Exact planned-origin seed roles required')
    seeds = [streams[str(o)][key] for o in origins
             for key in ('initialization_seed', 'sampler_seed', 'predictive_seed')]
    if any(type(s) is not int or not 0 <= s < 2**32 for s in seeds) or len(seeds) != len(set(seeds)):
        raise ValueError('Distinct uint32 origin/role seeds required')
    pins = dict(config['bindings'])
    for path in (Path(__file__), Path(issuer.__file__)):
        actual = digest(path)
        if str(path.resolve()) in pins and pins[str(path.resolve())] != actual:
            raise ValueError('Scheduler/issuer source differs from configuration')
        pins[str(path.resolve())] = actual
    if any(digest(p) != h for p, h in pins.items()):
        raise ValueError('Initial source/input drift')
    out.mkdir(parents=True, exist_ok=False)
    started = clock()
    deadline = min(started+int(deadline_seconds*1e9), capture_end_ns)
    save(out/'configuration.json', config)
    save(out/'plan.json', dict(schema='receipt-live-sv-schedule-v1',
         capture=str(capture), origins_ns=origins, capture_end_ns=capture_end_ns,
         deadline_ns=deadline, maximum_lag_seconds=60, minimum_history=20,
         lookback=256, model='sv_both_prior_whitened', minimum_free_bytes=minimum_free_bytes,
         started_monotonic_ns=started, started_utc_ns=utc(), source_sha256=pins,
         configuration_sha256=digest(out/'configuration.json'), qualified=False,
         budget_scope='Admission deadline and disk floor; worker containment is separate',
         retry_policy='No retries or replay of missed origins'))
    outcomes, abort = [], None

    def record(origin, reason):
        folder = out/str(origin); folder.mkdir()
        value = dict(schema='research-live-sv-issuance-v1', status='not_issued',
                     reason=reason, origin_receipt_ns=origin,
                     horizon_end_receipt_ns=origin+HORIZON, qualified=False,
                     maximum_lag_seconds=60, source_sha256=pins,
                     recorded_monotonic_ns=clock(), recorded_utc_ns=utc())
        save(folder/'issuance.json', value)
        return value

    def admission_failure(origin):
        if any(digest(p) != h for p, h in pins.items()):
            return 'source_drift'
        if (capture/'summary.json').exists():
            return 'capture_terminated'
        if clock() >= deadline:
            return 'scheduler_budget'
        if clock() > origin+LAG:
            return 'missed_origin'
        return None

    for origin in origins:
        location = out/str(origin)/'issuance.json'
        try:
            reason = abort or admission_failure(origin)
            if reason is None:
                due = origin+3_000_000_000
                while clock() < due and clock() < deadline:
                    sleep(max(0., min(30., (min(due, deadline)-clock())/1e9)))
                reason = admission_failure(origin)
            if reason:
                if reason != 'missed_origin':
                    abort = reason
                result = record(origin, reason)
                storage = None
            else:
                free = shutil.disk_usage(out).free
                storage = dict(observed_free_bytes=free, minimum_free_bytes=minimum_free_bytes)
                if free < minimum_free_bytes:
                    abort = 'scheduler_storage_floor'
                    result = record(origin, abort)
                else:
                    cfg = dict(config, **streams[str(origin)])
                    result = (issue_fn or issuer.issue)(capture, out/str(origin), origin, cfg)
                    detail = result.get('reason', '').lower()
                    if 'containment' in detail:
                        abort = 'worker_containment_failure'
                    elif 'actual native runtime' in detail or 'worker identity differs' in detail:
                        abort = 'worker_provenance_failure'
                    elif 'source' in detail and 'drift' in detail:
                        abort = 'source_drift'
            row = dict(origin_receipt_ns=origin, status=result['status'], reason=result.get('reason'),
                       path=str(location), issuance_sha256=digest(location), storage_admission=storage)
        except Exception as exc:
            abort = 'scheduler_error'
            folder = out/str(origin); folder.mkdir(exist_ok=True)
            if location.exists():
                location = folder/'scheduler-error.json'
            row = dict(schema='research-live-sv-issuance-v1', status='not_issued',
                       reason=abort, error=repr(exc), origin_receipt_ns=origin,
                       horizon_end_receipt_ns=origin+HORIZON, qualified=False,
                       recorded_monotonic_ns=clock(), recorded_utc_ns=utc())
            save(location, row)
            row['path'] = str(location)
            row['issuance_sha256'] = digest(location)
        outcomes.append(row)
        with (out/'events.jsonl').open('a') as stream:
            stream.write(json.dumps(row, allow_nan=False)+'\n'); stream.flush()
    final = dict(status='completed' if abort is None else 'completed_with_unattempted',
                 expected=len(origins), outcomes=outcomes, qualified=False,
                 ended_monotonic_ns=clock(), ended_utc_ns=utc())
    save(out/'terminal.json', final)
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--capture-end-ns', type=int, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    if config.get('status') != 'frozen_live_sv_plan':
        raise ValueError('Frozen live SV configuration required')
    config['bindings'] = {**config['bindings'], str(args.config.resolve()): digest(args.config)}
    print(json.dumps(run(args.capture, args.out, config, capture_end_ns=args.capture_end_ns)))


if __name__ == '__main__':
    main()
