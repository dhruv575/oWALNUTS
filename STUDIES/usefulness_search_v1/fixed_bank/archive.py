import hashlib,importlib.metadata,json,platform,shutil,sys,tarfile
from pathlib import Path
import owalnuts
root=Path(__file__).resolve().parent;deps=root/'dependencies';deps.mkdir(exist_ok=False)
monitor=Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py');shutil.copy2(monitor,deps/'resource_monitor.py')
folder=Path(owalnuts.__file__).parent;mapping={str(monitor):'dependencies/resource_monitor.py'}
for p in folder.rglob('*'):
 if p.is_file() and p.suffix in ('.py','.so','.pyi'):
  dest=deps/'owalnuts'/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(root))
(deps/'SOURCE-PATHS.json').write_text(json.dumps(mapping,indent=2)+'\n')
(deps/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='EVIDENCE-MANIFEST.json')
manifest={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files};(root/'EVIDENCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/dev/shm/fixed-bank-20261030-evidence.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
 tar.add(root/'EVIDENCE-MANIFEST.json',arcname='EVIDENCE-MANIFEST.json')
 for p in files:tar.add(p,arcname=str(p.relative_to(root)))
print(json.dumps(dict(archive=str(archive),members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
