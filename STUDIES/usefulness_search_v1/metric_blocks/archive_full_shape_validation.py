import hashlib,importlib.metadata,json,platform,shutil,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
summary=json.loads((root/'SUMMARY.json').read_text());assert summary['unchanged'] and len(summary['rows'])==80
jobs=list((root/'runs').glob('*/SUPERVISION.json'));assert 16<=len(jobs)<=96
assert all(json.loads(p.read_text())['group_drained'] for p in jobs)
deps=root/'dependencies';deps.mkdir(exist_ok=False)
for i,(name,digest) in enumerate(summary['inputs'].items()):
    p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
    shutil.copy2(p,deps/(str(i)+'-'+p.name))
shutil.copy2(root.parent/'model01/source/STUDIES/metric_autoselect_confirmation_v1/src/bin/online.rs',deps/'online.rs')
shutil.copy2('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py',deps/'resource_monitor.py')
(deps/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'fullshape02-evidence.tar.gz';assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(jobs=len(jobs),members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
