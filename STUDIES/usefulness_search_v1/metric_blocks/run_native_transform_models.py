"""Apply the unchanged exposed arK reconstruction check to the other five targets."""
import hashlib,json,shutil,sys,textwrap
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'native_transform_models01';root.mkdir(exist_ok=False)
parent=study/'probe_native_transform.py';source=parent.read_text();assert source.count('\nelse:\n')==1
body=textwrap.dedent(source.split('\nelse:\n')[1]);assert body.count("model_files('arK-arK')")==1
body=body.replace("model_files('arK-arK')","model_files(sys.argv[1])")
worker=root/'worker.py';worker.write_text('"""Unchanged exposed reconstruction gates on five additional models."""\nimport sys,json,hashlib\nfrom pathlib import Path\nstudy=Path('+repr(str(study))+');sys.path.insert(0,str(study));root=Path(sys.argv[2])\n'+body)
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [parent,worker,study/'native_common.py',Path(__file__)]}
(root/'SOURCE-PROVENANCE.json').write_text(json.dumps(hashes,indent=2)+'\n')
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
rows=[]
for model in ['arma-arma11','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
    assert shutil.disk_usage(root).free>=1024**3
    folder=root/model;folder.mkdir()
    r=execute([sys.executable,str(worker),model,str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
    (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
    passed=r['exit_code']==0 and r['group_drained'] and json.loads((folder/'SUMMARY.json').read_text())['passed']
    rows.append(dict(model=model,passed=passed,exit_code=r['exit_code'],group_drained=r['group_drained']))
    (root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,all_passed=all(r['passed'] for r in rows),inputs=hashes,unchanged=True),indent=2)+'\n');print(json.dumps(rows))
