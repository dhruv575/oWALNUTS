import hashlib,importlib.metadata,json,platform,shutil,sys,tarfile
from pathlib import Path
import bridgestan
from common import ROOT,MODELS,NAME
deps=ROOT/'dependencies';deps.mkdir(exist_ok=False);db=Path('/home/ubuntu/infra/posteriordb/posterior_database')
paths=[MODELS/(NAME+s) for s in ['_model.so','.data.json','.stan']]+[db/'reference_posteriors/draws/draws'/(NAME+'.json.zip'),db/'reference_posteriors/draws/info'/(NAME+'.info.json'),db/'data/info/gp_pois_regr.info.json',Path('/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source/resource_monitor.py')];mapping={}
for i,p in enumerate(paths):
 dest=deps/(str(i)+'-'+p.name);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(ROOT))
folder=Path(bridgestan.__file__).parent
for p in folder.rglob('*'):
 if p.is_file() and p.suffix in ('.py','.so','.pyi'):
  dest=deps/'bridgestan'/p.relative_to(folder);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);mapping[str(p)]=str(dest.relative_to(ROOT))
(deps/'SOURCE-PATHS.json').write_text(json.dumps(mapping,indent=2)+'\n');(deps/'ENVIRONMENT.json').write_text(json.dumps(dict(python=sys.version,platform=platform.platform(),packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}),indent=2)+'\n')
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc' and p.name!='EVIDENCE-MANIFEST.json');manifest={str(p.relative_to(ROOT)):dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files};(ROOT/'EVIDENCE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=Path('/dev/shm/gp-count-20261030-evidence.tar.gz');assert not archive.exists()
with tarfile.open(archive,'w:gz') as tar:
 tar.add(ROOT/'EVIDENCE-MANIFEST.json',arcname='EVIDENCE-MANIFEST.json')
 for p in files:tar.add(p,arcname=str(p.relative_to(ROOT)))
print(json.dumps(dict(archive=str(archive),members=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())))
