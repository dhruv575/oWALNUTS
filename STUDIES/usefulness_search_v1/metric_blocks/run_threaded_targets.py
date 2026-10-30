import json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'threaded_targets01';root.mkdir(exist_ok=False)
base=Path(json.loads((local/'threaded_build01/SUPERVISION.json').read_text())['build_directory']);sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
rows=[]
for model in ['arma-arma11','arK-arK','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
    assert min(shutil.disk_usage(base).free,shutil.disk_usage(root).free)>=1024**3
    out=root/model;out.mkdir();work=base/('qualified-'+model)
    r=execute([sys.executable,str(study/'build_threaded_targets_worker.py'),model,str(out),str(work)],str(base),180,base,2*1024**3,1024**3,base/(model+'-worker.log'),output_scan_interval=2)
    shutil.copy2(base/(model+'-worker.log'),out/'worker.log');(out/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    rows.append(dict(model=model,exit_code=r['exit_code'],group_drained=r['group_drained'],passed=(r['exit_code']==0 and r['group_drained'] and json.loads((out/'SUMMARY.json').read_text())['passed'])))
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=all(r['passed'] for r in rows),rows=rows),indent=2)+'\n');print(json.dumps(rows))
