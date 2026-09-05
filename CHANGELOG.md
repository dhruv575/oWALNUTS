# Changelog

All notable changes to oWALNUTS are documented here. Kernel behaviour is
identified by `owalnuts::walnutpie::ALGORITHM_REVISION`; a seed reproduces a
run only under the same revision, crate build, lock file, target
architecture and operating system (see the `walnutpie` module documentation).

## [0.2.0] - 2026-09-04

The kernel is at revision `walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10`
(unchanged since 0.1.0-beta.2: every pinned fingerprint and oracle still
holds); the paper adaptation mode advances to
`walnutpie-paper-adaptation-kquantile-gamma-v4`. Evidence for every claim is a
checksummed study under `STUDIES/` (study codes in brackets). Summary in
`wiki/release-0.2.0.md`.

### Upgrading from 0.1.0-beta

- The `walnutpie` facade is still exported unchanged; every 0.1 call site
  compiles. New code should use `owalnuts::sampler`, whose `run` paths are
  thin wrappers over the same entry points and produce bit-identical draws.
- Research-only items (`OuterOrbitSelection`,
  `ResearchTargetEvaluationLimit`, `ResearchRestartReferenceMultiplier`,
  `DualAveragingAcceptance::AcceptedTrajectory`,
  `TargetEvaluationLimitProvenance::ExplicitResearchOptIn`, the
  `direct_original_q` family, the projected/pooled arrowhead warmup) now need
  `features = ["research"]`.
- `sampler::Tuning::default()` is **not** `walnutpie::KernelTuning::default()`,
  and `RunConfig` keeps the frozen legacy defaults: the sampler defaults are
  max depth 10, macro step `h = 0.5` and `delta = 1`, with eight refinement
  levels; `KernelTuning::default()` remains the frozen replay tuning of
  `ALGORITHM_REVISION` (depth 3). Runs configured through `RunConfig` are
  unaffected; runs configured through `Sampler` without an explicit
  `.tuning(..)` use the new defaults.
- `PaperAdaptationConfig::default()` changed behaviour (v4, see Changed). The
  v3 behaviour is one builder call away.
- `Sampler` caches the initial evaluation by default (see Changed): draws
  are bit-identical but every transition makes one target call fewer, so
  target-call totals and ESS-per-call figures are not comparable with 0.1
  runs; `Sampler::cache_initial_evaluation(false)` restores the old
  accounting, and `RunConfig` keeps the cache off.

### Added

