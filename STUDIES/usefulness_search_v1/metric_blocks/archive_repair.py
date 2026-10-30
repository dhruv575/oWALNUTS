import hashlib,json,shutil,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;old=root.parent/'model01'
assert json.loads((root/'SUMMARY.json').read_text())['unchanged']
jobs=list((root/'runs').glob('*/SUPERVISION.json'));assert len(jobs)==16
assert all(json.loads(p.read_text())['group_drained'] for p in jobs)
receipt=json.loads((root/'PARENT-S3-VERIFICATION.json').read_text())
assert receipt['sha256']=='a745dac01daf953d60b6f52f19c22516f289ffd0a8e55b6b6e066bfc5df35b13' and receipt['verified_members']==408
# Reclaim only this verified duplicate on the capacity-constrained root disk.
duplicate=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/model01-evidence.tar.gz')
assert duplicate.resolve()==duplicate and duplicate.is_file()
assert hashlib.sha256(duplicate.read_bytes()).hexdigest()==receipt['sha256']
duplicate.unlink()
reclaim=dict(path=str(duplicate),bytes=receipt['bytes'],sha256=receipt['sha256'],
    exact_s3_version=receipt['version_id'],retained_tmpfs_original=str(old.parent/'model01-evidence.tar.gz'))
(root/'RECLAIM.json').write_text(json.dumps(reclaim,indent=2)+'\n')
shutil.copy2(root/'RECLAIM.json','/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/RECLAIM-model01.json')
for name in ['REFERENCES.json','ENVIRONMENT.json','resource_monitor.py']:
    shutil.copy2(old/name,root/name)
files=sorted(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='EVIDENCE-MANIFEST.json')
manifest={p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in files}
mp=root/'EVIDENCE-MANIFEST.json';mp.write_text(json.dumps(manifest,indent=2)+'\n')
out=root.parent/'model02-evidence.tar.gz';assert not out.exists()
with tarfile.open(out,'w:gz') as tar:
    tar.add(mp,arcname=mp.name)
    for p in files:tar.add(p,arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(files),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest())))
