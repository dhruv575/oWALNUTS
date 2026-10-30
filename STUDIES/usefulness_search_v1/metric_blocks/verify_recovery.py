import hashlib,json,shutil
from pathlib import Path
base=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030');root=base/'work/audit';old=base/'work/reconsider';deps=json.loads((old/'run01/MANIFEST.json').read_text())['dependencies'];verified={}
for name,digest in deps.items():
 p=Path(name);p=old/p.relative_to('/dev/shm/reconsider-20261029') if str(p).startswith('/dev/shm/reconsider-20261029/') else p
 assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,(name,str(p));verified[name]=digest
first=json.loads((root/'FIRST-ANALYSIS-EXPECTED.json').read_text());repeated=json.loads((root/'analysis01/ROWS.json').read_text());assert first==repeated
checks=[]
for run,analysis in [('run01','analysis01'),('run02','analysis02')]:
 final=json.loads((root/run/'FINAL.json').read_text());parity=json.loads((root/analysis/'PARITY.json').read_text());assert final['unchanged'] and len(parity)==12 and all(x['passed'] for x in parity) and all(j['exit_code']==0 and j['group_drained'] for j in final['jobs']);checks.append(dict(run=run,all_fields_except_wall_equal=True,jobs=len(parity)))
curvature=json.loads((root/'curvature01/SUPERVISION.json').read_text());assert curvature['exit_code']==0 and curvature['group_drained'] and curvature['unchanged']
shutil.copy2(base/'evidence/RESTORE.json',root/'RESTORE.json');r=dict(passed=True,baseline_dependencies_verified=verified,first_analysis_reproduced_exactly=True,audits=checks,curvature_recomputed=True,initial_raw_curvature_lost=True,independent_replication=False)
(root/'RECOVERY-VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');shutil.copy2(root/'RECOVERY-VERIFICATION.json',base/'evidence/RECOVERY-VERIFICATION.json');print(json.dumps(r))
