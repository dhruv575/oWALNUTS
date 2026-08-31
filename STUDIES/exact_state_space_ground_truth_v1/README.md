# Exact state-space ground truth v1 (WP4)

Evidence class: diagnostic against an exactly known Gaussian posterior. Not a
benchmark claim and not a Polyscope target result. Preregistration:
[PREREGISTRATION.md](PREREGISTRATION.md); frozen constants and hashes:
`protocol.json`; per-run outputs: `artifacts/runs/*.json`; ArviZ post-processing:
`artifacts/summary.json`, `artifacts/results-table.md`. Raw draws
(`artifacts/draws/*.f64`, 4×2000×T little-endian f64) are reproduced by the
binary and are not committed.

Sampler source: oWALNUTS commit `bc49ffb` (`src/walnutpie.rs` SHA-256
`1b1bcbc5…12ef95`, `src/kernel.rs` `e6cf7700…9680f6`). The live `src/` was
mid-edit by WP1 and did not compile while this ran, so the binary was built
against a `git archive` snapshot of that commit (`Cargo.toml` is committed
pointing at `../..`; rebuild from `bc49ffb` to reproduce bit-for-bit). Two
executions produced byte-identical run summaries.

```powershell
cargo +1.88.0-x86_64-pc-windows-gnu test --release
cargo +1.88.0-x86_64-pc-windows-gnu run --release -- artifacts
python analyze.py
```

## Design (as preregistered)

Centered Gaussian local-level path `x_1..x_T`, fixed globals
(`mu=0.01`, `sigma_x=0.08`, `R_t = 0.0125(1+s_t^2+1/(v_t+1))`, `x_1~N(0,1)`),
posterior precision `H = Q_rw + diag(1/R_t)` (tridiagonal), exact mean and
marginal variances by tridiagonal solves (unit-tested against a dense inverse).
Four fixed momentum covariances `M`, otherwise identical kernels (initial step
0.1, depth 8, refinement levels 3, max error 1.0, dual-averaged step at target
acceptance 0.8 with default initial-step search, mass adaptation off, 500
warmup / 2,000 retained, 4 chains, prior-dispersed starts):

* **I** identity; **D** `diag(1/Var_post)`; **P** `M = H` (bidiagonal Cholesky
  of the posterior precision, `sample_chains_structured`); **Q** `M = Q_rw`
  (prior precision only — exactly the non-centered innovations with unit mass).

Predicted per arm from the whitened spectrum `W = L^-1 H L^-T`:
`kappa`, leapfrogs `~1.75 sqrt(kappa)`, and cap/no-cap at depth 8.
Seeds 83001/83003 (T=100) and 83002/83004 (T=1000). All 16 preflights
started zero target callbacks; worst-case admission was 25.5M evaluations
per cell under the 113M ceiling.

## Results

