import concurrent.futures,hashlib,json,shutil,sys
from pathlib import Path
import numpy as np,bridgestan as bs
base=Path(__file__).resolve().parent;runtime=Path('/home/ubuntu/lanes/gp-portable-runtime-20261030');sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
assert shutil.disk_usage(base).free>1024**3
build=json.loads((base/'TARGET-CHECK.json').read_text());assert build['passed'] and hashlib.sha256((base/'predictive_gp_model.so').read_bytes()).hexdigest()==build['library_sha256']
raw=bs.StanModel(str(runtime/'models/raw.so'),data=(base/'GP-TRAIN.json').read_text(),seed=1);pred=bs.StanModel(str(base/'predictive_gp_model.so'),data=(base/'DATA.json').read_text(),seed=1)
for point in build['points']:
    point=np.asarray(point,dtype=float)
    a,g=raw.log_density_gradient(point);b,h=pred.log_density_gradient(point);assert abs(a-b)<=1e-8 and max(abs(g-h))<=1e-8
paths=[base/n for n in ['predictive_worker.py','run_predictive_batch.py','PREDICTIVE-SCORING-PROTOCOL.md','predictive_gp_model.so','DATA.json','GP-TRAIN.json','HELDOUT.json','TARGET-CHECK.json']]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in paths};(base/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n');jobs=[]
for group in range(4):
    path=Path(f'/home/ubuntu/lanes/real-counts-reference-20261030/results/{group}/DRAWS-STATS.npz');digest=hashlib.sha256(path.read_bytes()).hexdigest()
    for chain in range(4):jobs.append(dict(name=f'reference-{group}-{chain}',kind='reference',group=group,chain=chain,draws=str(path),draws_sha256=digest))
for rep in range(2):
    for method in ['native','wal']:
        path=Path(f'/home/ubuntu/lanes/real-counts-fresh-workflows-20261030/results/{rep}-{method}/DRAWS-STATS.npz');digest=hashlib.sha256(path.read_bytes()).hexdigest()
        for chain in range(4):jobs.append(dict(name=f'fresh-{rep}-{method}-{chain}',kind='fresh',rep=rep,method=method,chain=chain,draws=str(path),draws_sha256=digest))
    for label,folder in [('screen','real-counts-importance-20261030'),('fresh','real-counts-fresh-workflows-20261030')]:
        path=Path('/home/ubuntu/lanes')/folder/'results'/(str(rep) if label=='screen' else f'{rep}-importance')/'DRAWS.npz';jobs.append(dict(name=f'{label}-{rep}-importance',kind='importance',stage=label,rep=rep,draws=str(path),draws_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len(jobs)==36;(base/'JOBS.json').write_text(json.dumps(jobs,indent=2)+'\n');root=base/'results';root.mkdir(exist_ok=False)
def run(i):
    job=jobs[i];out=root/job['name'];out.mkdir();s=execute([sys.executable,str(base/'predictive_worker.py'),str(i)],str(base),300,out,768*1024**2,32*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');return dict(name=job['name'],completed=s['exit_code']==0 and s['group_drained'] and (out/'SUMMARY.json').exists(),supervision=s)
rows=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
    for f in concurrent.futures.as_completed([pool.submit(run,i) for i in range(36)]):
        row=f.result();rows.append(row);(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(dict(job=row['name'],completed=row['completed'])),flush=True)
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(completed=True,rows=rows),indent=2)+'\n')
