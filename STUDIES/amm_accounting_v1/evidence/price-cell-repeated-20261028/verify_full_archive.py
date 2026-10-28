from pathlib import Path
import hashlib,json,tarfile
p=Path('target/price-cell-repeated-full.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='93171d0d89e12cf5e22e868d8613b260220fea68a02e9e47677c7b4ff71ac0b7'
manifest={};prefix='price-cell-repeated-20261028/';plan=None
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix);name=m.name[len(prefix):];raw=t.extractfile(m).read()
  manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if name=='run01/PLAN.json':plan=json.loads(raw)
for name,v in plan['sources'].items():assert manifest[name]['sha256']==v
for j in range(4):
 for u in range(3):
  for name in ('warm-draws.npz','cold.nc','WARM.json','fixture.npz'):assert f'run01/job-{j}/fit/update-{u}/{name}' in manifest
base=Path('STUDIES/amm_accounting_v1/evidence/price-cell-repeated-20261028')
(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),source_bindings_verified=True,all_twelve_pairs_present=True)
(base/'FULL-ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');print(r)
