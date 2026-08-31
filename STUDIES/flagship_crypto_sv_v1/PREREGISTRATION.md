# Flagship crypto SV study v1 — preregistration

Frozen 2026-08-31 before any evidence run. Kernel `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`;
`owalnuts` Python package 0.1.0b2 with the budget/admission patch in
`integrations/python/src/lib.rs` (structured masses honor the caller budget as a
research admission ceiling); nutpie 0.16.8; NumPyro 0.21.0; PyMC 5.28.5.
One shared 16-core Windows machine; other agents may run concurrently — wall
times carry that caveat, ESS per work unit is the robust figure.

## Subject

Full-posterior stochastic volatility on daily log returns of the five largest
non-stablecoin cryptocurrencies. Set {BTC, ETH, XRP, BNB, SOL} — BTC and ETH
are #1/#2 by every source; XRP/BNB/SOL are the remaining top-five
non-stablecoins with order varying by source and date (checked 2026-08-31 via
web listings; exact order not material to the study). Data: OKX public
`history-candles` daily closes (confirmed UTC bars, no API key), maximum
available history per symbol, committed under `data/` with SHA-256 in
`CHECKSUMS.sha256`. Returns r_t = ln(c_t/c_{t-1}); T = 3153 (BTC, ETH),
2433 (XRP), 2159 (SOL), 1348 (BNB).

## Model (identical density in every backend)

r_t ~ N(0, e^{h_t}); h_t = mu + phi(h_{t-1}-mu) + sigma eta_t, stationary
init h_1 ~ N(mu, sigma^2/(1-phi^2)). Unconstrained q = [mu, a, s, h_1..h_T]:
phi = 2 sigmoid(a) - 1 with (phi+1)/2 ~ Beta(20, 1.5); sigma = e^s ~
HalfNormal(0.5); mu ~ N(-10, 5^2). Rust reference gradient is finite-difference
tested; the PyMC model and the JAX transcription must pass a parity check
against the Rust reference on 8 frozen points (gradient max relative deviation
and logp shift-sd both ≤ 1e-5) before any BTC sampling; other symbols reuse the
same code paths.

## Cells per asset

| cell | sampler | metric | warmup/draws | notes |
|---|---|---|---|---|
| native | oWALNUTS Rust, paper Appendix C adaptation (defaults) | one-shot precision: tridiagonalized 3x3 global block (2x-inflated stage-A covariance, (mu,s) corner dropped) + AR(1)+curvature path block at stage-A (phi,sigma,h-path) | 1000/3000 | threads 4; depth 10; 6 refinement levels; research evaluation ceiling 1e9 |
| pymc | oWALNUTS via `from_pymc(gil_free=True)` | same metric, same settings | 1000/3000 | measures Python transport cost |
| nutpie | nutpie 0.16.8 on the identical PyMC model | its windowed diagonal | 1000/3000 | cores 4, library defaults otherwise |
| numpyro | NumPyro NUTS on the JAX transcription | adapted diagonal | 1000/3000 | depth 12, target 0.9, sequential chains |

Stage A (part of the native/pymc procedure, run first per asset/seed): oWALNUTS
adapted-diagonal calibration, 800/400 at seed XOR 0xC0FFEE, producing
(mu,a,s) means, 3x3 global covariance, posterior-mean h path, and
(phi_hat, sigma_hat). Its cost is included in the native cell's end-to-end wall.
CmdStan cell: skipped — the timebox went to a Python-package admission defect
found and fixed during piloting (see Deviations).

Seeds: native and pymc run 97001–97003; nutpie and numpyro run 97001 (one seed,
external references). Pilot seed 97000 (BTC only) is non-evidence and was used
to shake out the harness, the calibration procedure, and the metric.

## Gates (per asset, per cell)

Functionals: mu, a, s (reported as phi, sigma), h_T, mean_h; rank-normalized
folded split R-hat and bulk/tail ESS via ArviZ.

- Primary health: R-hat ≤ 1.01 AND bulk/tail ESS ≥ 400 on mu, h_T, mean_h;
  max-depth rate ≤ 1%; oWALNUTS cells: zero divergences, zero invalid, zero
  refinement exhaustions (others: divergences reported).
- Globals (shared bottleneck, measured in pilots at ESS ≈ 15–55 per 1000
  draws for every backend): R-hat ≤ 1.05 and bulk ESS ≥ 100 on a and s at
  this budget; report exact values. This is a weaker gate than the program's
  default 400 and is preregistered as such, before evidence.
- Agreement: for every pair of cells that pass primary health, posterior means
  of all five functionals within 3 combined MCSE.

## Measures

Wall (sampling; plus end-to-end including calibration/compile), work
(oWALNUTS: fused target calls, exact; nutpie/NumPyro: retained leapfrogs,
proxy — never merged), bulk/tail ESS per functional, ESS/s, ESS per work unit,
depth distribution, divergences.

## Pilot findings that shaped the design (recorded before evidence)

1. All four backends agree on the BTC posterior (phi ≈ 0.81, sigma ≈ 0.68) and
   all are bottlenecked by the (a,s) ridge (corr ≈ −0.89): a/s bulk ESS per
   1000 retained ≈ owalnuts-structured 15, owalnuts-diagonal 26, numpyro 17,
   nutpie 55. The globals gate above reflects this shared reality.
2. The one-shot precision metric cut native wall 17.2 s → 4.9 s at equal
   draws and fixed the path functionals; it does not fix the global ridge
   (block-diagonal metrics cannot express the global–path coupling; see
   WP4b's rank-2 analysis).
3. gil_free from_pymc transport cost is ≈ nil on this target (4.73 s vs
   4.93 s native at pilot scale).

## Predictions (frozen)

P1: every cell passes primary health on every asset.
P2: oWALNUTS cells have zero divergences on every asset; NumPyro divergence
    count is reported (no prediction).
P3: pymc-cell sampling wall within 1.3x native on every asset.
P4: cross-backend agreement holds wherever primary health passes.
P5 (risky, from pilots): nutpie exceeds oWALNUTS bulk ESS/s on a and s, while
    oWALNUTS native leads every backend on wall for equal retained draws on at
    least 3 of 5 assets.
P6: no asset shows the sspd-10-style sigma→0 boundary (posterior sigma far
    from zero everywhere); if one does, it is reported as the known open
    boundary, not swapped out.

## Amendment A1 (before any evidence sampling)

The frozen depth-10/6-level configuration is inadmissible at 1000+3000
transitions: the conservative worst-case bound (~1.54e9) exceeds the facade's
hard research ceiling (1e9), and the first evidence dispatch failed closed at
zero-callback preflight. Amended to max_depth 9 (bound ~770M). Pilot depth
histograms under the calibrated metric never exceeded depth 7, so this does
not bind. No evidence draws existed at amendment time.

## Deviations recorded at freeze time

- Binance is geo-blocked from this machine; OKX is the source (equivalent
  public daily closes; BNB history begins 2022-12-21 on OKX).
- During piloting the Python package rejected structured-mass runs above the
  113M conservative ceiling (`Mass::Structured` ignored the caller budget);
  fixed in `integrations/python/src/lib.rs` (budget now also raises the
  research admission ceiling, bounded by the facade hard maximum); package
  tests 13/13.
- Two pilot-phase metric revisions (EWMA constants → stage-A calibration;
  diagonal → tridiagonalized global block) occurred before this freeze and are
  visible in the git history of this study.
