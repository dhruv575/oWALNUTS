import hashlib,io,json,tarfile
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery';s=json.loads((l/'gp_transport_target01/SUMMARY.json').read_text());smoke=json.loads((l/'gp_transport_smoke01/SUMMARY.json').read_text());assert s['passed'] and smoke['completed'] and len(smoke['rows'])==16;files={}
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for name,h in smoke['source_hashes'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==h
assert hashlib.sha256(Path(s['library']).read_bytes()).hexdigest()==s['library_sha256']
maxima={k:max(row['maxima'][k] for row in s['rows']) for k in ['roundtrip','density','gradient','functionals']}
lines=['# Compiled transport preflight passed','','Eight map/control cells,48 points each, pass the frozen equivalence gates. Maximum errors: '+json.dumps(maxima)+'. The density includes both the original log-positive-parameter Jacobian and the constant transport Jacobian. Original-space functionals match exactly at the checked points. This does not certify unseen-tail numerical behavior.','','Both samplers also completed execution/accounting smoke runs for every map/control cell:16 runs,4 chains,128 warmup and128 retained draws. These short runs are not posterior qualification or performance evidence. Native uses low-rank/.99; WAL uses diagonal/.9. Their default initialization workflows differ. All draws and constrained outputs are finite. Native counted gradient totals cover recorded integration steps; other counted derivative categories are zero. Retained divergences total: '+str(sum(x['retained_divergences'] for x in smoke['rows']))+'.','','The compiled template is shared by both engines. Separate-map data files, source, library, native counter shim and raw smoke outputs are preserved. No production change. Next required step is fresh full-chain calibration/validation with original-space all-functional gates, raw and affine controls, transformed native NUTS, all four maps and explicitly accounted pilot/fitting costs. The earlier successful conditional importance method remains a practical comparator. No application advantage or goal completion is established.']
(p/'GP-TRANSPORT-TARGET-RESULT.md').write_text('\n'.join(lines)+'\n')
for dirname in ['gp_transport_target01','gp_transport_target_supervision01','gp_transport_smoke01','gp_transport_smoke_supervision01']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['gp_transport.stan','GP-TRANSPORT-TARGET-PROTOCOL.md','GP-TRANSPORT-TARGET-RESULT.md','build_gp_transport_target.py','run_gp_transport_target.py','gp_transport_smoke.py','run_gp_transport_smoke.py','archive_gp_transport_target.py','quadratic_transport.py','native_common.py','local_recovery/inputs/resource_monitor.py','local_recovery/gp_transport_qualified_archive01/VERIFICATION.json']:files[name]=p/name
for name in s['inputs']:
    f=Path(name)
    if str(f).startswith(str(p)):files[str(f.relative_to(p))]=f
f=Path(smoke['wal_binary']['binary']);assert hashlib.sha256(f.read_bytes()).hexdigest()==smoke['wal_binary']['binary_sha256'];files['binaries/'+f.name]=f
out=l/'gp_transport_target_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive; no off-device claim');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
