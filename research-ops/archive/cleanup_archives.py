"""Remove only byte-identical archive copies with completed S3 restore receipts."""
import argparse,hashlib,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('manifest');p.add_argument('receipt');a=p.parse_args()
records=json.loads(Path(a.manifest).read_bytes());base=Path('/home/ubuntu/lanes').resolve()
if len(records)!=9:raise ValueError('Expected fixed nine-archive batch')
paths=[]
for r in records:
 path=Path(r['remote_path'])
 if path.is_symlink() or not path.resolve().is_relative_to(base) or not path.name.endswith('.tar.gz'):raise ValueError('Unsafe path')
 if not r['verified'] or r['sha256']!=r['restored_sha256'] or not r['version_id']:raise ValueError('No verified restoration')
 if path.stat().st_size!=r['bytes'] or hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=r['sha256']:raise ValueError('Remote archive mismatch')
 paths.append(path)
with Path(a.receipt).open('x') as f:
 deleted=[]
 for path,r in zip(paths,records):
  # Recheck immediately before deletion; files are completed, immutable artifacts.
  with path.open('rb') as src:
   if hashlib.file_digest(src,'sha256').hexdigest()!=r['sha256']:raise ValueError('File changed')
  path.unlink();deleted.append(r)
 json.dump(dict(deleted=deleted,total_bytes=sum(r['bytes'] for r in deleted)),f,indent=2)
print(json.dumps(dict(deleted=len(deleted),bytes=sum(r['bytes'] for r in deleted))))
