import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
from bounded_transport import fit
p=Path(__file__).resolve().parent;l=p/'local_recovery';pilot=json.loads((l/'gp_wal_pilot01/SUMMARY.json').read_text());target=json.loads((l/'gp_wal_target01/SUMMARY.json').read_text());assert pilot['completed'] and target['completed']
assert json.loads((l/'gp_wal_pilot01/RAW-AUDIT.json').read_text())['passed']
for batch in [pilot,target]:
    for name,h in batch['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for row in pilot['rows']:
    d=l/f"gp_wal_pilot01/scenario-{row['scenario']}"
    for name,h in row['result'].get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    if row['passed']:
        q=np.load(d/'DRAWS-STATS.npz')['sample_stats__unconstrained_draw'];assert fit(q[:,:100].reshape(-1,13))==json.loads((d/'MAP.json').read_text())
        setup=json.loads((d/'MAP-SETUP.json').read_text());assert setup['training_positions']==400 and setup['pilot_calls']==row['result']['calls']
        for name,h in setup['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for row in target['rows']:
    assert len(row['errors'])==48
    maxima={k:max(x[k] for x in row['errors']) for k in row['maxima']};assert maxima==row['maxima']
    assert row['passed']==(maxima['roundtrip']<=1e-9 and maxima['density']<=1e-6 and maxima['gradient']<=1e-5 and maxima['functionals']<=1e-6)
assert len(pilot['rows'])==4 and len(target['rows'])==8
lines=['# Fresh pilot maps and target equivalence','','| Dataset | Pilot qualified | Full pilot gradient calls | Affine target | Bounded target |','|---|---|---|---|---|']
for row in pilot['rows']:
    scenario=row['scenario'];checks={x['arm']:x['passed'] for x in target['rows'] if x['scenario']==scenario};lines.append(f"| {scenario} | {row['passed']} | {row['result']['calls']['gradient']} | {checks['affine']} | {checks['bounded']} |")
lines+=['','All maps use K=4,ridge10 and the prescribed400 training positions from separate pilots; map reconstruction was independently checked against saved pilot draws. All384 equivalence points are preserved. Passing setup is not evidence of sampler efficiency, practical value or novelty.']
(p/'GP-WAL-SETUP-RESULT.md').write_text('\n'.join(lines)+'\n')
files={}
for folder in ['gp_wal_pilot01','gp_wal_target01','gp_wal_target_supervision01']:
    for f in (l/folder).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['GP-WAL-PILOT-PROTOCOL.md','GP-WAL-TARGET-PROTOCOL.md','GP-WAL-SETUP-RESULT.md','gp_wal_pilot_worker.py','run_gp_wal_pilot.py','check_gp_wal_targets.py','run_gp_wal_targets.py','archive_gp_wal_setup.py','audit_gp_wal_pilot.py','bounded_transport.py','gp_workflow_setup.py','local_recovery/gp_fresh_reference_archive01/VERIFICATION.json']:files[name]=p/name
out=l/'gp_wal_setup_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    raw=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(raw);t.addfile(info,io.BytesIO(raw))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        raw=t.extractfile(n).read();assert len(raw)==m['bytes'] and hashlib.sha256(raw).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local fresh pilot/target evidence; reference and compiled-target dependencies retained separately; not off-device')
(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
