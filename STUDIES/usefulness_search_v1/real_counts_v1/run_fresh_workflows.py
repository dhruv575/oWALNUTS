import hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030');sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
assert shutil.disk_usage(base).free>1024**3
manifest=json.loads((runtime/'MANIFEST.json').read_text())
for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2','gp-wal-tuned-runner']:assert hashlib.sha256((runtime/n).read_bytes()).hexdigest()==manifest[n]
assert hashlib.sha256((runtime/'preflight/raw/counted_model.so').read_bytes()).hexdigest()=='36d06eca26b2a2bfc1f92aa6180b1b226ce3d50221e95966d2d3d6c8d2910ec8'
paths=[base/n for n in ['FRESH-WORKFLOW-PROTOCOL.md','fresh_sampler_worker.py','fresh_importance_worker.py','conditional_proposal.py','time_workflow.py','run_fresh_workflows.py','GP-TRAIN.json']]+[runtime/n for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2','gp-wal-tuned-runner','preflight/raw/counted_model.so','native_common.py']]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n');root=base/'results';root.mkdir(exist_ok=False);rows=[]
for rep,method in [(0,'wal'),(0,'importance'),(0,'native'),(1,'native'),(1,'importance'),(1,'wal')]:
    assert shutil.disk_usage(base).free>512*1024**2
    out=root/f'{rep}-{method}';out.mkdir()
    cmd=[sys.executable,str(base/'fresh_importance_worker.py'),str(out),str(rep)] if method=='importance' else [sys.executable,str(base/'fresh_sampler_worker.py'),str(out),str(2 if method=='native' else 3),str(rep)]
    s=execute([sys.executable,str(base/'time_workflow.py'),str(out),*cmd],str(base),300,out,3*1024**3,128*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
    complete=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists()
    row=dict(rep=rep,method=method,completed=complete,supervision=s)
    if complete:row.update(result=json.loads((out/'SUMMARY.json').read_text()),timing=json.loads((out/'PROCESS-TIME.json').read_text()))
    rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(rep=rep,method=method,completed=complete)),flush=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows,scope='Independent qualification and precision audit pending'),indent=2)+'\n')
