import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030')
assert shutil.disk_usage(base).free>1.5*1024**3
manifest=json.loads((runtime/'MANIFEST.json').read_text())
for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2','gp-wal-tuned-runner']:
    assert hashlib.sha256((runtime/n).read_bytes()).hexdigest()==manifest[n]
assert hashlib.sha256((runtime/'preflight/raw/counted_model.so').read_bytes()).hexdigest()=='36d06eca26b2a2bfc1f92aa6180b1b226ce3d50221e95966d2d3d6c8d2910ec8'
paths=[base/n for n in ['reference_worker.py','reference_summary.py','run_reference.py','REFERENCE-PROTOCOL.md','GP-TRAIN.json']]+[runtime/n for n in ['models/raw.so','models/raw.stan','models/libtbb.so.2','gp-wal-tuned-runner','preflight/raw/counted_model.so','native_common.py']]+[Path('/home/ubuntu/lanes/gp-full-cost-20261030/resource_monitor.py')]
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths};(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
root=base/'results';root.mkdir(exist_ok=False)
def run(g):
    out=root/str(g);out.mkdir()
    s=execute([sys.executable,str(base/'reference_worker.py'),str(g)],str(base),1200,out,4*1024**3,256*1024**2,out/'worker.log',output_scan_interval=2)
    (out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
    return json.loads((out/'SUMMARY.json').read_text()) if s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists() else dict(group=g,passed=False,supervision=s)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for f in concurrent.futures.as_completed([pool.submit(run,g) for g in range(4)]):
        row=f.result();rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(group=row['group'],passed=row['passed'])),flush=True)
out=base/'summary-supervision';out.mkdir()
s=execute([sys.executable,str(base/'reference_summary.py')],str(base),300,out,4*1024**3,16*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
print(json.dumps(dict(completed=s['exit_code']==0 and s['group_drained'])),flush=True)
