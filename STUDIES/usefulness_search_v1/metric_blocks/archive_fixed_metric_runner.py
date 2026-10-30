import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';repo=study.parents[2];files={}
for name in ['fixed_metric_build01','fixed_metric_build02','fixed_metric_test01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(local))]=p
assert json.loads((local/'fixed_metric_test01/SUMMARY.json').read_text())['passed']
build=json.loads((local/'fixed_metric_build02/SUMMARY.json').read_text());binary=Path(build['binary']);assert hashlib.sha256(binary.read_bytes()).hexdigest()==build['binary_sha256'];files['binary/runner']=binary
for directory in [study/'fixed_metric_runner',repo/'src',repo/'integrations/bridgestan/src']:
    for p in directory.rglob('*'):
        if p.is_file():files['repository/'+str(p.relative_to(repo))]=p
for p in [repo/'Cargo.toml',repo/'Cargo.lock',repo/'integrations/bridgestan/Cargo.toml',study/'build_fixed_metric_runner.py',study/'test_fixed_metric_runner.py',Path(__file__)]:files['repository/'+str(p.relative_to(repo))]=p
root=local/'fixed_metric_runner_archive01';root.mkdir(exist_ok=False)
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=root/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local source/binary/evidence read-back, not off-device backup.')
(root/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
