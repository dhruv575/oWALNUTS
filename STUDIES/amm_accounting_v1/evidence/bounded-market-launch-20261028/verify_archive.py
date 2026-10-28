from pathlib import Path
import hashlib,json,tarfile
p=Path('target/bounded-market-launch.tar.gz')
with p.open('rb') as f:h=hashlib.file_digest(f,'sha256').hexdigest()
assert h=='919d46066fbf8326d7f63d78235c24fe57d741256db5c931138c28c73bd4c398'
base=Path('STUDIES/amm_accounting_v1/evidence/bounded-market-launch-20261028');base.mkdir(exist_ok=False)
prefix='bounded-market-20261028/';files={};manifest={}
with tarfile.open(p) as t:
 for m in t:
  if not m.isfile():continue
  assert m.name.startswith(prefix)
  name=m.name[len(prefix):];assert not name.startswith('batch-')
  raw=t.extractfile(m).read();manifest[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
  dest=base/name;assert dest.resolve().is_relative_to(base.resolve());dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[name]=raw
freeze=json.loads(files['FREEZE.json'])
for name,digest in freeze['sources'].items():assert manifest[name.split('/bounded-market-20261028/')[1]]['sha256']==digest
assert manifest['SEED-AUDIT.json']['sha256']==freeze['seed_audit_sha256']
audit=json.loads(files['SEED-AUDIT.json']);assert audit['proposed']==list(range(398141000,398142152)) and not audit['collisions']
amend=json.loads(files['prelaunch-failure/AMENDMENT.json'])
assert manifest['prelaunch-failure/FREEZE.json']['sha256']==amend['old_freeze_sha256']
assert manifest['prelaunch-failure/bounded_market_supervisor.py']['sha256']==amend['old_source_sha256']
assert manifest['source/STUDIES/amm_accounting_v1/bounded_market_supervisor.py']['sha256']==amend['new_source_sha256']
assert b'Ran 1 test' in files['ORCHESTRATION-TEST.log'] and b'OK' in files['ORCHESTRATION-TEST.log']
(base/'.gitattributes').write_text('* -text\n');(base/'FULL-MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
r=dict(sha256=h,bytes=p.stat().st_size,files=len(manifest),frozen_sources_and_seed_reservation_verified=True,prelaunch_amendment_verified=True,scope='Launch and prepared-input evidence only; active batch outputs excluded')
(base/'ARCHIVE-VERIFIED.json').write_text(json.dumps(r,indent=2)+'\n');(base/'verify_archive.py').write_bytes(Path(__file__).read_bytes());print(r)
