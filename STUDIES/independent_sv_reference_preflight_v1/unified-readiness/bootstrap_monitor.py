"""Stdlib Linux preparation-only monitor, derived from reviewed preflight watchdog.

Pip/venv descendants remain in the newly created session/process group. Inherited
ownership token and kernel start ticks are checked before signaling each member.
"""
import os,signal,subprocess,time,uuid
from pathlib import Path

def execute(command,cwd,cap,output_root,rss_limit,byte_limit,log_path,ownership_env='OWALNUTS_PREPARATION_TOKEN'):
 if os.name!='posix' or not Path('/proc').exists():raise RuntimeError('Linux /proc required')
 token=uuid.uuid4().hex;marker=(ownership_env+'='+token).encode();started=time.monotonic();process=None
 result=dict(status='running',peak_rss=0,peak_output_bytes=0,ownership_token=token,ownership_env=ownership_env,cap_seconds=cap)
 def owned():
  found=[]
  for p in Path('/proc').iterdir():
   if not p.name.isdigit():continue
   try:
    if marker not in (p/'environ').read_bytes().split(b'\0'):continue
    stat=(p/'stat').read_text().rsplit(')',1)[1].split()
    if stat[0]!='Z':found.append((int(p.name),int(stat[19]),int(stat[21])*os.sysconf('SC_PAGE_SIZE')))
   except (OSError,ValueError,IndexError):pass
  return found
 def stop(sig):
  for pid,start,_ in owned():
   try:
    current=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split()
    if int(current[19])==start:os.kill(pid,sig)
   except (OSError,ValueError,IndexError):pass
 try:
  env=os.environ.copy();env[ownership_env]=token
  for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):env[name]='1'
  with Path(log_path).open('xb') as log:
   process=subprocess.Popen(command,cwd=cwd,env=env,start_new_session=True,stdout=log,stderr=subprocess.STDOUT)
   result.update(pid=process.pid,process_group=process.pid)
   while True:
    members=owned();rss=sum(x[2] for x in members);size=0
    for p in Path(output_root).rglob('*'):
     try:
      if p.is_file() and not p.is_symlink():size+=p.stat().st_size
     except FileNotFoundError:pass
    result['peak_rss']=max(result['peak_rss'],rss);result['peak_output_bytes']=max(result['peak_output_bytes'],size)
    reason='rss_limit' if rss>rss_limit else 'output_limit' if size>byte_limit else 'deadline' if time.monotonic()-started>=cap else None
    if reason:result.update(status='terminated',reason=reason);break
    if process.poll() is not None:
     result.update(status='exited',exit_code=process.returncode)
     if members:result['orphaned_children_after_leader_exit']=True
     break
    time.sleep(.1)
 except Exception as exc:result.update(status='failed',error=repr(exc))
 finally:
  stop(signal.SIGTERM);until=time.monotonic()+3
  while owned() and time.monotonic()<until:
   if process is not None:process.poll()
   time.sleep(.05)
  if owned():stop(signal.SIGKILL)
  until=time.monotonic()+2
  while owned() and time.monotonic()<until:
   if process is not None:process.poll()
   time.sleep(.05)
  remaining=owned();result['group_drained']=not remaining;result['remaining_owned_pids']=[x[0] for x in remaining]
  if remaining:result['status']='cleanup_failed'
  if process is not None:result['exit_code']=process.poll()
  result['elapsed_seconds']=time.monotonic()-started
 return result
