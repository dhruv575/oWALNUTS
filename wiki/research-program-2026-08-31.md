# Research program 2026-08-31: reproduce the paper, then ground-truth the hard target

Status: active. Written 2026-08-31 after auditing `sampler-path-ledger.md`,
the five oWALNUTS studies, and the Polyscope T=1000 line (rows 72–81 of the
Polyscope experiment ledger).

## Findings that motivate this program

1. **No competitor has ever sampled T=1000.** Only JAX gradient parity exists
   for `sspd-10`. Every T=1000 "falsified" row compared two arms that were both
   at R-hat 1.5–2.2 and bulk ESS < 10. Two broken arms are uninformative.
2. **`sspd-10` is a deliberately pathological covering-screen cell**
   (`n1000-strong-near_funnel_zero-…-contaminated`). `sspd-11`
   (`n1000-mixed-regular`) is the non-pathological T=1000 cell and is untouched.
3. **The macro step collapsed.** v7 warmup checkpoints recorded final steps
   3.8e-4–1.2e-3 from an initial 0.005. Under any diagonal or prior-based
   metric the path conditional precision has condition number ~T², a U-turn
   needs ~T leapfrogs, and depth 8 (256) cannot reach it. 83% depth caps at
   T=1000 were predictable from theory; depth 9 could never fix it.
4. **oWALNUTS does not run the paper's warmup.** The research crate has the
   Appendix C K-quantile δ rule (`INTERNAL_PACKAGES/walnuts/src/warmup.rs`);
   the beta replaced it with Stan-style dual averaging on the *coarsest-level
   endpoint energy error*. Neal v3 measured that statistic's correlation with
   accepted-trajectory acceptance at only 0.31–0.44. An adapter that shrinks
   `h` until the coarse step passes on its own defeats the point of WALNUTS
   and confounds every metric experiment run under it.
5. **oWALNUTS has never reproduced the headline result of the paper it
   implements** (Neal's funnel: δ=0.21, h₀=0.36, WALNUTS-D; Stock–Watson:
   δ=0.3, h=0.1, min 8 micro-steps, identity mass).
6. The one confirmed asset is throughput: fastest strict-matched competitor on
   noncentered Eight Schools (19,055 bulk ESS/s vs CmdStan 6,290).

## Decisions

* Freeze the mutable/pooled arrowhead line at stage 7. Keep the code; no new
  sampling on it until the adaptation confound (item 4) is removed.
* No further `sspd-10` sampling until a ground-truth fixture and an external
  reference exist. A paired comparison without a healthy arm or a known
  posterior is logged as *uninformative*, not *falsified*.
* A mechanism is tested on T=1000 only after its effect was predicted and
  observed on a fixture where the prediction is checkable.

## Work packages

### WP1 — Paper warmup in the facade (source change; additive; default bit-identical)

Implement Appendix C as an opt-in `WarmupConfig` mode:

* δ adaptation: per orbit record `K = (H_max − H_min)/δ`; at each window
  boundary set `δ = Δ / q_K(p_a)` with defaults `Δ = 2`, `p_a = 0.95`.
* `h` adaptation: track the fraction of macro steps that needed no refinement
  (`micro = 1`); adjust `h` toward target `Γ = 0.8` (multiplicative
  update on the log scale, bounded per window).
* Diagonal mass via the existing Welford windows is allowed but optional.
* Admit `max_refinement_levels ≥ 10` and `max_depth ≥ 10` in `KernelTuning`
  if currently capped; document resource implications.
* Typed telemetry per window: recorded `K` quantile, `δ` before/after,
  unrefined fraction, `h` before/after.
* Default construction and every existing fingerprint test stay bit-identical.
* Tests: closed-form quantile update, monotone `h` response, window
  accounting, sequential/parallel determinism, zero-callback preflight.

### WP2 — Paper funnel reproduction (`STUDIES/paper_funnel_reproduction_v1`)

