from pathlib import Path
import os,hashlib,json,tarfile
root=Path('/home/ubuntu/lanes/unified-readiness-20261027')
previous=root/'ARCHIVE-MANIFEST.json'
if previous.exists():(root/'ARCHIVE-MANIFEST01.json').write_bytes(previous.read_bytes())
files=[]
for current,dirs,names in os.walk(root):
 p=Path(current)
 if p==root/'installation02/work':dirs[:]=[d for d in dirs if d not in ('env','tmp','pip-cache')]
 for name in names:
  f=p/name
  if f.is_file() and f.name!='ARCHIVE-MANIFEST.json':files.append(f)
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(root/'ARCHIVE-MANIFEST.json').write_text(json.dumps(manifest,indent=2))
archive=root.parent/'unified-readiness-20261027-evidence02.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for f in files+[root/'ARCHIVE-MANIFEST.json']:tar.add(f,arcname=str(f.relative_to(root)))
print(len(files),hashlib.sha256(archive.read_bytes()).hexdigest(),archive.stat().st_size)
