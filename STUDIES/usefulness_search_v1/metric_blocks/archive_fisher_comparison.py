import hashlib,json,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
assert json.loads((root/'VERIFICATION.json').read_text())['passed']
shutil.copy2(root.parent/'broad01/ENVIRONMENT.json',root/'ENVIRONMENT.json')
shutil.copy2(root.parent/'broad01/resource_monitor.py',root/'resource_monitor.py')
shutil.copy2(root.parent/'fisher04/mpmath-1.3.0-py3-none-any.whl',root/'mpmath-1.3.0-py3-none-any.whl')
shutil.copy2(root.parent/'broad01/SUMMARY.json',root/'PARENT-CONTROLS.json')
shutil.copy2(root.parent/'broad01/online-binary',root/'online-binary')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'fishercompare01-evidence.tar.gz';assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
