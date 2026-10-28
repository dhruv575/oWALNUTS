"""One-time pre-sampling manifest amendment for a verified path-type bug."""
from pathlib import Path
import hashlib,json
lane=Path('/home/ubuntu/lanes/bounded-market-20261028');backup=lane/'prelaunch-failure'
assert not list(lane.glob('batch-*'))
file=lane/'source/STUDIES/amm_accounting_v1/bounded_market_supervisor.py'
old=(backup/file.name).read_bytes();new=file.read_bytes()
assert old.replace(b"if sha(file)!=digest:",b"if sha(Path(file))!=digest:")==new
raw=(lane/'FREEZE.json').read_bytes();assert raw==(backup/'FREEZE.json').read_bytes()
r=json.loads(raw)
for name,digest in r['sources'].items():
    if name!=str(file):assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==digest
assert hashlib.sha256(old).hexdigest()==r['sources'][str(file)]
assert hashlib.sha256((lane/'SEED-AUDIT.json').read_bytes()).hexdigest()==r['seed_audit_sha256']
receipt=dict(reason='Prelaunch AttributeError: binary path string passed to Path-only sha helper',old_freeze_sha256=hashlib.sha256(raw).hexdigest(),old_source_sha256=hashlib.sha256(old).hexdigest(),new_source_sha256=hashlib.sha256(new).hexdigest(),batch_directories_absent=True,sampling_not_started=True,seed_audit_unchanged=True)
r['sources'][str(file)]=receipt['new_source_sha256'];r['prelaunch_amendment']=receipt
(lane/'FREEZE.json').write_text(json.dumps(r,indent=2)+'\n')
with (backup/'AMENDMENT.json').open('x') as f:json.dump(receipt,f,indent=2);f.write('\n')
print(json.dumps(receipt))
