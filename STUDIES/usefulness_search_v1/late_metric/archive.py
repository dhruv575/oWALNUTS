"""Snapshot both attempts, binaries, source and external dependencies."""
import hashlib,json,tarfile
from pathlib import Path
root=Path('/dev/shm/late-metric-20261029');dest=Path('/dev/shm/late-metric-evidence.tar.gz')
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and 'target' not in p.relative_to(root).parts and '__pycache__' not in p.parts}
binary=root/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb';files['repaired-pdb']=binary
aliases={str(binary):'repaired-pdb'}
for p in [root/'run01/MANIFEST.json',root/'run02/MANIFEST.json',root/'analysis02/INPUT-HASHES.json']:
 d=json.loads(p.read_text());deps=d.get('dependencies',d)
 for name,digest in deps.items():
  path=Path(name)
  if name==str(binary) and 'run01' in str(p):path=root/'original-pdb'
  if name==str(root/'prepare.py') and 'run01' in str(p):pass
  assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,(p,name)
  if not path.is_relative_to(root):
   key='external/'+str(path).lstrip('/');files[key]=path;aliases[name]=key
files['source-archive.tar']=Path('/dev/shm/late-metric-source.tar')
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
import io
with tarfile.open(dest,'x:gz') as tar:
 raw=json.dumps(dict(files=manifest,external_aliases=aliases,original_binary_alias='original-pdb'),indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
 for n,p in sorted(files.items()):tar.add(p,arcname=n,recursive=False)
print(json.dumps(dict(sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size,members=len(files))))