| T | seed | arm | kappa (pred) | depth pred | median depth | cap rate | min bulk ESS | min tail ESS | max R-hat | min bulk ESS/call | max abs z | mean z^2 | frac abs z>3 | var ratio p05-p95 | level ESS | calls | wall s | step |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 100 | 83001 | I | 13.2 | 3 | 5 | 0.000 | 7588 | 6007 | 1.0010 | 3.92e-02 | 2.50 | 0.97 | 0.0000 | 0.97-1.03 | 7328 | 236,497 | 0.2 | 0.0222 |
| 100 | 83001 | D | 13.4 | 3 | 4 | 0.000 | 7862 | 5937 | 1.0019 | 4.26e-02 | 3.04 | 0.98 | 0.0100 | 0.97-1.02 | 6675 | 227,205 | 0.2 | 0.3102 |
| 100 | 83001 | P | 1 | 2 | 3 | 0.000 | 9382 | 4974 | 1.0026 | 1.46e-01 | 2.07 | 0.80 | 0.0000 | 0.96-1.03 | 11922 | 89,774 | 0.1 | 0.4850 |
| 100 | 83001 | Q | 6.1e+03 | 8* | 8 | 0.000 | 8165 | 5492 | 1.0014 | 4.17e-03 | 2.79 | 0.70 | 0.0000 | 0.96-1.02 | 7945 | 2,406,410 | 2.2 | 0.0136 |
| 1000 | 83002 | I | 13.2 | 3 | 5 | 0.000 | 6367 | 5284 | 1.0027 | 2.95e-02 | 3.35 | 0.87 | 0.0010 | 0.97-1.03 | 5234 | 275,793 | 1.0 | 0.0154 |
| 1000 | 83002 | D | 13.2 | 3 | 5 | 0.000 | 5976 | 5148 | 1.0022 | 2.77e-02 | 3.55 | 1.07 | 0.0040 | 0.97-1.03 | 4869 | 274,780 | 1.0 | 0.2101 |
| 1000 | 83002 | P | 1 | 2 | 4 | 0.000 | 18049 | 3928 | 1.0051 | 1.41e-01 | 3.71 | 1.12 | 0.0060 | 0.95-1.05 | 25186 | 165,338 | 1.0 | 0.3291 |
| 1000 | 83002 | Q | 1.75e+05 | 10* | 8 | 0.929 | 256 | 580 | 1.0257 | 1.33e-04 | 3.54 | 1.02 | 0.0030 | 0.94-1.06 | 6444 | 2,375,908 | 14.8 | 0.0026 |
| 100 | 83003 | I | 13.2 | 3 | 4 | 0.000 | 7891 | 5795 | 1.0016 | 4.21e-02 | 2.27 | 0.88 | 0.0000 | 0.97-1.03 | 6775 | 231,077 | 0.2 | 0.0225 |
| 100 | 83003 | D | 13.4 | 3 | 4 | 0.000 | 7925 | 5945 | 1.0018 | 4.34e-02 | 2.80 | 1.11 | 0.0000 | 0.96-1.04 | 6027 | 225,202 | 0.1 | 0.3110 |
| 100 | 83003 | P | 1 | 2 | 3 | 0.000 | 10931 | 5003 | 1.0031 | 1.71e-01 | 2.84 | 1.11 | 0.0000 | 0.96-1.04 | 12336 | 89,165 | 0.1 | 0.4915 |
| 100 | 83003 | Q | 6.1e+03 | 8* | 8 | 0.000 | 8117 | 5315 | 1.0020 | 4.19e-03 | 2.83 | 1.24 | 0.0000 | 0.97-1.03 | 7671 | 2,392,694 | 2.1 | 0.0137 |
| 1000 | 83004 | I | 13.2 | 3 | 5 | 0.000 | 6311 | 4910 | 1.0020 | 2.92e-02 | 3.13 | 0.93 | 0.0030 | 0.97-1.03 | 4669 | 274,765 | 1.0 | 0.0152 |
| 1000 | 83004 | D | 13.2 | 3 | 5 | 0.000 | 5896 | 5231 | 1.0017 | 2.73e-02 | 3.50 | 1.08 | 0.0030 | 0.97-1.03 | 4698 | 275,050 | 1.1 | 0.2115 |
| 1000 | 83004 | P | 1 | 2 | 4 | 0.000 | 17795 | 3848 | 1.0051 | 1.39e-01 | 3.24 | 1.05 | 0.0020 | 0.95-1.05 | 20191 | 165,359 | 1.1 | 0.3303 |
| 1000 | 83004 | Q | 1.75e+05 | 10* | 8 | 0.922 | 292 | 616 | 1.0246 | 1.54e-04 | 3.23 | 0.99 | 0.0050 | 0.94-1.06 | 7498 | 2,345,322 | 14.3 | 0.0027 |

`*` = cap predicted. "cap rate" is the retained `MaximumDepth` stop fraction;
"calls" are actual fused target callbacks including warmup; "step" is the mean
final adapted macro step; "level ESS" is bulk ESS of the path mean. Every cell:
zero retained divergences, invalid evaluations, refinement exhaustions, and
zero warmup divergences.

## Prediction verdicts

1. **P mixes at depth 2–4 with Monte-Carlo-level accuracy — held.** Median
   depth 3 (T=100) and 4 (T=1000); depth histogram at T=1000 is 7,988/8,000
   transitions at depth 4 with 15 leaves; `frac |z|>3` 0–0.6%, no `|z|>5`,
   mean `z^2` 0.80–1.12, variance ratios 0.95–1.05. Bulk ESS exceeds the
   draw count (antithetic), min bulk ESS/call 0.14 at T=1000 — 4.8× arm I and
   ~1,000× arm Q.
