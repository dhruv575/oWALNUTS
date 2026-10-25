# funnel_defaults_30seed_v1 (WP53): is the shipped default calibrated on Neal's funnel, and is `delta = 2` safe?

## Verdict

**Mixed.** Calibration failure rule R1 did not fire, and the preregistered
rule R2 does recommend `delta = 2` for a posteriordb confirmation. But neither
arm's z distribution is consistent with N(0,1). Both are shifted low by the
same amount.

- **Shipped default (Q1).** 4 of 30 seeds have |z| > 2 (13.3 %; N(0,1)
  expects 1.4, binomial p = 0.046). All four are on the low side. Mean z is
  **−0.419** (p = 0.022) and sd is 1.13. R1 needs > 20 % or |mean z| > 0.5,
  so it is **not triggered**.
- **The four bad cells are silent.** They have zero divergences, no
  `chain_warnings`, and max R-hat ≤ 1.008. No diagnostic flags them.
- **`delta = 2` (Q2).** 0 of 30 seeds have |z| > 2. Mean z is −0.408
  (p = 0.025) and sd is 0.75. The pooled divergence rate is 1.5e-5
  (37 / 2.4 M retained transitions). R2 (a) 0 ≤ 4 + 2, (b) |−0.408| ≤ 0.5
  and (c) 1.5e-5 < 1e-3 all hold, so R2 **recommends `delta = 2` as a
  default candidate for a posteriordb confirmation**.
- **The WP49 divergence liability did not replicate.** WP49 saw 34 vs 11
  divergences. Here it is 37 for `delta2` vs 43 for the default. Depth caps
  are +38 % (3,965 vs 2,871).
- **No default was changed.**
- **The common low bias is the real finding.** It is not specific to either
  arm. The pooled P(omega < −5) is 0.0458 ± 0.0014 for the default and
  0.0455 ± 0.0010 for `delta2`, against an exact 0.0478. That is 4–5 % low;
  combining both arms (60 independent runs) gives t ≈ −2.7. WP49's 12 seeds
  showed the same (0.0451 / 0.0452). P(omega < −6) is 7 % low in both arms,
  and the omega variance is 8.82 / 8.90 against 9.
  - The bias is small: about 0.3 per-seed MCSE.
  - The z statistic amplifies it to a mean of −0.42 because the MCSE is
    positively correlated with the estimate (r = +0.66 / +0.77). A
    low-estimate seed gets a smaller MCSE.
- **House budget (Q3, 1,000/1,000).** The funnel is not sampled adequately
  by any arm. No cell passes the house health gates (0/30 in each arm). The
  median min bulk ESS is 25–30, and z values run down to −25 when a seed's
  chains never reach omega < −5. Divergences are 5 (default), 3 (`delta2`)
  and 0 (`delta0.5`).

