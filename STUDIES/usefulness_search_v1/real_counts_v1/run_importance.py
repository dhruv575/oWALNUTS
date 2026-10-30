import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030');sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
assert shutil.disk_usage(base).free>1024**3
manifest=json.loads((runtime/'MANIFEST.json').read_text())
for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2']:assert hashlib.sha256((runtime/n).read_bytes()).hexdigest()==manifest[n]
assert hashlib.sha256((runtime/'preflight/raw/counted_model.so').read_bytes()).hexdigest()=='36d06eca26b2a2bfc1f92aa6180b1b226ce3d50221e95966d2d3d6c8d2910ec8'
paths=[base/n for n in ['IMPORTANCE-PROTOCOL.md','conditional_proposal.py','importance_worker.py','run_importance.py','GP-TRAIN.json']]+[runtime/n for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2','preflight/raw/counted_model.so','native_common.py']]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n');root=base/'results';root.mkdir(exist_ok=False)
def run(rep):
    out=root/str(rep);out.mkdir();s=execute([sys.executable,str(base/'importance_worker.py'),str(rep)],str(base),300,out,3*1024**3,128*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
    return json.loads((out/'SUMMARY.json').read_text()) if s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists() else dict(rep=rep,completed=False,supervision=s)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for f in concurrent.futures.as_completed([pool.submit(run,i) for i in range(2)]):
        row=f.result();rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(rep=row['rep'],completed=row['completed'])),flush=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows),indent=2)+'\n')
