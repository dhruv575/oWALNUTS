"""Run remotely: stream an evidence archive without allocating a second EC2 copy."""
import hashlib,json,sys,tarfile
from pathlib import Path

root=Path(sys.argv[1])
files=sorted(p for p in root.rglob('*') if p.is_file() and not any(x in ('cache','__pycache__') for x in p.relative_to(root).parts) and p.name!='EVIDENCE-MANIFEST.json')
manifest={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=hashlib.file_digest(p.open('rb'),'sha256').hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(dict(manifest_sha256=hashlib.file_digest(mp.open('rb'),'sha256').hexdigest(),members=len(files))),file=sys.stderr,flush=True)
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz',compresslevel=1) as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root))
