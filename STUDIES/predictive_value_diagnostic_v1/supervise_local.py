"""Parent-owned sampled resource watchdog; never computes predictive outcomes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


def atomic(path, value):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['preflight', 'full', 'recovery'])
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--python', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    study, out = args.study.resolve(), args.out.resolve()
    report = out.parent / (out.name + '.' + args.mode + '.supervisor.json')
    log = report.with_suffix('.log')
    if report.exists() or log.exists():
        raise FileExistsError('This supervised stage was already attempted')
    if args.mode == 'preflight':
        if out.exists():
            raise FileExistsError(out)
        budget = 120
    elif args.mode == 'recovery':
        if out.exists():
            raise FileExistsError(out)
        audit = json.loads((study / 'RECOVERY-AUDIT.json').read_text())
        budget = audit['remaining_seconds']
        if abs(budget - 308.172) > 1e-9 or len(audit['remaining']) != 79:
            raise ValueError('Recovery budget or fixed schedule mismatch')
    else:
        pilot = json.loads((out / 'preflight.json').read_text())
        budget = pilot['remaining_budget_seconds']
        if pilot['status'] != 'complete' or not 300 <= budget <= 1800:
            raise ValueError('Frozen preflight admission/budget failed')
    out.parent.mkdir(parents=True, exist_ok=True)
    command = [os.path.abspath(args.python), str(study / 'evaluate.py'),
               args.mode, '--out', str(out)]
    if args.mode == 'recovery':
        command = [os.path.abspath(args.python), str(study / 'recover.py'), '--out', str(out)]
    env = os.environ.copy()
    threads = {key: '1' for key in
               ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS')}
    env.update(threads)
    start, wall_start = time.monotonic(), time.time()
    state = dict(status='starting', supervisor_pid=os.getpid(), command=command,
                 supervisor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                 psutil_version=psutil.__version__, started_unix=wall_start,
                 phase_seconds=budget, startup_allowance_seconds=60,
                 sampling_interval_seconds=.25, rss_limit_bytes=2*1024**3,
                 output_limit_bytes=50*1024**2, thread_environment=threads,
                 observed_peak_owned_rss=0, observed_output_bytes=0,
                 processes=[], limitation='Sampled limits, not OS allocation reservations')
    atomic(report, state)
    tracked, process = {}, None

    def discover():
        # Never reconstruct the launcher solely from its numeric PID after exit.
        # Its PID could have been reused while the real Python child still runs.
        for key, parent in list(tracked.items()):
            try:
                if not parent.is_running() or parent.create_time() != key[1]:
                    continue
                for item in parent.children(recursive=True):
                    tracked.setdefault((item.pid, item.create_time()), item)
            except psutil.NoSuchProcess:
                pass
        alive = []
        for key, item in tracked.items():
            try:
                if item.is_running() and item.create_time() == key[1] and item.status() != psutil.STATUS_ZOMBIE:
                    alive.append(item)
            except psutil.NoSuchProcess:
                pass
        return alive

    try:
        with log.open('xb') as stream:
            process = subprocess.Popen(command, cwd=study, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT)
            launcher = psutil.Process(process.pid)
            tracked[(launcher.pid, launcher.create_time())] = launcher
            state.update(status='running', launcher_pid=process.pid)
            phase_start = None
            while True:
                alive = discover()
                rss = 0
                for item in alive:
                    try:
                        rss += item.memory_info().rss
                    except psutil.NoSuchProcess:
                        pass
                size = sum(p.stat().st_size for p in out.rglob('*') if p.is_file()) if out.exists() else 0
                size += log.stat().st_size
                state['observed_peak_owned_rss'] = max(state['observed_peak_owned_rss'], rss)
                state['observed_output_bytes'] = max(state['observed_output_bytes'], size)
                phase_file = out / ('recovery-start.json' if args.mode == 'recovery' else args.mode + '.json')
                if phase_file.exists() and phase_start is None:
                    record = json.loads(phase_file.read_text())
                    if record['pid'] not in [p.pid for p in alive] or record['hard_seconds'] != budget:
                        raise ValueError('Unexpected evaluator PID or budget')
                    phase_start = float(record['started_unix'])
                    state.update(evaluator_pid=record['pid'], phase_started_unix=phase_start,
                                 setup_wall_seconds=phase_start-wall_start)
                reason = None
                if rss > state['rss_limit_bytes']:
                    reason = 'rss_limit'
                elif size > state['output_limit_bytes']:
                    reason = 'output_limit'
                elif time.monotonic()-start > budget+60:
                    reason = 'whole_process_deadline'
                elif phase_start is None and time.monotonic()-start > 60:
                    reason = 'startup_deadline'
                elif phase_start is not None and time.time()-phase_start > budget+1:
                    reason = 'phase_deadline'
                if reason:
                    state.update(status='terminated', reason=reason)
                    break
                code = process.poll()
                if code is not None and not alive:
                    state.update(status='exited', exit_code=code)
                    break
                atomic(report, state)
                time.sleep(.25)
    except BaseException as error:
        state.update(status='supervisor_failed', error=repr(error))
    finally:
        for item in reversed(discover()):
            try:
                item.terminate()
            except psutil.NoSuchProcess:
                pass
        _, remaining = psutil.wait_procs(discover(), timeout=3)
        for item in remaining:
            try:
                item.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(remaining, timeout=2)
        if process is not None:
            state['exit_code'] = process.poll()
        state['processes'] = [dict(pid=key[0], create_time=key[1]) for key in tracked]
        state['remaining_owned_pids'] = [p.pid for p in discover()]
        if state['remaining_owned_pids']:
            state['status'] = 'cleanup_failed'
        phase_file = out / ('recovery-final.json' if args.mode == 'recovery' else args.mode + '.json')
        try:
            state['evaluator_status'] = json.loads(phase_file.read_text()).get('status') if phase_file.exists() else 'missing'
        except Exception as error:
            state.update(evaluator_status='unreadable', result_error=repr(error))
        state.update(ended_unix=time.time(), elapsed_seconds=time.monotonic()-start)
        atomic(report, state)
    print(json.dumps({k: state.get(k) for k in
                      ('status', 'evaluator_status', 'exit_code', 'elapsed_seconds',
                       'observed_peak_owned_rss', 'remaining_owned_pids')}))


if __name__ == '__main__':
    main()
