"""Bounded handoff: avoid overlapping the two 12-core campaigns."""
import json,os,subprocess,sys,time
from pathlib import Path
root=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029');old=Path('/home/ubuntu/lanes/pharma-ode-20261029/initial02/FINAL.json')
start=time.monotonic()
while not old.exists():
    if time.monotonic()-start>1200:raise TimeoutError('Legacy batch did not drain before bounded handoff')
    time.sleep(5)
final=json.loads(old.read_text());assert final['sources_unchanged']
assert all(j.get('group_drained',False) or j['status']=='not_started_resource_admission' for j in final['jobs'])
cmd=[sys.executable,str(root/'source/supervisor.py'),'initial',str(root/'initial02')]
with (root/'initial02-launch.log').open('x') as log:
    child=subprocess.Popen(cmd,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
(root/'LAUNCH.json').write_text(json.dumps(dict(pid=child.pid,command=cmd,legacy_finished=True,launched_unix=time.time()),indent=2)+'\n')
