"""180-second arithmetic-only process group envelope, no retries."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]).resolve();source=root/'source'
python=Path('/home/ubuntu/lanes/resident-predictive-build-20261027/env/bin/python')
status=root/'supervisor.json'
if status.exists() or (root/'result.json').exists():raise SystemExit('Refuse overwrite')
start=time.monotonic();state=dict(status='running',started_utc=datetime.now(timezone.utc).isoformat(),supervisor_pid=os.getpid(),execution_cap_seconds=180,cleanup_grace_seconds=5)
planned=[f'{rep}:{tick}:{name}' for rep,ticks in enumerate(([4,3,2,1],[1,2,3,4],[4,3,2,1])) for tick in ticks for name in (['exact','scipy'] if (rep+tick)%2==0 else ['scipy','exact'])]
state['planned_calls']=planned
process=None
def save():
    p=root/'supervisor.partial';p.write_text(json.dumps(state,indent=2));p.replace(status)
def alive():
    if process is None:return False
    try:os.killpg(process.pid,0);return True
    except ProcessLookupError:return False
def send(sig):
    try:os.killpg(process.pid,sig)
    except ProcessLookupError:pass
save()
try:
    manifest=json.loads((source/'linux-manifest.json').read_text())
    for name,want in manifest['sources'].items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest()==want,name
    state['manifest_sha256']=hashlib.sha256((source/'linux-manifest.json').read_bytes()).hexdigest();save()
    env=os.environ.copy()
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):env[key]='1'
    with (root/'execution.log').open('wb') as log:
        process=subprocess.Popen(['taskset','-c','0-3',str(python),str(source/'linux_run.py')],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        state['process_group']=process.pid;save()
        try:
            rc=process.wait(timeout=max(.001,180-(time.monotonic()-start)));state.update(status='complete' if rc==0 else 'failed',exit_code=rc)
        except subprocess.TimeoutExpired:state['status']='timeout'
except Exception as exc:state.update(status='failed',error=repr(exc))
finally:
    if process is not None:
        if alive():
            send(signal.SIGTERM);deadline=time.monotonic()+3
            while alive() and time.monotonic()<deadline:process.poll();time.sleep(.05)
            if alive():send(signal.SIGKILL)
        deadline=time.monotonic()+2
        while alive() and time.monotonic()<deadline:process.poll();time.sleep(.05)
        process.poll();state['owned_group_drained']=not alive()
        if alive():state['status']='cleanup_failed'
    state['complete_evidence_verified']=False
    try:
        r=json.loads((root/'result.json').read_text());rows=r.get('rows',[]);ids=[x['call'] for x in rows]
        state.update(workload_status=r.get('status'),returned_calls=[dict(call=x['call'],status=x['status']) for x in rows],interrupted_call=r.get('in_progress'),never_started=[x for x in planned if x not in ids and x!=r.get('in_progress')])
        state['complete_evidence_verified']=r.get('status')=='complete' and ids==planned and all(x['status']=='ok' for x in rows) and r.get('in_progress') is None and r.get('postrun_integrity') is True and r.get('tests',{}).get('passed') is True
    except Exception as exc:state.update(result_error=repr(exc),never_started=planned)
    if state['status']=='complete' and not state['complete_evidence_verified']:state['status']='workload_failed'
    state.update(ended_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start);save()
