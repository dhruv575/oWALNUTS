from pathlib import Path
import hashlib,json,tarfile,io
import numpy as np
p=Path('target/bounded-walnuts-full.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='ee81e19134b99ce214545676f3d17e2480b57914b4f3d01e0c21bfeb033f1a22'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-walnuts-20261028');base.mkdir(exist_ok=False)
prefix='bounded-walnuts-20261028/';files={};manifest={}
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  name=m.name[len(prefix):];raw=t.extractfile(m).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if '/__pycache__/' in name or '/runtime-cache/' in name:continue
  if name.endswith('.npz'):
   if name.endswith('draws.npz'):
    j=int(name.split('/')[1].split('-')[1]);n=12 if j%3==0 else 250
    with np.load(io.BytesIO(raw)) as f:
     assert f['draws'].shape==(4,4000,n+3) and np.isfinite(f['draws']).all()
     assert f['divergent'].shape==(4,6000) and f['depth'].shape==(4,6000)
   continue
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
for receipt in ['run01/PLAN.json','NATIVE-PARITY.json']:
 for name,digest in json.loads(files[receipt])['sources'].items():assert manifest[name]['sha256']==digest
results=json.loads(files['run01/FINAL.json']);success=[r['index'] for r in results if r['exit_code']==0]
assert success==[0,2,3,6] and all(r['group_drained'] for r in results)
outer=json.loads(files['run01/SUPERVISION.json']);assert outer['exit_code']==1 and outer['sources_unchanged'] and outer['group_drained']
(base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),sources_verified=True,successful_draw_shapes_verified=True,successful_fit_indices=success,failed_fit_indices=[1,4,5,7,8],all_groups_drained=True)
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
