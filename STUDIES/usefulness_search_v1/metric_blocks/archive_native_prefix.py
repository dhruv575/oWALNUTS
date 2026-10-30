import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['native_prefix01','native_prefix02']:
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['unchanged']
    for p,h in s['inputs'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(local))]=p
for name in ['native_prefix_worker.py','native_prefix_nojitter_worker.py','run_native_prefix.py','run_native_prefix_nojitter.py','prepare_native_prefix_nojitter.py','native_common.py','archive_native_prefix.py']:
    files['source/'+name]=study/name
assert json.loads((local/'native_prefix02/SUMMARY.json').read_text())['all_passed']
root=local/'native_prefix_archive01';root.mkdir(exist_ok=False)
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()};archive=root/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local prefix qualification evidence read-back; preserves failed jittered attempt.')
(root/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
