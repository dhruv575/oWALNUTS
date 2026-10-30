import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';a=json.loads((l/'gp_transport_tail_audit01/SUMMARY.json').read_text());b=json.loads((l/'gp_transport_divergence_replay01/REPLAY.json').read_text());c=json.loads((l/'gp_transport_divergence_replay01/PROPOSAL-AUDIT.json').read_text());assert a['completed'] and b['passed'] and c['completed'];assert c['summary']['start']['stored_gradient_error_max']==0;files={}
for s in [a,b]:
    for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for dirname in ['gp_transport_tail_audit01','gp_transport_tail_audit_supervision01','gp_transport_divergence_replay01']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-TRANSPORT-TAIL-AUDIT-PROTOCOL.md','GP-TRANSPORT-TAIL-AUDIT-RESULT.md','GP-TRANSPORT-DIVERGENCE-REPLAY-PROTOCOL.md','audit_gp_transport_tails.py','run_gp_transport_tail_audit.py','replay_gp_transport_divergences.py','analyze_gp_divergence_proposals.py','archive_gp_transport_tail_audit.py','quadratic_transport.py','local_recovery/gp_transport_validation_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'gp_transport_tail_audit_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved validation/target archives; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
