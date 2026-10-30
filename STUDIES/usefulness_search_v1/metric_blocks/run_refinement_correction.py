import hashlib,json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';assert json.loads((local/'refinement_ablation_test01/SUMMARY.json').read_text())['passed']
root=local/'refinement_ablation02';root.mkdir(exist_ok=False);parent=study/'matched_geometry_worker.py';source=parent.read_text()
source=source.replace("'fixed_metric_build02/SUMMARY.json'","'refinement_ablation_build01/SUMMARY.json'").replace("STUDY/'MATCHED-GEOMETRY-DIAGNOSTIC.md'","STUDY/'REFINEMENT-ABLATION-CORRECTION.md'")
source=source.replace('from native_common import LOCAL,STUDY,model_files','sys.path.insert(0,'+repr(str(study))+')\nfrom native_common import LOCAL,STUDY,model_files')
needle='spec=dict(model=str(so),data=str(data),draws=2000,chains=configs)';assert source.count(needle)==1
source=source.replace(needle,'spec=dict(model=str(so),data=str(data),draws=2000,chains=configs,levels=int(sys.argv[3]),max_error=float(sys.argv[4]))')
needle="result=json.loads(out.read_text())";assert source.count(needle)==1
source=source.replace(needle,needle+'''
for c in result['chains']:
    assert c['levels']==spec['levels'] and c['max_error']==spec['max_error']
    assert c['work']['all_phase_calls']==c['target_calls']
    if spec['levels']==1:assert c['work']['target_calls_reverse']==0
''')
source += "\nif spec['levels']==8 and spec['max_error']==1:\n    old=json.loads((LOCAL/'matched_geometry01'/model/'OUTPUT.json').read_text())\n    assert result['target_calls']==old['target_calls']\n    for a,b in zip(result['chains'],old['chains']):\n        for key in ['draws','target_calls','retained_divergences','step_size','mass','seed','revision']:assert a[key]==b[key]\n"
worker=root/'worker.py';worker.write_text(source)
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [parent,worker,Path(__file__),study/'REFINEMENT-ABLATION-CORRECTION.md',study/'native_common.py']};(root/'SOURCE-SNAPSHOT.json').write_text(json.dumps(hashes,indent=2)+'\n')
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
rows=[]
for levels,error in [(8,1.),(8,1000.)]:
    for model in ['arK-arK','sblrc-blr','eight_schools-eight_schools_centered','garch-garch11','gp_pois_regr-gp_pois_regr']:
        assert shutil.disk_usage(root).free>=1024**3;folder=root/(model+f'-L{levels}-E{error}');folder.mkdir()
        r=execute([sys.executable,str(worker),model,str(folder),str(levels),str(error)],str(root),180,folder,2*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
        (folder/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');rows.append(dict(model=model,levels=levels,max_error=error,folder=folder.name,completed=r['exit_code']==0 and r['group_drained']));(root/'PROGRESS.json').write_text(json.dumps(rows,indent=2)+'\n')
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
(root/'SUMMARY.json').write_text(json.dumps(dict(rows=rows,inputs=hashes,unchanged=True),indent=2)+'\n');print(json.dumps(rows))
