import hashlib,json,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent
assert json.loads((root/'SUPERVISION.json').read_text())['group_drained']
models=Path('/home/ubuntu/lanes/metric_autoselect_confirmation_v1/models')
for suffix in ['.stan','.data.json','_model.so']:
    shutil.copy2(models/('sblrc-blr'+suffix),root/('sblrc-blr'+suffix))
shutil.copy2(root.parent/'broad01/REFERENCES.json',root/'REFERENCES.json')
shutil.copy2(root.parent/'broad01/ENVIRONMENT.json',root/'ENVIRONMENT.json')
shutil.copy2(root.parent/'broad01/resource_monitor.py',root/'resource_monitor.py')
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'collapsed01-evidence.tar.gz';assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
