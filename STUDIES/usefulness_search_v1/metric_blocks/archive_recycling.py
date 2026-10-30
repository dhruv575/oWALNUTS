import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['recycling_source01','recycling_source02','recycling_build01','recycling_build02','recycling_build03','recycling_test01','recycling_test02']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
s=json.loads((local/'recycling_test02/SUMMARY.json').read_text());assert s['passed'] and s['unchanged']
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
assert json.loads((study/'RECYCLING-PREFLIGHT-REPLAY.json').read_text())['passed']
old=json.loads((local/'recycling_build02/SUMMARY.json').read_text());assert hashlib.sha256((local/'recycling_build02/EXECUTED-runner').read_bytes()).hexdigest()==old['binary_sha256']
for p in (study/'recycling_runner').rglob('*'):
    if p.is_file():files[str(p.relative_to(study))]=p
for glob in ['*recycling*.py','RECYCLING-*']:
    for p in study.glob(glob):
        if p.is_file():files[p.name]=p
build=json.loads((local/'recycling_build03/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256'];files['binary/corrected-runner']=binary
dest=local/'recycling_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local initial/corrected source snapshots, binaries, failed and passing evidence with per-member readback; not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
