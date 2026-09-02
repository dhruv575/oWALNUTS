# Changelog

All notable changes to oWALNUTS are documented here. Kernel behaviour is
identified by `owalnuts::walnutpie::ALGORITHM_REVISION`; a seed reproduces a
run only under the same revision, crate build, lock file, and target
architecture (see the `walnutpie` module documentation).

## [Unreleased]

### Changed

- **`sampler::Tuning::default()` max depth 8 -> 10** (Stan's default). Chosen
  by the preregistered ablation `STUDIES/adaptation_parity_v1` (nine
  posteriordb models, two seeds): 1.45x geometric-mean minimum bulk ESS per
  gradient over the 0.1 defaults, 17/18 gate passes versus 12/18, no model
  worse beyond seed noise; the correlated regressions `diamonds`, `earnings`
  and `sblrc` capped 55-85 % of transitions at depth 8 and failed every gate.
  Geomean versus CmdStan on the nine models: 0.34x -> 0.49x. Only the
  `sampler` default changes; `walnutpie::KernelTuning::default()` and
  `WarmupConfig::default()` are the frozen `v10` legacy, `ALGORITHM_REVISION`
  is unchanged and the kernel fingerprints still hold.

### Added

- **Robustness after the posteriordb benchmark (WP22 follow-up).**
  (1) `owalnuts-bridgestan` maps a `NaN`/`+inf` log density and a finite log
  density with a nonfinite gradient to the recoverable zero-density path
  (`map_evaluation`), as CmdStan and nutpie reject such proposals; only a
  dimension mismatch stays fatal. (2) `owalnuts::sampler::Init`
  (`Given`, `Uniform { radius, max_attempts }`), `uniform_starts`,
  `Sampler::run_with_init` and `Sampler::run_from_random_starts`: Stan's
  uniform(-2, 2) start rule with retries until the log density and gradient
  are finite, deterministic given the seed. (3) Additive, off-by-default
  guards on `PaperAdaptationConfig`: `with_min_max_error`,
  `with_first_update_after`, `with_metric_update_required`,
  `with_unhealthy_orbits_excluded`, `with_trim_fraction`,
  `with_exhausted_transitions_as_zero`, plus
  `PaperAdaptationOutcome::Deferred`. Measured in
  `STUDIES/paper_adaptation_robust_v1`; kernel fingerprints unchanged.
- **Opt-in Stan-parity warmup controls** on `walnutpie::WarmupConfig`:
  `DualAveragingAcceptance::MeanTrajectoryAcceptance` (Stan's
  `accept_stat__`), `InitialStepSearchConfig::stan()` (Stan's
  `init_stepsize`, at the start and after every metric update),
  `DiagonalMetricRegularization::{TowardUnit, Stan}`,
  `with_stan_restart_reference` (`mu = ln(10 h)` on restart),
  `with_initial_phase_max_error` (a different `delta` for the initial fast
  phase), and the preset `WarmupConfig::stan_style(target)`.
  `sampler::Adaptation::Custom(WarmupConfig)` passes any of them through the
  builder. Evidence in `STUDIES/adaptation_parity_v1`: alone, none of the
  four Stan warmup differences helps (Stan's metric prior freezes chains
  started in a tail under `delta = 1`); with the initial-phase `delta` the
  full preset at depth 10 is 2.0x the default's ESS per gradient (0.68x
  CmdStan) but loses 12-16 % on `kidiq`, `mesquite`, `garch11` and fails
  R-hat on `kidiq`, `earnings`, so it stays opt-in.

- **`owalnuts::sampler`, the 0.2 public API.** One builder, `Sampler`
  (`warmup`, `draws`, `chains`, `seed`, `threads`, `metric`, `adaptation`,
  `tuning`, `limits`, `run`), one result, `Posterior` (chains, flat and
  per-draw access, telemetry, metadata, refresh records), and four small
  option types: `Metric` (`Identity`, `Diagonal`, `Dense`, `Structured`,
  `StructuredRefresh`), `Adaptation` (`None`, `DualAveraging` — the default —
  and `Paper`), `Tuning`, and `Limits` (target-evaluation budget, worst-case
  admission, deadline, timeout, cancellation, depth-stop limit). Twenty-one
  public items including re-exports. Every `run` path is a thin wrapper over
  one `walnutpie` entry point and produces bit-identical draws to calling it
  directly (`tests/sampler_api.rs`); kernel behaviour is unchanged. The
  README quick start and the `gaussian` and `funnel_paper_adaptation`
  examples use it.
- **`research` Cargo feature (off by default).** The research-only items
  (`OuterOrbitSelection`, `ResearchTargetEvaluationLimit`,
  `ResearchRestartReferenceMultiplier`,
  `DualAveragingAcceptance::AcceptedTrajectory`,
  `TargetEvaluationLimitProvenance::ExplicitResearchOptIn`, the
  `direct_original_q` family, and the projected/pooled arrowhead warmup) are
  exported from `walnutpie` only with the feature. They are still compiled
  (`src/walnutpie/research.rs`), so no kernel path changed; the `STUDIES/`
  crates and the Python integration enable the feature.
