# Paper funnel reproduction v1 (WP2)

Evidence class: preregistered reproduction of the JMLR/arXiv 2506.18746 §4.3
Neal's-funnel claim with fixed paper tuning, plus labelled post-hoc mechanism
probes. Executed 2026-08-31. No sampler source was modified.

Reproduce:

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu build --release
.\target\release\paper-funnel-reproduction-v1.exe --preflight artifacts\preflight.json
.\target\release\paper-funnel-reproduction-v1.exe --sample F artifacts\F.json      # also F50 N11 N36
.\.venv-ref314\Scripts\python reference_run.py R0 artifacts\R0.json           # also R1
.\.venv-ref314\Scripts\python analyze.py
.\target\release\paper-funnel-reproduction-v1.exe --posthoc FT artifacts\posthoc-FT.json  # also G S M8
.\.venv-ref314\Scripts\python reference_fixed36.py artifacts\posthoc-R36.json
.\.venv-ref314\Scripts\python posthoc_analyze.py
```

The reference is the Flatiron `walnutpie` 0.0.3 PyPI wheel (the same code
family as the crate's oracle fixtures, commit `f5bba365`) driven through
`walnuts_pyfunc` on Python 3.14; it runs its own initial step search even with
zero warmup, so arm R0's per-chain steps are `[0.1273, 0.36, 1.0182, 1.0182]`.

## Headline

**The paper's funnel claim did not reproduce with oWALNUTS at the paper's
tuning, and the failure is a bias, not slow mixing.** With `h = 0.36`,
`δ = 0.21`, 10 refinement levels, depth 10, identity mass, oWALNUTS explores
the neck (unlike NUTS) but puts **twice the correct mass** below `ω = −5`:
0.0959 at 4×10,000 draws and 0.0971 ± 0.0090 at 4×50,000 draws against the
exact 0.0478 (z ≈ 10.7 on the 50k run); `var(ω)` is 11.1–11.4 against 9. Every
chain shows it. The reference implementation at the same nominal tuning gets
the tail right (R0: 0.0420 ± 0.0291; R1: 0.0405 ± 0.0199), and at **exactly the same h, δ, halvings, depth and identity metric** (post-hoc arm R36, 4×30,000 draws) it is exact: P(ω<−5) = 0.0477 vs 0.0478, P(ω<−6) = 0.0217 vs 0.0228, 1% quantile −6.978 vs −6.979, var(ω) 8.87. The
fixed-step NUTS control reproduces the paper's *NUTS* failure exactly (too
little left tail, `ω` never below −5.7).

Post-hoc probes localize the defect: a 10-D standard Gaussian at the same
tuning is exact; a tiny fixed step with refinement disabled (arm S) is
approximately unbiased on the funnel (tail z ≈ −1.4); every configuration that
exercises refinement (F, F50, M8) over-weights the neck. The excess mass is
therefore produced by the refinement/reverse-check path, not by orbit
construction or state selection.

## Preregistered arms (protocol.json; gates in PREREGISTRATION.md)

| arm | draws | R-hat ω | R-hat x1 | bulk/tail ESS ω | bulk/tail ESS x1 | mean ω (MCSE) | var ω | P(ω<−5) obs / exact ± hw | P(ω<−6) obs / exact ± hw | q1% / q0.5% (exact −6.98 / −7.73) | div / invalid / exhaust / depth-cap | target calls | wall s | convergence gates | paper-claim gates |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F (primary) | 4×10,000 | 1.0061 | 1.0048 | 239 / 571 | 21,277 / 1,921 | −0.308 (0.215) | 11.06 | **0.0959** / 0.0478 ± 0.0175 | **0.0509** / 0.0228 ± 0.0122 | −8.26 / −9.06 | 0 / 0 / 0 / 0 | 2,858,238 | 1.3 | FAIL (ESS ω) | **FAIL** (tail too heavy) |
| F50 | 4×50,000 | 1.0053 | 1.0040 | 1,162 / 2,147 | 114,582 / 8,655 | −0.434 (0.099) | 11.41 | **0.0971** / 0.0478 ± 0.0090 | **0.0557** / 0.0228 ± 0.0063 | −8.24 / −9.02 | 0 / 0 / 17 / 64 | 12,770,697 | 7.4 | pass | **FAIL** (tail; 17 retained exhaustions) |
| N11 (NUTS control, h=0.11, no refinement, no local cap) | 4×10,000 | 1.0040 | 1.0023 | 475 / 677 | 44,843 / 3,607 | +0.200 (0.125) | 7.44 | 0.0163 / 0.0478 ± 0.0161 | 0.0000 / 0.0228 ± 0.0112 | −5.22 / −5.37 | 0 / 0 / 0 / 138 | 4,430,890 | 4.8 | pass | FAIL (tail too light — the paper's NUTS result) |
| N36 (h=0.36, δ=0.21, no refinement) | 4×10,000 | 1.4322 | 1.5984 | 8 / 17 | 5,517 / 466 | −0.572 (0.901) | 6.73 | 0.0000 | 0.0000 | −3.61 / −3.61 | 0 / 0 / 30,923 / 0 | 812,986 | 0.9 | FAIL | FAIL (77% refinement exhaustion; cannot enter the neck) |
| R0 (walnutpie, 0 warmup) | 4×10,000 | 1.0095 | 1.0077 | 220 / 207 | 3,469 / 469 | +0.333 (0.209) | 9.64 | 0.0420 / 0.0478 ± 0.0291 | 0.0204 / 0.0228 ± 0.0203 | −6.78 / −7.66 | n/a | 2,538,956 | 62.9 | FAIL (ESS) | pass |
| R1 (walnutpie, adaptive 1,000 warmup) | 4×10,000 | 1.0353 | 1.0222 | 197 / 442 | 8,379 / 1,170 | +0.093 (0.206) | 8.38 | 0.0405 / 0.0478 ± 0.0199 | 0.0194 / 0.0228 ± 0.0139 | −6.90 / −7.68 | n/a | 1,531,917 | 43.2 | FAIL (R-hat) | pass |

`hw` is the preregistered half-width `1.96·sqrt(p(1−p)/tail-ESS(ω))`. Per-chain
`P(ω<−5)` for F: 0.064, 0.113, 0.103, 0.104; for F50: 0.099, 0.082, 0.102,
0.106; for R0: 0.032, 0.044, 0.044, 0.048. Reference wall times are dominated by
the Python callback (2.5M callbacks); they are not throughput measurements.
The runtime callback budget was `min(1e9, exact worst case)` because the
facade rejects a budget above its admission ceiling; no arm approached it.

Retained stop mix for F: outer U-turn 22,677; recursive U-turn 3,419;
**reverse-coarser-accepted 13,904 (34.8%)**. Depth histogram peaks at 3;
selected refinement level histogram `[14409, 11267, 4812, 3185, 1845, 1053,
473, 196, 49, 10]` (level 9 never selected). Retained maximum absolute energy
error 0.21 (F) and 0.62 (F50, the 17 exhaustion transitions).

## Post-hoc probes (posthoc.json; not preregistered; not evidence for the claim)

| arm | change from F | R-hat ω | bulk/tail ESS ω | mean ω | var ω | P(ω<−5) (z) | P(ω<−6) (z) | health (div/exhaust/depth/reverse-coarser) | calls | wall s |
|---|---|---|---|---|---|---|---|---|---|---|
| FT | same seed, per-transition trace | bit-identical samples to F | | | | | | | | |
| G | 10-D N(0, I) target, same tuning | 1.0001 | ≈54,000 | 0.005 (z 1.2) | 1.005 | P(x<−2)=0.0232 vs 0.0228 | | 0/0/0/**0** | 634,976 | 0.4 |
| S | h=0.005625, 1 level (no refinement), depth 14 | 1.0092 | 438 / 562 | +0.220 | 8.59 | 0.0350 (−1.4) | 0.0137 (−1.4) | 0/1/476/0 | 76,152,782 | 63.5 |
| M8 | min micro 8, 7 levels | 1.1947 | 15 / 8 | −0.754 | 14.43 | 0.1308 | 0.1150 | 28/4,116/0/5,464 | 9,542,632 | 1.6 |
| R36 | reference, 4 single chains (seeds 81001, 81005, 81006, 81009) whose zero-warmup step search landed exactly on h=0.36, identity metric, 30,000 draws each | 1.0042 | 1,028 / 1,353 | −0.080 | 8.87 | **0.0477** / 0.0478 ± 0.0114 (z −0.01) | **0.0217** / 0.0228 ± 0.0079 (z −0.25) | n/a; q1% = −6.978 (exact −6.979), q0.5% = −7.59 | 9,939,052 | 103.7 |

Trace of F binned by the selected `ω` (retained transitions, all chains):

| ω bin | n | mean depth | mean level | mean calls | outer U-turn | recursive U-turn | reverse-coarser stop |
|---|---:|---:|---:|---:|---:|---:|---:|
| < −8 | 501 | 1.92 | 5.68 | 854 | 0.42 | 0.22 | 0.37 |
| [−8, −6) | 1,535 | 1.85 | 4.28 | 252 | 0.42 | 0.25 | 0.33 |
| [−6, −5) | 1,799 | 1.50 | 3.42 | 97 | 0.61 | 0.17 | 0.22 |
| [−5, −4) | 2,153 | 1.30 | 2.61 | 43 | 0.67 | 0.11 | 0.22 |
| [−4, −2) | 5,592 | 1.95 | 1.63 | 31 | 0.48 | 0.11 | 0.41 |
| [−2, 0) | 9,140 | 2.78 | 0.78 | 17 | 0.53 | 0.09 | 0.39 |
| [0, 2) | 9,338 | 3.93 | 0.47 | 23 | 0.62 | 0.07 | 0.31 |
| [2, 4) | 6,246 | 4.98 | 0.33 | 45 | 0.63 | 0.04 | 0.33 |
| ≥ 4 | 3,696 | 5.91 | 0.34 | 119 | 0.55 | 0.03 | 0.42 |

Neck kinetics from the trace: `P(ω_{t+1} ≥ −5 | ω_t < −5) = 0.081`,
`P(ω_{t+1} < −5 | ω_t ≥ −5) = 0.0086`; the implied stationary neck mass
0.096 equals the observed. The correct ratio would be 0.050. Arm S (no
refinement) has escape 0.086 and entry 0.0031 (implied 0.035). The refinement
path therefore roughly triples the entry rate into the neck relative to what
would balance the escape rate; the reference `walnutpie` code (read, not
copied: `macro_step`/`reversible`/`build_span` in `walnuts.hpp`) treats a
failed reversibility check as a whole-subtree discard that ends the orbit,
which is the same stop semantics oWALNUTS reports as
`ReverseCoarserAccepted`, so the semantics of the stop itself are not the
obvious difference; the discrepancy must be in what the forward/reverse
refinement decisions accept.

Arm M8 additionally shows chains becoming trapped below `ω = −8` with 99%
refinement exhaustion (finest micro step `0.36/512`), which is a health
failure rather than the bias mechanism, but it means `min_micro_steps = 8` with
seven levels is unusable on this target.

## Gate outcomes and decision

* Paper-claim reproduction: **failed** for oWALNUTS (arm F, F50); **passed**
  for the reference implementation (R0, R1, R36).
* The paper's NUTS-side claim reproduces (N11).
* Convergence gates at 4×10,000: only F50 and N11 pass; the reference fails
  them at 10,000 draws per chain too, consistent with the paper's "both
  samplers mix very slowly".
* Health: F is clean at 10,000; F50 has 17 retained refinement exhaustions
  and 64 depth caps in 200,000 transitions.

Decision: **stop treating oWALNUTS's fixed-kernel funnel behaviour as
paper-equivalent.** The next work is a defect hunt in the refinement/reverse
path with the oracle fixtures extended to funnel-like leaves (large forward
level with a flat reverse region), not more tuning. See the ledger entry for
the exact next step.

## Sampler defects observed (documented, not fixed — WP1 owns `src/`)

1. **Neck over-weighting bias under refinement** (this study's main result).
   Reproducible, all chains, z ≈ 10 at 200,000 retained draws, absent on a
   Gaussian and absent without refinement.
2. Refinement-exhaustion trapping at `ω < −8` when `min_micro_steps > 1`
   (M8), i.e. exhaustion is handled as a stop that leaves the chain in place
   indefinitely rather than a rejected leaf with a further-coarsened retry.
3. Reverse-coarser stops occur in 31–42% of transitions in the *mouth*
   (`ω > 0`) where the mean selected level is < 0.5; either coarse reverse
   passes are very common at `δ = 0.21`, or reverse checking is being
   triggered at level 0 (the reference returns `true` immediately when
   `num_steps == 1`). This is worth a unit test.

## Files

`PREREGISTRATION.md`, `protocol.json` (frozen before sampling),
`posthoc.json`, `src/main.rs`, `reference_run.py`, `reference_fixed36.py`,
`analyze.py`, `posthoc_analyze.py`, `checksums.py`, `artifacts/`
(`preflight.json`, `F.json`, `F50.json`, `N11.json`, `N36.json`, `R0.json`,
`R1.json`, `summary.json`, `posthoc-*.json`, `posthoc-summary.json`),
`CHECKSUMS.sha256`. The `.venv-ref314` virtual environment is local and not
committed.
