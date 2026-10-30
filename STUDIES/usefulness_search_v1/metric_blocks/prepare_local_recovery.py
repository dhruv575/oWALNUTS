import hashlib,json,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;dest=root/'local_recovery/inputs';dest.mkdir(parents=True,exist_ok=False)
archive=root/'hybrid01_archive/evidence.tar-s3-restored.tar.gz';receipt=json.loads((root/'hybrid01_archive/S3-VERIFICATION.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256'];extracted={}
with tarfile.open(archive) as tar:
    manifest=json.load(tar.extractfile('EVIDENCE-MANIFEST.json'))
    for name,entry in manifest.items():
        if not (name.startswith('dependencies/') or name in ['ENVIRONMENT.json','online-binary','resource_monitor.py','mpmath-1.3.0-py3-none-any.whl']):continue
        raw=tar.extractfile(name).read();assert len(raw)==entry['bytes'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
        target=dest/name;assert target.resolve().is_relative_to(dest.resolve());target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);extracted[name]=entry
result=dict(parent_archive_sha256=receipt['sha256'],parent_s3_version=receipt['version_id'],verified_files=extracted,
    purpose='Local WSL compatibility checks only; no AWS budget override, no mixing local timing with EC2 timing.')
(root/'LOCAL-RECOVERY-INPUTS.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(files=len(extracted),bytes=sum(e['bytes'] for e in extracted.values()))))
