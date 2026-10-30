"""Bounded initial-analysis-validation-report handoff; never changes frozen source."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029');start=time.monotonic()
def status(phase,**extra):(root/'WORKFLOW-STATUS.json').write_text(json.dumps(dict(phase=phase,elapsed_seconds=time.monotonic()-start,**extra),indent=2)+'\n')
def run(name,args,cap):
    status(name)
    with (root/(name+'.log')).open('x') as log:
        subprocess.run([sys.executable]+args,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=cap,check=True)
try:
    status('waiting_for_initial')
    while not (root/'initial02/FINAL.json').exists():
        if time.monotonic()-start>3600:raise TimeoutError('Initial batch wait cap')
        time.sleep(5)
    final=json.loads((root/'initial02/FINAL.json').read_text());assert final['sources_unchanged'] and all(j.get('group_drained') or j['status']=='not_started_resource_admission' for j in final['jobs'])
    run('reference-analysis',['source/analyze.py','initial',str(root/'initial02')],900)
    selection=root/'SELECTION.json';digest=hashlib.sha256(selection.read_bytes()).hexdigest()
    (root/'SELECTION-FREEZE.json').write_text(json.dumps(dict(sha256=digest,frozen_unix=time.time(),initial_final_sha256=hashlib.sha256((root/'initial02/FINAL.json').read_bytes()).hexdigest()),indent=2)+'\n')
    run('validation-launch',['source/supervisor.py','validate',str(root/'validation01'),str(selection)],4600)
    assert hashlib.sha256(selection.read_bytes()).hexdigest()==digest
    final=json.loads((root/'validation01/FINAL.json').read_text());assert final['sources_unchanged'] and all(j.get('group_drained') or j['status']=='not_started_resource_admission' for j in final['jobs'])
    run('final-analysis',['source/analyze.py','final',str(root/'validation01')],300)
    run('report',['packaging/report.py',str(root)],60)
    status('complete',selection_sha256=digest)
except Exception as exc:
    status('failed',error=repr(exc));raise
