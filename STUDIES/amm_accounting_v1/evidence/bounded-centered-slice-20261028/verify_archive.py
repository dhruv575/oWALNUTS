from pathlib import Path
import hashlib,json,tarfile,io
import numpy as np
p=Path('target/bounded-centered-slice-full.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='9f34f40c98d007ccc3f013aaa2418d5e3fe15d16d97420d97eb3b1985211dbbc'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-centered-slice-20261028');base.mkdir(exist_ok=False)
prefix='bounded-centered-slice-20261028/';files={};manifest={}
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  name=m.name[len(prefix):];raw=t.extractfile(m).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if '/__pycache__/' in name or '/runtime-cache/' in name:continue
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
plan=json.loads(files['run01/PLAN.json'])
for name,digest in plan['sources'].items():assert manifest[name]['sha256']==digest
for j in range(12):
 with np.load(io.BytesIO(files[f'run01/job-{j}/fit/draws.npz'])) as f:
  assert f['warmup'].shape==(1000,15) and f['draws'].shape==(4000,15)
  assert all(np.isfinite(f[k]).all() for k in f.files)
r=json.loads(files['comparison/COMPARISON.json']);ref=json.loads(files['FULL-MANIFEST.json'])
assert hashlib.sha256(files['compare_bounded_rescaled_slice.py']).hexdigest()==r['source_sha256']
assert manifest['FULL-MANIFEST.json']['sha256']==r['reference_manifest_sha256']
for name,digest in r['inputs'].items():
 if name=='FULL-MANIFEST.json' or name.startswith('run01/'):
  assert manifest[name]['sha256']==digest
 else:
  relative=name.split('/bounded-rescaled-20261028/')[1];assert ref[relative]['sha256']==digest
outer=json.loads(files['run01/SUPERVISION.json']);assert outer['sources_unchanged'] and outer['group_drained'] and outer['exit_code']==0
(base/'.gitattributes').write_text('* -text\n')
(base/'ARCHIVE-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),sources_and_comparison_inputs_verified=True,all_twelve_array_shapes_and_finiteness_verified=True,full_small_draws_preserved=True)
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
