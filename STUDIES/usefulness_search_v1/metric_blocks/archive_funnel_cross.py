import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['funnel_cross01','funnel_cross_build01','funnel_cross_test01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(study))]=p
s=json.loads((local/'funnel_cross01/SUMMARY.json').read_text());assert s['unchanged']
for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
for r in s['rows']:assert json.loads((local/'funnel_cross01'/r['folder']/'SUPERVISION.json').read_text())['group_drained']
assert json.loads((study/'FUNNEL-CROSS-REPLAY.json').read_text())['passed']
for p in (study/'funnel_cross_runner').rglob('*'):
    if p.is_file():files[str(p.relative_to(study))]=p
for glob in ['*funnel_cross*.py','FUNNEL-CROSS-*']:
    for p in study.glob(glob):
        if p.is_file():files[p.name]=p
# Keep exact analytic functions and the source pilot archive receipt as dependencies.
for n in ['analyze_funnel_error_guard.py','FUNNEL-ERROR-GUARD-PROTOCOL.md','local_recovery/funnel_error_guard_archive01/VERIFICATION.json']:files[n]=study/n
build=json.loads((local/'funnel_cross_build01/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256'];files['binary/runner']=binary
dest=local/'funnel_cross_archive01';dest.mkdir(exist_ok=False);archive=dest/'evidence.tar.gz';manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local source/binary/raw-draw evidence and per-member readback; prior pilot archive remains a dependency, not off-device backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
