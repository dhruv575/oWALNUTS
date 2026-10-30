import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'threaded_targets01';summary=json.loads((root/'SUMMARY.json').read_text());assert summary['passed']
base=Path(json.loads((local/'threaded_build01/SUPERVISION.json').read_text())['build_directory']);release=local/'threaded_build01/bridgestan-2.9.0.tar.gz';build=json.loads((local/'threaded_build01/SUMMARY.json').read_text());assert hashlib.sha256(release.read_bytes()).hexdigest()==build['archive_sha256']
checked=0;source_bytes=0
with tarfile.open(release) as tar:
    for item in tar:
        if not item.isfile():continue
        raw=tar.extractfile(item).read();p=base/item.name;assert p.resolve().is_relative_to(base.resolve())
        assert p.read_bytes()==raw,f'Original release file changed: {item.name}'
        checked+=1;source_bytes+=len(raw)
(root/'TOOLCHAIN-AUDIT.json').write_text(json.dumps(dict(passed=True,unchanged_release_files=checked,source_bytes=source_bytes,release_sha256=build['archive_sha256']),indent=2)+'\n')
files={str(p.relative_to(root)):p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
for row in summary['rows']:
    folder=root/row['model'];s=json.loads((folder/'SUMMARY.json').read_text());sup=json.loads((folder/'SUPERVISION.json').read_text());assert s['passed'] and sup['exit_code']==0 and sup['group_drained']
    for i,(name,h) in enumerate(s['inputs'].items()):
        p=Path(name);assert hashlib.sha256(p.read_bytes()).hexdigest()==h;files[f'dependencies/{row["model"]}/{i}-{p.name}']=p
files['provenance/threaded_build01-VERIFICATION.json']=local/'threaded_build01_archive/VERIFICATION.json'
for p in [study/'run_threaded_targets.py',Path(__file__),local/'inputs/resource_monitor.py']:files['provenance/'+p.name]=p
dest=local/'threaded_targets01_archive';dest.mkdir(exist_ok=False);manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=dest/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('EVIDENCE-MANIFEST.json');info.size=len(raw);tar.addfile(info,io.BytesIO(raw))
    for n,p in files.items():tar.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as tar:
    for n,e in manifest.items():
        raw=tar.extractfile(n).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
r=dict(passed=True,members=len(manifest),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),unchanged_release_files=checked,scope='Local member read-back; no off-device/S3 backup.')
(dest/'VERIFICATION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