Preregistered in `PREREGISTRATION.md` / `protocol.json` (commit `3eea1a7f`,
before the first evidence cell). All 150 cells ran, with exit 0, no errors and
no reruns. Seeds were 530101–530130 (grep-verified fresh). The library is
`main` `e89f54b9`: the branch was fast-forwarded before the build on the
coordinator's instruction, so it includes `f097391c` (`Init::default()` =
`best_of(16)`; `RejectLeaf`). The kernel revision is
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`. The funnel check uses
explicit house starts, so the Init default does not enter. Nonfinite-position
rejections were 0 in every cell.

## Block A: 4 x 2,000 / 20,000 (the house side check), 30 seeds

| arm | \|z\|>2 | mean z | sd z | p(mean) | p(var) | KS p | N(0,1)? | min / max z | pooled P(<−5) | pooled P(<−6) | divergences (rate) | div-free seeds | depth caps | exhaustions | gross-safe | median min bulk ESS | geomean min ESS / gradient | median gradients | median end-of-warmup h | warning cells |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `default` | **4** (13 %) | **−0.419** | 1.130 | 0.022 | 0.29 | 0.29 | no (mean) | −2.95 / +0.96 | 0.0458 | 0.0211 | 43 (1.8e-5) | 14 | 2,871 | 707 | 14 | 522 | 1.18e-4 | 4.38 M | 0.102 | 6 |
| `delta2` | **0** | **−0.408** | 0.751 | 0.025 | 0.057 | 0.058 | no (mean) | −1.90 / +1.01 | 0.0455 | 0.0210 | 37 (1.5e-5) | 18 | 3,965 | 200 | 18 | 515 | 1.11e-4 | 4.03 M | 0.091 | 8 |

Exact values: P(<−5) = 0.0478 and P(<−6) = 0.0228.

Notes on the columns:

- "N(0,1)?" is the frozen test: the mean, variance and KS p-values must all
  be ≥ 0.05.
- Every gross-safety (WP37A F3) failure in all 60 cells is a divergence
  failure. R-hat, the P5 and P6 errors and the omega variance are within F3
  bounds everywhere.

### z histogram (block A)

| z bin | `default` | `delta2` | N(0,1) expected |
|---|---:|---:|---:|
| < −4 | 0 | 0 | 0.0 |
| [−4, −3) | 0 | 0 | 0.0 |
| [−3, −2) | **4** | 0 | 0.6 |
| [−2, −1) | 4 | 8 | 4.1 |
| [−1, 0) | 7 | 14 | 10.2 |
| [0, 1) | 15 | 7 | 10.2 |
| [1, 2) | 0 | 1 | 4.1 |
| [2, 3) | 0 | 0 | 0.6 |
| ≥ 3 | 0 | 0 | 0.0 |

Neither arm has a z ≥ 2, and the default has none ≥ 1. Both are shifted left.
The default has the wider spread, with a left tail; `delta2` is narrower than
N(0,1).

The four default exceedances are seeds 530101 (−2.37), 530105 (−2.49),
530106 (−2.15) and 530111 (−2.95). Divergences in those cells: 0, 1, 0, 1.
None has a chain warning, and max R-hat is 1.005–1.008. These are silent
under-visits of the neck. WP44's checks (5 RHat and 2 WarmupStep flags across
6 default cells) fired only on cells whose z was between +0.13 and +0.96.

### Not preregistered: an MCSE-free check of the bias

The seeds are independent, so the between-seed standard error of the mean
estimate needs no MCSE.

| arm | mean P(<−5) ± s.e. | t vs exact | mean P(<−6) ± s.e. | t vs exact | omega variance (exact 9) |
|---|---|---:|---|---:|---:|
| `default` | 0.0458 ± 0.0014 | −1.44 | 0.0211 ± 0.0009 | −1.82 | 8.82 |
| `delta2` | 0.0455 ± 0.0010 | −2.24 | 0.0210 ± 0.0007 | −2.36 | 8.90 |

The between-seed s.e. of the default (0.0014) equals the mean MCSE over
√30, so the MCSE is not miscalibrated on average. What drives the negative
mean z is a small real deficit of tail mass (about 4–5 % relative, about
0.3 MCSE per seed), seen in both arms and in WP49. The z statistic
exaggerates that deficit because its denominator shrinks with the estimate.
At the house gate of |z| ≤ 2 per seed, the deficit turns about 1 seed in 8 of
the shipped default into a fail. The default's sd of 1.13 is unremarkable;
`delta2`'s 0.75 is borderline (p = 0.057).

## Block B: 4 x 1,000 / 1,000 (the house budget), same seeds

| arm | \|z\|>2 | mean z | sd z | min z | pooled P(<−5) | divergences | div-free seeds | depth caps | exhaustions | house-healthy | median min bulk ESS | median max R-hat | geomean min ESS / gradient | median gradients | warning cells |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `default` | 9 | −2.04 | 3.70 | −14.98 | 0.0413 | 5 | 26 | 139 | 38 | 0 | 27 | 1.12 | 8.2e-5 | 0.31 M | 1 |
| `delta2` | 4 | −1.49 | 3.85 | −17.83 | 0.0436 | 3 | 27 | 129 | 17 | 0 | 25 | 1.12 | 7.7e-5 | 0.34 M | 2 |
| `delta0.5` | 8 | −3.22 | 6.31 | −25.22 | 0.0388 | **0** | 30 | 71 | 48 | 0 | 30 | 1.12 | 9.1e-5 | 0.29 M | 4 |

| z bin | `default` | `delta2` | `delta0.5` |
|---|---:|---:|---:|
| < −4 | 5 | 3 | 7 |
| [−4, −3) | 1 | 0 | 1 |
| [−3, −2) | 3 | 1 | 0 |
| [−2, −1) | 7 | 8 | 3 |
| [−1, 0) | 5 | 8 | 13 |
| [0, 1) | 7 | 9 | 6 |
| [1, 2) | 2 | 1 | 0 |
| ≥ 2 | 0 | 0 | 0 |

At 1,000 draws the MCSE z is not a usable statistic. With bulk ESS around
25, a seed whose chains never enter omega < −5 has an estimate near 0 and a
tiny MCSE, so its z is −10 or lower. All three arms fail the house gates on
every seed, and every arm's pooled tail mass is 9–19 % low. This is what a
user running the house budget on a funnel gets, whichever `delta` they use.
The arms differ only in divergences (0 for `delta0.5`) and slightly in
efficiency: `delta0.5` 1.10x the default's min ESS per gradient, `delta2`
0.94x.

## Predictions

| | prediction | observed | held |
|---|---|---|---|
| P1 | default \|z\|>2 in 2–6 of 30 | 4 | **held** |
| P2 | default mean z in [−0.4, 0.4] | −0.419 | **failed** (narrowly) |
| P2 | default sd z in [0.7, 1.4] | 1.130 | **held** |
| P3 | `delta2` exceedance ≤ default + 2 | 0 vs 4 | **held** |
| P4 | `delta2` divergences ≤ 3x default | 37 vs 43 (0.86x) | **held** |
| P5 | at 1,000/1,000, `delta0.5` fewest and `delta2` most divergences | 0 / 5 (default) / 3 (`delta2`) | **failed**: `delta0.5` fewest held; `delta2` was not the most |

## Decision rules

- **R1** (calibration failure headline iff exceedance > 20 % or |mean z| > 0.5):
  13.3 % and 0.419, so **not triggered**. The direction of the shift is low:
  the tail is under-sampled. It sits 0.08 inside the |mean z| threshold, and
  block B shows the same direction more strongly.
- **R2** (recommend `delta = 2` for a posteriordb confirmation iff
  exceedance ≤ default + 2, |mean z| ≤ 0.5, divergence rate < 0.1 %): all
  three hold, so **recommended**.
  - It is not a flip. WP49's 1.141x over the 17 models came from 3 seeds and
    two seed-pathology models; a confirmation on fresh seeds with more seeds
    on `accel_gp` and `hmm_drive_0` is the next step.
  - On the funnel itself `delta2` costs 0.94x min ESS per gradient and +38 %
    depth caps, and has fewer refinement exhaustions (200 vs 707).

## What this means

1. **The house funnel gate is close to its noise floor for the shipped
   default.** On 3-seed studies, |z| ≤ 2 on every seed fails about
   1 − 0.867³ ≈ 35 % of the time with no change to the sampler. WP49's −4.21
   (seed 94902, reproduced exactly here before the freeze) is a tail draw of
   the same mechanism, not a regression. Future studies should gate the
   funnel on pooled tail mass over ≥ 12 seeds plus total divergences, not on
   per-seed |z| over 3 seeds.
2. **There is a real but small tail deficit at defaults**, about 4–5 % of
   P(omega < −5) and 7 % of P(omega < −6), independent of `delta` ∈ {1, 2}.
   It does not trip R1, but it is the first time the house funnel has been
   measured precisely enough to see it. It belongs in
   `wiki/open-questions.md`. The likely sources are the adapted diagonal step
   or metric, which `delta` does not touch; that is untested here.
3. **`delta = 2` is not worse on the funnel than the shipped default on 30
   seeds.** WP49's "3x divergences" was a 12-seed fluctuation; pooled over
   both studies it is 71 vs 54. That removes the funnel objection to fixed 2.

## Caveats

- Wall times are contended and not used: block A took 107 s for 60 cells,
  and block B a few seconds.
- The z statistic is the house MCSE z. Its negative skew under a
  low-estimate / low-MCSE correlation is a property of the statistic and is
  reported, not corrected.
- The non-preregistered between-seed t-test is labelled as such.
- Disclosed pre-freeze runs on non-evidence seeds 94902 and 5 are listed in
  `PREREGISTRATION.md`.
- No raw draws are saved. Cells hold the summaries, per-coordinate ESS and
  R-hat, per-chain telemetry and warnings.

## Reproduce

```bash
cd STUDIES/funnel_defaults_30seed_v1
RUSTUP_TOOLCHAIN=1.88.0-x86_64-pc-windows-gnu cargo build --release
python run_study.py run A && python run_study.py run B   # stdlib only (Python 3.14.7 used)
python run_study.py analyze
python checksums.py
```

Files: `artifacts/results-table.md` (all tables and all 150 cells per seed),
`artifacts/summary.json`, `artifacts/cells/`, `artifacts/run-log.txt`,
`artifacts/analyze-log.txt`.
