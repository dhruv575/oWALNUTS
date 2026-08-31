# Changelog

All notable changes to oWALNUTS are documented here. Kernel behaviour is
identified by `owalnuts::walnutpie::ALGORITHM_REVISION`; a seed reproduces a
run only under the same revision, crate build, lock file, and target
architecture (see the `walnutpie` module documentation).

## [0.1.0-beta.2] - 2026-08-31

First release candidate. The kernel is at revision
`walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`; the paper adaptation mode
is at `walnutpie-paper-adaptation-kquantile-gamma-v3`. Evidence for every claim
below is a checksummed study under `STUDIES/` with an entry in
`wiki/research-ledger-2026-08-31.md` (entry ids in brackets).

### Fixed

- **Micro-step acceptance statistic (kernel `v9`).** Through `v8` a refinement
  level was accepted when the largest Hamiltonian departure of *any* visited
  micro-step from the start state was within `max_error`. That statistic is
  not symmetric under time reversal, so the deterministic reverse selection
  could disagree with the forward selection and non-reversible leaves were
  accepted. On Neal's 10-D funnel at the paper's tuning the kernel placed about
  twice the correct mass below `omega = -5` (0.0971 vs the exact 0.0478).
  Acceptance now uses the endpoint departure `|H(end) - H(start)|` exactly as
  upstream `walnutpie::macro_step`/`within_tolerance`. Verified by a
  4,000-leaf funnel differential oracle generated from the unmodified upstream
  headers (`oracle/walnutpie/f5bba365_funnel_leaves`; `v8` disagreed on 1,555
  leaves, `v9` agrees on all 4,000 to 1e-11) and by
  `STUDIES/funnel_bias_fix_v1` (P(omega<-5) 0.0474 at 4×50,000 draws).
  Runs that never refine are unchanged; every earlier result from a
  refinement-active run is provisional until re-run.
  [WP2-FUNNEL-REPRO-V1, WP6-FUNNEL-BIAS-FIX-V9]
- **Recoverable target failures refine instead of stopping (kernel `v10`).**
  Through `v9` a `TargetError::recoverable` result stopped the whole transition
  (`StopReason::InvalidEvaluation`), so a stiff model whose coarse micro-steps
  overshoot into a non-representable region produced no-op transitions (65–100%
  of transitions on the Stock–Watson study). Upstream maps a failed evaluation
  to `logp = -inf`, `grad = 0` (`walnutpie/util.hpp`), so the micro-step merely
  fails the endpoint tolerance and the leaf refines; only when every level
  fails is the leaf rejected by refinement exhaustion. `v10` does exactly that,
  excludes zero-density points from the Hamiltonian extrema and divergence
  statistic, and reports them as `zero_density_evaluations` per transition and
  per work partition. A successful run can no longer report
  `StopReason::InvalidEvaluation` (retained in the enum). Nonfinite *returned*
  values (`NaN`, `+inf`, nonfinite gradient) remain fatal. Verified by a
  4,000-leaf differential oracle with a throwing wall target
  (`oracle/walnutpie/f5bba365_invalid_leaves`) and by
  `STUDIES/invalid_evaluation_parity_v1` (0 invalid-evaluation stops across
  216,000 retained transitions and 8.5M recoverable evaluations; truncated
  Gaussian stationary; funnel unchanged). [WP2b-SW-REPRO-V1,
  WP10-INVALID-EVALUATION-PARITY-V10]
- **Paper-mode `h` statistic (paper adaptation `v2`).** The unrefined fraction
  is now taken over *built* leaves, a transition without a built leaf
  contributes no sample and no step update
  (`PaperAdaptationUpdate::transitions_without_statistic`), and the installed
  paper-mode step is bounded to `PAPER_STEP_RELATIVE_BOUND` (1e3) times the
  configured initial step. Under `v1`, all-invalid transitions counted as fully
  unrefined and could drive `h` to its 1e6 ceiling. [WP9]
- The pinned upstream macro-leaf oracle no longer carves out
  `forward_refinement`, `backward_refinement`, and
  `multi_level_reverse_coarsening`; all pinned cases pass unmodified.

### Added

- **JMLR Appendix C adaptation**, opt-in through
  `WarmupConfig::with_paper_adaptation(PaperAdaptationConfig)`: the K-quantile
  rule for `delta` (`max_error`) and `Gamma`-targeted dual averaging for `h`
  (`step_size`), with `PaperStepStatistic`, `PaperRestartPolicy`,
  `PaperAdaptationUpdate` telemetry, `WarmupCheckpointTelemetry::
  unrefined_fraction`/`max_error_after`, and `PAPER_ADAPTATION_REVISION`.
  On Neal's funnel from a conservative start it is unbiased and, with the `v3`
  default, 1.41×/1.61× (bulk/tail ESS per target call) more efficient than the
  paper's fixed funnel tuning. [WP7-FUNNEL-ADAPTIVE-V1,
  WP9-PAPER-H-RULE-STABILISATION-V2]
- Research-only outer-orbit selection switch
  `RunConfig::with_research_outer_orbit_selection` (`OuterOrbitSelection::
  {BiasedProgressive, ExactNormalizedMultinomial}`); the default is unchanged.
- Fixed-metric facades: `DenseMass`, `BlockDiagonalMass`,
  `StructuredBlockMass` (`StructuredCovarianceBlock::{BidiagonalCholesky,
  ScaledAr1}`, linear time), `LowRankArrowheadMass`, and the versioned
  `sample_direct_original_q` family (`DirectOriginalQMass`,
  `DIRECT_ORIGINAL_Q_REVISION`) executing dynamics in target coordinates.
