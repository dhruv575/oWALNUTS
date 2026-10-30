import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_calibration01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==64;files={}
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for f in r.rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-TRANSPORT-CALIBRATION-PROTOCOL.md','GP-TRANSPORT-CALIBRATION-RESULT.md','prepare_gp_transport_calibration.py','gp_transport_calibration_worker.py','run_gp_transport_calibration.py','summarize_gp_transport_calibration.py','archive_gp_transport_calibration.py','native_common.py','local_recovery/gp_transport_target_archive01/VERIFICATION.json','local_recovery/localscaled01/REFERENCES.json']:files[name]=p/name
for pilot in json.loads((r/'COST-LEDGER.json').read_text())['pilots']:
    f=Path(pilot['receipt']);assert hashlib.sha256(f.read_bytes()).hexdigest()==pilot['sha256'];files[str(f.relative_to(p))]=f
out=l/'gp_transport_calibration_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved target archive; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