- **Warmup-time chain rescue** (`STUDIES/chain_rescue_v1`,
  [WP33-CHAIN-RESCUE-V1]). `walnutpie::WarmupConfig::with_chain_rescue(ChainRescueConfig)`
  makes the multi-chain diagonal driver (`sample_chains_with_control` and
  its wrappers; the `sampler` identity and diagonal paths) advance the
  chains window by window and meet at the end of every slow metric window.
  `ChainRescueConfig::restart_from_best()` scores every chain on the window
  just completed (post-boundary step; median and IQR of the selected
  states' log density) and re-seeds an outlier — step below 0.1x the
  chains' median, or median log density more than three within-chain IQRs
  below the chains' median — from the largest-step non-outlier chain's
  window: one of its positions (drawn with the outlier's own RNG stream),
  its metric, step and dual-averaging state. `pool_at_boundaries()` merges
  the chains' window variances exactly and installs the pooled metric and
  the median step everywhere. Both act only on discarded transitions;
  retained draws come from the unchanged per-chain kernel, and a boundary
  with no outlier changes nothing. Every decision is a `ChainRescueUpdate`
  (`window_index`, `transition`, `chain`, scores, `ChainRescueOutcome::{Kept,
  Skipped, Restarted { source, criterion, source_position, step_after },
  Pooled }`) in `RunTelemetry::chain_rescues`. Internally `run_chain` is
  now `ChainRun::start / advance / finish`; the plain path runs the three
  back to back on one thread and is bit-identical (every fingerprint and
  test unchanged). Single-chain runs ignore the option; the dense and
  structured-refresh facades reject it. Tests: `tests/chain_rescue.rs`
  (determinism across seeds and thread counts, the density rule fires on a
  chain started in a trap and the rescued chain samples the main mode,
  never fires on a Gaussian and the draws are the plain run's, every
  record lies in warmup, skipped boundaries and one chain are the plain
  run, dense rejects).

- **Orbit-position diagnostics** (`STUDIES/kernel_gap_v1`,
  [WP30-KERNEL-GAP-V1]). `walnutpie::TransitionDiagnostics` gains
  `orbit_states` (states in the final orbit), `selected_index` and
  `initial_index` (positions of the selected and the initial state within
  it, from the backward end); `WorkTotals` gains
  `accepted_forward_micro_steps` (target calls attached to a built leaf)
  and `refinement_level_built` (built leaves by refinement level). Counters
  only: draws, call counts and fingerprints are unchanged. The kernel's
  `Span` carries `states` and `selected_offset` for them. The reference
  NUTS of `examples/kernel_efficiency.rs` moved to
  `examples/support/reference_nuts.rs` (any `Target`, the same orbit
  statistics); `examples/funnel_kernel_options.rs` takes `--seed` and
  `--sampler-defaults`. The study decomposes the per-gradient gap to NUTS
  on six posteriordb models at CmdStan's adapted step, metric and starts:
  gradients per leaf 1.01x and no selection difference; leaves per orbit
  0.60x under the endpoint U-turn statistic (41-69 % recursive U-turns);
  `UTurnRule::MomentumSum` restores 0.97x leaves and 0.90x ESS per gradient
  (default 0.77x), with the residual refinement's reverse-coarser stops.
  No new option; the recommendation is to re-decide `MomentumSum` as the
  default jointly with `DiagonalMetricRegularization::Stan`.
- **Per-chain R-hat attribution** (`STUDIES/step_collapse_v1`,
  [WP27-STEP-COLLAPSE-V1]). `diagnostics::Summary` carries
  `chain_disagreement: Option<ChainDisagreement>`: when the maximum rank
  R-hat over parameters exceeds `diagnostics::RHAT_DISAGREEMENT_THRESHOLD`
  (1.01) and there are at least three chains, the maximum R-hat is
  recomputed with each chain left out and the chains whose removal alone
  brings it below the threshold are named (a chain in a second mode, a
  chain that never left its start); an empty list says no single chain
  explains the failure. `Summary`'s `Display` prints the line.
- **Two opt-in warmup step floors**, off by default, measured and not
  recommended (`STUDIES/step_collapse_v1`): `WarmupConfig::with_step_floor_relative_to_search`
  (the adapted step is at least a fraction of the latest initial-step
  search result; requires a search) and `WarmupConfig::with_max_window_shrink`
  (the adapted step never falls below the step its dual-averaging stream
  started from divided by a factor). Neither moves a collapsed step, the
  search floor loses 30 % on the controls, and the shrink bound pins
  `arma11` chains that need to slide through thirty orders of magnitude.
- **The frozen-chain escape rule** (`STUDIES/freeze_mode_v1`,
  [WP24-FREEZE-MODE-V1]). `walnutpie::ExhaustionRule::AcceptUnlessDivergent`
  keeps the finest attempt of a leaf that failed `delta` at every refinement
  level unless it is divergent in Stan's sense, `H_end - H_0 >
  divergence_threshold` with `H_0` the transition's initial Hamiltonian:
  one-sided and relative to the transition, so an energy drop of any size is
  accepted and, once the trajectory sits below `H_0`, a leaf's own error no
  longer ends the orbit. Rises below the rounding noise of `H_0`
  (`|H_0| * 2^-40`, `walnutpie::HAMILTONIAN_NOISE_RELATIVE`) count as zero,
  and such a leaf feeds Stan's `min(1, exp(H_0 - H_end))` to the step
  statistic. `WarmupConfig::with_warmup_exhaustion_rule` applies a rule to
  the discarded transitions only. This is what lets a chain slide out of a
  start where the leapfrog is unstable at every step size: the `arma11`
  starts of `posteriordb_bench_v2` (log density -4.5e19 to -1.8e115) froze
  every oWALNUTS arm because WALNUTS' two-sided `|H_end - H_start| <= delta`
  turns every downhill step into an exhaustion and the coarse-endpoint
  statistic then drives dual averaging into a floating-point no-op
  equilibrium (`q + h v == q`); CmdStan escapes the same starts through its
  one-sided test. The one-sided rule is *not* reversible beyond the
  threshold (the funnel tail mass at the sampler defaults drops from 0.024
  to 0.014 when it is applied to retained draws — as does the existing
  two-sided `AcceptBelowDivergenceThreshold`, 0.013), hence the warmup-only
  option.
- `WarmupConfig::with_minimum_step`: a floor on the adapted step (a
  negative control of the study; a chain whose every leaf fails at every
  step size is not helped by it).
- `walnutpie::TransitionDiagnostics::{step_size, position_changed,
  acceptance_statistic}`: the macro step the transition ran with, whether
  the selected position differs from the initial one, and the statistic
  fed to dual averaging.
- `tests/freeze_mode.rs`: the pin and the escape on a synthetic Gaussian
  with an exponential wall, without BridgeStan.

- **`owalnuts::sampler`, the 0.2 public API.** One builder, `Sampler`
  (`warmup`, `draws`, `chains`, `seed`, `threads`, `metric`, `adaptation`,
  `tuning`, `limits`, `run`, `run_with_init`, `run_from_random_starts`), one
  result, `Posterior` (chains, flat and per-draw access, telemetry, metadata,
  refresh records), and five small option types: `Metric` (`Identity`,
  `Diagonal`, `Dense`, `Structured`, `StructuredRefresh`), `Adaptation`
  (`None`, `DualAveraging` — the default — `Paper`, and
  `Custom(WarmupConfig)` for the opt-in Stan-parity controls below), `Tuning`,
  `Limits` (target-evaluation budget, worst-case admission, deadline, timeout,
  cancellation, depth-stop limit) and `Init`. Every `run` path is a thin
  wrapper over one `walnutpie` entry point and produces bit-identical draws to
  calling it directly (`tests/sampler_api.rs`); kernel behaviour is unchanged.
  The README quick start and the `gaussian` and `funnel_paper_adaptation`
  examples use it.
- **Uniform starts with retries.** `sampler::Init` (`Given`, `Uniform {
  radius, max_attempts }`, default `Init::uniform()` = Stan's uniform(-2, 2)
  with 100 attempts), `uniform_starts`, `Sampler::run_with_init` and
  `Sampler::run_from_random_starts`: a start is redrawn until the log density
  and gradient are finite, deterministically given the seed (start RNG
  `splitmix64(seed ^ INIT_SEED_TAG)`, independent of the chain seeds).
  `STUDIES/posteriordb_bench_v1` aborted two `lotka_volterra` seeds on an
  unevaluable single draw; with this rule they proceed as CmdStan's do.
  [WP22-POSTERIORDB-BENCH-V1 follow-up]
- **`research` Cargo feature (off by default).** The research-only items
  listed under Upgrading are exported from `walnutpie` only with the feature.
  They are still compiled (`src/walnutpie/research.rs`), so no kernel path
  changed; the `STUDIES/` crates and the Python integration enable the
  feature.
- **Research-only `NonfinitePositionPolicy`.** `KernelTuning::
  with_nonfinite_position` / `sampler::Tuning::nonfinite_position` select
  what a transition does when the integrator hands the target a nonfinite
  position. The default `Abort` is the frozen `v10` behaviour (the run ends
  with `ErrorKind::Numerical`); the opt-in `RejectLeaf` treats the point as a
  zero-density leaf with a zero gradient, like a recoverable target failure,
  and counts it in `WorkTotals::nonfinite_position_rejections`. Runs in which
  the event never occurs are bit-identical under either policy; fingerprints
  unchanged. Motivated by `STUDIES/sspd_target_fatal_diag_v1`; qualified as
  an opt-in only by `STUDIES/nonfinite_position_policy_v1` (WP38).
- **Research-only `ReverseCoarserPolicy`.** `KernelTuning::
  with_reverse_coarser_policy` / `sampler::Tuning::reverse_coarser_policy`
  select what a transition does when a refined leaf fails the reverse
  coarsening check. The default `StopOrbit` is the frozen behaviour (the
  doubling is discarded and the orbit ends). The opt-in `ZeroWeightBeyond`
  keeps that leaf's forward endpoint and every leaf beyond it in the same
  direction at zero weight, skipping their reverse checks, and lets the
  orbit run to its U-turn or depth cap; selection is restricted to the
  states connected to the current one through passing leaves, so the
  transition stays exact. Counted in `WorkTotals::
  reverse_coarser_continuations` / `zero_weight_leaves`. Runs in which no
  leaf fails the check are bit-identical under either policy; fingerprints
  unchanged. Motivated by the WP34 finding that 26-59% of refinement
  attempts fail the check on the posteriordb models furthest behind CmdStan;
  measured in `STUDIES/reverse_coarser_policy_v1` (WP39).
- **Diagnostics and CmdStan export.** `owalnuts::diagnostics` computes
  rank-normalised folded split R-hat, bulk/tail/quantile/mean ESS, MCSE of
  the mean, and type-7 quantiles per parameter from `&[&[f64]]` chain views
  (Vehtari et al. 2021; every estimator matches `az.rhat`, `az.ess` and
  `az.mcse` to 1e-6 relative on the committed
  `tests/data/arviz_fixture.json`), and `Summary::from_output` builds a
  Stan-style table for a `MultiChainOutput` with per-chain and pooled
  `SamplerHealth` (divergences, invalid-evaluation, depth-cap and
  refinement-exhaustion stops, mean tree depth, target calls, step size);
  `Summary` implements `Display` as an aligned table.
  `owalnuts::export::CmdStanCsv` writes one CmdStan-format CSV per chain
  (`lp__` recomputed from the target when supplied, `stepsize__`,
  `treedepth__`, `n_leapfrog__` as fused target calls, `divergent__`,
  `energy__` as the transition's initial Hamiltonian, then the draws);
  `arviz.from_cmdstan` loads the files and its `az.summary` agrees with the
  Rust `Summary` (`tests/export_cmdstan.rs`, opt-in via
  `OWALNUTS_ARVIZ_PYTHON`). `accept_stat__` is not emitted because the kernel
  captures acceptance only during warmup. No new dependencies.
- **Opt-in Stan-parity warmup controls** on `walnutpie::WarmupConfig`:
  `DualAveragingAcceptance::MeanTrajectoryAcceptance` (Stan's
  `accept_stat__`), `InitialStepSearchConfig::stan()` (Stan's
  `init_stepsize`, at the start and after every metric update),
  `DiagonalMetricRegularization::{TowardUnit, Stan}`,
  `with_stan_restart_reference` (`mu = ln(10 h)` on restart),
  `with_initial_phase_max_error` (a different `delta` for the initial fast
  phase), and the preset `WarmupConfig::stan_style(target)`;
  `sampler::Adaptation::Custom(WarmupConfig)` passes any of them through the
  builder. Evidence in `STUDIES/adaptation_parity_v1`: alone, none of the
  four Stan warmup differences helps (Stan's metric prior freezes chains
  started in a tail under `delta = 1`); with the initial-phase `delta` the
  full preset at depth 10 is 2.0x the default's ESS per gradient (0.68x
  CmdStan) but loses 12-16 % on `kidiq`, `mesquite`, `garch11` and fails
  R-hat on `kidiq`, `earnings`, so it stays opt-in.
- **Opt-in kernel rule variants** (`STUDIES/kernel_efficiency_v1`).
  `walnutpie::KernelOptions` (`KernelTuning::with_options`,
  `sampler::Tuning::kernel_options`) selects the no-U-turn predicate
  (`UTurnRule::{Endpoints, EndpointsWithCross, MomentumSum}`; `MomentumSum`
  is Stan's generalised criterion on the sum of the leaf momenta with the
  2.21+ cross checks) and the treatment of a leaf that fails `delta` at
  every refinement level (`ExhaustionRule::{Stop,
  AcceptBelowDivergenceThreshold}`; the latter is Stan's rule, subject to
  the usual reverse coarsening check so the leaf stays reversible).
  `RunConfig::with_cached_initial_evaluation` reuses the previous
  transition's selected log density and gradient instead of re-evaluating
  the current position at the start of every transition. `KernelOptions::
  default()` and the cache off reproduce the frozen fingerprints; on the
  100-D Gaussian `MomentumSum` with the cache takes the kernel from 0.81x to
  1.09x reference NUTS ESS per gradient, is neutral within seed noise on the
  correlated Gaussian and Eight Schools, and preserves the funnel tail mass
  (`examples/funnel_kernel_options.rs`). The preregistered posteriordb
  decision (`STUDIES/uturn_default_v1`, [WP26-UTURN-DEFAULT-V1]) kept
  `Endpoints` as the default: `MomentumSum` is 1.06x geomean over the 17
  models (1.18–2.14x on six, 0.78–0.93x on seven), passes one cell fewer,
  and the funnel at the sampler defaults is biased under every rule.
- **Additive, off-by-default Appendix C guards** on `PaperAdaptationConfig`:
  `with_min_max_error`, `with_first_update_after`,
  `with_metric_update_required`, `with_unhealthy_orbits_excluded`,
  `with_trim_fraction`, `with_exhausted_transitions_as_zero` (a default since
  v4, see Changed), plus `PaperAdaptationOutcome::Deferred`. Measured in
  `STUDIES/paper_adaptation_robust_v1`; kernel fingerprints unchanged.
- **FFI and autodiff backend support.** `RawTarget` wraps a C-ABI fused
  log-density/gradient callback (`RawTargetFn`) so compiled gradients —
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
- **`owalnuts-autodiff` (`integrations/autodiff`, unpublished).** Write a
  log density once as `fn log_density<S: Scalar>(&self, q: &[S])`, evaluate
  it with `f64` or with `Var` on a reusable thread-local arena tape, and get
  an `AutodiffTarget<M>` implementing `walnutpie::Target`. Fused primitives
  (`normal_lpdf`/`lupdf` with broadcasting, Student-t, Cauchy, lognormal,
  exponential, gamma, half-normal, `bernoulli_logit`, `poisson_log`, `dot`,
  `sum`, `log_sum_exp`, `cumsum`, `softplus`, and the exp/logistic/interval/
  ordered constraints with log-Jacobians) with hand-gradient and
  finite-difference oracles; numbers in `integrations/AUTODIFF-RESEARCH.md`.
- **`owalnuts-bridgestan` (`integrations/bridgestan`, unpublished):**
  `ReplicatedStanTarget` (one library copy per thread, `try_lock` dispatch)
  and a per-library-file serialising mutex for `StanTarget`, after the
  measurement that `STAN_THREADS` on mingw-w64 costs 9-16x per gradient
  (emulated TLS); the non-threaded build matches CmdStan's per-gradient
  cost (`arK` wall 10.5 s -> 1.5 s against CmdStan's 1.0 s, trajectories
  bit-identical). [WP22-POSTERIORDB-BENCH-V1 follow-up]
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
- **Python package `owalnuts` 0.2.0** (`integrations/python`, unpublished):
  every run builds an `owalnuts::sampler::Sampler`, so the package inherits
  the sampler defaults (see Fixed); `owalnuts.DEFAULTS` reports them
  read-only from the Rust constants; `init="uniform"` start rule
  (`Init::uniform`), `Tuning(u_turn_rule=, exhaustion_rule=)` and
  `Adaptation(metric_regularization=)` overrides, `SampleResult.summary()`
  backed by `owalnuts::diagnostics`, plus the `from_cfunc` /
  `from_pymc(gil_free=True)` GIL-free transport and the structured-metric
  refresh callback. See its README.
- **Python package on PyPI.** `pip install owalnuts` (`owalnuts[stan]`,
  `[jax]`, `[torch]`, `[pymc]`, `[numba]`, `[arviz]`): abi3 wheels
  (CPython 3.10+, one per platform) for Linux x86_64/aarch64 (manylinux),
  macOS x86_64/arm64 and Windows x86_64 plus a self-contained sdist (maturin
  vendors the root crate and `integrations/bridgestan` into it), built and
  tested against a fresh interpreter by `.github/workflows/wheels.yml` and
  published from `v*` tags through PyPI trusted publishing.
- **Stan models from Python.** `owalnuts.from_stan(stan_file, data, seed=,
  make_args=)` compiles a Stan program with the `bridgestan` package on Linux
  and macOS (no `STAN_THREADS` by default) and
  returns a `StanTarget` that `owalnuts.sample` runs through the Rust
  `owalnuts_bridgestan::ReplicatedStanTarget` — snapshotted library replicas,
  GIL-free — with the model's
  unconstrained parameter names on the result (`bs_param_unc_names`, new in
  the bridgestan crate) and `StanTarget.constrain(result)` for the
  constrained draws (`bs_param_constrain`). Cargo feature `stan` of the
  extension (default on); the bridgestan crate's tape-backend `bench` binary
  moved behind its own `bench` feature. Windows 0.2 disables `from_stan` and
  direct Python model operations; use the Rust owned-worker API.
- `examples/kernel_bench.rs` (kernel hot-path microbenchmark) and
  `tests/kernel_fingerprint.rs` (bit-exact run fingerprints in both build
  profiles).

### Changed

- **POST-STUDY DEFAULT CHANGE (WP36): chain rescue is disabled by default.**
  `Adaptation::DualAveraging` and `Adaptation::Paper` no longer install a
  rescue on identity or diagonal multi-chain runs, and
  `sampler::DEFAULT_CHAIN_RESCUE` is now the truthful
  `Option<ChainRescueConfig> = None` (`STUDIES/chain_rescue_v2`,
  [WP36-CHAIN-RESCUE-V2]). WP36 launched all 288 frozen one-shot cells; 281
  were process-valid, while six Windows heap-corruption exits and one
  post-result timeout left six paired triplets invalid. The registered
  completeness gate therefore failed. Two-hit reduced nuisance unique-chain
  actions from 35 to 14, but `two_hit` failed its conjunctive gates, including
  the registered minimum sample size, efficacy, funnel, origin-safety and
  efficiency requirements. That failure alone did not select `no_rescue`; it
  advanced the mechanical rule to the `current` fallback check. `current`
  separately had registered red lines in four origin-overwrite cells (five
  events) plus unknown run history for HMM/92104, so the fallback selected
  `no_rescue`. The classifier found pathological/frozen ARMA and
  Lotka-Volterra origins and zero HMM origins, so WP36 does not establish
  genuine posterior-mode destruction. Immediate
  `restart_from_best` retains WP33's strong bad-start efficacy and remains
  fully opt-in, together with observe-only, two-hit and pooling, through
  `Adaptation::Custom(WarmupConfig::with_chain_rescue(...))`. A restart that
  acts copies state between chains and therefore invalidates the
  independent-start interpretation of ordinary R-hat. Historical WP35 replay
  must use study revision `8d3a7b5` and its recorded source under test
  `aa4510f`: running `STUDIES/posteriordb_bench_v6` at current HEAD would use
  the intentional no-rescue `Adaptation::default()` and would not reproduce
  WP35. Default sampler output is bit-identical to an otherwise identical
  explicit custom no-rescue warmup, and its rescue telemetry is empty. This is
  the post-study default commit, not an algorithm revision: the retained kernel,
  `walnutpie::WarmupConfig` / `RunConfig` defaults, walnutpie facade outputs,
  and all core fingerprints are unchanged.

- **HISTORICAL TEMPORARY DEFAULT CHANGE (WP33, by the preregistered rule): the sampler's own
  adaptation modes apply `sampler::DEFAULT_CHAIN_RESCUE =
  ChainRescueConfig::restart_from_best()` on the identity and diagonal
  metrics with at least two chains** (`STUDIES/chain_rescue_v1`,
  [WP33-CHAIN-RESCUE-V1]). The study preregistered the rule — a candidate
  flips if it passes >= 3 more of 27 cells (8 posteriordb models x 3 fresh
  seeds + 3 funnel cells) than the plain driver, no model below 0.9x
  ESS/gradient, no new reference disagreement |z| > 3.5, funnel |z| <= 2 on
  every seed — before the implementation existed, and restart-from-best
  met every part: 25 vs 21 cells (`lotka_volterra` 0/3 -> 3/3, the frozen
  chain caught at the first boundary, 25 min -> 5 min on one seed; `arma11`
  2/3 -> 3/3, the crawl cell R-hat 1.60 -> 1.003), per-model ESS/gradient
  1.00–289x (geomean 2.72), `mesquite` and `nes2000` byte-identical,
  funnel z +0.94 / −0.77 / −1.02, max |z| unchanged within noise. Pooling
  (`pool_at_boundaries`) gained two cells and fell to 0.42x on
  `lotka_volterra`; it stays opt-in. Draws of every multi-chain `Sampler`
  run on an identity or diagonal metric with `Adaptation::DualAveraging`
  or `Adaptation::Paper` can change (they are the plain draws whenever no
  chain is an outlier at any boundary); `Adaptation::Custom` is used as
  given (the opt-out), dense and structured metrics, single-chain runs,
  `walnutpie::WarmupConfig::default()`, `RunConfig`, `ALGORITHM_REVISION`
  and the kernel fingerprints are unchanged. Read
  `RunTelemetry::chain_rescues` before trusting R-hat on a multimodal
  target: a `LogDensity` rescue merges a chain into the others and hides
  the mode it had found. Three of six predictions failed and are reported
  (the density rule also fires on chains merely late at the first
  boundary; the funnel 88101 R-hat is not a one-bad-chain failure; the
  rule was predicted not to be met). `tests/sampler_api.rs` mirrors the
  new default.

- **DEFAULT CHANGE (post-hoc after WP31): `sampler::Tuning::default()`
  U-turn rule `Endpoints` -> `MomentumSum`, and the sampler's own
  adaptation modes regularise the diagonal metric with Stan's prior**
  (`STUDIES/joint_default_v1`, [WP31-JOINT-DEFAULT-V1]; validated by
  `STUDIES/posteriordb_bench_v5`, [WP32-POSTERIORDB-BENCH-V5]). New
  constants `sampler::DEFAULT_U_TURN_RULE = UTurnRule::MomentumSum` and
  `sampler::DEFAULT_METRIC_REGULARIZATION = DiagonalMetricRegularization::Stan`;
  `Adaptation::DualAveraging` and `Adaptation::Paper` apply the latter to
  the `WarmupConfig` they build (as they apply `DEFAULT_WARMUP_EXHAUSTION`);
  `Adaptation::Custom` is used as given. This is a **post-hoc decision**:
  WP31 preregistered a flip rule (geomean >= 1.15x, no model < 0.85x, gates
  >= the default's, funnel |z| <= 2 at both tunings, Eight Schools >= 0.9x)
  and the pair met four of five — 1.51x geomean over the 17 posteriordb
  models, 41 vs 35 cells, funnel exact with zero divergences, Eight Schools
  1.29x — but failed the per-model floor on the two cells no option passes
  (`hmm_drive_0`'s arm-dependent second-mode draw at 0.005x, the centered
  eight schools at 0.79x and 0/3 everywhere), so the study did not flip.
  The flip was decided afterwards on that evidence and validated on fresh
  seeds 87101–87103 against CmdStan 2.39.0 and nutpie 0.16.8 with
  preregistered predictions (WP32; numbers in `wiki/release-0.2.0.md`).
  Draws of every `Sampler` run that adapts a diagonal metric or uses
  `Tuning::default()` change; `walnutpie::KernelOptions::default()`,
  `walnutpie::WarmupConfig::default()`, `RunConfig`, `ALGORITHM_REVISION`
  and the kernel fingerprints are unchanged, and the old behaviour is
  `Tuning::new().kernel_options(KernelOptions::default())` with
  `Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(DiagonalMetricRegularization::TowardUnit))`.
  `tests/sampler_api.rs` mirrors the new defaults, and the Python package
  inherits them through `Sampler` (see Fixed).
- **`sampler::Tuning::default()` refinement levels 4 -> 8**
  (`STUDIES/funnel_defaults_v1`, [WP28-FUNNEL-DEFAULTS-V1]). At four
  levels the sampler defaults (adapted diagonal metric, dual averaging,
  `h0 = 0.5`) put half the exact mass below `omega = -5` on Neal's funnel
  (0.0203 / 0.0242 / 0.0625 on three fresh seeds against 0.0478, z -3.5 /
  -3.8 / +0.3, ~1,000 retained refinement exhaustions per cell): the
  adapted step cannot enter the neck with micro-steps no finer than
  `h / 16`. At eight levels (`h / 256`) the tail mass is 0.0412 / 0.0346 /
  0.0897 (|z| <= 1.43), exhaustions fall 26x and divergences 7x, at 1.08x
  the funnel's target calls, 1.05x the ESS per call on the noncentered
  Eight Schools and 1.00x on a 100-D Gaussian (two of three seeds
  call-for-call identical: the cap never engages there). The preregistered
  grid also rejected `delta` 0.5 / 0.25 alone (more exhaustions, worse
  bias), `Adaptation::Paper` from `h0 = 0.5` (one seed at z -2.7; 0.4x on
  the Gaussian) and the `stan_style` preset (biased; one cell errored on a
  nonfinite density). Eight levels remove the bias, not the funnel's poor
  mixing under dual averaging (one chain per seed at `h ~ 0.01`, `omega`
  R-hat 1.01-1.04); `max_error(0.5)` with eight levels mixes better there
  at 0.79x on the Gaussian and stays opt-in. `tests/sampler_api.rs` and the
  Python package default follow; `walnutpie::KernelTuning::default()`,
  `RunConfig`, `ALGORITHM_REVISION` and the kernel fingerprints are
  unchanged.

- **`sampler` default warmup exhaustion rule.** `Adaptation::DualAveraging`
  and `Adaptation::Paper` now apply `sampler::DEFAULT_WARMUP_EXHAUSTION`
  (`ExhaustionRule::AcceptUnlessDivergent`, below) to the discarded
  transitions; retained transitions keep `Tuning::kernel_options` (the
  frozen two-sided rule), so no retained draw of the frozen kernel changes
  and warmup differs only where a leaf exhausts at every level.
  `Adaptation::Custom` configurations are used as given. On the
  `posteriordb_bench_v2` starts this turns `arma11` from 7 frozen chains of
  12 into 0 (min bulk ESS 1,290-1,460 against 4-7) and passes two of three
  `lotka_volterra` seeds against one, with the funnel tail mass and the
  centered Eight Schools unchanged or better (`STUDIES/freeze_mode_v1`).
  `tests/sampler_api.rs` mirrors the new default; `ALGORITHM_REVISION` and
  the kernel fingerprints are unchanged.

- **`sampler::Limits` admits the exact worst case by default.** The sampler's
  own defaults (depth 10, eight refinement levels) exceed the conservative
  `walnutpie` admission ceiling for ordinary 4 x 1,000/2,000 runs, which made
  `Sampler::run` fail with a resource-limit error. The worst case is an exact
  bound the run cannot exceed, so admitting against it costs nothing; draws are
  unchanged. `Limits::admit_conservative` restores the 0.1.x check.
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
- **`sampler::Sampler` caches the initial evaluation by default.** Draws are
  bit-identical to the uncached run; one target call per transition is saved
  (11 % of the gradients on Eight Schools and the 100-D Gaussian at 8-9
  leaves per orbit, `STUDIES/kernel_efficiency_v1`). `walnutpie::RunConfig`
  keeps the cache off so the frozen target-call fingerprints hold;
  `Sampler::cache_initial_evaluation(false)` restores the old accounting.
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
- **Allocation-free kernel hot path, bit-identical.** Micro-steps write the
  gradient into the state's own buffer (`FusedEval`), a per-transition
  workspace replaces the clones in refinement and reverse coarsening, span
  endpoints share `Rc` states, leaf states live in a per-thread ring, the
  endpoint joint log density is reused for the reverse check, and the
  per-call kinetic energy is skipped when no proposal observer is attached.
  Kernel overhead per fused target call (single thread, best of 3,
  `examples/kernel_bench.rs`): funnel 480 -> 255 ns, Gaussian-100D 2002 ->
  936 ns, Eight Schools 889 -> 510 ns; allocations per call 8.5 -> 0.19,
  14 -> 0.56 and 14.4 -> 1.27. Every fingerprint, oracle and facade test is
  unchanged in both build profiles.
- Crate description, README and module docs point first-time readers at
  `owalnuts::sampler`; the `walnutpie` docs describe it as the complete
  facade underneath.

### Fixed

- **Windows BridgeStan native lifetime is isolated on one owned OS thread.**
  Every library/symbol, construct, metadata/name, gradient/error-free, and
  model-destruct call now runs on that owner; bounded-channel callers never
  enter model code, and drop joins through native TLS teardown. Windows
  `ReplicatedStanTarget::requested_replicas()` preserves the caller's request
  while `effective_replicas()` returns one; `threading()` reports serialized
  effective execution, `compiled_threading()` preserves the DLL capability,
  and `execution()` names the owned-serialized backend. Model bytes use a
  verified SHA-256 cache and
  module-global setup is locked; a process-global Windows native-call mutex
  additionally serializes all owner threads/models through setup, evaluation,
  error free, and destruction. Non-Windows replica 0 preserves the original
  `$ORIGIN`/`@loader_path` path while replicas 1..n use one source snapshot.
  The first resident-DLL/scoped-pool mitigation was rejected because its fixed
  arm still faulted in 8/180 children. The owned-one follow-up had zero faults
  in 540 children against 19/180 event-inclusive comparator faults. A fresh
  fixed-only qualification of the final process-global implementation then
  completed all 540 ordinary and 180 concurrent-four-target children with
  zero process faults, timeouts, missing/incomplete outputs, invariant
  mismatches, or correlated Event 1000 records: 0/720, with a one-sided 95%
  upper bound of 0.415210%. Sampling medians remained 3.1–5.1x the
  four-replica comparator. The historical root cause is not proven, and this
  mitigation is qualified only on one Windows GNU host, three model binaries,
  short runs, and one effective worker per target. Windows MSVC,
  Linux/macOS, the package/wheel matrix, and multi-worker Windows execution
  remain unqualified, so release publication stays blocked.
  Python `from_stan` and direct Python `bridgestan.StanModel` call/name/
  constrain paths are disabled on Windows 0.2 because they bypass this Rust
  owner backend. Python `StanTarget.probe_*` metadata now names its one-load
  scope; `SampleResult` alone reports the target actually used for sampling.
  (`STUDIES/bridgestan_lifetime_v1`,
  `STUDIES/bridgestan_owned_worker_v1`)
- **The Python package goes through `owalnuts::sampler` and inherits its
  defaults.** `integrations/python` built `KernelTuning` / `WarmupConfig` on
  the `walnutpie` facade directly and restated the sampler defaults, so it
  silently missed the ones changed during 0.2.0 (depth 10 and eight
  refinement levels were copied by hand; `DEFAULT_U_TURN_RULE`,
  `DEFAULT_METRIC_REGULARIZATION`, `DEFAULT_WARMUP_EXHAUSTION`, the cached
  initial evaluation and the worst-case admission were not). The PyO3
  `sample` / `preflight` paths now construct `Sampler` with `Tuning`,
  `Adaptation`, `Metric`, `Limits` and `Init` from the Python arguments and
  send only what the caller set, `owalnuts.DEFAULTS` reads the defaults
  from the Rust values, and a test checks that `owalnuts.sample` with
  explicit arguments equal to `DEFAULTS` reproduces a Rust `Sampler` run bit
  for bit on a 3-D Gaussian. Two consequences on the Python surface: an
  explicit `max_target_evaluations` is also the admission ceiling (the
  package used to admit budgeted runs against a 2^50 dummy ceiling), and a
  structured-metric run at the defaults must keep its worst case under the
  hard 1e9 research ceiling, as it always had to.
- **`Sampler` admits structured metrics with their worst case under the
  `research` feature.** The structured facade paths have no budgeted
  admission variant, so `Limits::admit_worst_case` (the default) left them
  rejected at the conservative 113M ceiling whenever the sampler defaults
  exceeded it. With `features = ["research"]` the sampler now raises the
  `RunConfig` admission ceiling to the budget (capped at the research
  maximum) when, and only when, the worst case exceeds the conservative
  ceiling; runs it already admitted are configured exactly as before, and
  without the feature the facade's conservative admission still applies.
  `tests/sampler_api.rs` covers the admission and the rejection under
  `Limits::admit_conservative`.
- **BridgeStan targets no longer abort on `NaN`/`+inf` log densities.**
  `owalnuts-bridgestan` maps a `NaN`/`+inf` log density and a finite log
  density with a nonfinite gradient to the recoverable zero-density path
  (`map_evaluation`), as CmdStan and nutpie reject such proposals; only a
  dimension mismatch stays fatal. [WP22-POSTERIORDB-BENCH-V1 follow-up]
- `sample_chains_structured` and `sample_chains_structured_with_control`
  reject a target, mass, or initial position whose dimensions differ with a
  configuration error instead of panicking.

### Validation (2026-09-01 program)

- **Step collapse and the post-escape crawl (WP27-STEP-COLLAPSE-V1).** The
  default step collapse on `sblrc` (h 0.003 against CmdStan's 0.10) and
  `earnings` (0.003 against 0.017) is the `v10` diagonal regularisation
  `(n/(n+5)) var + 5/(n+5)`, whose additive term floors every variance at
  0.0099 for `n = 500` while those coefficients have posterior variances
  1e-5 to 5e-4; dual averaging's statistic sits on target throughout and
  holds `h` at the step the 30x-too-wide metric allows. Stan's statistic,
  Stan's `init_stepsize` at every window, the delta ramp, the restart
  reference and two step floors leave `h` unchanged;
  `DiagonalMetricRegularization::Stan` alone restores CmdStan's step (`sblrc`
  9.7x ESS/gradient, `earnings` 1.9x with zero depth-cap draws, `arma11`'s
  healthy chains 2.9x, controls 1.08x) but `earnings` then fails R-hat
  (1.02, min bulk ESS 164–179: at CmdStan's step and metric the WALNUTS
  orbit is 49 leaves against NUTS's 163, a retained-kernel U-turn matter),
  so the preregistered flip rule is not met and the regularisation stays
  opt-in, recommended for regressions with coefficient scales below ~0.1.
  The `arma11` 79103 crawl (chain 3 at `h` 5e-8 after escaping the wall) is
  a start CmdStan cannot leave in 1,000 iterations either (same log
  density plateau at −3.7e5 from iteration 250, final `h` 1.7e-6, R-hat
  1.6); no warmup option changes it. Seeds 80101–80102, seven models, ten
  arms, CmdStan 2.39.0 from the same starts.
- **posteriordb v3 (WP25-POSTERIORDB-BENCH-V3).** With the WP24 warmup rule, the
  dual-averaging arm passes 35/51 cells (CmdStan 37, nutpie 31), zero frozen
  chains, geomean 0.34x CmdStan ESS per gradient, 0.75x wall per gradient,
  1.35x nutpie ESS per second. `STUDIES/posteriordb_bench_v3`.

- posteriordb benchmark against CmdStan and nutpie
  (`STUDIES/posteriordb_bench_v1`, 17 posteriors x 4 arms x 3 seeds, 204
  cells): with the 0.1 defaults the dual-averaging arm was 0.32x CmdStan and
  0.25x nutpie on minimum bulk ESS per gradient over 14 models (gate passes
  26/51 versus CmdStan 34/51, nutpie 29/51), refinement engaged on 1 % of
  retained leaves, and the v3 paper arm froze on nine models. This study
  motivated the depth-10 default, the start retries, the BridgeStan fixes and
  the Appendix C v4 defaults above.
  [WP22-POSTERIORDB-BENCH-V1]
- posteriordb v2 on the 0.2.0 defaults (`STUDIES/posteriordb_bench_v2`, the
  same 17 posteriors, five arms, three fresh seeds, all 255 cells present):
  the dual-averaging arm passes 32/51 cells (CmdStan 35, nutpie 27; the
  `stan_style` arm 32, the Appendix C v4 arm 29 versus 8 in v1) with zero
  cells lost to a fatal evaluation or start failure; geomean 0.233x CmdStan
  bulk ESS per gradient over 17 models (0.447x over the 15 models without a
  frozen chain), 0.771x CmdStan wall per gradient and 1.108x nutpie ESS per
  second. `arma11` and `lotka_volterra` chains freeze from uniform starts
  where every leaf fails at every refinement level; the Appendix C v4 arm is
  at parity with dual averaging (geomean 0.995), so it stays opt-in. The
  breadth-throughput release gate (P1–P3, P5) is not met.
  [WP23-POSTERIORDB-BENCH-V2]
- Adaptation ablation (`STUDIES/adaptation_parity_v1`, nine posteriordb
  models, two seeds): depth 10 over depth 8 gives 1.45x geomean minimum bulk
  ESS per gradient and 17/18 gate passes; geomean versus CmdStan 0.49x; the
  full `stan_style` preset reaches 0.68x but regresses four models and fails
  R-hat on two, so it is opt-in.
- Appendix C robustness (`STUDIES/paper_adaptation_robust_v1`): the v4
  default is robust on all 14 previously freezing posteriordb cells and
  0.90-1.35x dual averaging's minimum bulk ESS per gradient (geomean 1.04).
- Kernel efficiency against a clean-room reference NUTS
  (`STUDIES/kernel_efficiency_v1`, ESS per gradient, seed medians): the
  default kernel is 0.81x on Eight Schools, 0.75x on the 100-D Gaussian and
  1.03x on the 50-D correlated Gaussian; with the initial-evaluation cache
  0.91x / 0.81x / 1.06x, and with Stan's momentum-sum U-turn rule as well
  0.86x / 1.09x / 1.07x. The gap decomposes into the wasted re-evaluation
  (exact, now cached by default), the endpoint U-turn rule (0.75x on the
  isotropic Gaussian, 1.0x on the correlated one) and refinement rejections
  (0.85-0.95x where refinement engages), consistent with the posteriordb
  0.7-0.8x.
- Sampler API parity: every `Sampler::run` path is bit-identical to the
  `walnutpie` entry point it wraps (`tests/sampler_api.rs`); the
  allocation-free kernel reproduces the pinned run fingerprints in debug and
  release (`tests/kernel_fingerprint.rs`).
- Diagnostics: R-hat, ESS (bulk, tail, quantile, mean) and MCSE match ArviZ
  to 1e-6 relative on `tests/data/arviz_fixture.json`; `az.summary` over the
  exported CmdStan CSV agrees with the Rust `Summary`.

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
