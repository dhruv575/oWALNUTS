import json, hashlib, pathlib
S=json.load(open('artifacts/summary.json'))
ctrl=S['control']
rows=[]
for o in S['arms']:
    f=o['functionals']; h=o['health']; t5,t6=o['tail_mass']
    p=o['settings']['paper']
    rows.append(f"| {o['arm']} | {p['global_energy_bound']} | {p['step_statistic']} | {p['restart_policy']} | "
        f"{', '.join(f'{x:.3f}' for x in o['final_delta_per_chain'])} ({o['final_delta_spread_ratio']:.3f}) | "
        f"{', '.join(f'{x:.3f}' for x in o['final_step_per_chain'])} ({o['final_step_spread_ratio']:.2f}) | "
        f"{f['omega']['rhat']:.4f} | {f['omega']['bulk_ess']:.0f}/{f['omega']['tail_ess']:.0f} | {o['omega_variance']:.2f} | "
        f"{t5['observed']:.4f} ({t5['z']:+.2f}) | {t6['observed']:.4f} ({t6['z']:+.2f}) | "
        f"{h['divergences']}/{h['invalid_evaluation_stops']}/{h['refinement_exhaustion_stops']}/{h['maximum_depth_stops']} | "
        f"{h['target_calls']:,} | {o['bulk_ess_per_call_ratio_vs_F9']:.2f}/{o['tail_ess_per_call_ratio_vs_F9']:.2f} | "
        f"{'pass' if o['unbiased_and_healthy'] else 'FAIL'} / {'pass' if o['stable'] else 'FAIL'} / {'pass' if o['efficient'] else 'FAIL'} | "
        f"{o['wall_seconds']:.1f} |")
table="\n".join(rows)
readme=f"""# paper_funnel_adaptive_v2 — stabilising the Appendix C `h` rule

Preregistered (see `PREREGISTRATION.md`, `protocol.json`) and run 2026-08-31 on
kernel `v9` (commit `cfd813b`), paper adaptation
`walnutpie-paper-adaptation-kquantile-gamma-v2`. Eight arms: two `Delta`
families (2.0, 0.72) × four `h`-rule variants — control (per-transition
statistic, dual-averaging restart at every `delta` install), (a) cumulative
statistic, (b) continue through `delta` installs, (a)+(b). 10-D Neal funnel,
identity mass, 10 refinement levels, depth 10, 4 chains from ω ∈ {{−3,−1,1,3}},
2,000 discarded + 4×50,000 retained, one thread; zero-callback preflight
(`artifacts/preflight.json`). Control reference F9 = `funnel_bias_fix_v1`
arm F50 (bulk ESS(ω)/call {ctrl['bulk_ess_omega_per_retained_call']:.3e}, tail
{ctrl['tail_ess_omega_per_retained_call']:.3e}; fixed δ = 0.21, h = 0.36).

Run:

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight artifacts/preflight.json
foreach ($a in "A2-C","A2-S","A2-R","A2-SR","AD-C","AD-S","AD-R","AD-SR") {{ cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample $a artifacts/$a.json }}
$env:PYTHONIOENCODING = "utf-8"; python analyze.py; python make_readme.py
```

## Results

| arm | Δ | statistic | restart at δ install | final δ per chain (spread) | final h per chain (spread) | R-hat ω | bulk/tail ESS ω | var ω | P(ω<−5) (z) | P(ω<−6) (z) | div/inval/exhaust/depth-cap | retained calls | bulk/tail ESS/call ×F9 | unbiased+healthy / stable / efficient | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
{table}

Gates: unbiased = P(ω<−5) within ±0.009 of 0.0478, P(ω<−6) within ±0.006 of
0.0228, var ω ∈ [8.2, 9.8]; healthy = zero retained divergences / invalid /
exhaustions, rank R-hat ≤ 1.01, bulk/tail ESS ≥ 400 on ω and x₁; stable =
final h max/min ≤ 1.5 and final δ max/min ≤ 1.2; efficient = bulk ESS/call
≥ 0.8× F9 and tail ≥ 0.7× F9.

## Prediction verdicts

* P1 (all arms unbiased and healthy): **7/8 held**; A2-S had 4 retained
  refinement exhaustions (its chain at h = 4.05 exceeded the ten-level
  refinement budget). Bias gates passed in every arm.
* P2 (controls fail the h-spread gate): **held** (1.68 and 2.77).
* P3 ((b) alone stabilises h): **held** — A2-R spread 1.21, AD-R 1.27, and
  both pass every gate in both families.
* P4 ((a) alone reduces the spread): **falsified** — the cumulative statistic
  made the instability far worse (spread 26× and 95×; 178 and 12,974 depth
  caps). Mechanism: dual averaging already integrates `Gamma − statistic`;
  feeding it a lagged running mean turns a noisy statistic into a persistent
  offset that is integrated for hundreds of transitions before the mean
  catches up, so h oscillates with enormous amplitude.
* P5 ((a)+(b) at least as stable as (b)): **falsified** — 45× and 15×
  spreads, ~8,000 depth caps, efficiency 0.13–0.22× F9.
* P6 (δ spread ≤ 1.2 everywhere): held for C and R arms; failed for the AD
  S/SR arms (1.65, 1.73), where the runaway h changed the orbit energy ranges.
* P7 (stabilised arms gain tail efficiency): **held for (b)** — A2-R
  1.61× F9 tail (control 1.18×), AD-R 0.89× (control 0.54×). A2-R is also
  1.41× F9 in bulk ESS per call, i.e. more efficient than the paper's fixed
  funnel tuning.

## Decision

Per the preregistered rule, (b) alone — `PaperRestartPolicy::
ContinueThroughLocalErrorInstall` — qualifies in both `Delta` families and
(a)+(b) does not add stability, so (b) becomes the default of paper mode
(`walnutpie-paper-adaptation-kquantile-gamma-v3`, separate commit).
`PaperStepStatistic::Cumulative` remains available but is falsified as a
stabiliser on this target and is not recommended. WP7
(`paper_funnel_adaptive_v1`) ran under revision `v1` with the restart default
and is unchanged.
"""
pathlib.Path('README.md').write_text(readme,encoding='utf-8')
files=['protocol.json','PREREGISTRATION.md','README.md','Cargo.toml','Cargo.lock','src/main.rs','analyze.py','make_readme.py']+sorted(p.as_posix() for p in pathlib.Path('artifacts').glob('*.json'))+['../../src/walnutpie.rs','../../src/kernel.rs','../../Cargo.lock']
lines=[f"{hashlib.sha256(open(f,'rb').read()).hexdigest()} *{f}" for f in files]
pathlib.Path('CHECKSUMS.sha256').write_text("\n".join(lines)+"\n",encoding='utf-8')
print("\n".join(l for l in lines if 'summary' in l or 'walnutpie' in l or 'protocol' in l or 'PREREG' in l))
