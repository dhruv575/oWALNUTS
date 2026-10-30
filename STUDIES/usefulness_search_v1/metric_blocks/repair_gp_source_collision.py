from pathlib import Path
import subprocess,hashlib,json
p=Path(__file__).resolve().parent
c=p/'local_recovery/gp_newdata_source_collision01'
assert json.loads((p/'local_recovery/gp_newdata_comparison_archive01/VERIFICATION.json').read_text())['passed']
names=['gp_fresh_comparison_worker.py','GP-FRESH-COMPARISON-PROTOCOL.md','run_gp_newdata_comparison.py','prepare_gp_fresh_comparison.py','archive_gp_newdata_comparison.py']
mapping={}
for name in names:
    b=(p/name).read_bytes();(c/('executed-'+name)).write_bytes(b);mapping[name]=dict(preserved='executed-'+name,sha256=hashlib.sha256(b).hexdigest())
for old,new in [('gp_fresh_comparison_worker.py','gp_newdata_comparison_worker.py'),('GP-FRESH-COMPARISON-PROTOCOL.md','GP-NEWDATA-COMPARISON-PROTOCOL.md')]:
    (p/new).write_bytes((p/old).read_bytes())
    relative=str((p/old).relative_to(p.parents[2])).replace('\\','/')
    original=subprocess.check_output(['git','-C',str(p),'show','a74dd1be:'+relative])
    (p/old).write_bytes(original)
    mapping[old]['restored_git_sha256']=hashlib.sha256(original).hexdigest()
for name in ['gp_newdata_comparison_worker.py','run_gp_newdata_comparison.py','prepare_gp_fresh_comparison.py']:
    s=(p/name).read_text().replace('gp_fresh_comparison_worker.py','gp_newdata_comparison_worker.py').replace('GP-FRESH-COMPARISON-PROTOCOL.md','GP-NEWDATA-COMPARISON-PROTOCOL.md')
    (p/name).write_text(s)
(c/'RESTORATION.json').write_text(json.dumps(dict(passed=True,original_revision='a74dd1be',mapping=mapping,note='Archive contains exact executed sources. Relocated sources have updated path references for future reproduction and were not executed in this batch.'),indent=2)+'\n')
print('Restored historical files; preserved exact executed sources and provenance.')
