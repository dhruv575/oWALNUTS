import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['recycling_source03','compact_recycling_build01','compact_original_build01','compact_recycling_test01','compact_original_test01','compact_validation01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
for name in ['compact_recycling_test01','compact_original_test01','compact_validation01']:
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
assert json.loads((study/'COMPACT-VALIDATION-REPLAY.json').read_text())['passed']
for name in ['compact_recycling_runner','compact_original_runner']:
    for p in (study/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
for glob in ['*compact*.py','COMPACT-*']:
    for p in study.glob(glob):
        if p.is_file():files[p.name]=p
for n in ['RECYCLING-MSE-ANALYSIS.json','local_recovery/recycling_archive01/VERIFICATION.json','local_recovery/recycling_mse_archive01/VERIFICATION.json']:files[n]=study/n
for arm,b in json.loads((local/'compact_validation01/SUMMARY.json').read_text())['builds'].items():
    p=Path(b['binary']);assert hashlib.sha256(p.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+arm]=p
dest=local/'compact_validation_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local compact source snapshot, binaries, preflight and fresh evidence with per-member readback; earlier source/evidence archives remain dependencies, not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
