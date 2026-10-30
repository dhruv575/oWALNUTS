import hashlib,io,json,tarfile
from pathlib import Path
roots={name:Path(path) for name,path in [('analytic','/dev/shm/population-analytic-20261029'),('reference','/dev/shm/population-analytic-reference-20261029'),('importance-failed','/dev/shm/population-importance-20261029'),('importance-repaired','/dev/shm/population-importance-repaired-20261029'),('native','/dev/shm/population-native-confirm-20261030')]}
files={};aliases={}
for label,root in roots.items():
 for p in root.rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:files[label+'/'+str(p.relative_to(root))]=p
manifests=[roots['analytic']/'ANALYTIC-INPUTS.json',roots['native']/'COMPARISON-INPUTS.json']+[root/'run01/MANIFEST.json' for label,root in roots.items() if label!='analytic']
for path in manifests:
 obj=json.loads(path.read_text());deps=obj.get('dependencies',obj)
 for name,digest in deps.items():
  p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,(path,name)
  key=next((label+'/'+str(p.relative_to(root)) for label,root in roots.items() if p.is_relative_to(root)),None)
  if key is None:key='external/'+str(p).lstrip('/');files[key]=p
  aliases[name]=key
for name in ['native.py','population.cpp']:
 p=Path('/dev/shm/population-jumps-20261029')/name;files['prior-backend/'+name]=p
manifest={name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in files.items()};dest=Path('/dev/shm/population-qualified-evidence-20261030.tar.gz')
with tarfile.open(dest,'x:gz') as tar:
 raw=json.dumps(dict(files=manifest,external_aliases=aliases),indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
 for name,p in sorted(files.items()):tar.add(p,arcname=name,recursive=False)
print(json.dumps(dict(bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),members=len(files))))
