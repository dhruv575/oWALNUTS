import hashlib,json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'step_ladder01';root.mkdir(exist_ok=False)
parent=study/'matched_geometry_worker.py';source=parent.read_text();needle="seed=941850001+c))";assert source.count(needle)==1
source=source.replace(needle,"seed=941850001+c))\n    configs[-1]['step_size']*=float(sys.argv[3])")
source=source.replace("STUDY/'MATCHED-GEOMETRY-DIAGNOSTIC.md'","STUDY/'STEP-LADDER-PROTOCOL.md'")
source=source.replace('from native_common import LOCAL,STUDY,model_files','sys.path.insert(0,'+repr(str(study))+')\nfrom native_common import LOCAL,STUDY,model_files')
worker=root/'worker.py';worker.write_text(source)
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [parent,worker,Path(__file__),study/'STEP-LADDER-PROTOCOL.md',study/'native_common.py']}
(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
rows=[]
for factor in [.5,2.,4.,8.]:
    for model in ['arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
        assert shutil.disk_usage(root).free>=1024**3
        folder=root/(model+'-x'+str(factor));folder.mkdir()
        r=execute([sys.executable,str(worker),model,str(folder),str(factor)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
        rows.append(dict(model=model,factor=factor,folder=folder.name,completed=r['exit_code']==0 and r['group_drained']));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True),indent=2)+'\n');print(json.dumps(rows))
