import hashlib,io,json,tarfile
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';files={}
for name in ['native_transform_models01','dense_metric_preflight01']:
    s=json.loads((local/name/'SUMMARY.json').read_text());assert s['unchanged']
    for p in (local/name).rglob('*'):
        if p.is_file():files[str(p.relative_to(local))]=p
for name in ['run_native_transform_models.py','check_metric_convention.py','run_dense_metric_preflight.py','archive_transform_models.py','probe_native_transform.py','native_common.py','NATIVE-TRANSFORM-DIAGNOSTIC.md']:
    files['source/'+name]=study/name
files['METRIC-CONVENTION-CHECK.json']=local/'METRIC-CONVENTION-CHECK.json'
root=local/'native_transform_models_archive01';root.mkdir(exist_ok=False)
manifest={n:dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for n,p in files.items()}
archive=root/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    data=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(data);t.addfile(info,io.BytesIO(data))
    for n,p in files.items():t.add(p,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,r in manifest.items():
        data=t.extractfile(n).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
out=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Local evidence read-back, not off-device backup or statistical validation.')
(root/'VERIFICATION.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
