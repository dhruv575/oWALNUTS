import hashlib,json,shutil,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_widegrid_bundle01';r.mkdir(exist_ok=False)
for folder in ['runtime','models','data']:(r/folder).mkdir()
for n in ['gp_widegrid_worker.py','run_gp_widegrid.py','GP-WIDEGRID-REPAIR-PROTOCOL.md']:shutil.copyfile(p/n,r/n)
shutil.copyfile(l/'inputs/resource_monitor.py',r/'resource_monitor.py')
for n in ['common.py','conditional_v3.py','prepare_conditional_v3.py']:shutil.copyfile(l/'gp_conditional_local01'/n,r/'runtime'/n)
shutil.copyfile(p/'gp_conditional_confirmation_worker.py',r/'runtime/sample.py')
name='gp_pois_regr-gp_pois_regr';so=l/'threaded_targets01'/name/(name+'_model.so');shutil.copyfile(so,r/'models'/so.name)
for i in range(4):shutil.copyfile(l/f'gp_fresh_data01/scenario-{i}/DATA.json',r/f'data/{i}.json')
shutil.copyfile(l/'gp_fresh_reference01/SUMMARY.json',r/'REFERENCE.json')
manifest={str(f.relative_to(r)):hashlib.sha256(f.read_bytes()).hexdigest() for f in r.rglob('*') if f.is_file()};(r/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
for n in ['gp_widegrid_worker.py','run_gp_widegrid.py']:compile((r/n).read_text(),n,'exec')
with tarfile.open(l/'gp_widegrid_bundle01.tar.gz','w:gz') as t:
 for f in r.rglob('*'):
  if f.is_file():t.add(f,arcname=str(f.relative_to(r)),recursive=False)
print(json.dumps(dict(files=len(manifest),sha256=hashlib.sha256((l/'gp_widegrid_bundle01.tar.gz').read_bytes()).hexdigest())))
