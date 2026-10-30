import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_native_repair01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and len(s['rows'])==32;files={}
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
lines=['# Stronger transformed-native calibration','','This adds16 fits to the preserved original16 quadratic native fits. Same maps/seeds, unchanged diagnostic gates; this is baseline calibration, not validation.','','| Mode | Target acceptance | Qualified folds | Geometric calls/minimum bulk ESS |','|---|---|---|---|']
for mode in ['diag','low_rank']:
    for accept in [.9,.99,.999,.9999]:
        rows=[x for x in s['rows'] if x['mode']==mode and x['target_accept']==accept];assert len(rows)==4;v=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in rows])))) if all('calls_per_min_bulk_ess' in x for x in rows) else None;lines.append(f"| {mode} | {accept} | {sum(x['passed'] for x in rows)}/4 | {v} |")
cost=sum(x.get('calls',{}).get('gradient',0) for x in s['rows'] if x['target_accept']>.99);lines+=['','Selection: '+json.dumps(s['selected']),f'Additional native calibration gradient calls: {cost}.','', 'Unqualified rows are diagnostic only. If a selection exists, freeze it for a new-seed comparison with the selected quadratic WAL configuration, affine configurations and raw controls; retain all four maps and account for full pilot/fitting work. Otherwise report the remaining qualification gap. No competitive or goal-completion claim is made from these calibration outcomes.']
(p/'GP-TRANSPORT-NATIVE-REPAIR-RESULT.md').write_text('\n'.join(lines)+'\n')
for f in r.rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-TRANSPORT-NATIVE-REPAIR-PROTOCOL.md','GP-TRANSPORT-NATIVE-REPAIR-RESULT.md','prepare_gp_transport_native_repair.py','gp_transport_native_repair_worker.py','run_gp_transport_native_repair.py','archive_gp_transport_native_repair.py','local_recovery/gp_transport_calibration_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'gp_transport_native_repair_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved calibration archive; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
