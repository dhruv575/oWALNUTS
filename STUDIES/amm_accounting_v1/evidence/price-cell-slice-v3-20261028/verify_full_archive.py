import hashlib,json,tarfile,io
from pathlib import Path
import numpy as np
p=Path('target/price-cell-slice-v3-full.tar.gz');digest=hashlib.sha256(p.read_bytes()).hexdigest()
assert digest=='deb423e060874fbc11e973b3bd75a43b8b301b080928ec6562920b74d876e47e'
prefix='price-cell-slice-long-v3-20261028/'
with tarfile.open(p) as t:
 files={m.name[len(prefix):]:t.extractfile(m).read() for m in t if m.isfile() and m.name.startswith(prefix)}
plan=json.loads(files['run01/PLAN.json']);report=json.loads(files['comparison01/REPORT.json'])
for name,h in plan['sources'].items():assert hashlib.sha256(files[name]).hexdigest()==h
for i in range(16):
 name=f'run01/job-{i}/fit/draws.npz';raw=files[name]
 assert hashlib.sha256(raw).hexdigest()==report['bindings']['/home/ubuntu/lanes/'+prefix+name]
 n=12 if i<8 else 250
 with np.load(io.BytesIO(raw)) as f:
  assert f['draws'].shape==(4000,3+2*n) and f['warmup'].shape==(1000,3+2*n)
  assert np.isfinite(f['draws']).all() and np.isfinite(f['warmup']).all()
base=Path('STUDIES/amm_accounting_v1/evidence/price-cell-slice-v3-20261028')
manifest={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in files.items()}
(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
result=dict(sha256=digest,bytes=p.stat().st_size,files=len(files),source_bindings_verified=True,all_16_draw_bindings_verified=True,all_shapes_finite=True)
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
