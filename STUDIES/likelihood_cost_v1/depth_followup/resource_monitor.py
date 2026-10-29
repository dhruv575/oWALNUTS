"""Linux scoped-process monitor, including orphaned children after leader exit."""
import os,signal,subprocess,time,uuid
from pathlib import Path
import psutil

def execute(command,cwd,cap,output_root,rss_limit,byte_limit,log_path,ownership_env='OWALNUTS_JOB_TOKEN',output_scan_interval=.1):
    if os.name!='posix' or not Path('/proc').exists():raise RuntimeError('Linux deployment only')
    if not 0<output_scan_interval<=60:raise ValueError('Output scan interval must be in (0,60] seconds')
    started=time.monotonic();result=dict(status='running',cap_seconds=cap,output_scan_interval_seconds=output_scan_interval,output_size_scans=0,output_cap_scope='Sampled byte cap, not a hard filesystem quota; overshoot between scans is possible. Final scan follows process drain.');p=None;tracked={};token=uuid.uuid4().hex
    last_scan=None;size=0
    marker=(ownership_env+'='+token).encode()
    def scan_output():
        total=0
        for path in Path(output_root).rglob('*'):
            try:
                if path.is_file() and not path.is_symlink():total+=path.stat().st_size
            except FileNotFoundError:pass
        result['output_size_scans']+=1
        result['peak_output_bytes']=max(result.get('peak_output_bytes',0),total)
        return total
    def discover():
        # Environment token survives parent exit and nested start_new_session.
        for entry in Path('/proc').iterdir():
            if not entry.name.isdigit():continue
            try:
                if marker not in (entry/'environ').read_bytes().split(b'\0'):continue
                item=psutil.Process(int(entry.name));tracked.setdefault((item.pid,item.create_time()),item)
            except (OSError,psutil.NoSuchProcess,psutil.AccessDenied):pass
        live=[]
        for key,item in list(tracked.items()):
            try:
                if item.is_running() and item.create_time()==key[1] and item.status()!=psutil.STATUS_ZOMBIE:live.append(item)
            except psutil.NoSuchProcess:pass
        return live
    def stop(sig):
        # Verify identity again immediately before signaling, never reconstruct by bare PID.
        for item in discover():
            try:item.send_signal(sig)
            except psutil.NoSuchProcess:pass
    try:
        with Path(log_path).open('xb') as log:
            env=os.environ.copy();env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')});env[ownership_env]=token
            p=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
            try:
                item=psutil.Process(p.pid);tracked[(item.pid,item.create_time())]=item
            except psutil.NoSuchProcess:pass
            result.update(pid=p.pid,process_group=p.pid,peak_rss=0,peak_output_bytes=0,ownership_env=ownership_env,ownership_token=token)
            while True:
                alive=discover();rss=0
                for item in alive:
                    try:rss+=item.memory_info().rss
                    except psutil.NoSuchProcess:pass
                now=time.monotonic()
                if last_scan is None or now-last_scan>=output_scan_interval:
                    size=scan_output();last_scan=time.monotonic()
                result['peak_rss']=max(result['peak_rss'],rss)
                reason='rss_limit' if rss>rss_limit else 'output_limit' if size>byte_limit else 'deadline' if time.monotonic()-started>=cap else None
                if reason:result.update(status='terminated',reason=reason);break
                code=p.poll()
                if code is not None:
                    result.update(status='exited',exit_code=code)
                    if discover():result['orphaned_children_after_leader_exit']=True
                    break
                time.sleep(.1)
    except Exception as exc:result.update(status='failed',error=repr(exc))
    finally:
        stop(signal.SIGTERM);until=time.monotonic()+3
        while discover() and time.monotonic()<until:
            if p is not None:p.poll()
            time.sleep(.05)
        if discover():stop(signal.SIGKILL)
        until=time.monotonic()+2
        while discover() and time.monotonic()<until:
            if p is not None:p.poll()
            time.sleep(.05)
        remaining=discover();result['group_drained']=not remaining;result['remaining_owned_pids']=[x.pid for x in remaining]
        if remaining:result['status']='cleanup_failed'
        if p is not None:result['exit_code']=p.poll()
        try:
            result['final_output_bytes']=scan_output()
            if result['final_output_bytes']>byte_limit:
                result['final_output_limit_exceeded']=True
                if result['status']=='exited':result.update(status='terminated',reason='output_limit_final_scan')
        except Exception as exc:
            result['final_output_scan_error']=repr(exc)
            if result['status']=='exited':result['status']='failed'
        result['elapsed_seconds']=time.monotonic()-started
    return result
