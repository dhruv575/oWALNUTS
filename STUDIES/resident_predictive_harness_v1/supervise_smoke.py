"""One 600-second process-group envelope for host tests and development smoke."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
from datetime import datetime,timezone
root=Path(sys.argv[1]).resolve();python=Path(os.path.abspath(sys.argv[2]));source=Path(sys.argv[3]).resolve()
root.mkdir(parents=True,exist_ok=True);status=root/'supervisor.json'
if status.exists():raise SystemExit('Refusing to overwrite host supervision')
start=time.monotonic();state=dict(status='running',start_utc=datetime.now(timezone.utc).isoformat(),supervisor_pid=os.getpid(),deadline_seconds=600,planned_updates=4,
    sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in (Path(__file__).resolve(),source/'harness.py',source/'sv_target.py',source/'host_smoke.py',source/'test_harness.py')])
def save():status.write_text(json.dumps(state,indent=2))
save();process=None
try:
 # Python runner is passed arguments as data; no shell interpolation.
 runner=root/'run_checked.py'
 runner.write_text('import subprocess,sys\nsubprocess.run([sys.argv[1],"-m","unittest","discover","-s",sys.argv[2],"-p","test_harness.py"],check=True)\nsubprocess.run([sys.argv[1],sys.argv[2]+"/host_smoke.py","--out",sys.argv[3]],check=True)\n')
 with (root/'execution.log').open('wb') as log:
  process=subprocess.Popen(['taskset','-c','0-3',str(python),str(runner),str(python),str(source),str(root/'outputs')],cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  state['process_group']=process.pid;save()
  try:rc=process.wait(timeout=max(1,600-(time.monotonic()-start)));state.update(status='complete' if rc==0 else 'failed',exit_code=rc)
  except subprocess.TimeoutExpired:state['status']='timeout'
except Exception as exc:state.update(status='failed',error=repr(exc))
finally:
 if process is not None:
  def alive():
   try:os.killpg(process.pid,0);return True
   except ProcessLookupError:return False
  if alive():
   os.killpg(process.pid,signal.SIGTERM);grace=time.monotonic()+5
   while alive() and time.monotonic()<grace:process.poll();time.sleep(.1)
   if alive():os.killpg(process.pid,signal.SIGKILL)
   process.wait();grace=time.monotonic()+5
   while alive() and time.monotonic()<grace:time.sleep(.1)
  else:process.wait()
  state['owned_process_group_drained']=not alive()
  if alive():state['status']='cleanup_failed'
 result=root/'outputs/results.json'
 if result.exists():
  try:
   r=json.loads(result.read_text());state['workload_status']=r.get('status')
   state['returned_ticks']=[dict(tick=x['tick'],status=x['status']) for x in r.get('rows',[])]
   state['interrupted_tick']=r.get('in_progress_tick')
   state['never_started_ticks']=[i for i in range(1,5) if i not in [x['tick'] for x in r.get('rows',[])] and i!=r.get('in_progress_tick')]
   complete=(r.get('status')=='complete' and [x.get('tick') for x in r.get('rows',[])]==[1,2,3,4] and all(x.get('status')=='ok' for x in r.get('rows',[])) and r.get('in_progress_tick') is None)
   state['complete_evidence_verified']=complete
   if not complete and state['status']=='complete':state['status']='workload_failed'
  except Exception as exc:
   state['result_read_error']=repr(exc);state['complete_evidence_verified']=False
   if state['status']=='complete':state['status']='workload_failed'
 else:
  state['never_started_ticks']=[1,2,3,4];state['complete_evidence_verified']=False
  if state['status']=='complete':state['status']='workload_failed'
 state.update(end_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start);save()
