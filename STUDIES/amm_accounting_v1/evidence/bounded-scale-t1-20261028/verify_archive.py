from pathlib import Path
import tarfile,hashlib,json,io
import numpy as np
p=Path('target/bounded-scale-t1-full.tar.gz');h=hashlib.sha256(p.read_bytes()).hexdigest();assert h=='1cd8c558d7735cf13066730dbe6eb1f4938b3a965aa2b4bebe5472b82a3835ff'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-scale-t1-20261028');base.mkdir(exist_ok=False);prefix='bounded-scale-t1-20261028/'
with tarfile.open(p) as t:files={m.name[len(prefix):]:t.extractfile(m).read() for m in t if m.isfile() and m.name.startswith(prefix)}
plan=json.loads(files['run01/PLAN.json'])
for name,v in plan['sources'].items():assert hashlib.sha256(files[name]).hexdigest()==v
for j in range(3):
 report=json.loads(files[f'run01/job-{j}/fit/REPORT.json'])
 with np.load(io.BytesIO(files[f'run01/job-{j}/fit/reference.npz'])) as f:assert f['draws'].shape==(report['accepted'],4) and np.isfinite(f['draws']).all()
for n,raw in files.items():
 if n.endswith(('.npz','.nc')):continue
 dest=base/n;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
(base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps({n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in files.items()},indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(files),sources_verified=True,reference_shapes_and_finiteness_verified=True)
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
