import hashlib,json,shutil,sys
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery'
# This batch must only be started after the known sampler process is verified terminal.
confirmation=json.loads((l/'gp24_confirmation01/SUMMARY.json').read_text());assert confirmation['completed']
r=l/'gp_conditional_confirmation01';r.mkdir(exist_ok=False);sys.path.insert(0,str(l/'inputs'))
from resource_monitor import execute
sys.path.insert(0,str(p));from native_common import model_files
so,data,source=model_files('gp_pois_regr-gp_pois_regr')
names=[p/'gp_conditional_confirmation_worker.py',p/'run_gp_conditional_confirmation.py',p/'GP-CONDITIONAL-CONFIRMATION-PROTOCOL.md',p.parent/'gp_count/REFERENCE.json',so,data,source]+[l/'gp_conditional_local01'/n for n in ['common.py','conditional_v3.py','conditional-grid.npz','ADAPTER.json','CONDITIONAL-PREFLIGHT.json']]
hashes={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in names};rows=[]
(r/'INPUT-HASHES.json').write_text(json.dumps(hashes,indent=2)+'\n')
for seed in range(949200001,949200005):
    assert shutil.disk_usage(r).free>2*1024**3
    d=r/str(seed);d.mkdir();result=execute([sys.executable,str(p/'gp_conditional_confirmation_worker.py'),str(seed),str(d)],str(p),180,d,2*1024**3,64*1024**2,d/'worker.log',output_scan_interval=2)
    (d/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n')
    complete=result['exit_code']==0 and result['group_drained'] and (d/'RESULT.json').exists()
    row=json.loads((d/'RESULT.json').read_text()) if complete else dict(seed=seed,passed=False,completed=False,supervision=result)
    rows.append(row);print(json.dumps(dict(seed=seed,passed=row['passed'])),flush=True)
assert all(hashlib.sha256(Path(f).read_bytes()).hexdigest()==h for f,h in hashes.items())
(r/'SUMMARY.json').write_text(json.dumps(dict(completed=True,all_qualified=all(x['passed'] for x in rows),rows=rows,inputs=hashes),indent=2)+'\n')
