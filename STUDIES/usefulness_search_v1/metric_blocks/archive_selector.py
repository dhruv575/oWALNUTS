import hashlib
import json
import tarfile
from pathlib import Path

root = Path(__file__).resolve().parent/'selector_evidence'
paths = sorted(p for p in root.rglob('*') if p.is_file() and
               '__pycache__' not in p.parts and p.name != 'EVIDENCE-MANIFEST.json')
assert len(paths) == 17
for version in ['selector-preflight01', 'selector-preflight02']:
    folder = root/version
    receipt = json.loads((folder/'SUPERVISION.json').read_text())
    assert receipt['unchanged'] and receipt['group_drained']
    for source, digest in receipt['inputs'].items():
        assert hashlib.sha256((folder/Path(source).name).read_bytes()).hexdigest() == digest
manifest = {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size,
            sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths}
mp = root/'EVIDENCE-MANIFEST.json'
mp.write_text(json.dumps(manifest, indent=2)+'\n')
out = root.parent/'selector_archive_complete'
out.mkdir(exist_ok=True)
archive = out/'evidence.tar.gz'
assert not archive.exists()
with tarfile.open(archive, 'w:gz') as tar:
    tar.add(mp, arcname=mp.name)
    for p in paths:
        tar.add(p, arcname=p.relative_to(root).as_posix())
print(json.dumps(dict(members=len(paths), bytes=archive.stat().st_size)))
