from pathlib import Path
import hashlib,json,tarfile,io
import numpy as np
p=Path('target/bounded-market-preparation.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='f6b06c47d6262c15f550b1dd0b46f757b932dc0344b1f8f8549b25e04c9c5527'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-market-preparation-20261028');base.mkdir(exist_ok=False)
files={};manifest={};prefix='bounded-market-20261028/'
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  name=m.name[len(prefix):];raw=t.extractfile(m).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  if '/__pycache__/' in name:continue
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
r=json.loads(files['fixtures/PREPARATION.json'])
for name,v in r['files'].items():assert manifest['fixtures/'+name]==v
for name,digest in r['sources'].items():
 if '/bounded-market-20261028/' in name:
  relative=name.split('/bounded-market-20261028/')[1];assert manifest[relative]['sha256']==digest
rows=json.loads(files['fixtures/FIXTURES.json']);labels=json.loads(files['fixtures/LABELS.json']);scores=json.loads(files['fixtures/BASELINES.json'])
assert len(rows)==24 and len(labels)==24 and len(scores)==72
for row,label in zip(rows,labels):
 assert row['index']==label['index'] and row['label_index']==250+row['tick']
 with np.load(io.BytesIO(files['fixtures/returns-'+row['month']+'.npz'])) as f:y=f['y']
 with np.load(io.BytesIO(files['fixtures/'+row['fixture']])) as f:
  assert np.array_equal(f['history'],y[:row['label_index']])
  assert np.array_equal(f['window'],y[row['tick']:row['label_index']])
  assert f['window'].shape==(250,) and np.isfinite(f['window']).all()
 assert label['label']==float(y[row['label_index']])
 assert row['label_available_ms']-row['origin_ms']==1800000
assert all(s['fit']['status']=='ok' and s['score'] is not None for s in scores)
assert b'Ran 14 tests' in files['TESTS.log'] and b'OK' in files['TESTS.log']
(base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),fixture_labels_and_causal_slices_verified=True,baseline_slots=72,origins=24,scope='Remote raw acquisition verified by bound data_contract; local verification of prepared arrays and provenance, no candidate scores')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
