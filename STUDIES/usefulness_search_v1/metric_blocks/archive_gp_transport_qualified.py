import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
from quadratic_transport import encode,score,logdet
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'gp_transport_qualified02';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed'] and s['advance'];files={}
for name,h in s['inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
lines=['# Qualified-input quadratic transport: advance to full-chain test','','This exposed-data mechanism diagnostic repairs the old unqualified-pilot objection. It is not fresh sampling validation. The fitting rule is unchanged from the failed earlier transport study; four independent fit/evaluation seed pairs use qualified native GP runs.','','| Fold | Quadratic/affine score discrepancy | Cross-entropy change, nat/dimension |','|---|---|---|']
for row in s['rows']:
    f=r/f"fold-{row['fold']}";m=json.loads((f/'MAP.json').read_text());a=np.load(f/'INPUTS.npz')
    for arm,affine in [('affine',True),('quadratic',False)]:
        b=np.load(f/(arm+'.npz'));z=encode(a['q'],m,affine);g=score(a['q'],a['gradient'],m,affine);assert np.array_equal(z,b['z']) and np.array_equal(g,b['score']);assert float(np.mean((g+z)**2))==row['metrics'][arm]['score_discrepancy'];assert float(.5*np.mean(z*z)+logdet(m,affine)/13)==row['metrics'][arm]['cross_entropy_per_dimension']
    lines.append(f"| {row['fold']} | {row['score_ratio']:.6f} | {row['cross_entropy_change']:.6f} |")
lines+=['','All four pass the frozen ratio<.8 and cross-entropy increase<=.1 gates. Twelve transformed-gradient and determinant checks pass; worst scaled gradient discrepancy2.58e-5. Diagnostic work:32000 target-gradient and312 density evaluations for the completed attempt, plus the preserved failed attempt and numerical diagnosis. The first finite-difference attempt failed from a small-perturbation discrepancy; a fixed larger perturbation passed without relaxing the threshold. See GP-TRANSPORT-QUALIFIED-REPAIR.md.','','Next: implement a compiled transformed target usable by both WALNUTS and native NUTS, verify original-space density/Jacobian/gradient equivalence and coordinate roundtrips, then freeze fresh calibration/validation. Use affine and untransformed controls; include training/pilot work and map evaluation cost, maintain all original GP accuracy and tail gates, and report native transformed performance. All four maps must remain visible; do not select the most favorable fold. The known conditional-importance baseline already succeeds on24 means/SDs and must remain a practical comparator. No sampler or application advantage, generality, novelty, deployment or goal completion follows from this diagnostic.']
(p/'GP-TRANSPORT-QUALIFIED-RESULT.md').write_text('\n'.join(lines)+'\n')
for dirname in ['gp_transport_qualified01','gp_transport_qualified02','gp_transport_qualified_supervision01','gp_transport_qualified_supervision02']:
    for f in (l/dirname).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for n in ['GP-TRANSPORT-QUALIFIED-PROTOCOL.md','GP-TRANSPORT-QUALIFIED-REPAIR.md','GP-TRANSPORT-QUALIFIED-RESULT.md','gp_transport_qualified.py','gp_transport_qualified02.py','run_gp_transport_qualified.py','run_gp_transport_qualified02.py','diagnose_gp_transport_gradient.py','archive_gp_transport_qualified.py','quadratic_transport.py','native_common.py','local_recovery/inputs/resource_monitor.py','local_recovery/gp_repair_comparison_archive01/VERIFICATION.json','local_recovery/quadratic_transport_archive01/VERIFICATION.json']:files[n]=p/n
for name in s['inputs']:
    f=Path(name)
    if str(f).startswith(str(p)):files[str(f.relative_to(p))]=f
out=l/'gp_transport_qualified_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive; no off-device claim');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
