import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';s=json.loads((l/'bounded_gp_target01/SUMMARY.json').read_text());assert s['completed'] and s['passed'];files={}
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
assert hashlib.sha256(Path(s['library']).read_bytes()).hexdigest()==s['library_sha256'];maxima={k:max(x['maxima'][k] for x in s['rows']) for k in ['roundtrip','density','gradient','functionals']}
(p/'BOUNDED-GP-TARGET-RESULT.md').write_text('# Bounded GP compiled-target equivalence passed\n\nAll eight map/control cells and384 points pass the unchanged equivalence gates. Maximum errors: '+json.dumps(maxima)+'. Original-space functionals are checked against the original GP target. This verifies the implementation at those points, not full-chain behavior or an advantage. The earlier bounded-feature mechanism screen remains failed on its relative tail criterion. A separately frozen direct sampling experiment is required; no production change.\n')
for dirname in ['bounded_gp_target01','bounded_gp_target_supervision01']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['bounded_gp.stan','BOUNDED-GP-TARGET-PROTOCOL.md','BOUNDED-GP-TARGET-RESULT.md','prepare_bounded_gp_target.py','build_bounded_gp_target.py','run_bounded_gp_target.py','archive_bounded_gp_target.py','bounded_transport.py','local_recovery/bounded_transport_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'bounded_gp_target_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive; depends on preserved inputs, no off-device claim');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