- **Diagnostics and CmdStan export.** `owalnuts::diagnostics` computes
  rank-normalised folded split R-hat, bulk/tail/quantile/mean ESS, MCSE of
  the mean, and type-7 quantiles per parameter from `&[&[f64]]` chain views
  (Vehtari et al. 2021; every estimator matches `az.rhat`, `az.ess` and
  `az.mcse` to 1e-6 relative on the committed
  `tests/data/arviz_fixture.json`), and `Summary::from_output` builds a
  Stan-style table for a `MultiChainOutput` with per-chain and pooled
  `SamplerHealth` (divergences, invalid-evaluation, depth-cap and
  refinement-exhaustion stops, mean tree depth, target calls, step size);
  `Summary` implements `Display` as an aligned table. `owalnuts::export::
  CmdStanCsv` writes one CmdStan-format CSV per chain (`lp__` recomputed
  from the target when supplied, `stepsize__`, `treedepth__`,
  `n_leapfrog__` as fused target calls, `divergent__`, `energy__` as the
  transition's initial Hamiltonian, then the draws); `arviz.from_cmdstan`
  loads the files and its `az.summary` agrees with the Rust `Summary`
  (`tests/export_cmdstan.rs`, opt-in via `OWALNUTS_ARVIZ_PYTHON`).
  `accept_stat__` is not emitted because the kernel captures acceptance only
  during warmup. No new dependencies.

- **FFI and autodiff backend support.** `RawTarget` wraps a C-ABI
  fused log-density/gradient callback (`RawTargetFn`) so compiled gradients —
  numba/Cython `cfunc`s, BridgeStan-style entry points — run from parallel
  chains with no interpreter lock; `-inf` returns follow the v10 recoverable
  zero-density path and any other nonfinite output is fatal. References,
  boxes, and `Arc`s of targets are now targets (`&dyn Target` works
  everywhere). Fatal target error messages are carried into `Error` and shown
  by its `Display`. `Target::parameter_names` (default `None`) labels
  unconstrained coordinates for diagnostics export. Motivated by the autodiff
  track's measurement that GIL-free callback transport, not sampler
  efficiency, was the remaining gap to nutpie on PyMC models.
  [WP15a-AUTODIFF-BRIDGESTAN-ENZYME-V1, WP15B-PYTHON-TARGETS-V1]

- **Boundary-refreshed structured metrics.** `sample_structured_refresh`,
  `sample_chains_structured_refresh`, and
  `preflight_chains_structured_refresh` run the fixed kernel directly in
  original coordinates through a `StructuredBlockMass` operator and rebuild it
  with a caller-supplied `StructuredMetricRefresh` at every completed slow
  warmup-window boundary (per-chain Welford `WindowSummary`; typed
  `StructuredRefreshUpdate` telemetry; optional boundary step re-search;
  `StructuredRefreshRestartPolicy` for dual averaging; failures keep the
  previous metric installed; the metric freezes before the first retained
  transition). Execution identity `STRUCTURED_REFRESH_REVISION`
  (`walnutpie-structured-metric-refresh-v1`); an identity refresh is
  bit-identical to the fixed direct driver, and `ALGORITHM_REVISION` is
  unchanged. Motivated by the T=1000 state-space result that the posterior-
  precision path block depends on global parameters best estimated during
  warmup. [WP4B-REAL-TARGET-PATH-METRIC-V1, WP12-SSPD11-CONFIRMATION-V1]

### Changed

- **`PaperAdaptationConfig::default()` is `walnutpie-paper-adaptation-kquantile-gamma-v4`.**
  `with_exhausted_transitions_as_zero(true)` and
  `with_step_relative_bound(DEFAULT_PAPER_STEP_RELATIVE_BOUND = 1e6)` are
  now the defaults. `STUDIES/paper_adaptation_robust_v1` traced the
  posteriordb freezes to leaf-less transitions producing no `h` statistic
  and then to the `1e3` step band, not to the `delta` rule; with both
  guards the default is robust on all 14 freeze-model cells and
  0.90-1.35x dual averaging's min bulk ESS per gradient (geomean 1.04).
  The `v3` behaviour is
  `.with_exhausted_transitions_as_zero(false).with_step_relative_bound(PAPER_STEP_RELATIVE_BOUND)`.
  Acceptance-driven warmup, `ALGORITHM_REVISION` and the kernel
  fingerprints are unchanged.

### Fixed

- `sample_chains_structured` and `sample_chains_structured_with_control`
  reject a target, mass, or initial position whose dimensions differ with a
  configuration error instead of panicking.

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
  oWALNUTS with an adapted diagonal in centered coordinates passes every gate
  NumPyro NUTS passes, confirmed on three fresh seeds; the posterior-precision
  path block agrees on every seed and gives 2.7× ESS per call but passed the
  strict conjunctive gate on 2/3 seeds (not yet confirmed)
  [WP12-SSPD11-CONFIRMATION-V1]. On the σ_x → 0
  funnel fixture no tested Euclidean sampler passes, NumPyro included (1,510
  divergences). [WP4B-REAL-TARGET-PATH-METRIC-V1]
- Stock–Watson stochastic volatility (simulated series): the paper's fixed
  tuning does not reproduce the paper's energy-error contrast on this series;
  the Appendix C adaptation arm passes every gate on 2/3 fresh seeds at
  4×2,000 draws (miss: R-hat 1.0101, clean health) and is 2.0× more efficient
  per call than the fixed tuning. [WP2b-SW-REPRO-V1,
  WP12-SSPD11-CONFIRMATION-V1]

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
