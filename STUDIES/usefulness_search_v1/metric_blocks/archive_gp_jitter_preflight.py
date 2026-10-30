import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';s=json.loads((l/'gp_jitter_test02/SUMMARY.json').read_text());assert s['passed'];files={}
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
for dirname in ['gp_jitter_source01','gp_jitter_source02','gp_jitter_build01','gp_jitter_build02','gp_jitter_test01','gp_jitter_test02']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['gp_jitter_original_runner','gp_jitter_candidate_runner','gp_jitter_candidate02_runner']:
    for f in (p/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for n in ['prepare_gp_jitter.py','repair_gp_jitter.py','build_gp_jitter.py','build_gp_jitter02.py','test_gp_jitter.py','test_gp_jitter02.py','archive_gp_jitter_preflight.py','GP-JITTER-KERNEL.patch','GP-JITTER-KERNEL-02.patch','GP-JITTER-PREFLIGHT-PROTOCOL.md','GP-JITTER-PREFLIGHT-REPAIR.md','local_recovery/inputs/resource_monitor.py']:files[n]=p/n
for entry in s['build']:
    f=Path(entry['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==entry['binary_sha256'];files['binaries/'+f.name]=f
spec=json.loads((l/'gp_jitter_test02/dense-original/INPUT.json').read_text())
for key in ['model','data']:
    f=Path(spec[key]);files['model/'+f.name]=f
repo=p.parents[2]
for f in (repo/'src').rglob('*'):
    if f.is_file():files['original-source/'+str(f.relative_to(repo))]=f
for name in ['Cargo.toml','Cargo.lock']:files['original-source/'+name]=repo/name
out=l/'gp_jitter_preflight_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
