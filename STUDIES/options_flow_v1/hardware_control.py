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


class _WindowsJob:
    """Kill-on-close job, assigned while the worker's primary thread is suspended."""
    def __init__(self):
        from ctypes import wintypes as w
        self.api=ctypes.WinDLL('kernel32',use_last_error=True)
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),('flags',w.DWORD),('min_ws',ctypes.c_size_t),('max_ws',ctypes.c_size_t),('active_limit',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class IO(ctypes.Structure):
            _fields_=[(name,ctypes.c_ulonglong) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',IO),('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),('peak_process',ctypes.c_size_t),('peak_job',ctypes.c_size_t)]
        class Entry(ctypes.Structure):
            _fields_=[('size',w.DWORD),('usage',w.DWORD),('tid',w.DWORD),('pid',w.DWORD),('base_priority',w.LONG),('delta_priority',w.LONG),('flags',w.DWORD)]
        self.Entry=Entry
        signatures={'CreateJobObjectW':([ctypes.c_void_p,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.c_void_p],w.BOOL),'CloseHandle':([w.HANDLE],w.BOOL),'CreateToolhelp32Snapshot':([w.DWORD,w.DWORD],w.HANDLE),'Thread32First':([w.HANDLE,ctypes.POINTER(Entry)],w.BOOL),'Thread32Next':([w.HANDLE,ctypes.POINTER(Entry)],w.BOOL),'OpenThread':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'ResumeThread':([w.HANDLE],w.DWORD)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.api,name);fn.argtypes=args;fn.restype=result
        self.handle=self.api.CreateJobObjectW(None,None)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
        info=Extended();info.basic.flags=0x2000 # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway
        if not self.api.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)):
            error=ctypes.WinError(ctypes.get_last_error());self.close();raise error

    def assign_and_resume(self,worker):
        if not self.api.AssignProcessToJobObject(self.handle,int(worker._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        snapshot=self.api.CreateToolhelp32Snapshot(4,0) # TH32CS_SNAPTHREAD
        if snapshot==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry=self.Entry();entry.size=ctypes.sizeof(entry);found=[]
            ok=self.api.Thread32First(snapshot,ctypes.byref(entry))
            while ok:
                if entry.pid==worker.pid:found.append(entry.tid)
                ok=self.api.Thread32Next(snapshot,ctypes.byref(entry))
            if len(found)!=1:raise RuntimeError('Suspended worker must have exactly one primary thread')
            thread=self.api.OpenThread(2,False,found[0]) # THREAD_SUSPEND_RESUME
            if not thread:raise ctypes.WinError(ctypes.get_last_error())
            try:
                if self.api.ResumeThread(thread)!=1:raise RuntimeError('Unexpected primary thread suspension count')
            finally:self.api.CloseHandle(thread)
        finally:self.api.CloseHandle(snapshot)

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle,124):raise ctypes.WinError(ctypes.get_last_error())
        class Accounting(ctypes.Structure):
            _fields_=[('user',ctypes.c_longlong),('kernel',ctypes.c_longlong),('period_user',ctypes.c_longlong),('period_kernel',ctypes.c_longlong),('faults',ctypes.c_ulong),('total',ctypes.c_ulong),('active',ctypes.c_ulong),('terminated',ctypes.c_ulong)]
        deadline=time.monotonic()+10
        while True:
            info=Accounting()
            if not self.api.QueryInformationJobObject(self.handle,1,ctypes.byref(info),ctypes.sizeof(info),None):raise ctypes.WinError(ctypes.get_last_error())
            if info.active==0:return
            if time.monotonic()>=deadline:raise RuntimeError('Job descendants did not terminate within cleanup deadline')
            time.sleep(.01)

    def close(self):
        if self.handle:self.api.CloseHandle(self.handle);self.handle=None


class _ContainedWorker:
    def __init__(self,command):
        self.job=None;self.worker=None
        try:
            if os.name=='nt':
                self.job=_WindowsJob()
                self.worker=subprocess.Popen(list(command),creationflags=0x4) # CREATE_SUSPENDED
                self.job.assign_and_resume(self.worker)
                self.metadata={'kind':'windows-job-object','assigned_before_worker_execution':True,'kill_on_job_close':True,'breakaway_allowed':False}
            else:
                self.worker=subprocess.Popen(list(command),start_new_session=True)
                self.metadata={'kind':'posix-process-group','new_session':True,'limitation':'Descendants deliberately creating new sessions can escape process-group cleanup.'}
        except BaseException:
            if self.worker is not None:self.worker.kill();self.worker.wait()
            if self.job is not None:self.job.close()
            raise
        self.pid=self.worker.pid

    def wait(self,timeout=None):return self.worker.wait(timeout=timeout)
    def terminate(self):
        if self.job is not None:self.job.terminate()
        else:
            import signal
            try:os.killpg(self.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        self.worker.wait()
    def close(self):
        # Clean up descendants even when the direct launcher has already exited.
        try:self.terminate()
        finally:
            if self.job is not None:self.job.close()


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
        worker = _ContainedWorker(command)
        record['containment'] = worker.metadata
        record['worker_pid'] = worker.pid
        atomic_record(path, record)
        try:
            returncode = worker.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            worker.terminate()
            record.update(returncode=124, status='worker-timeout')
            return 124
        record.update(returncode=returncode, status='completed' if returncode == 0 else 'worker-failed')
    except BaseException as exc:
        if worker is not None:
            worker.terminate()
        record.update(status='launcher-failed', error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        if worker is not None:
            try:
                worker.close()
                record['descendant_cleanup_requested'] = True
                record['job_active_processes_after_cleanup'] = 0 if os.name=='nt' else None
            except BaseException as cleanup_error:
                record.update(status='cleanup-failed',cleanup_error=str(cleanup_error))
                record['elapsed_seconds']=time.perf_counter()-started
                record['finished_utc']=datetime.now(timezone.utc).isoformat()
                atomic_record(path,record)
                raise
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
