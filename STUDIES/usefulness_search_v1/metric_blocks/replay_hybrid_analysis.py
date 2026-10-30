import hashlib,json,subprocess,sys,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;dest=root/'hybrid_analysis_replay';dest.mkdir(exist_ok=False)
archive=root/'hybrid_analysis_archive/evidence.tar-s3-restored.tar.gz'
receipt=json.loads((root/'hybrid_analysis_archive/S3-VERIFICATION.json').read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest()==receipt['sha256']
with tarfile.open(archive) as tar:
    members=tar.getmembers()
    for member in members:
        assert member.isfile() and (dest/member.name).resolve().is_relative_to(dest.resolve())
        target=dest/member.name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(tar.extractfile(member).read())
manifest=json.loads((dest/'EVIDENCE-MANIFEST.json').read_text());assert len(manifest)==receipt['verified_members']
assert all((dest/p).stat().st_size==e['bytes'] and hashlib.sha256((dest/p).read_bytes()).hexdigest()==e['sha256'] for p,e in manifest.items())
before=json.loads((dest/'HYBRID-COMPARISON.json').read_text())
subprocess.run([sys.executable,str(dest/'analyze_hybrid.py')],check=True,capture_output=True,text=True)
after=json.loads((dest/'HYBRID-COMPARISON.json').read_text())
for result in [before,after]:
    result['inputs']={'/'.join(Path(p).parts[-2:]):h for p,h in result['inputs'].items()}
assert before==after
result=dict(passed=True,verified_members=len(manifest),exact_numerical_and_gate_replay=True,
    archive_sha256=receipt['sha256'],s3_version=receipt['version_id'],continuation_gate=after['continuation_gate'],
    note='Exact artifact analysis replay; not a new statistical replication. Replay directory retained; no recursive deletion.')
(root/'HYBRID-REPLAY-VERIFICATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