- Research-only projected/pooled arrowhead warmup (`sample_projected_arrowhead`,
  `sample_chains_projected_arrowhead`, `PROJECTED_ARROWHEAD_REVISION`); frozen
  at its stage-7 state and not recommended for use (see
  `wiki/sampler-path-ledger.md`).
- `RunConfig::with_research_target_evaluation_limit`
  (`ResearchTargetEvaluationLimit`, `RESEARCH_MAX_TARGET_EVALUATIONS`) and the
  explicitly budgeted entry points `sample_chains_with_target_budget` /
  `preflight_chains_with_target_budget` for deep-refinement runs that exceed
  the conservative admission ceiling.
- Warmup telemetry checkpoints, `DualAveragingAcceptance::AcceptedTrajectory`
  (research-only), `InitialStepSearchConfig`, and trace-only depth diagnostics
  (final U-turn predicate dots, margin, physical trajectory length).
- Examples `funnel_paper_adaptation` and `state_space_path_metric`; CI on
  Linux/Windows GNU 1.88 and Linux stable.

### Changed

- **Paper-mode default restart policy (paper adaptation `v3`).**
  `PaperAdaptationConfig::default()` continues one dual-averaging stream
  across `delta` installations (`PaperRestartPolicy::
  ContinueThroughLocalErrorInstall`); restarting left chain-specific final
  steps (spread 1.7–2.8×) while continuing gave ≤ 1.3× with equal or better
  efficiency in both tested `Delta` families. Select
  `RestartOnLocalErrorInstall` to reproduce the `v1`/`v2` behaviour.
  [WP9-PAPER-H-RULE-STABILISATION-V2]
- `ALGORITHM_REVISION` advanced `v8 → v9 → v10`. Seeds are not portable across
  revisions; both changes leave the frozen default tuning bit-identical (no
  pinned fingerprint changed) because it never reaches a leaf where the old and
  new rules differ.
- Crate description and README rewritten for a first-time reader; the
  "internal beta" framing is replaced by an explicit validated-results table
  and known-limitations list.

### Validation (2026-08-31 program)

- Neal's funnel, paper tuning (δ = 0.21, h = 0.36, WALNUTS-D, depth 10, 10
  levels), 4×50,000 draws: P(omega<-5) 0.0474 vs exact 0.0478 (z −0.08),
  var(omega) 9.04 vs 9, zero divergences/invalid/exhaustions; the upstream
  reference at identical tuning gives 0.0477. [WP6-FUNNEL-BIAS-FIX-V9]
- Neal's funnel, Appendix C warmup from δ = 1, h = 0.1 (`v3` default): all
  gates pass, final-step spread ≤ 1.27× across chains, 1.41×/1.61× bulk/tail
  ESS per call versus fixed paper tuning. [WP9-PAPER-H-RULE-STABILISATION-V2]
- Noncentered Eight Schools, v38 strict track, kernel `v9`: conservative
  minimum over seven seeds and six functionals 12,830 bulk / 10,346 tail ESS/s
  (CmdStan 6,290 / 3,951; BlackJAX 5,645 / 4,195; NumPyro 5,241 / 4,050); ESS
  per target call unchanged from `v7` (0.96 / 0.99). Walls were measured on a
  loaded machine. [WP8-EIGHT-SCHOOLS-V9-REBENCH-V1]
- Outer-selection reverse ablation on Eight Schools: biased progressive
  selection (the default) gives 1.75× bulk ESS per target call over exact
  normalized multinomial with no tail penalty. [WP3-1]
- Exact Gaussian state-space ground truth, T ∈ {100, 1000}: the
  posterior-precision tridiagonal path metric mixes at depth 3–4 at
  Monte-Carlo accuracy (ESS/call 4.8× identity, ~1,000× a prior-based metric,
  which caps at depth 8 in 92% of transitions at T = 1000). [WP4-ESSGT-V1]
- Real Polyscope state-space target at T = 1000 (non-pathological fixture):
  oWALNUTS passes every gate NumPyro NUTS passes; the posterior-precision path
  block gives 2.8× ESS per call over an adapted diagonal. On the σ_x → 0
  funnel fixture no tested Euclidean sampler passes, NumPyro included (1,510
  divergences). [WP4B-REAL-TARGET-PATH-METRIC-V1]
- Stock–Watson stochastic volatility (simulated series, one seed per arm): the
  paper's fixed tuning does not reproduce the paper's energy-error contrast on
  this series; the Appendix C adaptation arm passes every gate and is 2.0× more
  efficient per call than the fixed tuning. [WP2b-SW-REPRO-V1]

### Errata

- The Eight Schools figures previously circulated as oWALNUTS's "conservative
  minimum across seeds and six functionals" (19,054.65 bulk / 14,494.34 tail
  ESS/s) were the minimum over functionals of the across-seed *median*, while
  competitor figures in the same table were true minima. The like-for-like
  `v7` minimum was 8,634 / 5,949 ESS/s (still fastest among the strict matched
  competitors, 1.37× / 1.42×). The corrected `v9` numbers are above.
  [WP8-EIGHT-SCHOOLS-V9-REBENCH-V1]

## [0.1.0-beta.1] - internal, never published

### Added

- Minimal standalone `owalnuts` crate containing the fixed-diagonal internal-beta facade.
- Bounded Gaussian example, facade tests, resource controls, telemetry, and run identity metadata.
- Private parity tests and pinned upstream oracle fixtures with provenance.
- Opt-in acceptance-driven warmup (dual-averaged step, Welford diagonal mass)
  and configurable `KernelTuning`.

### Removed

- Legacy weighted sampler, NUTS, Python, benchmark, and prototype public surfaces.
