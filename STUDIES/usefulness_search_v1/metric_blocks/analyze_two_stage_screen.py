import hashlib,io,json,math,tarfile
from pathlib import Path
import numpy as np
p=Path(__file__).resolve().parent;l=p/'local_recovery';r=l/'two_stage_screen01';s=json.loads((r/'SUMMARY.json').read_text());assert s['completed']
assert hashlib.sha256((p/'two_stage_screen.py').read_bytes()).hexdigest()==s['source_sha256'];assert hashlib.sha256((p/'TWO-STAGE-PROTOCOL.md').read_bytes()).hexdigest()==s['protocol_sha256']
undefined=[]
for ti in range(4):
    for si in range(4):
        base=np.load(r/f'outputs-{ti}-{si}-0.npz')['score']
        for ai in range(3):
            data=np.load(r/f'outputs-{ti}-{si}-{ai}.npz');row=s['rows'][ti*12+si*3+ai];assert data['score'].shape==(8192,);assert np.isfinite(data['score']).all();assert float(data['score'].mean())==row['mean_accepted_normalized_jump'];assert float(data['accept'].mean())==row['mean_acceptance'];assert float(data['finite'].mean())==row['finite_fraction']
            if ai:
                if base.mean()==0:
                    assert data['score'].mean()==0 and math.isnan(row['jump_ratio']);row['jump_ratio']=None;row['interval']=None;row['ratio_status']='undefined_zero_baseline';undefined.append(dict(target_index=ti,step_index=si,arm_index=ai))
                else:assert float(data['score'].mean()/base.mean())==row['jump_ratio']
(r/'REVIEWED-SUMMARY.json').write_text(json.dumps(s,indent=2,allow_nan=False)+'\n');(r/'REPLAY.json').write_text(json.dumps(dict(passed=True,arrays_verified=48,undefined_ratios=undefined,note='Original summary preserved; two zero/zero ratios rendered as null in reviewed summary, excluded by frozen acceptance gate.'),indent=2)+'\n')
lines=['# Two-stage integration feasibility: no curved-target candidate qualifies','','This is an exact-stationary one-trajectory screen, not a cold MCMC or WALNUTS result. Each comparison uses the same8192 independent phase points, integration time and eight fresh gradient evaluations. All gradient, reversibility, determinant and concatenated-leapfrog checks passed. Neither published two-stage coefficient satisfies the frozen advancement rule.','','| Target / baseline step | Baseline acceptance | BCSS accepted-jump ratio (95% interval) | Minimum-norm ratio (95% interval) |','|---|---:|---|---|']
for ti,si in [(0,2),(1,2),(2,1),(2,2),(3,2),(3,3)]:
    group=s['rows'][ti*12+si*3:ti*12+si*3+3];base=group[0];vals=[f"{a['jump_ratio']:.4f} [{a['interval'][0]:.4f},{a['interval'][1]:.4f}]" for a in group[1:]];lines.append(f"| {base['target']} c={base['curvature']} / {base['h']} | {base['mean_acceptance']:.4f} | {' | '.join(vals)} |")
lines+=['','The Gaussian improvement does not transfer to the curved-target settings in this grid. The stronger banana grid jumps from baseline acceptance.968 to.310, so it contains no point in the qualifying[.5,.95] band; this is a coverage limitation, not evidence that all intermediate steps fail. At the tested moderate banana and funnel points that qualify, neither candidate clears the1.05 lower-bound gate. At larger steps numerical instability can make both methods worse. These findings do not exclude tuning different coefficients, a denser grid, or model-specific use.','','Two zero/zero ratios at banana c=5,h=.3 were NaN in the raw JSON because all phase points were rejected. Raw evidence remains unchanged; REVIEWED-SUMMARY.json labels these undefined and uses strict JSON null. They cannot pass the gate and are not silently dropped. Finite-path energy quantiles are explicitly conditional on numerical finiteness; all failures contribute zero accepted jump. Intervals are exploratory paired bootstrap, not adjusted for32 comparisons.','','Published method attribution: Blanes, Casas and Sanz-Serna, Numerical Integrators for the Hybrid Monte Carlo Method, DOI10.1137/130932740; https://www.gicas.uji.es/Fernando/MyPapers/93274-gg.pdf . Symmetric kick/drift compositions preserve volume and reversibility algebraically; numerical checks are supplementary. No novelty or practical-usefulness claim. Production unchanged.','','Next reviewed work: close the coverage gap with an independently calibrated step at baseline acceptance.8 for each curved target, keeping equal gradient budget and using fresh phase points. Freeze coefficients, calibration budget, selection rule and validation gate before execution. Only a qualifying validation should trigger full sampler implementation. This is a targeted follow-up to missing coverage, not a reclassification of the failed initial screen.','','Resources: worker completed in4.04s, observed peakRSS63.5MiB, evidence16.2MiB. AWS authentication expired on the status recheck; last verified instance state was budget-stopped and no restart was attempted. Local C drive had about212GiB free. Goal remains active.']
(p/'TWO-STAGE-RESULT.md').write_text('\n'.join(lines)+'\n')
files={}
for folder in [r,l/'two_stage_supervision01']:
    for f in folder.rglob('*'):
        if f.is_file():files[str(f.relative_to(p))]=f
for name in ['TWO-STAGE-PROTOCOL.md','TWO-STAGE-RESULT.md','two_stage_screen.py','run_two_stage_screen.py','analyze_two_stage_screen.py']:files[name]=p/name
out=l/'two_stage_archive01';out.mkdir(exist_ok=False);manifest={n:dict(bytes=f.stat().st_size,sha256=hashlib.sha256(f.read_bytes()).hexdigest()) for n,f in files.items()};archive=out/'evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    b=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('MANIFEST.json');info.size=len(b);t.addfile(info,io.BytesIO(b))
    for n,f in files.items():t.add(f,arcname=n,recursive=False)
with tarfile.open(archive) as t:
    for n,m in manifest.items():
        b=t.extractfile(n).read();assert len(b)==m['bytes'] and hashlib.sha256(b).hexdigest()==m['sha256']
receipt=dict(passed=True,members=len(files),sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),scope='Verified local archive, not off-device');(out/'VERIFICATION.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
