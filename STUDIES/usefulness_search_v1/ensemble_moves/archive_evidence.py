import hashlib,importlib.metadata,json,platform,shutil,subprocess,sys,tarfile
from pathlib import Path
import owalnuts,bridgestan
root=Path(__file__).resolve().parent;deps=root/'dependencies';deps.mkdir(exist_ok=False)
paths=[Path('/dev/shm/bounded-init-20261030/run01/012/RESULT.json'),Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py')]
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');name='hudson_lynx_hare-lotka_volterra'
paths += [models/(name+s) for s in ['_model.so','.data.json','.stan']]
mapping={}
for i,p in enumerate(paths):
 dest=deps/(str(i)+'-'+p.name);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(root))
for package in [owalnuts,bridgestan]:
 folder=Path(package.__file__).parent
 for p in folder.rglob('*'):
  if p.is_file() and p.suffix in ('.py','.so','.pyi'):
   dest=deps/package.__name__/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(root))
(deps/'SOURCE-PATHS.json').write_text(json.dumps(mapping,indent=2)+'\n')
(deps/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='EVIDENCE-MANIFEST.json')
manifest={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
(root/'EVIDENCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/dev/shm/ensemble-moves-20261030-evidence.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
 tar.add(root/'EVIDENCE-MANIFEST.json',arcname='EVIDENCE-MANIFEST.json')
 for p in files:tar.add(p,arcname=str(p.relative_to(root)))
print(json.dumps(dict(archive=str(archive),members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
