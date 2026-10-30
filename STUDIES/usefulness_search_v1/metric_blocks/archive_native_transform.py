import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery'
files={}
for name in ['native_source01','native_metric_probe01','native_transform_probe01']:
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(local))]=p
for name in ['fetch_native_source.py','probe_native_metric.py','probe_native_transform.py','native_common.py','NATIVE-TRANSFORM-DIAGNOSTIC.md','archive_native_transform.py']:
    files['source/'+name]=study/name
assert json.loads((local/'native_transform_probe01/SUMMARY.json').read_text())['passed']
for name in ['native_metric_probe01','native_transform_probe01']:
    s=json.loads((local/name/'SUPERVISION.json').read_text());assert s['exit_code']==0 and s['group_drained']
root=local/'native_transform_archive01';root.mkdir(exist_ok=False)
manifest={name:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for name,p in files.items()}
archive=root/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for name,p in files.items():t.add(p,arcname=name,recursive=False)
with tarfile.open(archive) as t:
    for name,r in manifest.items():
        data=t.extractfile(name).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local raw evidence and source read-back, not off-device backup or sampler validation.')
(root/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
