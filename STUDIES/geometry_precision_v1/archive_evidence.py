"""Freeze all completed study evidence; omit disposable interpreter caches."""
import hashlib,json,sys,tarfile
from pathlib import Path

root=Path(sys.argv[1]);out=Path(sys.argv[2])
files=sorted(p for p in root.rglob('*') if p.is_file() and not any(x in ('cache','__pycache__') for x in p.relative_to(root).parts) and p.name not in ('EVIDENCE-MANIFEST.json',out.name))
manifest={str(p.relative_to(root)).replace('\\','/'):dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
with tarfile.open(out,'w:gz',compresslevel=1) as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root))
print(json.dumps(dict(bytes=out.stat().st_size,sha256=hashlib.file_digest(out.open('rb'),'sha256').hexdigest(),members=len(files))))
