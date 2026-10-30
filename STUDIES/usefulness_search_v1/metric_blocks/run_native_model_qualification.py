import json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'nativemodels01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
models=['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr'];rows=[]
for model in models:
    assert shutil.disk_usage(root).free>=1024**3;folder=root/model;folder.mkdir()
    r=execute([sys.executable,str(study/'qualify_native_models_worker.py'),model,str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    passed=r['exit_code']==0 and r['group_drained'] and json.loads((folder/'SUMMARY.json').read_text())['passed'];rows.append(dict(model=model,passed=passed));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows),indent=2)+'\n');print(json.dumps(rows))
