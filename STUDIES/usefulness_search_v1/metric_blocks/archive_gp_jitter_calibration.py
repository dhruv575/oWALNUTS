import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_jitter_calibration01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'];files={};eligible=[]
for row in s['rows']:
    for name,h in row.get('inputs',{}).items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
for amplitude in [0.,.25,.5,.75]:
    rows=[x for x in s['rows'] if x['amplitude']==amplitude];assert len(rows)==2
    if all(x['passed'] for x in rows):eligible.append(dict(amplitude=amplitude,calls_per_min_bulk_ess_geomean=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in rows]))))))
eligible.sort(key=lambda x:(x['calls_per_min_bulk_ess_geomean'],x['amplitude']));assert eligible==s['eligible'];assert s['selected']==(eligible[0] if eligible else None)
lines=['# GP jitter calibration checkpoint','','Two fresh seeds, four amplitudes, four chains with1100 warmup and2000 retained draws. All prior all-functional qualification gates remain enforced. This is calibration, not independent validation.','','| Amplitude | Qualified fits | Geometric mean calls/minimum bulk ESS |','|---|---|---|']
for a in [0.,.25,.5,.75]:
    rows=[x for x in s['rows'] if x['amplitude']==a];v=float(np.exp(np.mean(np.log([x['calls_per_min_bulk_ess'] for x in rows]))));lines.append(f"| {a} | {sum(x['passed'] for x in rows)}/2 | {v:.3f} |")
lines+=['',f"Frozen selection: {s['selected']}",'','A selected nonzero amplitude must face the zero-jitter configuration and tuned native low-rank NUTS on the eight new seeds specified in GP-JITTER-CALIBRATION-PROTOCOL.md. If zero wins or no candidate is eligible, no validation advantage is asserted. Calibration selection alone does not establish improvement, application value, novelty or goal completion. The earlier dense warmup implementation failure remains in the preflight archive.']
(p/'GP-JITTER-CALIBRATION-RESULT.md').write_text('\n'.join(lines)+'\n')
for f in r.rglob('*'):
    if f.is_file():files[str(f.relative_to(p))]=f
for n in ['GP-JITTER-CALIBRATION-PROTOCOL.md','GP-JITTER-CALIBRATION-RESULT.md','prepare_gp_jitter_calibration.py','gp_jitter_calibration_worker.py','run_gp_jitter_calibration.py','archive_gp_jitter_calibration.py','native_common.py','local_recovery/gp_jitter_preflight_archive01/VERIFICATION.json','local_recovery/localscaled01/REFERENCES.json']:files[n]=p/n
out=l/'gp_jitter_calibration_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, depends on preserved preflight archive; not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
