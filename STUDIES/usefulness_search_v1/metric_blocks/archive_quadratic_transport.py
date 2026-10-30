import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
from quadratic_transport import encode,decode,score,logdet
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'quadratic_transport02';s=json.loads((r/'SUMMARY.json').read_text());a=json.loads((l/'transport_gradient_audit01/SUMMARY.json').read_text());assert s['completed'] and s['unchanged'] and all(x['passed'] for x in a['rows']);assert not any(x['advance'] for x in s['rows'])
for f,h in s['inputs'].items():assert hashlib.sha256(Path(f).read_bytes()).hexdigest()==h
for row in s['rows']:
    assert row['passed'];name=row['model'];m=json.loads((r/name/'MAP.json').read_text())
    with np.load(l/'native_prefix02'/name/'long.npz') as z:q=z['sample_stats__unconstrained_draw'][:,100:];g=z['sample_stats__gradient'][:,100:]
    d=q.shape[-1];q=q.reshape(-1,d);g=g.reshape(-1,d)
    for arm,affine in [('affine',True),('quadratic',False)]:
        with np.load(r/name/(arm+'.npz')) as z:assert np.array_equal(z['z'],encode(q,m,affine));assert np.array_equal(z['score'],score(q,g,m,affine))
        assert np.isfinite(score(q,g,m,affine)).all()
lines=['# Triangular quadratic transport diagnostic: no advancement','','The pilot-only fit and held-out evaluation completed for all six saved models. No model clears the frozen advancement gate. This is an exposed one-seed-set geometry diagnostic; held-out continuations are temporally adjacent to pilot draws, not independent fresh validation. Production is unchanged.','','| Model | Prior native qualified | Candidate/affine score discrepancy | Cross-entropy change (nat/dimension) |','|---|---|---:|---:|']
for row in s['rows']:lines.append(f"| {row['model']} | {row['prior_native_qualified']} | {row['score_ratio']:.4f} | {row['cross_entropy_change']:.5f} |")
lines+=['','The GARCH score discrepancy improves by12.1%, short of the required20%; other qualified models worsen. GP improves by65.2%, but its saved native posterior was unqualified (R-hat1.060, minimum bulkESS55.6, tailESS17.2 and128 divergences). It cannot provide promotion evidence. Centered eight schools also remains unqualified. ARMA lacks the matched-geometry qualification artifact; it is explicitly unqualified rather than assumed healthy, and its enormous gradient discrepancy remains visible.','','The first diagnostic attempt stopped on the missing ARMA qualification file. The repaired attempt preserves that failure and treats missing qualification as false, keeping every target. Model parameters, map, fit, order, ridge and thresholds were unchanged. Inverse, gradient and constant-Jacobian preflight checks pass. A separate post-diagnostic audit recomputed72 target gradients (12 positions per model); every stored gradient matched exactly, including the ARMA examples. This validates the checked storage semantics, not all posterior draws or posterior correctness. No target evaluations were used to fit the map. All affine/nonlinear transformed positions and scores replay exactly from preserved inputs and map coefficients.','','The triangular construction uses a globally invertible additive shear with constant positive determinant. It has no modeled conditional variance and is order-dependent; limited pilot size and quadratic feature count can overfit. A smaller Gaussian-score discrepancy is neither an ESS guarantee nor a tail certificate. This experiment does not establish runtime, application value, uniqueness or a useful algorithm improvement. Transport preconditioning is established prior work: https://doi.org/10.1137/17M1134640 and https://arxiv.org/abs/1602.05023 .','','Research queue: do not promote this fixed fit or retune its threshold on these outcomes. Investigate the GP failure mechanism separately using its qualified target/reference and existing successful arms before considering any new method. In particular determine whether discrepancies are poor initial conditioning, nonlinear curvature, weak-identification tails, or finite-budget noise; existing dense/Fisher/native controls must stay in scope. A fresh qualification/repair study would require its own protocol and could not retroactively change this gate.','','Evidence: quadratic_transport02, failed attempt01, transport_gradient_audit01 and scoped supervisor receipts; verified local archive quadratic_transport_archive01. No off-device claim.']
(p/'QUADRATIC-TRANSPORT-RESULT.md').write_text('\n'.join(lines)+'\n');(r/'REPLAY.json').write_text(json.dumps(dict(passed=True,models=6,transformed_arrays=24,checked_gradients=72,advance=False),indent=2)+'\n');files={}
for name in ['quadratic_transport01','quadratic_transport02','quadratic_transport_supervision01','quadratic_transport_supervision02','transport_gradient_audit01','transport_gradient_audit_supervision01']:
    for f in (l/name).rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for f in s['inputs']:
    f=Path(f);files[str(f.relative_to(p))]=f
for pattern in ['*quadratic_transport*.py','*transport_gradient*.py','QUADRATIC-TRANSPORT-*']:
    for f in p.glob(pattern):
        if f.is_file():files[f.name]=f
out=l/'quadratic_transport_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive with saved pilot/continuation inputs; prior target binaries remain dependencies; not off-device backup');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
