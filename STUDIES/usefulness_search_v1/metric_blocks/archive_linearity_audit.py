import hashlib,json,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
assert json.loads((root/'SUPERVISION.json').read_text())['group_drained']
s=json.loads((root/'SUMMARY.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in s['inputs'].items())
shutil.copy2('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py',root/'resource_monitor.py')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'linearity01-evidence.tar.gz';assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
