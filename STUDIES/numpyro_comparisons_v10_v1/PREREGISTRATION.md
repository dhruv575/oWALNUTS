# Preregistration — oWALNUTS v10 versus NumPyro NUTS, three comparison gaps

Frozen 2026-08-31 before any sampling in this directory. Kernel
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10` at HEAD `d8617a8`; paper
adaptation v3. The machine-readable protocol is `protocol.json` (all
settings, gates, predictions); this page states the design and decision rules.

## Why

The research ledger holds three oWALNUTS-vs-NumPyro comparisons that are either
stale (measured on the pre-v9 kernel, whose micro-step acceptance was not
time-reversal symmetric) or missing:

1. **sspd-05 matched timing** — the Polyscope `matched-timing-v1` result
   (5.4–7.3× bulk ESS/s over NumPyro, 12.3 s vs 87.8 s) was measured on
   kernel v7.
2. **Real-market T=48** — the only real-data comparison: NumPyro passed its
   Phase 0.2 confirmation cleanly, while the oWALNUTS pilot (v5–v7, depth 8)
   failed only the maximum-depth gate (3.625% > 1%).
3. **Neal's funnel** — oWALNUTS v10 reproduces the paper (WP6, WP9); the
   paper's contrast claim about NUTS has only been inferred from our own
   no-refinement control arm, never measured on NumPyro itself.

## Common rules

* Seeds `92001, 92002, 92003` for every evidence cell of every backend
  (verified absent from all ledgers and studies); `92000` is the NumPyro
  compile probe and is never evidence.
* Every oWALNUTS cell runs a zero-callback preflight first; every cell has a
  900 s wall cap; deviations are recorded in the cell artifact and README.
* NumPyro cells run with single-thread XLA/BLAS environment flags and
  `chain_method="sequential"`, exactly as `matched-timing-v1`; oWALNUTS cells
  run with one thread. Physical starts are identical across backends
  (`starts/*.json`, WP4b/WP12 rule; the Rust runner re-derives and asserts
  them).
* Timing: oWALNUTS reports the single sampler-call wall (warmup + retained,
  release binary built beforehand); NumPyro reports warmup + sampling wall
  after a same-shape compile probe, and the probe's wall separately. Work
  units are labelled — oWALNUTS fused target calls versus NumPyro leapfrog
  `num_steps` — and are never silently equated.
* Diagnostics: ArviZ 1.3 rank-normalised folded split R-hat, bulk ESS, tail
  ESS (0.05/0.95) on the exported functionals, computed by `analyze.py` from
  the same code path for both backends.
* The machine is shared with two other running agents; ESS per work unit is
  the robust figure, wall figures carry that caveat.

## Part 1 — sspd-05 matched timing on v10

Arms `T-F` (exact matched-timing-v1 oWALNUTS settings: frozen shared
diagonal, levels 4, δ=10, h₀=0.005, accept 0.9, depth 8, 500/4,000), `T-I`
(WP12 arm I: adapted diagonal, levels 3, δ=1, step search, accept 0.8),
`T-P` (WP12 arm P: fixed posterior-precision path block + same-seed `T-I`
globals mass), `T-N` (exact matched-timing-v1 NumPyro settings).
Primary estimand: geometric-mean ratio `T-F`/`T-N` of bulk ESS per total
sampling second over the four matched-timing functionals; ratios are
reported only when both cells pass every gate.

Predictions: **P1** overall ratio ≥ 3; **P2** `T-F`, `T-I`, `T-N` pass 3/3;
**P3** `T-P`/`T-I` bulk ESS per retained call ≥ 2 on every seed.

## Part 2 — real-market T=48 on v10

Arms `R-B` (a=0.75 production coordinates, adapted diagonal, **depth 10**,
kernel v10), `R-I` (a=1, adapted diagonal, depth 10), `R-N` (Phase 0.2
NumPyro settings: a=0.75, accept 0.9, depth 10, 500/2,000). The frozen
NumPyro confirmation (`1ec74426…b828`) is cited as the reference; `R-N`
re-runs it on the evidence seeds for a same-machine wall.

Predictions: **P4** `R-B` and `R-I` pass 3/3 with cap rate ≤ 1%; **P5**
`R-N` passes 3/3; **P6** `R-I` median depth ≤ `R-B` median depth.

## Part 3 — NumPyro on Neal's funnel

10-D funnel, starts ω ∈ {−3, −1, 1, 3}, 2,000 warmup / 4×50,000 retained
(fallback 4×20,000 if a cell exceeds the wall cap; recorded). Arms `FN-F`
(fixed paper tuning, WP6 F50 config), `FN-A` (Appendix C, WP9 A2-R config =
v3 defaults), `FN-N80` (NumPyro NUTS, accept 0.8, depth 10), `FN-N95`
(accept 0.95). Gates are the WP6/WP9 fix gates. A cell "under-covers the
neck" when P(ω<−5) < 0.0478 − 0.009.

Predictions: **P7** `FN-F`, `FN-A` pass 3/3; **P8** `FN-N80` under-covers on
≥ 2/3 seeds and has divergences on 3/3; **P9** `FN-N95` under-covers on ≥ 2/3
(less severely) with divergences on ≥ 2/3; **P10** no NumPyro cell passes
every funnel gate.

## What the results may and may not support

Part 1 and Part 2 wall ratios are platform- and load-specific; they support
"faster on this machine under these settings", not a general claim. ESS per
work unit compares different operations (fused target call vs leapfrog) and
is reported as such. Part 3 supports or retracts the sentence "NumPyro's NUTS
under-covers the funnel neck where oWALNUTS v10 does not" — nothing broader.
