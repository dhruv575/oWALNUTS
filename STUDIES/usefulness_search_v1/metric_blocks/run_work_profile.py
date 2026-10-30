import hashlib,json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';assert json.loads((local/'work_profile_build01/SUMMARY.json').read_text())['passed']
root=local/'work_profile01';root.mkdir(exist_ok=False);sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
sources=[Path(__file__),study/'work_profile_worker.py',study/'WORK-PROFILE-PROTOCOL.md'];hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources};rows=[]
for factor in [1,4]:
    for model in ['arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
        assert shutil.disk_usage(root).free>=1024**3;folder=root/(model+'-x'+str(factor));folder.mkdir()
        r=execute([sys.executable,str(study/'work_profile_worker.py'),model,str(factor),str(folder)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');rows.append(dict(model=model,factor=factor,folder=folder.name,completed=r['exit_code']==0 and r['group_drained']));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True),indent=2)+'\n');print(json.dumps(rows))
