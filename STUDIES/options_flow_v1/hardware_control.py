"""Enforce CPU affinity in an isolated launcher before a worker imports libraries.

python hardware_control.py --cpus 0,1 --record affinity.json -- python reference.py ...
Affinity constrains scheduling; it does not reserve cores or guarantee a quiet machine.
Windows support uses the current processor group (up to a pointer-width mask).
"""
from __future__ import annotations
import argparse
import ctypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time


def validate_cpus(cpus, allowed):
    values = list(cpus)
    if not values or any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in values):
        raise ValueError('CPU list must contain nonnegative integer indices')
    if len(set(values)) != len(values):
        raise ValueError('CPU indices must be unique')
    if not set(values).issubset(set(allowed)):
        raise ValueError(f'Requested CPUs {values} are outside allowed CPUs {sorted(allowed)}')
    return sorted(values)


def parse_cpus(text):
    try:
        values = [int(value.strip()) for value in text.split(',')]
    except (ValueError, AttributeError) as exc:
        raise ValueError('Use a comma-separated list of CPU indices, e.g. 0,1') from exc
    # Validation independent of hardware first; membership is checked at launch.
    return validate_cpus(values, values)


def _windows_api():
    from ctypes import wintypes
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.GetCurrentProcess.argtypes = []
    api.GetCurrentProcess.restype = wintypes.HANDLE
    api.GetProcessAffinityMask.argtypes = [wintypes.HANDLE,
                                          ctypes.POINTER(ctypes.c_size_t),
                                          ctypes.POINTER(ctypes.c_size_t)]
    api.GetProcessAffinityMask.restype = wintypes.BOOL
    api.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    api.SetProcessAffinityMask.restype = wintypes.BOOL
    return api


def get_affinity():
    if os.name == 'nt':
        api = _windows_api()
        process_mask, system_mask = ctypes.c_size_t(), ctypes.c_size_t()
        if not api.GetProcessAffinityMask(api.GetCurrentProcess(),
                                         ctypes.byref(process_mask), ctypes.byref(system_mask)):
            raise OSError(ctypes.get_last_error(), 'GetProcessAffinityMask failed')
        if not process_mask.value:
            raise OSError('Empty/current-group Windows affinity mask; processor-group setup unsupported')
        return [i for i in range(ctypes.sizeof(ctypes.c_size_t)*8)
                if process_mask.value & (1 << i)]
    if hasattr(os, 'sched_getaffinity'):
        return sorted(os.sched_getaffinity(0))
    raise NotImplementedError('Enforced affinity is supported on Windows and Linux only')


def set_affinity(cpus):
    """Modify only the calling launcher process; child workers inherit its mask."""
    desired = validate_cpus(cpus, get_affinity())
    if os.name == 'nt':
        api = _windows_api()
        mask = sum(1 << cpu for cpu in desired)
        if not api.SetProcessAffinityMask(api.GetCurrentProcess(), ctypes.c_size_t(mask)):
            raise OSError(ctypes.get_last_error(), 'SetProcessAffinityMask failed')
    elif hasattr(os, 'sched_setaffinity'):
        os.sched_setaffinity(0, set(desired))
    else:
        raise NotImplementedError('Enforced affinity is supported on Windows and Linux only')
    realized = get_affinity()
    if realized != desired:
        raise RuntimeError(f'Affinity enforcement mismatch: requested {desired}, realized {realized}')
    return realized


def hardware_metadata():
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'processor': platform.processor(), 'logical_cpu_count': os.cpu_count(),
            'python': platform.python_version(),
            'windows_processor_group_note': 'Current process group only' if os.name == 'nt' else None}


def atomic_record(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def wrapper_command(command, cpus, record_path, timeout=None):
    """Return a command that enforces affinity without changing the caller's process."""
    desired = validate_cpus(cpus, cpus)
    if not command:
        raise ValueError('Worker command must not be empty')
    prefix = [sys.executable, str(Path(__file__).resolve()), '--cpus',
              ','.join(map(str, desired)), '--record', str(record_path)]
    if timeout is not None:
        if timeout <= 0:
            raise ValueError('Timeout must be positive')
        prefix += ['--timeout', str(timeout)]
    return [*prefix, '--', *map(str, command)]


def run_worker(command, cpus, record_path, timeout=None):
    """CLI-only launcher body. Call wrapper_command from long-lived Python processes."""
    if not command:
        raise ValueError('Worker command must not be empty')
    path = Path(record_path)
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite existing affinity evidence: {path}')
    record = {'schema_version': 1, 'started_utc': datetime.now(timezone.utc).isoformat(),
              'launcher_pid': os.getpid(), 'command': list(command),
              'hardware': hardware_metadata(), 'status': 'starting',
              'limitation': 'CPU affinity is not exclusive allocation; other processes may share these cores.'}
    started = time.perf_counter()
    worker = None
    try:
        allowed = get_affinity()
        desired = validate_cpus(cpus, allowed)
        record.update(allowed_cpus=allowed, requested_cpus=desired)
        record['realized_cpus'] = set_affinity(desired)
        record['enforced_before_worker_launch'] = True
        record['status'] = 'running'
        atomic_record(path, record)
        # No shell: argument bytes remain separate. Affinity is inherited at process creation.
        worker = subprocess.Popen(list(command))
        record['worker_pid'] = worker.pid
        atomic_record(path, record)
        try:
            returncode = worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            worker.kill()
            worker.wait()
            record.update(returncode=124, status='worker-timeout')
            return 124
        record.update(returncode=returncode, status='completed' if returncode == 0 else 'worker-failed')
    except BaseException as exc:
        if worker is not None and worker.poll() is None:
            worker.kill()
            worker.wait()
        record.update(status='launcher-failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        record['elapsed_seconds'] = time.perf_counter()-started
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        atomic_record(path, record)
    return returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cpus', required=True, type=parse_cpus)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--timeout', type=float)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.timeout is not None and args.timeout <= 0:
        parser.error('--timeout must be positive')
    return run_worker(command, args.cpus, args.record, args.timeout)


if __name__ == '__main__':
    raise SystemExit(main())
