import hashlib,importlib.metadata,json,platform,shutil,subprocess,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;deps=root/'dependencies';deps.mkdir(exist_ok=False);old=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work/reconsider');models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models');manifest=json.loads((root/'run01/MANIFEST.json').read_text());mapping={}
paths=[old/'BUILD.json',old/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb',Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py')]
paths += [old/'run01'/f"{j['original_index']:03d}"/'RESULT.json' for j in manifest['jobs']]
paths += [models/(m+s) for m in sorted({j['model'] for j in manifest['jobs']}) for s in ['_model.so','.data.json','.stan']]
for i,p in enumerate(paths):
 dest=deps/(str(i)+'-'+p.name);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(root))
for name in ['source','source2']:
 p=root/name/'STUDIES/metric_autoselect_confirmation_v1/target/release/pdb';dest=deps/(name+'-pdb');shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(root))
(deps/'SOURCE-PATHS.json').write_text(json.dumps(mapping,indent=2)+'\n');(deps/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),rustc=subprocess.check_output(['/home/ubuntu/.cargo/bin/rustc','--version'],text=True).strip(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in root.rglob('*') if p.is_file() and not any(x in p.relative_to(root).parts for x in ['target','__pycache__']) and p.suffix!='.pyc' and p.name!='EVIDENCE-MANIFEST.json');inventory={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files};(root/'EVIDENCE-MANIFEST.json').write_text(json.dumps(inventory,indent=2)+'\n');archive=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work/audit-evidence.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
 tar.add(root/'EVIDENCE-MANIFEST.json',arcname='EVIDENCE-MANIFEST.json')
 for p in files:tar.add(p,arcname=str(p.relative_to(root)))
print(json.dumps(dict(archive=str(archive),members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
