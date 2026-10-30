import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'endpoint_error_audit01';s=json.loads((r/'SUMMARY.json').read_text());assert s['passed']
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
names=['audit_endpoint_error.py','archive_endpoint_error.py','ENDPOINT-ERROR-AUDIT.md','local_recovery/endpoint_error_audit01/SUMMARY.json'];manifest={n:hashlib.sha256((p/n).read_bytes()).hexdigest() for n in names};out=l/'endpoint_error_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n in names:t.add(p/n,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,h in manifest.items():assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h
receipt=dict(passed=True,members=len(names),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
