import json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';assert json.loads((local/'native_prefix02/SUMMARY.json').read_text())['all_passed']
root=local/'matched_geometry01';root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
rows=[]
for model in ['arma-arma11','arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
    assert shutil.disk_usage(root).free>=1024**3;folder=root/model;folder.mkdir()
    r=execute([sys.executable,str(study/'matched_geometry_worker.py'),model,str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    rows.append(dict(model=model,completed=r['exit_code']==0 and r['group_drained']));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,scope='Exposed one-seed mechanism diagnostic.'),indent=2)+'\n');print(json.dumps(rows))
