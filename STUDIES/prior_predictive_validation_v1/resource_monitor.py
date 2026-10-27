"""POSIX one-job resource monitor; generation/fitting occurs only in child worker."""
import os,signal,subprocess,time
from pathlib import Path
import psutil

def execute(command,cwd,cap,output_root,rss_limit,byte_limit,log_path):
    if os.name!='posix':raise RuntimeError('POSIX deployment only; tests inject executor')
    started=time.monotonic();result=dict(status='running',cap_seconds=cap);p=None;tracked={}
    def alive_group():
        if p is None:return False
        try:os.killpg(p.pid,0);return True
        except ProcessLookupError:return False
    def kill(sig):
        try:os.killpg(p.pid,sig)
        except ProcessLookupError:pass
    def discover():
        live=[]
        for key,item in list(tracked.items()):
            try:
                if not item.is_running() or item.create_time()!=key[1] or item.status()==psutil.STATUS_ZOMBIE:continue
                live.append(item)
                for child in item.children(recursive=True):tracked.setdefault((child.pid,child.create_time()),child)
            except psutil.NoSuchProcess:pass
        return live
    try:
        with Path(log_path).open('xb') as log:
            env=os.environ.copy();env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')})
            p=subprocess.Popen(command,cwd=cwd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
            item=psutil.Process(p.pid);tracked[(item.pid,item.create_time())]=item
            result.update(pid=p.pid,process_group=p.pid,peak_rss=0,peak_output_bytes=0)
            while True:
                alive=discover();rss=0
                for item in alive:
                    try:rss+=item.memory_info().rss
                    except psutil.NoSuchProcess:pass
                size=0
                for path in Path(output_root).rglob('*'):
                    try:
                        if path.is_file():size+=path.stat().st_size
                    except FileNotFoundError:pass
                result['peak_rss']=max(result['peak_rss'],rss);result['peak_output_bytes']=max(result['peak_output_bytes'],size)
                reason='rss_limit' if rss>rss_limit else 'output_limit' if size>byte_limit else 'deadline' if time.monotonic()-started>=cap else None
                if reason:result.update(status='terminated',reason=reason);break
                code=p.poll()
                if code is not None and not alive_group():result.update(status='exited',exit_code=code);break
                time.sleep(.1)
    except Exception as exc:result.update(status='failed',error=repr(exc))
    finally:
        if alive_group():
            kill(signal.SIGTERM);until=time.monotonic()+3
            while alive_group() and time.monotonic()<until:
                if p is not None:p.poll()
                time.sleep(.05)
            if alive_group():kill(signal.SIGKILL)
        until=time.monotonic()+2
        while alive_group() and time.monotonic()<until:
            if p is not None:p.poll()
            time.sleep(.05)
        result['group_drained']=not alive_group();result['remaining_owned_pids']=[x.pid for x in discover()]
        if not result['group_drained'] or result['remaining_owned_pids']:result['status']='cleanup_failed'
        if p is not None:result['exit_code']=p.poll()
        result['elapsed_seconds']=time.monotonic()-started
    return result
