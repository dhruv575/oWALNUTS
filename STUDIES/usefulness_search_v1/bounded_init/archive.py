import hashlib,io,json,tarfile
from pathlib import Path
root=Path('/dev/shm/bounded-init-20261030');files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and 'target' not in p.relative_to(root).parts and '__pycache__' not in p.parts};aliases={}
for manifest in [root/'run01/MANIFEST.json',root/'BUILD.json',root/'analysis01/INPUTS.json']:
 obj=json.loads(manifest.read_text());deps=obj.get('dependencies',obj.get('files',obj))
 for name,digest in deps.items():
  p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==digest,(manifest,name)
  key=str(p.relative_to(root)) if p.is_relative_to(root) else 'external/'+str(p).lstrip('/');files[key]=p;aliases[name]=key
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');modelnames=['earnings-logearn_interaction','hudson_lynx_hare-lotka_volterra','bball_drive_event_0-hmm_drive_0','mcycle_gp-accel_gp','radon_all-radon_hierarchical_intercept_centered']
for model in modelnames:
 for suffix in ['.data.json','.stan','_model.so']:
  p=models/(model+suffix);assert p.is_file();files['external/'+str(p).lstrip('/')]=p
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};dest=Path('/dev/shm/bounded-init-evidence-20261030.tar.gz')
with tarfile.open(dest,'x:gz') as tar:
 raw=json.dumps(dict(files=manifest,external_aliases=aliases),indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
 for n,p in sorted(files.items()):tar.add(p,arcname=n,recursive=False)
print(json.dumps(dict(bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),members=len(files))))
