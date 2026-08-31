# paper_funnel_adaptive_v2 — preregistration

Frozen 2026-08-31 on kernel `v9` (`ALGORITHM_REVISION =
walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v9`, commit `cfd813b`) and paper
adaptation `walnutpie-paper-adaptation-kquantile-gamma-v2`, before any
sampling in this directory.

## Question

WP7 (`paper_funnel_adaptive_v1`) found the Appendix C `delta` rule reliable
but the `h` rule unstable on the funnel: the per-transition unrefined fraction
is position dependent (0.00–0.86 across windows at the paper's own tuning),
dual averaging restarts after every `delta` installation and therefore stays
in its aggressive early iterations, per-window `h` swung 10–30×, and final `h`
differed 2.4–3.9× across chains. Which of two generic stabilisations of the
`h` rule — (a) a cumulative unrefined-fraction statistic, (b) no dual-averaging
restart at `delta` installations — removes the instability without cost, and
should either become the default of the opt-in paper mode?

Revision `v2` also changed the statistic itself (built leaves only; no sample
from leaf-less transitions; step bounded to 1e3× the initial step). The
control arm therefore reproduces WP7's *rule*, not WP7's numbers; WP7 ran
under `v1`.

## Design

Target, starts (ω ∈ {−3, −1, 1, 3}), identity mass, 10 refinement levels,
depth 10, min micro 1, 2,000 discarded (mass adaptation off) + 4×50,000
retained, one thread, 1e9 callback cap, 900 s wall cap per arm, and the
control reference F9 (`funnel_bias_fix_v1` arm F50, artifact SHA-256
`b0d51a5e…`) are identical to WP7. Conservative start δ = 1.0, h = 0.1.

Two `Delta` families × four `h`-rule variants = eight arms; base seeds
89001, 89011, …, 89071 (chain `i` uses base + i; none of 89001–89074 appears
as a seed in any ledger or study; the `890xx` substrings found by a repository
scan are digits inside floating-point artifact values):

| arm | Δ | statistic | restart at δ install |
|---|---|---|---|
| A2-C | 2.0 | per-transition | yes (v2 default) |
| A2-S | 2.0 | cumulative | yes |
| A2-R | 2.0 | per-transition | no |
| A2-SR | 2.0 | cumulative | no |
| AD-C | 0.72 | per-transition | yes (v2 default) |
| AD-S | 0.72 | cumulative | yes |
| AD-R | 0.72 | per-transition | no |
| AD-SR | 0.72 | cumulative | no |

## Gates (per arm)

1. Unbiased: `|P(ω<−5) − 0.04779| ≤ 0.009`, `|P(ω<−6) − 0.02275| ≤ 0.006`,
   `var(ω) ∈ [8.2, 9.8]`.
2. Health: zero retained divergences, invalid evaluations, refinement
   exhaustions; rank R-hat ≤ 1.01 and bulk/tail ESS ≥ 400 on ω and x₁.
3. Stability: across-chain final `h` max/min ≤ 1.5 and final `δ` max/min ≤ 1.2.
4. Efficiency: bulk ESS(ω) per retained target call ≥ 0.8 × F9 and tail
   ≥ 0.7 × F9.

## Predictions (committed)

* P1. All eight arms pass gate 1 and the health part of gate 2 (retained
  draws use a fixed `v9` kernel; adaptation cannot bias).
* P2. The control arms fail gate 3 on `h` (spread > 1.5), as WP7 did.
* P3. (b) alone removes most of the spread: A2-R and AD-R have `h` spread
  ≤ 1.5. Reasoning: a single dual-averaging stream over ~1,900 slow-window
  transitions weights the whole warmup trajectory of every chain, and its
  averaged iterate is far less sensitive to the last window's region.
* P4. (a) alone reduces but does not remove the spread (the restart still
  re-centres `mu` at a swung instantaneous step; a cumulative mean lags δ
  changes).
* P5. (a)+(b) is at least as stable as (b) and no less efficient than the
  control; its final `h` lands nearer the paper's 0.36 than the control in the
  AD family.
* P6. `δ` spread is ≤ 1.2 in every arm (the δ rule was already stable).
* P7. Efficiency: the stabilised arms gain tail ESS/call relative to the
  control (fewer chains stuck at tiny `h` with depth caps); whether they reach
  0.8×/0.7× F9 is uncertain — the AD family is predicted to fall short on tail.

## Decision rule

A variant becomes the default of paper mode only if it passes gates 1–3 in
both `Delta` families and gate 4 in at least one family, and is not worse
than the control on any gate. If (b) alone qualifies and (a)+(b) does not add
stability, (b) alone becomes the default (smaller change). Otherwise the
defaults stay as they are and the options remain documented opt-ins.
