"""Linux-only 600 second / sampled 4 GiB owned-process-group envelope."""
import argparse,json,os,signal,subprocess,time
from pathlib import Path

def members(group):
 rows=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   fields=(d/'stat').read_text().rsplit(')',1)[1].split()
   if int(fields[2])!=group:continue
   rss=int(fields[21])*os.sysconf('SC_PAGE_SIZE')
   rows.append((int(d.name),rss,fields[0]))
  except (OSError,ValueError,IndexError):pass
 return rows

def output_bytes(root):
 total=0
 for path in root.rglob("*"):
  try:
   if path.is_file() and not path.is_symlink():total+=path.stat().st_size
  except FileNotFoundError:pass
 return total

def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--python',required=True);p.add_argument('--native-python',required=True);p.add_argument('--bridgestan-sdk',required=True);a=p.parse_args()
 root=Path(a.root).absolute();root.mkdir(exist_ok=False);start=time.monotonic();record=dict(status='running',limit_seconds=600,rss_limit_bytes=4*1024**3,peak_sampled_group_rss=0,output_limit_bytes=1024**3,peak_sampled_output_bytes=0)
 command=[os.path.abspath(a.python),str(Path(__file__).with_name('preflight.py')),'--output',str(root/'work'),'--native-python',os.path.abspath(a.native_python),'--bridgestan-sdk',a.bridgestan_sdk]
 with (root/'stdout.log').open('wb') as log:
  child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);record.update(pid=child.pid,command=command)
  (root/'supervisor.json').write_text(json.dumps(record,indent=2))
  try:
   while child.poll() is None:
    rss=sum(x[1] for x in members(child.pid));record['peak_sampled_group_rss']=max(rss,record['peak_sampled_group_rss'])
    size=output_bytes(root);record['peak_sampled_output_bytes']=max(size,record['peak_sampled_output_bytes'])
    if size>record['output_limit_bytes']:record['status']='output_limit';break
    if rss>record['rss_limit_bytes']:record['status']='memory_limit';break
    if time.monotonic()-start>=600:record['status']='timeout';break
    time.sleep(.2)
  finally:
   # Drain independently of leader status, including compile descendants.
   if members(child.pid):
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    until=time.monotonic()+3
    while members(child.pid) and time.monotonic()<until:time.sleep(.1)
    if members(child.pid):
     try:os.killpg(child.pid,signal.SIGKILL)
     except ProcessLookupError:pass
   try:child.wait(timeout=3)
   except subprocess.TimeoutExpired:record['status']='cleanup_failed'
   until=time.monotonic()+3
   while any(x[2]!='Z' for x in members(child.pid)) and time.monotonic()<until:time.sleep(.1)
   record['remaining_group']=members(child.pid);record['exit_code']=child.returncode
   if any(x[2]!='Z' for x in record['remaining_group']):record['status']='cleanup_failed'
   if record['status']=='running':
    try:
     result=json.loads((root/'work/result.json').read_text())
     ok=child.returncode==0 and result['status']=='complete' and result['api_and_target_verified'] is True and len(result['parity'])==6
     record['status']='complete' if ok else 'workload_failed'
    except Exception as e:record.update(status='workload_failed',evidence_error=repr(e))
   record['elapsed_seconds']=time.monotonic()-start
   (root/'supervisor.json').write_text(json.dumps(record,indent=2))
 return 0 if record['status']=='complete' else 1
if __name__=='__main__':raise SystemExit(main())
