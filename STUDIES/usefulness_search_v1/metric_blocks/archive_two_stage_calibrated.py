import hashlib,io,json,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'two_stage_calibrated01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed']
for n,h in s['source_hashes'].items():assert hashlib.sha256((p/n).read_bytes()).hexdigest()==h
for ti in range(3):
    for ai in range(3):
        a=np.load(r/f'validation-output-{ti}-{ai}.npz');row=s['rows'][3*ti+ai];assert a['score'].shape==(16384,);assert np.isfinite(a['score']).all();assert float(a['score'].mean())==row['mean_accepted_normalized_jump'];assert float(a['accept'].mean())==row['mean_acceptance']
        if ai:
            base=np.load(r/f'validation-output-{ti}-0.npz')['score'];assert float(a['score'].mean()/base.mean())==row['jump_ratio']
assert s['baseline_qualified'] and not s['primary_passed']
lines=['# Calibrated two-stage follow-up: reject both fixed coefficients','','The original grid had no qualifying high-curvature step. This follow-up selected each baseline step using2048 independent calibration phase points, a frozen48-point grid and12 bisections toward acceptance.8. Candidate performance did not enter selection. Fresh16384-point validation accepts at.790,.807,.814 for moderate banana,strong banana,funnel respectively, within the frozen qualification band.','','| Target | BCSS accepted-jump ratio (95% interval) | Minimum-norm ratio (95% interval) |','|---|---|---|']
for ti,name in enumerate(['Banana c2','Banana c5 (primary)','Funnel']):
    vals=[]
    for ai in [1,2]:
        x=s['rows'][3*ti+ai];vals.append(f"{x['jump_ratio']:.4f} [{x['interval'][0]:.4f},{x['interval'][1]:.4f}]")
    lines.append(f"| {name} | {' | '.join(vals)} |")
lines+=['','Primary BCSS/c5 lower bound.8325 fails the required1.05; moderate-curvature control lower bound.7732 also fails.85. The minimum-norm alternative loses more movement on both bananas. Both are rejected for this proposed integration change. Production remains unchanged; no full sampler benefit is established. Every contrast uses eight fresh gradients and the same integration time, with all numerical failures counted as rejection. These stationary one-proposal statistics are not ESS, full-chain mixing, elapsed speed or application value. Other integration schedules or problem-specific tuning are outside the claim.','','Evidence: two_stage_calibrated01 contains every calibration point/iteration, fresh phase inputs and per-point output; two_stage_calibrated_supervision01 confirms bounded worker completion. Original screen and nonstandard zero/zero raw ratios remain separately archived. Both studies use published methods and make no novelty claim.','','Next research queue: audit whether regional curvature changes can be addressed through a model transformation or mass structure that remains useful after strong native-NUTS controls. Prior diagonal/dense/Fisher/adaptive-delta failures must be checked before designing another experiment. Do not return to the two fixed coefficients or treat the Gaussian-only numerical gain as the goal.']
(p/'TWO-STAGE-CALIBRATED-RESULT.md').write_text('\n'.join(lines)+'\n')
(r/'REPLAY.json').write_text(json.dumps(dict(passed=True,arrays_verified=9,primary_passed=False),indent=2)+'\n')
files={}
for folder in [r,l/'two_stage_calibrated_supervision01']:
    for f in folder.rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for n in ['two_stage_screen.py','two_stage_calibrated.py','run_two_stage_calibrated.py','archive_two_stage_calibrated.py','TWO-STAGE-PROTOCOL.md','TWO-STAGE-CALIBRATED-PROTOCOL.md','TWO-STAGE-CALIBRATED-RESULT.md']:files[n]=p/n
f=l/'two_stage_archive01/VERIFICATION.json';files[str(f.relative_to(p))]=f
out=l/'two_stage_calibrated_archive01';out.mkdir(exist_ok=False);archive=out/'evidence.tar.gz';manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()}
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
