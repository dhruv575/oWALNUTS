"""POSIX fixed-budget supervisor scaffold. Requires future frozen run manifest."""
import hashlib,json,os,signal,subprocess,time
from pathlib import Path

def supervise(manifest_path,output):
    manifest_path=Path(manifest_path);spec=json.loads(manifest_path.read_text());out=Path(output)
    if spec.get('status')!='frozen_authorized':raise ValueError('draft cannot execute')
    if out.exists():raise ValueError('refuse overwrite')
    if os.name!='posix':raise RuntimeError('POSIX process group supervision required')
    cap=spec['wall_cap_seconds']
    if type(cap) is not int or not 1<=cap<=3600:raise ValueError('explicit bounded cap required')
    command=spec['command']
    if not isinstance(command,list) or not command or not all(isinstance(x,str) for x in command):raise ValueError('argument vector required')
    for path,want in spec['sources'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=want:raise ValueError('source mismatch '+path)
    out.mkdir();start=time.monotonic();state=dict(status='running',planned_streams=32,planned_ticks=1024,cap_seconds=cap,manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest());p=None
    def save():
        temp=out/'supervisor.partial';temp.write_text(json.dumps(state,indent=2));temp.replace(out/'supervisor.json')
    def alive():
        if p is None:return False
        try:os.killpg(p.pid,0);return True
        except ProcessLookupError:return False
    def kill(sig):
        try:os.killpg(p.pid,sig)
        except ProcessLookupError:pass
    save()
    try:
        with (out/'execution.log').open('wb') as log:
            p=subprocess.Popen(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            state['process_group']=p.pid;save()
            try:state['exit_code']=p.wait(timeout=max(.001,cap-(time.monotonic()-start)));state['status']='exited'
            except subprocess.TimeoutExpired:state['status']='timeout'
    except Exception as exc:state.update(status='failed',error=repr(exc))
    finally:
        if alive():
            kill(signal.SIGTERM);until=time.monotonic()+3
            while alive() and time.monotonic()<until:p.poll();time.sleep(.05)
            if alive():kill(signal.SIGKILL)
        until=time.monotonic()+2
        while alive() and time.monotonic()<until:p.poll();time.sleep(.05)
        if p is not None:p.poll()
        state['group_drained']=not alive()
        if alive():state['status']='cleanup_failed'
        state['postrun_sources_match']=all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==want for path,want in spec['sources'].items())
        # Exit0 never means calibrated/completed: dedicated final evidence validator required.
        state['complete_evidence_verified']=False
        state['elapsed_seconds']=time.monotonic()-start;save()
    return state
