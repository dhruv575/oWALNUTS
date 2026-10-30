"""Snapshot candidate study, binaries, source and external dependencies."""
import hashlib,json,tarfile
from pathlib import Path
root=Path('/dev/shm/population-pk-20261029');dest=Path('/dev/shm/population-pk-evidence.tar.gz')
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and 'target' not in p.relative_to(root).parts and '__pycache__' not in p.parts}
aliases={}
for p in [root/'run01/MANIFEST.json',root/'analysis01/INPUT-HASHES.json']:
 d=json.loads(p.read_text());deps=d.get('dependencies',d)
 for name,digest in deps.items():
  path=Path(name)
  assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,(p,name)
  if not path.is_relative_to(root):
   key='external/'+str(path).lstrip('/');files[key]=path;aliases[name]=key
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
import io
with tarfile.open(dest,'x:gz') as tar:
 raw=json.dumps(dict(files=manifest,external_aliases=aliases),indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
 for n,p in sorted(files.items()):tar.add(p,arcname=n,recursive=False)
print(json.dumps(dict(sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size,members=len(files))))
