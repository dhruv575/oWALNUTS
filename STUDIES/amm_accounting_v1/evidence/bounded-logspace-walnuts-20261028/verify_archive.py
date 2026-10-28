from pathlib import Path
import hashlib,json,tarfile,io
import numpy as np
p=Path('target/bounded-logspace-walnuts-full.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='c6b3f9a0650331550f5dce80afe6181ec49fb9f600c354b9bb796b2065748faa'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-logspace-walnuts-20261028');base.mkdir(exist_ok=False)
prefix='bounded-logspace-walnuts-20261028/';files={};manifest={}
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
     assert not f['divergent'].any() and not (f['depth'][:,2000:]>=10).any()
   continue
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
for receipt in ['run01/PLAN.json','NATIVE-PARITY.json']:
 for name,digest in json.loads(files[receipt])['sources'].items():assert manifest[name]['sha256']==digest
results=json.loads(files['run01/FINAL.json']);assert len(results)==9 and all(r['exit_code']==0 and r['group_drained'] for r in results)
outer=json.loads(files['run01/SUPERVISION.json']);assert outer['exit_code']==0 and outer['sources_unchanged'] and outer['group_drained']
comparison=json.loads(files['comparison/COMPARISON.json']);catalog=json.loads(files['bounded-reference-manifests.json'])
assert manifest['bounded-reference-manifests.json']['sha256']==comparison['manifest_catalog_sha256']
assert manifest['compare_bounded_walnuts.py']['sha256']==comparison['source_sha256']
for name,digest in comparison['inputs'].items():
 if name.startswith('run01/'):assert manifest[name]['sha256']==digest
 else:
  lane,relative=name.split('/home/ubuntu/lanes/')[1].split('/',1);assert catalog[lane][relative]['sha256']==digest
assert len(comparison['rows'])==18
assert all(not r['walnuts_failed'] and not r['reference_failed'] and not r['flags_over_4'] for r in comparison['rows'])
(base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),sources_and_comparison_bindings_verified=True,all_nine_draw_shapes_and_event_counts_verified=True,all_eighteen_summary_comparisons_pass=True,scope='Coordinate summaries used for cross-method comparison; not a fresh raw-draw ArviZ recomputation')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
