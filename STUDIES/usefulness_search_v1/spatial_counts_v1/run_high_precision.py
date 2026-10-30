import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
assert shutil.disk_usage(base).free>1024**3
paths=[base/n for n in ['high_precision_worker.py','run_high_precision.py','HIGH-PRECISION-PREFLIGHT.md','spatial_gp_model.so','spatial_gp.stan','GP-TRAIN.json']];hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n');root=base/'results';root.mkdir(exist_ok=False)
def run(i):
    out=root/str(i);out.mkdir();s=execute([sys.executable,str(base/'high_precision_worker.py'),str(i)],str(base),300,out,1024**3,8*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');return json.loads((out/'SUMMARY.json').read_text()) if s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists() else dict(point=i,passed=False,supervision=s)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for f in concurrent.futures.as_completed([pool.submit(run,i) for i in range(8)]):
        row=f.result();rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(point=row['point'],passed=row['passed'])),flush=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items());(root/'SUMMARY.json').write_text(json.dumps(dict(completed=True,passed=all(x['passed'] for x in rows),rows=rows),indent=2)+'\n')
