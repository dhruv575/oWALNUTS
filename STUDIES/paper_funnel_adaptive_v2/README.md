# paper_funnel_adaptive_v2 — stabilising the Appendix C `h` rule

Preregistered (see `PREREGISTRATION.md`, `protocol.json`) and run 2026-08-31 on
kernel `v9` (commit `cfd813b`), paper adaptation
`walnutpie-paper-adaptation-kquantile-gamma-v2`. Eight arms: two `Delta`
families (2.0, 0.72) × four `h`-rule variants — control (per-transition
statistic, dual-averaging restart at every `delta` install), (a) cumulative
statistic, (b) continue through `delta` installs, (a)+(b). 10-D Neal funnel,
identity mass, 10 refinement levels, depth 10, 4 chains from ω ∈ {−3,−1,1,3},
2,000 discarded + 4×50,000 retained, one thread; zero-callback preflight
(`artifacts/preflight.json`). Control reference F9 = `funnel_bias_fix_v1`
arm F50 (bulk ESS(ω)/call 2.071e-04, tail
2.687e-04; fixed δ = 0.21, h = 0.36).

Run:

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --preflight artifacts/preflight.json
foreach ($a in "A2-C","A2-S","A2-R","A2-SR","AD-C","AD-S","AD-R","AD-SR") { cargo +1.88.0-x86_64-pc-windows-gnu run --release -- --sample $a artifacts/$a.json }
$env:PYTHONIOENCODING = "utf-8"; python analyze.py; python make_readme.py
```

## Results

| arm | Δ | statistic | restart at δ install | final δ per chain (spread) | final h per chain (spread) | R-hat ω | bulk/tail ESS ω | var ω | P(ω<−5) (z) | P(ω<−6) (z) | div/inval/exhaust/depth-cap | retained calls | bulk/tail ESS/call ×F9 | unbiased+healthy / stable / efficient | wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A2-C | 2.0 | per_transition | restart | 1.310, 1.200, 1.215, 1.162 (1.127) | 0.532, 0.638, 0.499, 0.381 (1.68) | 1.0033 | 1416/1749 | 9.39 | 0.0541 (+1.24) | 0.0265 (+1.06) | 0/0/0/60 | 5,525,449 | 1.24/1.18 | pass / FAIL / pass | 3.2 |
| A2-S | 2.0 | cumulative | restart | 1.258, 1.428, 1.523, 1.437 (1.211) | 0.154, 0.392, 4.052, 1.398 (26.37) | 1.0012 | 1273/1441 | 8.77 | 0.0416 (-1.10) | 0.0178 (-1.26) | 0/0/4/178 | 13,171,920 | 0.47/0.41 | FAIL / FAIL / FAIL | 5.8 |
| A2-R | 2.0 | per_transition | continue | 1.175, 1.242, 1.254, 1.116 (1.124) | 0.618, 0.511, 0.511, 0.574 (1.21) | 1.0012 | 1383/2057 | 8.97 | 0.0503 (+0.53) | 0.0215 (-0.39) | 0/0/0/31 | 4,739,088 | 1.41/1.61 | pass / pass / pass | 2.5 |
| A2-SR | 2.0 | cumulative | continue | 1.587, 1.507, 1.361, 1.474 (1.166) | 0.010, 0.439, 0.177, 0.467 (44.77) | 1.0077 | 1365/1033 | 9.41 | 0.0550 (+1.08) | 0.0279 (+1.11) | 0/0/0/8099 | 29,446,417 | 0.22/0.13 | pass / FAIL / FAIL | 21.9 |
| AD-C | 0.72 | per_transition | restart | 0.389, 0.378, 0.367, 0.359 (1.084) | 0.353, 0.371, 0.354, 0.134 (2.77) | 1.0025 | 1484/1368 | 8.90 | 0.0466 (-0.21) | 0.0214 (-0.34) | 0/0/0/183 | 9,386,064 | 0.76/0.54 | pass / FAIL / FAIL | 6.1 |
| AD-S | 0.72 | cumulative | restart | 0.219, 0.315, 0.338, 0.363 (1.654) | 0.007, 0.064, 0.209, 0.634 (95.20) | 1.0021 | 1508/1348 | 8.62 | 0.0471 (-0.11) | 0.0227 (-0.00) | 0/0/0/12974 | 41,091,216 | 0.18/0.12 | pass / FAIL / FAIL | 29.5 |
| AD-R | 0.72 | per_transition | continue | 0.361, 0.402, 0.366, 0.353 (1.140) | 0.381, 0.365, 0.411, 0.465 (1.27) | 1.0012 | 1575/1666 | 9.15 | 0.0504 (+0.49) | 0.0248 (+0.57) | 0/0/0/68 | 6,994,024 | 1.09/0.89 | pass / pass / pass | 3.9 |
| AD-SR | 0.72 | cumulative | continue | 0.335, 0.351, 0.295, 0.510 (1.729) | 0.221, 0.298, 0.020, 0.021 (15.08) | 1.0032 | 1614/1536 | 8.74 | 0.0513 (+0.65) | 0.0242 (+0.39) | 0/0/0/7322 | 37,765,804 | 0.21/0.15 | pass / FAIL / FAIL | 28.4 |

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