* 10-D Neal funnel exactly as the paper (`ω ~ N(0,3)`, `x_i | ω ~ N(0, e^{ω})`
  — confirm against JMLR Section 4.3 text in the Polyscope wiki).
* Arm F (fixed paper tuning): δ=0.21, h=0.36, WALNUTS-D, refinement levels
  ≥8, depth 10, identity mass, no adaptation.
* Arm R (reference): Flatiron `walnutpie` at `C:\dev\walnutpie-f5bba365`
  (Python bindings) with identical tuning, if buildable; otherwise record why.
* Arm A (added in phase 2): WP1 warmup from conservative starts; success is
  landing near arm F's δ/h and matching its diagnostics.
* Gates: rank-normalized folded split R-hat ≤ 1.01 on ω and x₁; bulk and
  tail ESS ≥ 400 per 4×10,000 draws; zero retained divergences/invalid
  evaluations; ω-tail check: retained mass below ω = −5 within Monte-Carlo
  error of the exact `N(0,3²)` marginal (that is the paper's claim NUTS
  fails).
* Fresh seeds; preregister before running; ledger entry with hashes.

### WP3 — Outer-selection ablation (`STUDIES/outer_selection_bps_vs_multinomial_v1`)

The switch `RunConfig::with_research_outer_orbit_selection` exists and is
tested. Freeze the Eight Schools protocol (v38 noncentered target, four frozen
starts, 1,000/1,000, target .95, depth 8, diagonal adaptation), run both arms
on three fresh seeds, evaluate the preregistered ≥1.10 primary ratio and the
tail/squared-functional ≥0.95 safety gates from
`nextstat-0.10.1-clean-room-study.md`. Expected outcome: no change.

### WP4 — Exact state-space ground truth and the posterior-precision path metric (`STUDIES/exact_state_space_ground_truth_v1`)

* Fixture family: Gaussian-observation local level model
  `x_t = x_{t−1} + μ + N(0,σ_x²)`, `y_t = x_t + N(0, R_t)`, T ∈ {100, 1000},
  globals **fixed** (so the posterior is exactly Gaussian with tridiagonal
  precision `Q_rw(σ_x) + diag(1/R_t)`), plus one variant with free `(μ, log σ_x)`
  whose exact 2-D marginal is available by Kalman likelihood on a grid.
* Truth: exact mean/variance per coordinate from the banded solve.
* Arms, all fixed metric, all existing public APIs (no source edits):
  identity; diagonal = posterior variances; **posterior-precision tridiagonal
  metric** via `StructuredCovarianceBlock::BidiagonalCholesky` (Cholesky of the
  tridiagonal precision); prior-precision-only metric (the v7 "local AR(1)"
  analogue) as the negative control.
* Preregistered predictions: identity/diagonal need ~T leapfrogs per U-turn
  (depth cap at T=1000, depth ≤8); posterior-precision metric mixes at depth
  3–4 with error-to-truth at Monte-Carlo level; prior-only fails in the level
  direction.
* Report error-to-truth (mean/variance z-scores), depth distribution, calls,
  wall, and ESS/call.

### WP5 — Phase 2: adaptive funnel arm, Stock–Watson, release hygiene

After WP1 and WP2 complete: run arm A; if it fails, debug WP1 against arm F.
Then CHANGELOG, README, version `0.1.0-beta.2`, `cargo package --locked`,
strict Clippy/fmt/rustdoc, CI, and a release report.

## Rules for agents

* Only WP1 edits `src/`. Others report defects; they do not edit source.
* Commit only your own directories (`git add <dir>`); never `git add -A`.
  Retry on `index.lock`.
* Preregister (write the protocol file) before sampling. Fresh seeds only.
* Every WP ends with an entry in `wiki/research-ledger-2026-08-31.md` using
  the Polyscope ledger template (time, protocol+hash, seeds, status, outcome,
  diagnostics, artifacts, conclusion, next decision).
* Report numbers exactly as measured; failed gates are reported as failed.