2. **I and D do not cap at either T — held** (cap rate 0.000 in all 8 cells,
   min bulk ESS ~6,000 at T=1000, T-independent). This confirms the
   preregistered refinement of the program's item 3: centered path
   coordinates with informative observations have `kappa ~ 13` independent of
   `T`; the `~T^2` conditioning belongs to innovation coordinates.
3. **Q caps at T=1000 with degraded ESS — held** (cap 92–93%, min bulk ESS
   256–292, R-hat 1.025, step 0.0026, 5–8% reverse-coarser stops). At T=100 it
   U-turns at depth 8 (0% truncation, matching the 137-leapfrog prediction)
   but is already 10× less efficient per call than I. **The mechanism clause
   did not hold as written:** the path level is the *stiff* direction under a
   prior-only metric (it forces the tiny step; its ESS stays ~6,000), and the
   slow modes are the prior-dominated fine-scale coordinates (min-ESS
   coordinates 832/835; first-difference ESS ~300).
4. **ESS/call ordering at T=1000 `P > D >= I >> Q` — held except `D >= I`**:
   observed P 0.14 > I 0.029 ≈ D 0.028 >> Q 0.00013. With `kappa` already 13,
   the diagonal rescaling has nothing left to fix.

The mechanical "median depth within ±1 of predicted" gate failed in 9/16
cells: the heuristic assumed a step near the stability limit, while dual
averaging on the coarse-endpoint statistic lands ~3× below it (arm I:
0.015–0.022 vs `1.8/sqrt(lambda_max)` ≈ 0.068), adding 1–2 doublings. The
cap/no-cap dichotomy, which is the substantive claim, held in 16/16 cells.
One accuracy gate (T=100, D, seed 83001) failed at the boundary with exactly
1/100 coordinates at `|z| = 3.04`; its replicate passed and mean `z^2` is 0.98,
so this is not evidence of bias.

Cross-reference for WP2/WP6: reverse-coarser stops fired at refinement level
0 in every arm (0.2–0.6% of retained transitions for I/D/P, 5–8% for Q). On
this Gaussian target the pooled calibration (`mean z^2` ≈ 1 over 100–1,000
coordinates per cell, variance ratios centered on 1) bounds any resulting
bias below Monte-Carlo resolution at 8,000 draws; it does not test the funnel
regime where WP2 observed bias.

## Implications for the Polyscope T=1000 line

* The v7/v8 path metrics ("exact a=.75 covariance pushforward", "local
  AR(1)") are **prior-based** metrics. In this controlled setting a
  prior-based path metric is arm Q: 92% depth-8 caps, step ~3e-3, min bulk ESS
  ~270 — the same phenomenology the ledger recorded at T=1000 (83–92% caps,
  steps 4e-4–1e-3, ESS < 10). Restoring omitted local links (row 77) could not
  help because the metric family, not its completeness, is wrong.
* The **posterior-precision** path metric `Q_rw(sigma_x) + diag(1/R_t)` is
  tridiagonal, linear-time, already representable with
  `StructuredCovarianceBlock::BidiagonalCholesky`, and makes the path block
  exactly whitened at any `T`. Even the identity metric in centered
  coordinates is ~100× more efficient per call than the prior-based metric at
  T=1000.
* The remaining difficulty on the real target is therefore not the path block
  but (a) the global–path coupling (rank ≤ 6; the arrowhead machinery's proper
  job) and (b) the globals' own geometry (`sigma_x` funnel, weakly identified
  `alpha/beta/gamma/nu`). Those are not addressed here.

## Next step

Fresh-seed diagnostic on the canonical-v2 target in fully centered (`a=1`)
coordinates with the globals **frozen** at data-informed values: (i) exact
truth by Kalman for the Gaussian-observation variant, (ii) arms I and P as
here, (iii) then release `(mu, log sigma_x)` with the posterior-precision path
block re-derived from the current global estimate at each slow-window
boundary and a rank-2 arrowhead for the coupling. No `sspd-10` sampling is
authorised by this study.
