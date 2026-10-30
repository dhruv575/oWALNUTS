import hashlib,json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';chunk=int(sys.argv[1]);assert chunk in [1,2,3,4]
assert json.loads((local/'nativemodels01/SUMMARY.json').read_text())['passed']
assert json.loads((local/'nativemodels01_archive/VERIFICATION.json').read_text())['passed']
if chunk>1:assert json.loads((local/f'nativescreen{chunk-1:02d}_archive/VERIFICATION.json').read_text())['passed']
root=local/f'nativescreen{chunk:02d}';root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'))
source_names=['run_native_screen_chunk.py','native_screen_worker.py','native_common.py','scaled_policy.py','scaled_policy_qr.py','fisher_high_precision.py','fisher_qr_mp.py','hybrid_gate.py','selector.py','selector_full_shape.py','NATIVE-COMPARISON-SCREEN.md']
hashes={str(study/n):hashlib.sha256((study/n).read_bytes()).hexdigest() for n in source_names}
(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
from resource_monitor import execute
models=['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr'];arms=['walnuts_auto','scaled_original','scaled_fast','fisher_fast','native_draw_diag','native_diag','native_low_rank'];rows=[];seed=940600000+chunk
for model in models:
    assert shutil.disk_usage(root).free>=1024**3;folder=root/model;folder.mkdir()
    r=execute([sys.executable,str(study/'native_screen_worker.py'),model,str(seed),str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    if r['exit_code']==0 and r['group_drained']:rows+=json.loads((folder/'SUMMARY.json').read_text())['rows']
    else:rows.extend(dict(model=model,seed=seed,arm=a,passed=False,error='cell_worker_failed') for a in arms)
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,chunk=chunk,seed=seed,inputs=hashes,unchanged=True),indent=2)+'\n');print(json.dumps([dict(model=r['model'],arm=r['arm'],passed=r['passed']) for r in rows]))
