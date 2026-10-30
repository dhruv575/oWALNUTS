import json
from pathlib import Path
study=Path(__file__).resolve().parent;s=json.loads((study/'LOCAL-SCALED-COMPARISON.json').read_text())
def ratio(e,key='geomean',interval='ci95'):
    if key not in e:return 'unqualified'
    lo,hi=e[interval];return f"{e[key]:.3f} [{lo:.3f}, {hi:.3f}]"
lines=['# Fresh local scale-corrected policy results','',
    'Frozen six-target/six-arm validation,16 fresh seeds per target. Local WSL only; no cloud observations pooled.',
    f"Continuation gate: **{'PASS' if s['continuation_gate'] else 'FAIL'}**. This is a research continuation criterion, not goal completion or application evidence.",'',
    '| Target | Passes scaled/hybrid/v4/Fisher/dense/auto | ESS/call vs auto | ESS/call vs Fisher | ESS/operational-second vs auto |',
    '|---|---|---|---|---|']
for model,e in s['models'].items():
    passes='/'.join(str(e['passes'][a]) for a in ['scaled','hybrid','v4','fisher','dense','auto'])
    lines.append(f"| {model} | {passes} | {ratio(e['comparisons']['auto'])} | {ratio(e['comparisons']['fisher'])} | {ratio(e['comparisons']['auto'],'operational_ess_rate_geomean','operational_ess_rate_ci95')} |")
lines+=['','Intervals are95% paired bootstrap intervals (10000 replicates, frozen seed929599999). They are exploratory per-target intervals, not simultaneous inference. A ratio is reported only if all16 candidate/control pairs pass every accuracy gate. Failed controls receive no infinite-ratio credit.','',
    f"Accuracy losses vs auto/v4/old hybrid: {json.dumps(s['accuracy_losses'])}.",
    f"Prespecified non-Gaussian signals: {json.dumps(s['signals'])}.",
    f"Fully qualified targets below the .90 Fisher efficiency floor: {json.dumps(s['fisher_efficiency_losses'])}.",'',
    '## Repair and old-policy contrasts','',
    '| Target | Candidate branch counts | ESS/call vs old hybrid | ESS/operational-second vs old hybrid |',
    '|---|---|---|---|']
for model,e in s['models'].items():
    lines.append(f"| {model} | {json.dumps(e['branches'])} | {ratio(e['comparisons']['hybrid'])} | {ratio(e['comparisons']['hybrid'],'operational_ess_rate_geomean','operational_ess_rate_ci95')} |")
lines+=['','## Evidence and limits','',
    f"All eight chunks verified: {s['total_jobs']} jobs and {s['total_matched_stages']} matched stages. Algorithm/source and target hashes agree across chunks. Each local evidence archive was read back and its members verified. These are local copies, not S3/off-device backups.",'',
    'Operational time includes supervised worker startup, model loading, policy fitting, sampler invocation and output, plus the shared pilot charged to every arm. Common reference diagnostics and controller IO are excluded. The ESS/time ratio uses measured minimum bulkESS divided by this time; it is distinct from raw elapsed-time ratios. Startup and the80-digit Fisher solver can dominate cheap targets. This is not a comparison against optimized or persistent-process implementations.','',
    'The unconditional Fisher arm is the published dense estimator in our fixed-stage schedule. It does not reproduce the published native Fisher-HMC adaptation schedule. Native full-schedule controls remain a required comparison before practical superiority claims.','',
    'The six models are an exposed development family; new seeds protect against reuse of fitted trajectories, not model-selection bias. Centered eight-schools remains in the denominator and failure record. The regression also has a cheap collapsed control. Neither a repaired regression fallback nor this gate demonstrates application value, profitability or uniqueness. See RELATED-WORK-CHECK.md and SCORE-GATE-METHODS.md.','']
(study/'LOCAL-SCALED-REPORT.md').write_text('\n'.join(lines))
print(json.dumps(dict(gate=s['continuation_gate'],report=str(study/'LOCAL-SCALED-REPORT.md'))))
