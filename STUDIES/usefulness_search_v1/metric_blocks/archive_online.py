import hashlib, importlib.metadata, json, platform, shutil, sys, tarfile
from pathlib import Path
root = Path(__file__).resolve().parent
assert json.loads((root/'SUMMARY.json').read_text())['unchanged']
jobs = list((root/'runs').glob('*/SUPERVISION.json'))
assert len(jobs) == 32
for p in jobs:
    r = json.loads(p.read_text()); assert r['exit_code']==0 and r['group_drained']
shutil.copy2('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py', root/'resource_monitor.py')
shutil.copy2(root/'source/STUDIES/metric_autoselect_confirmation_v1/target/release/online', root/'online-binary')
(root/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version, platform=platform.platform(),
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in root.rglob('*') if p.is_file() and
    not any(x in p.relative_to(root).parts for x in ['target','__pycache__']) and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'online01-evidence.tar.gz'; assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
shutil.copy2(out, '/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/online01-evidence.tar.gz')
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
