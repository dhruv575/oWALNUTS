import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['recycling_mse01','recycling_mse_timing01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
assert json.loads((study/'RECYCLING-MSE-REPLAY.json').read_text())['passed']
for glob in ['*recycling_mse*.py','analyze_recycling_timing.py','RECYCLING-MSE-*']:
    for p in study.glob(glob):
        if p.is_file():files[p.name]=p
for n in ['local_recovery/recycling_archive01/VERIFICATION.json','local_recovery/funnel_cross_archive01/VERIFICATION.json']:files[n]=study/n
for arm,b in json.loads((local/'recycling_mse01/SUMMARY.json').read_text())['builds'].items():
    p=Path(b['binary']);assert hashlib.sha256(p.read_bytes()).hexdigest()==b['binary_sha256'];files['binary/'+arm]=p
dest=local/'recycling_mse_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local MSE and timing evidence, binaries, source/protocol/analysis with per-member readback; source snapshot archives remain dependencies, not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
