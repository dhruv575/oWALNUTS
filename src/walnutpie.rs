//! Internal limited-beta, fixed-tuning, diagonal-mass WALNUTS facade.
//!
//! This is an internal beta, not a generally supported or statistically validated
//! production sampler. It is limited to deterministic, smooth densities in
//! unconstrained `f64` coordinates. Adaptation is opt-in. Student-t and
//! other heavy-tailed targets, constrained transforms, hierarchical targets,
//! and real models have not been validated. Only this facade is public; the
//! numerical implementation remains private.
//!
//! # Frozen kernel
//!
//! Revision [`ALGORITHM_REVISION`] freezes step size `0.6`, minimum micro-step
//! count `1`, at most `2` refinement levels, local error threshold `1.0`, and
//! maximum tree depth `3`. By default, `discarded` merely labels initial
//! fixed-kernel transitions. [`WarmupConfig`] opts those transitions into
//! step-size and diagonal-mass adaptation.
//! Maximum-depth stops are valid completed transitions, but frequent stops
//! indicate a truncated trajectory. Use
//! [`RunConfig::with_maximum_depth_stop_limit`] to turn that health signal into
//! [`ErrorKind::Unhealthy`]; the run fails when the cumulative count becomes
//! strictly greater than the configured limit.
//!
//! # Paper adaptation
//!
//! [`WarmupConfig::with_paper_adaptation`] replaces acceptance-driven dual
//! averaging by the JMLR Appendix C rules under
//! [`PAPER_ADAPTATION_REVISION`]: the local error threshold (`max_error`,
//! the paper's `delta`) follows the K-quantile rule
//! `delta = Delta / max(1, q_{p_a}(K))` with `K = (H_max - H_min) / delta`
//! per completed orbit, and the macro step (`step_size`, the paper's `h`)
//! is dual averaged toward a target fraction `Gamma` of macro leaves that
//! need no refinement. Updates happen only at the initial-fast boundary and
//! nonterminal slow-window ends, consume no random draws or callbacks, and
//! are frozen before retention; see [`PaperAdaptationUpdate`] telemetry.
//! [`PaperStepStatistic`] selects the per-transition (default) or cumulative
//! unrefined-fraction statistic and [`PaperRestartPolicy`] selects whether
//! `delta` installations continue dual averaging (default since `v3`) or
//! restart it. The unrefined fraction is taken over built leaves only and
//! the paper-mode step is bounded by [`PAPER_STEP_RELATIVE_BOUND`] around
//! the initial step (since `v2`).
//! Deep refinement (`max_refinement_levels >= 8`) with deep trees exceeds
//! the conservative constructor bound; admit such runs through
//! [`sample_chains_with_target_budget`] and
//! [`TargetEvaluationAdmissionLimit`] or the research ceiling. The rules
//! are supported by the diagonal and fixed-operator facades only.
//!
//! [`DiagonalMass`] is the diagonal covariance `M` of refreshed momentum:
//! `p_i ~ Normal(0, M_i)`. The kinetic energy is
//! `K(p) = 0.5 * sum_i(p_i^2 / M_i)`, and the kernel receives inverse mass
//! `M_i^-1`. It is not a position covariance or precision parameter.
//!
//! # Target and output contract
//!
//! [`Target::dimension`] must return one fixed, nonzero dimension.
//! [`Target::log_density_gradient`] receives a finite position of that exact
//! dimension, must overwrite every gradient element, and must return a finite
//! unnormalized log density and finite gradient. It must be deterministic,
//! thread-safe, and free of hidden cross-chain state. A
//! [`TargetError::recoverable`] result at a proposed position treats that
//! position as a zero-density point with a zero gradient, exactly as upstream
//! walnutpie maps a failed evaluation (`logp = -inf`, `grad = 0`). Returning
//! a fatal [`TargetError`], returning nonfinite data (`NaN`, `+inf`, or a
//! nonfinite gradient), or panicking fails the whole call. The
//! initial/current position must always be evaluable. Every public sampling
//! function is all-or-error: no samples, diagnostics, telemetry, or partially
//! completed chains are returned in [`Error`].
//!
//! Recoverable failures define a deterministic zero-density region: for the
//! same position the target must always return the same classification.
//! Since kernel revision `v10` a micro-step that ends at a zero-density point
//! has an infinite endpoint Hamiltonian error, so it fails the `max_error`
//! tolerance and the leaf refines to the next level like any over-tolerance
//! step; the leaf is rejected (refinement exhaustion, zero weight, extension
//! stops in that direction) only when every level ends in the region.
//! Interior micro-steps of an attempt that ends at a finite-density point do
//! not by themselves reject the attempt, and integration continues through
//! them with the zero gradient; this is the upstream `macro_step` rule, which
//! overwrites the log density at every micro-step and tests only the last.
//! Because the leapfrog map with a position-dependent gradient field (zero on
//! the region) is still a reversible volume-preserving involution and the
//! accept/reject decision depends only on the two endpoint Hamiltonians,
//! detailed balance for the target restricted to its support is unchanged;
//! the reverse coarsening check treats a zero-density endpoint identically
//! (it is never "within tolerance"), so forward and reverse selections agree.
//! The same fused call is counted in its forward or reverse phase and no
//! acceptance uniform is drawn for a rejected leaf. Misclassifying a
//! finite-density region as recoverable instead samples a truncated target
//! and is a target-definition error.
//!
//! [`ChainOutput::samples`] is flat draw-major `[draw][parameter]` data and
//! excludes the initial position and discarded transitions.
//! [`ChainOutput::diagnostics`] has one item per transition, with all discarded
//! items first and retained items second. Multi-chain output is in chain-index
//! order. A diagnostic's depth is the number of completed tree doublings;
//! leaves attempted includes rejected leaves, while leaves built includes only
//! accepted constructions. Direction and uniform counts are actual consumed
//! kernel draws; target evaluations are fused log-density/gradient calls.
//!
//! # Telemetry
//!
//! [`RunTelemetry`] partitions work into `discarded`, `retained`, and `total`;
//! `total` is the exact componentwise sum of the first two and its transition
//! count is `discarded + retained`. For every [`WorkTotals`]:
//!
//! * `transitions` counts completed transitions included in that partition;
//! * `momentum_refreshes` counts one refresh per completed transition;
//! * `standard_normal_components` counts `dimension` normal variates per
//!   refresh;
//! * `target_calls_initial`, `target_calls_forward`, and
//!   `target_calls_reverse` count fused target calls by kernel phase, and
//!   `target_calls_total` is their exact sum;
//! * `recoverable_target_failures` counts calls that returned
//!   [`TargetErrorKind::Recoverable`];
//! * refinement/coarsening attempts count levels tried, while their
//!   `*_micro_steps_executed` fields count integrator micro-steps actually run;
//! * `leaves_attempted` includes rejected attempts and `leaves_built` includes
//!   successful leaves, so `leaves_built <= leaves_attempted`;
//! * `direction_draws` and `uniform_draws` count consumed random decisions;
//! * `maximum_depth_stops` counts completed transitions whose stop reason is
//!   [`StopReason::MaximumDepth`].
//!
//! Failed/incomplete transitions are excluded from returned telemetry because
//! errors return no output. For successful output,
//! `target_calls_total == sum(diagnostics.target_evaluations)`, and transition,
//! refresh, and diagnostic counts agree.
//!
//! # Reproducibility, failure, and concurrency
//!
//! A seed is not a cross-version portability promise. Bitwise replay requires
//! the same algorithm revision, crate build, `Cargo.lock`, target architecture,
//! floating-point behavior, inputs, and thread-independent deterministic
//! target. Random algorithms may change when dependencies change. Chain `i`
//! uses `splitmix64(base_seed + i)`, so chain zero agrees between single- and
//! multi-chain entry points.
//!
//! Panic containment requires `panic=unwind`. With `panic=abort`, a target,
//! cancellation callback, worker, or internal panic aborts the process and no
//! [`ErrorKind::Panic`] can be produced.
//!
//! Cancellation and deadlines are cooperative checks between bounded kernel
//! operations and immediately before and after target callbacks. They cannot
//! interrupt a callback that never returns, deadlocks, or blocks indefinitely;
//! isolate untrusted targets in a killable process. A deadline is therefore
//! not a hard wall-clock bound. Parallel calls wait for the run-local Rayon
//! work to finish before returning. If chains fail concurrently, the error for
//! the lowest chain index is selected deterministically; higher-index work is
//! asked to stop cooperatively, not forcibly terminated.
//!
//! # Resource accounting
//!
//! [`ResourceLimits`] are preflight ceilings for allocations explicitly
//! accounted by this API, not process RSS, address-space, stack, allocator, or
//! operating-system limits. Result accounting covers sample scalar storage,
//! transition diagnostic storage, per-chain mass metadata, output containers,
//! and telemetry containers. Working accounting conservatively covers copied
//! initial positions, inverse mass, momentum, gradients, kernel states/spans,
//! and transition workspaces for all chains live at once. It excludes the
//! target and its allocations, callback stack/temporaries, Rayon and thread
//! stacks, RNG/dependency/allocator overhead, code and shared libraries,
//! caller-owned inputs, panic payloads, and unrelated process memory. Actual
//! allocation failure can therefore occur below a configured ceiling.
//!
//! Research warmup experiments may explicitly raise only the conservative
//! target-evaluation preflight ceiling with
//! [`RunConfig::with_research_target_evaluation_limit`]. This does not raise
//! dimension, chain, transition, result-memory, or working-memory limits, and
//! does not change cancellation or deadline checks. The opt-in is recorded in
//! [`RunMetadata`].
//!
use std::cell::Cell;
use std::fmt;
use std::num::NonZeroUsize;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

use rand::distr::Distribution;
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::StandardNormal;
use rayon::prelude::*;

use crate::kernel::{
    Direction, EvaluatedTransitionInput, EvaluationPhase, FixedTuning, MassOperator,
    OuterSelectionPolicy, Rejection, SelectedState, SpanStop, TransitionInput, TransitionRng,
    TransitionStop, TransitionTuning, TransitionWorkTelemetry, Uniform01, macro_leaf,
    take_evaluation_context, transition_w_from_evaluated_traced_with_telemetry_and_outer_policy,
    transition_w_from_evaluated_with_telemetry_and_outer_policy,
    transition_w_traced_with_telemetry_and_outer_policy,
    transition_w_with_telemetry_and_outer_policy,
};
use crate::types::{State, ValidationError};

/// Revision of the numerical kernel, seed derivation, random stream layout,
/// frozen tuning, and counter meanings.
///
/// Bitwise replay is promised only for this crate build with the same
/// `Cargo.lock`, target architecture, inputs, and revision. In particular,
/// `rand`'s `SmallRng` and `rand_distr::StandardNormal` are not upstream-stable
/// algorithms across dependency updates.
///
/// `v9` (2026-08-31) corrects the micro-step acceptance statistic. Revisions
/// through `v8` accepted a refinement level when the largest Hamiltonian
/// departure of any visited micro-step from the *start* state was within
/// `max_error`. That statistic is not symmetric under time reversal, so the
/// deterministic reverse selection could disagree with the forward selection
/// and the kernel accepted non-reversible leaves; on Neal's funnel this put
/// about twice the correct mass below `omega = -5`. `v9` decides acceptance on
/// the endpoint departure `|H(end) - H(start)|` exactly as upstream
/// `walnutpie::macro_step`/`within_tolerance`, which restores the pinned
/// upstream macro-leaf oracle and a 4,000-leaf funnel differential oracle.
///
/// `v10` (2026-08-31) corrects recoverable-failure semantics. Through `v9` a
/// [`TargetError::recoverable`] result stopped the whole transition
/// (`StopReason::InvalidEvaluation`) on the failed call. Upstream maps a
/// failed evaluation to `logp = -inf`, `grad = 0`, so the micro-step merely
/// fails the endpoint tolerance and the leaf refines; `v10` does the same and
/// rejects only on refinement exhaustion. Runs whose target never returns a
/// recoverable error are bit-identical to `v9`.
/// Path-wide Hamiltonian extrema remain telemetry only. Runs that never
/// refine (`max_refinement_levels == 1`, single-step leaves) are unchanged.
pub const ALGORITHM_REVISION: &str = "walnutpie-warmup-telemetry-tau0.6-m1-r2-e1-d3-v10";
/// Execution revision for explicitly original-coordinate metric APIs.
///
/// This stream is deterministic within the same build and lockfile, but is
/// intentionally not bit-compatible with the legacy Cholesky-coordinate
/// wrappers.
pub const DIRECT_ORIGINAL_Q_REVISION: &str = "walnutpie-direct-original-q-mass-operator-v2";
/// Execution revision for projected arrowhead warmup in original coordinates.
pub const PROJECTED_ARROWHEAD_REVISION: &str = "walnutpie-projected-arrowhead-warmup-v2";
/// Research-only outer-orbit selection ablation. Production defaults to
/// [`OuterOrbitSelection::BiasedProgressive`].
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum OuterOrbitSelection {
    BiasedProgressive,
    ExactNormalizedMultinomial,
}

impl From<OuterOrbitSelection> for OuterSelectionPolicy {
    fn from(value: OuterOrbitSelection) -> Self {
        match value {
            OuterOrbitSelection::BiasedProgressive => Self::BiasedProgressive,
            OuterOrbitSelection::ExactNormalizedMultinomial => Self::NormalizedMultinomial,
        }
    }
}

/// Qualified default micro-step size.
pub const DEFAULT_STEP_SIZE: f64 = 0.6;
/// Conservative production target-evaluation preflight ceiling.
pub const CONSERVATIVE_MAX_TARGET_EVALUATIONS: usize = 113_000_000;
/// Hard ceiling for explicit research-only target-evaluation opt-ins.
pub const RESEARCH_MAX_TARGET_EVALUATIONS: usize = 1_000_000_000;
/// Default maximum number of refinement levels.
pub const DEFAULT_MAX_REFINEMENT_LEVELS: usize = 2;
/// Default number of micro steps at the coarsest level.
pub const DEFAULT_MIN_MICRO_STEPS: usize = 1;
/// Default inclusive Hamiltonian-error tolerance.
pub const DEFAULT_MAX_ERROR: f64 = 1.0;
/// Default maximum absolute trajectory energy error for divergence reporting.
pub const DEFAULT_DIVERGENCE_THRESHOLD: f64 = 1000.0;
/// Default maximum transition-tree depth.
pub const DEFAULT_MAX_DEPTH: usize = 3;

/// Validated fixed-kernel tuning.
///
/// [`KernelTuning::default`] preserves the qualified tuning associated with
/// [`ALGORITHM_REVISION`] and therefore preserves historical replay behavior.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct KernelTuning {
    step_size: f64,
    max_depth: usize,
    min_micro_steps: usize,
    max_refinement_levels: usize,
    max_error: f64,
    divergence_threshold: f64,
}

// All floating-point fields are finite by construction.
impl Eq for KernelTuning {}

impl Default for KernelTuning {
    fn default() -> Self {
        Self {
            step_size: DEFAULT_STEP_SIZE,
            max_depth: DEFAULT_MAX_DEPTH,
            min_micro_steps: DEFAULT_MIN_MICRO_STEPS,
            max_refinement_levels: DEFAULT_MAX_REFINEMENT_LEVELS,
            max_error: DEFAULT_MAX_ERROR,
            divergence_threshold: DEFAULT_DIVERGENCE_THRESHOLD,
        }
    }
}

impl KernelTuning {
    pub fn new(
        step_size: f64,
        max_depth: NonZeroUsize,
        min_micro_steps: NonZeroUsize,
        max_refinement_levels: NonZeroUsize,
        max_error: f64,
    ) -> Result<Self, Error> {
        if !step_size.is_finite() || step_size <= 0.0 {
            return Err(Error::configuration(
                "kernel step size must be finite and positive",
            ));
        }
        if !max_error.is_finite() || max_error <= 0.0 {
            return Err(Error::configuration(
                "kernel maximum error must be finite and positive",
            ));
        }
        let tuning = Self {
            step_size,
            max_depth: max_depth.get(),
            min_micro_steps: min_micro_steps.get(),
            max_refinement_levels: max_refinement_levels.get(),
            max_error,
            divergence_threshold: DEFAULT_DIVERGENCE_THRESHOLD,
        };
        tuning.max_leaves_per_transition()?;
        tuning.maximum_micro_steps()?;
        tuning.max_target_calls_per_transition()?;
        Ok(tuning)
    }

    pub fn step_size(&self) -> f64 {
        self.step_size
    }
    pub fn max_depth(&self) -> usize {
        self.max_depth
    }
    pub fn min_micro_steps(&self) -> usize {
        self.min_micro_steps
    }
    pub fn max_refinement_levels(&self) -> usize {
        self.max_refinement_levels
    }
    pub fn max_error(&self) -> f64 {
        self.max_error
    }
    pub fn divergence_threshold(&self) -> f64 {
        self.divergence_threshold
    }
    pub fn with_divergence_threshold(mut self, threshold: f64) -> Result<Self, Error> {
        if !threshold.is_finite() || threshold <= 0.0 {
            return Err(Error::configuration(
                "kernel divergence threshold must be finite and positive",
            ));
        }
        self.divergence_threshold = threshold;
        Ok(self)
    }

    fn maximum_micro_steps(&self) -> Result<usize, Error> {
        let shift = u32::try_from(self.max_refinement_levels - 1)
            .map_err(|_| Error::configuration("kernel refinement level count is too large"))?;
        let multiplier = 1usize
            .checked_shl(shift)
            .ok_or_else(|| Error::configuration("kernel micro-step count overflows usize"))?;
        self.min_micro_steps
            .checked_mul(multiplier)
            .ok_or_else(|| Error::configuration("kernel micro-step count overflows usize"))
    }

    fn max_leaves_per_transition(&self) -> Result<usize, Error> {
        let shift = u32::try_from(self.max_depth)
            .map_err(|_| Error::configuration("kernel maximum depth is too large"))?;
        1usize
            .checked_shl(shift)
            .and_then(|leaves| leaves.checked_sub(1))
            .ok_or_else(|| Error::configuration("kernel maximum depth overflows leaf count"))
    }

    fn max_target_calls_per_transition(&self) -> Result<usize, Error> {
        let maximum = self.maximum_micro_steps()?;
        let exhaustion = maximum
            .checked_mul(2)
            .and_then(|value| value.checked_sub(self.min_micro_steps))
            .ok_or_else(Error::overflow)?;
        let accepted_at_finest = maximum
            .checked_mul(3)
            .and_then(|value| {
                self.min_micro_steps
                    .checked_mul(2)
                    .and_then(|minimum| value.checked_sub(minimum))
            })
            .ok_or_else(Error::overflow)?;
        let calls_per_leaf = exhaustion.max(accepted_at_finest);
        self.max_leaves_per_transition()?
            .checked_mul(calls_per_leaf)
            .and_then(|calls| calls.checked_add(1))
            .ok_or_else(Error::overflow)
    }

    fn transition_tuning(&self) -> TransitionTuning {
        TransitionTuning {
            leaf: FixedTuning {
                step_size: self.step_size,
                max_refinement_levels: self.max_refinement_levels,
                min_micro_steps: self.min_micro_steps,
                max_error: self.max_error,
                divergence_threshold: self.divergence_threshold,
            },
            max_depth: self.max_depth,
        }
    }
}
const MIN_ADAPTATION_VARIANCE: f64 = 1.0e-12;

#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
pub enum DualAveragingAcceptance {
    #[default]
    CurrentCoarseEndpoint,
    AcceptedTrajectory,
}

/// Identity of the opt-in JMLR Appendix C adaptation rules.
///
/// Default warmup does not use these rules and keeps [`ALGORITHM_REVISION`].
///
/// `v2` counts the unrefined fraction over *built* leaves only (a transition
/// without built leaves contributes no statistic, so all-invalid transitions
/// no longer read as fully unrefined) and bounds the paper-mode step to
/// [`PAPER_STEP_RELATIVE_BOUND`] times the initial step in either direction.
///
/// `v3` makes [`PaperRestartPolicy::ContinueThroughLocalErrorInstall`] the
/// default: dual averaging is no longer restarted at `delta` installations.
pub const PAPER_ADAPTATION_REVISION: &str = "walnutpie-paper-adaptation-kquantile-gamma-v3";
/// Paper-mode step bound relative to the initial step: dual averaging never
/// installs `h` outside `[h_0 / bound, h_0 * bound]`.
pub const PAPER_STEP_RELATIVE_BOUND: f64 = 1.0e3;
/// Default global orbit energy-error bound `Delta` (Appendix C.1).
pub const DEFAULT_PAPER_GLOBAL_ENERGY_BOUND: f64 = 2.0;
/// Default quantile level `p_a` for the inflation factor `K` (Appendix C.1).
pub const DEFAULT_PAPER_QUANTILE_PROBABILITY: f64 = 0.95;
/// Default target fraction `Gamma` of macro steps needing no refinement
/// (Appendix C.2).
pub const DEFAULT_PAPER_UNREFINED_FRACTION_TARGET: f64 = 0.8;
/// Default minimum number of completed orbits before `delta` is updated.
pub const DEFAULT_PAPER_MINIMUM_ORBITS: usize = 10;
const PAPER_MAX_ERROR_BOUNDS: (f64, f64) = (1.0e-8, 1.0e4);

/// Opt-in adaptation of the local error threshold `delta` and macro step `h`
/// following JMLR Appendix C instead of acceptance-driven dual averaging.
///
/// * `delta` (the kernel's `max_error`): every completed discarded orbit
///   records `K = (H_max - H_min) / delta`. At the end of the initial fast
///   phase and of every nonterminal slow window, `delta` is replaced by
///   `Delta / max(1, q_{p_a}(K))`, the empirical `p_a`-quantile over that
///   window's orbits. The result is therefore never larger than `Delta`.
/// * `h` (the kernel's `step_size`): dual averaging keeps the standard
///   Hoffman--Gelman constants but its statistic is the per-transition fraction
///   of attempted macro leaves that needed no refinement, targeted at
///   `Gamma`. The fraction is taken over built leaves: a built leaf counts
///   as unrefined when it was accepted at its coarsest level, rejected
///   attempts count on neither side, and a transition that built no leaf
///   contributes no sample and no step update. The installed step never
///   leaves [`PAPER_STEP_RELATIVE_BOUND`] times the configured initial step
///   in either direction. By default the statistic is the
///   per-transition fraction ([`PaperStepStatistic::PerTransition`]) and one
///   dual-averaging stream continues across `delta` installations
///   ([`PaperRestartPolicy::ContinueThroughLocalErrorInstall`]); mass
///   installations still restart it. The alternatives
///   [`PaperRestartPolicy::RestartOnLocalErrorInstall`] (restart around the
///   current step after every `delta` installation, the `v1`/`v2`
///   behaviour) and [`PaperStepStatistic::Cumulative`] (feed the running
///   mean of the fraction since the end of the initial fast phase) remain
///   selectable. `STUDIES/paper_funnel_adaptive_v2` measured all four
///   combinations on Neal's funnel: restarting left chain-specific final
///   steps (spread 1.7–2.8×) because each restart returns dual averaging to
///   its aggressive early iterations, continuing gave spread ≤ 1.3× with
///   equal or better efficiency, and the cumulative statistic was harmful
///   (spread 15–95×) because dual averaging integrates its lag as a
///   persistent offset.
///
/// Both rules are applied only during discarded transitions and are frozen
/// before the first retained transition. They consume no random draws and no
/// target callbacks. Windows with fewer completed orbits than the minimum
/// leave `delta` unchanged and report [`PaperAdaptationOutcome::InsufficientOrbits`].
/// The installed step is always the dual-averaging averaged iterate.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct PaperAdaptationConfig {
    global_energy_bound: f64,
    quantile_probability: f64,
    unrefined_fraction_target: f64,
    adapt_local_error: bool,
    minimum_orbits: usize,
    step_statistic: PaperStepStatistic,
    restart_policy: PaperRestartPolicy,
}

/// Which unrefined-fraction statistic drives the paper `h` rule.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[non_exhaustive]
pub enum PaperStepStatistic {
    /// Each discarded transition feeds its own unrefined leaf fraction.
    #[default]
    PerTransition,
    /// Each discarded transition feeds the running mean of the unrefined
    /// leaf fraction over all discarded transitions since the end of the
    /// initial fast phase (since the first transition before that boundary).
    Cumulative,
}

/// Whether a paper `delta` installation restarts dual averaging.
#[derive(Clone, Copy, Debug, Default, Eq, PartialEq)]
#[non_exhaustive]
pub enum PaperRestartPolicy {
    /// Restart dual averaging around the current step after every `delta`
    /// installation (the `v1`/`v2` behaviour).
    RestartOnLocalErrorInstall,
    /// Keep the dual averaging state across `delta` installations; only mass
    /// installations restart it (default since `v3`).
    #[default]
    ContinueThroughLocalErrorInstall,
}

impl Default for PaperAdaptationConfig {
    fn default() -> Self {
        Self {
            global_energy_bound: DEFAULT_PAPER_GLOBAL_ENERGY_BOUND,
            quantile_probability: DEFAULT_PAPER_QUANTILE_PROBABILITY,
            unrefined_fraction_target: DEFAULT_PAPER_UNREFINED_FRACTION_TARGET,
            adapt_local_error: true,
            minimum_orbits: DEFAULT_PAPER_MINIMUM_ORBITS,
            step_statistic: PaperStepStatistic::PerTransition,
            restart_policy: PaperRestartPolicy::ContinueThroughLocalErrorInstall,
        }
    }
}

impl PaperAdaptationConfig {
    pub fn new(
        global_energy_bound: f64,
        quantile_probability: f64,
        unrefined_fraction_target: f64,
    ) -> Result<Self, Error> {
        if !global_energy_bound.is_finite() || global_energy_bound <= 0.0 {
            return Err(Error::configuration(
                "paper adaptation global energy bound must be finite and positive",
            ));
        }
        if !quantile_probability.is_finite()
            || quantile_probability <= 0.0
            || quantile_probability >= 1.0
        {
            return Err(Error::configuration(
                "paper adaptation quantile probability must be strictly between zero and one",
            ));
        }
        if !unrefined_fraction_target.is_finite()
            || unrefined_fraction_target <= 0.0
            || unrefined_fraction_target >= 1.0
        {
            return Err(Error::configuration(
                "paper adaptation unrefined fraction target must be strictly between zero and one",
            ));
        }
        Ok(Self {
            global_energy_bound,
            quantile_probability,
            unrefined_fraction_target,
            ..Self::default()
        })
    }

    /// Disable the `delta` rule while keeping the `Gamma`-targeted step rule.
    pub fn with_local_error_adaptation(mut self, enabled: bool) -> Self {
        self.adapt_local_error = enabled;
        self
    }

    /// Minimum completed orbits in a window before `delta` is updated.
    pub fn with_minimum_orbits(mut self, minimum_orbits: NonZeroUsize) -> Self {
        self.minimum_orbits = minimum_orbits.get();
        self
    }

    /// Select the unrefined-fraction statistic that drives the `h` rule.
    pub fn with_step_statistic(mut self, statistic: PaperStepStatistic) -> Self {
        self.step_statistic = statistic;
        self
    }

    /// Select whether `delta` installations restart dual averaging.
    pub fn with_restart_policy(mut self, policy: PaperRestartPolicy) -> Self {
        self.restart_policy = policy;
        self
    }

    pub fn step_statistic(&self) -> PaperStepStatistic {
        self.step_statistic
    }
    pub fn restart_policy(&self) -> PaperRestartPolicy {
        self.restart_policy
    }

    pub fn global_energy_bound(&self) -> f64 {
        self.global_energy_bound
    }
    pub fn quantile_probability(&self) -> f64 {
        self.quantile_probability
    }
    pub fn unrefined_fraction_target(&self) -> f64 {
        self.unrefined_fraction_target
    }
    pub fn adapts_local_error(&self) -> bool {
        self.adapt_local_error
    }
    pub fn minimum_orbits(&self) -> usize {
        self.minimum_orbits
    }
}

/// Result of one paper-rule `delta` update point.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum PaperAdaptationOutcome {
    /// A new `delta` was installed.
    Installed,
    /// Too few completed orbits; `delta` is unchanged.
    InsufficientOrbits,
    /// The candidate was nonfinite; `delta` is unchanged.
    NonFinite,
    /// The `delta` rule is disabled; only the window summary is reported.
    Disabled,
}

/// Typed record of one paper-rule update point.
#[derive(Clone, Copy, Debug, PartialEq)]
#[non_exhaustive]
pub struct PaperAdaptationUpdate {
    transition: usize,
    window_index: Option<usize>,
    orbits: usize,
    inflation_quantile: Option<f64>,
    energy_range_quantile: Option<f64>,
    max_error_before: f64,
    max_error_after: f64,
    unrefined_fraction_mean: Option<f64>,
    step_before: f64,
    step_after: f64,
    outcome: PaperAdaptationOutcome,
    step_statistic: Option<f64>,
    dual_averaging_restarted: bool,
    transitions_without_statistic: usize,
}

impl PaperAdaptationUpdate {
    /// The statistic value fed to the `h` rule by the transition at which
    /// this update was applied (the running mean under
    /// [`PaperStepStatistic::Cumulative`]).
    pub fn step_statistic(&self) -> Option<f64> {
        self.step_statistic
    }
    /// Transitions in this window that built no macro leaf and therefore
    /// contributed no unrefined-fraction sample and no step update.
    pub fn transitions_without_statistic(&self) -> usize {
        self.transitions_without_statistic
    }
    /// Whether dual averaging was restarted at this update point.
    pub fn dual_averaging_restarted(&self) -> bool {
        self.dual_averaging_restarted
    }
    /// Zero-based discarded transition after which the update was applied.
    pub fn transition(&self) -> usize {
        self.transition
    }
    /// Slow window index, or `None` for the end of the initial fast phase.
    pub fn window_index(&self) -> Option<usize> {
        self.window_index
    }
    /// Completed orbits whose energy range entered the quantile.
    pub fn orbits(&self) -> usize {
        self.orbits
    }
    /// Empirical `p_a`-quantile of `K = (H_max - H_min) / delta`.
    pub fn inflation_quantile(&self) -> Option<f64> {
        self.inflation_quantile
    }
    /// Empirical `p_a`-quantile of the raw orbit energy range `H_max - H_min`.
    pub fn energy_range_quantile(&self) -> Option<f64> {
        self.energy_range_quantile
    }
    pub fn max_error_before(&self) -> f64 {
        self.max_error_before
    }
    pub fn max_error_after(&self) -> f64 {
        self.max_error_after
    }
    /// Mean over the window of the per-transition unrefined leaf fraction.
    pub fn unrefined_fraction_mean(&self) -> Option<f64> {
        self.unrefined_fraction_mean
    }
    pub fn step_before(&self) -> f64 {
        self.step_before
    }
    /// Step after the dual-averaging restart that follows an installation.
    pub fn step_after(&self) -> f64 {
        self.step_after
    }
    pub fn outcome(&self) -> PaperAdaptationOutcome {
        self.outcome
    }
}

/// Fraction of built macro leaves that were accepted at their coarsest
/// refinement level. `None` when the transition built no leaf, so rejected
/// (invalid, exhausted, or non-reversible) attempts never count as
/// unrefined and an all-invalid transition contributes no statistic.
fn unrefined_leaf_fraction(work: &TransitionWorkTelemetry) -> Option<f64> {
    if work.leaves_built == 0 {
        return None;
    }
    let unrefined = work
        .histograms
        .refinement_level_built
        .first()
        .copied()
        .unwrap_or(0)
        .min(work.leaves_built);
    Some(unrefined as f64 / work.leaves_built as f64)
}

/// Bound a paper-mode step to [`PAPER_STEP_RELATIVE_BOUND`] around `initial`.
fn clamp_paper_step(step: f64, initial: f64) -> f64 {
    step.clamp(
        initial / PAPER_STEP_RELATIVE_BOUND,
        initial * PAPER_STEP_RELATIVE_BOUND,
    )
}

/// Linear-interpolation sample quantile of finite values; `None` when empty.
fn sample_quantile(values: &mut [f64], probability: f64) -> Option<f64> {
    if values.is_empty() {
        return None;
    }
    values.sort_by(f64::total_cmp);
    let position = probability * (values.len() - 1) as f64;
    let lower = position.floor() as usize;
    let upper = position.ceil() as usize;
    let fraction = position - lower as f64;
    Some(values[lower] + fraction * (values[upper] - values[lower]))
}

/// Per-chain state for the paper `delta` rule: orbit energy ranges and
/// unrefined fractions collected since the last update point, plus the
/// running mean of the unrefined fraction for
/// [`PaperStepStatistic::Cumulative`].
struct PaperWindow {
    energy_ranges: Vec<f64>,
    unrefined_sum: f64,
    unrefined_count: usize,
    without_statistic: usize,
    cumulative_sum: f64,
    cumulative_count: usize,
}

impl PaperWindow {
    fn new() -> Self {
        Self {
            energy_ranges: Vec::new(),
            unrefined_sum: 0.0,
            unrefined_count: 0,
            without_statistic: 0,
            cumulative_sum: 0.0,
            cumulative_count: 0,
        }
    }

    fn record(&mut self, energy_range: f64, unrefined_fraction: Option<f64>) {
        if energy_range.is_finite() && energy_range >= 0.0 {
            self.energy_ranges.push(energy_range);
        }
        match unrefined_fraction {
            Some(fraction) => {
                self.unrefined_sum += fraction;
                self.unrefined_count += 1;
            }
            None => self.without_statistic += 1,
        }
    }

    fn unrefined_mean(&self) -> Option<f64> {
        (self.unrefined_count > 0).then(|| self.unrefined_sum / self.unrefined_count as f64)
    }

    /// Fold one transition's unrefined fraction into the running mean and
    /// return the statistic to feed to the `h` rule under the given policy.
    fn step_statistic(
        &mut self,
        statistic: PaperStepStatistic,
        unrefined_fraction: Option<f64>,
    ) -> Option<f64> {
        if let Some(fraction) = unrefined_fraction {
            self.cumulative_sum += fraction;
            self.cumulative_count += 1;
        }
        match statistic {
            PaperStepStatistic::Cumulative => self.cumulative_mean(),
            _ => unrefined_fraction,
        }
    }

    fn cumulative_mean(&self) -> Option<f64> {
        (self.cumulative_count > 0).then(|| self.cumulative_sum / self.cumulative_count as f64)
    }

    fn reset_cumulative(&mut self) {
        self.cumulative_sum = 0.0;
        self.cumulative_count = 0;
    }

    /// Candidate `delta` from this window; consumes the collected orbits.
    fn candidate(
        &mut self,
        paper: &PaperAdaptationConfig,
        max_error: f64,
    ) -> (
        usize,
        Option<f64>,
        Option<f64>,
        Option<f64>,
        PaperAdaptationOutcome,
    ) {
        let orbits = self.energy_ranges.len();
        if !paper.adapt_local_error {
            return (orbits, None, None, None, PaperAdaptationOutcome::Disabled);
        }
        if orbits < paper.minimum_orbits.max(1) {
            return (
                orbits,
                None,
                None,
                None,
                PaperAdaptationOutcome::InsufficientOrbits,
            );
        }
        let range_quantile = sample_quantile(&mut self.energy_ranges, paper.quantile_probability);
        let inflation_quantile = range_quantile.map(|q| q / max_error);
        let candidate = inflation_quantile
            .map(|q| paper.global_energy_bound / q.max(1.0))
            .filter(|delta| delta.is_finite() && *delta > 0.0)
            .map(|delta| delta.clamp(PAPER_MAX_ERROR_BOUNDS.0, PAPER_MAX_ERROR_BOUNDS.1));
        let outcome = if candidate.is_some() {
            PaperAdaptationOutcome::Installed
        } else {
            PaperAdaptationOutcome::NonFinite
        };
        (
            orbits,
            inflation_quantile,
            range_quantile,
            candidate,
            outcome,
        )
    }

    fn reset(&mut self) {
        self.energy_ranges.clear();
        self.unrefined_sum = 0.0;
        self.unrefined_count = 0;
        self.without_statistic = 0;
    }
}

/// Opt-in adaptation performed during the discarded transitions.
///
/// Step size uses Nesterov dual averaging with the standard Hoffman--Gelman
/// constants. The diagonal mass is estimated by Welford's algorithm and
/// regularized toward unit variance and inverted to obtain momentum covariance
/// (the API's mass convention). Adaptation ends before the first retained
/// transition, so retained draws use one fixed kernel.
#[derive(Clone, Debug, PartialEq)]
pub struct WarmupConfig {
    target_acceptance: f64,
    adapt_step_size: bool,
    adapt_mass: bool,
    initial_step_search: Option<InitialStepSearchConfig>,
    windows: WarmupWindowConfig,
    warmup_telemetry_checkpoints: Vec<usize>,
    research_restart_reference_multiplier: ResearchRestartReferenceMultiplier,
    dual_averaging_acceptance: DualAveragingAcceptance,
    paper_adaptation: Option<PaperAdaptationConfig>,
}

impl Default for WarmupConfig {
    fn default() -> Self {
        Self {
            target_acceptance: 0.8,
            adapt_step_size: true,
            adapt_mass: true,
            initial_step_search: None,
            windows: WarmupWindowConfig::default(),
            warmup_telemetry_checkpoints: Vec::new(),
            research_restart_reference_multiplier: ResearchRestartReferenceMultiplier::One,
            dual_averaging_acceptance: DualAveragingAcceptance::CurrentCoarseEndpoint,
            paper_adaptation: None,
        }
    }
}

impl WarmupConfig {
    pub fn new(target_acceptance: f64) -> Result<Self, Error> {
        if !target_acceptance.is_finite() || target_acceptance <= 0.0 || target_acceptance >= 1.0 {
            return Err(Error::configuration(
                "warmup target acceptance must be finite and strictly between zero and one",
            ));
        }
        Ok(Self {
            target_acceptance,
            ..Self::default()
        })
    }

    pub fn with_step_size_adaptation(mut self, enabled: bool) -> Self {
        self.adapt_step_size = enabled;
        self
    }

    pub fn with_mass_adaptation(mut self, enabled: bool) -> Self {
        self.adapt_mass = enabled;
        self
    }

    /// Select an initial macro-step before dual averaging starts.
    pub fn with_initial_step_search(mut self, search: InitialStepSearchConfig) -> Self {
        self.initial_step_search = Some(search);
        self
    }

    pub fn with_windows(mut self, windows: WarmupWindowConfig) -> Self {
        self.windows = windows;
        self
    }

    /// Capture bounded warmup snapshots at exactly these zero-based transitions.
    pub fn with_telemetry_checkpoints(mut self, checkpoints: Vec<usize>) -> Result<Self, Error> {
        if checkpoints.windows(2).any(|pair| pair[0] >= pair[1]) {
            return Err(Error::configuration(
                "warmup telemetry checkpoints must be strictly increasing",
            ));
        }
        self.warmup_telemetry_checkpoints = checkpoints;
        Ok(self)
    }

    /// Research-only control; production defaults preserve the historical factor one.
    pub fn with_research_restart_reference_multiplier(
        mut self,
        multiplier: ResearchRestartReferenceMultiplier,
    ) -> Self {
        self.research_restart_reference_multiplier = multiplier;
        self
    }

    pub fn target_acceptance(&self) -> f64 {
        self.target_acceptance
    }

    pub fn adapts_step_size(&self) -> bool {
        self.adapt_step_size
    }

    pub fn adapts_mass(&self) -> bool {
        self.adapt_mass
    }

    pub fn initial_step_search(&self) -> Option<&InitialStepSearchConfig> {
        self.initial_step_search.as_ref()
    }

    pub fn windows(&self) -> &WarmupWindowConfig {
        &self.windows
    }
    pub fn telemetry_checkpoints(&self) -> &[usize] {
        &self.warmup_telemetry_checkpoints
    }
    pub fn research_restart_reference_multiplier(&self) -> ResearchRestartReferenceMultiplier {
        self.research_restart_reference_multiplier
    }
    pub fn with_dual_averaging_acceptance(mut self, acceptance: DualAveragingAcceptance) -> Self {
        self.dual_averaging_acceptance = acceptance;
        self
    }
    pub fn dual_averaging_acceptance(&self) -> DualAveragingAcceptance {
        self.dual_averaging_acceptance
    }

    /// Replace acceptance-driven step adaptation by the JMLR Appendix C
    /// rules; see [`PaperAdaptationConfig`]. Supported by the diagonal and
    /// fixed-operator facades only.
    pub fn with_paper_adaptation(mut self, paper: PaperAdaptationConfig) -> Self {
        self.paper_adaptation = Some(paper);
        self
    }
    pub fn paper_adaptation(&self) -> Option<&PaperAdaptationConfig> {
        self.paper_adaptation.as_ref()
    }
}

/// Dual-averaging target: acceptance by default, `Gamma` under the paper rules.
fn step_adaptation_target(warmup: &WarmupConfig) -> f64 {
    warmup
        .paper_adaptation
        .as_ref()
        .map_or(warmup.target_acceptance, |paper| {
            paper.unrefined_fraction_target
        })
}

fn reject_paper_adaptation(config: &RunConfig, facade: &str) -> Result<(), Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.paper_adaptation.is_some())
    {
        return Err(Error::configuration(format!(
            "paper adaptation is not supported by the {facade} facade"
        )));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum ResearchRestartReferenceMultiplier {
    One,
    Ten,
}

impl ResearchRestartReferenceMultiplier {
    pub fn value(self) -> f64 {
        match self {
            Self::One => 1.0,
            Self::Ten => 10.0,
        }
    }
}

/// Policy used to construct expanding metric-adaptation windows.
#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct WarmupWindowConfig {
    initial_buffer: usize,
    base_window: usize,
    terminal_buffer: usize,
}

impl Default for WarmupWindowConfig {
    fn default() -> Self {
        Self {
            initial_buffer: 75,
            base_window: 25,
            terminal_buffer: 50,
        }
    }
}

impl WarmupWindowConfig {
    pub fn new(
        initial_buffer: usize,
        base_window: NonZeroUsize,
        terminal_buffer: usize,
    ) -> Result<Self, Error> {
        initial_buffer
            .checked_add(base_window.get())
            .and_then(|value| value.checked_add(terminal_buffer))
            .ok_or_else(Error::overflow)?;
        Ok(Self {
            initial_buffer,
            base_window: base_window.get(),
            terminal_buffer,
        })
    }

    pub fn initial_buffer(&self) -> usize {
        self.initial_buffer
    }
    pub fn base_window(&self) -> usize {
        self.base_window
    }
    pub fn terminal_buffer(&self) -> usize {
        self.terminal_buffer
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum WarmupPhase {
    InitialFast,
    SlowWindow,
    TerminalFast,
}

#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct WarmupWindowMetadata {
    start: usize,
    end: usize,
}

impl WarmupWindowMetadata {
    pub fn start(&self) -> usize {
        self.start
    }
    pub fn end(&self) -> usize {
        self.end
    }
    pub fn len(&self) -> usize {
        self.end - self.start
    }
    pub fn is_empty(&self) -> bool {
        self.start == self.end
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct WarmupScheduleMetadata {
    initial_fast_end: usize,
    terminal_fast_start: usize,
    windows: Vec<WarmupWindowMetadata>,
    used_short_warmup_fallback: bool,
}

impl WarmupScheduleMetadata {
    pub fn initial_fast_end(&self) -> usize {
        self.initial_fast_end
    }
    pub fn terminal_fast_start(&self) -> usize {
        self.terminal_fast_start
    }
    pub fn windows(&self) -> &[WarmupWindowMetadata] {
        &self.windows
    }
    pub fn used_short_warmup_fallback(&self) -> bool {
        self.used_short_warmup_fallback
    }
    pub fn phase_at(&self, transition: usize) -> Option<WarmupPhase> {
        if transition < self.initial_fast_end {
            Some(WarmupPhase::InitialFast)
        } else if transition < self.terminal_fast_start {
            Some(WarmupPhase::SlowWindow)
        } else {
            Some(WarmupPhase::TerminalFast)
        }
    }
}

fn warmup_schedule(
    transitions: usize,
    config: &WarmupWindowConfig,
) -> Result<WarmupScheduleMetadata, Error> {
    let configured = config
        .initial_buffer
        .checked_add(config.base_window)
        .and_then(|value| value.checked_add(config.terminal_buffer))
        .ok_or_else(Error::overflow)?;
    let fallback = configured > transitions;
    let (initial, terminal, first_window) = if fallback {
        let initial = transitions.checked_mul(15).ok_or_else(Error::overflow)? / 100;
        let terminal = transitions.checked_mul(10).ok_or_else(Error::overflow)? / 100;
        (initial, terminal, transitions - initial - terminal)
    } else {
        (
            config.initial_buffer,
            config.terminal_buffer,
            config.base_window,
        )
    };
    let slow_end = transitions - terminal;
    let mut start = initial;
    let mut size = first_window;
    let mut windows = Vec::new();
    while start < slow_end {
        let remaining = slow_end - start;
        let mut length = size.min(remaining);
        if remaining > length {
            let after = remaining - length;
            let next = size.saturating_mul(2);
            if after < next {
                length = remaining;
            }
        }
        let end = start.checked_add(length).ok_or_else(Error::overflow)?;
        windows.push(WarmupWindowMetadata { start, end });
        start = end;
        size = size.saturating_mul(2);
    }
    Ok(WarmupScheduleMetadata {
        initial_fast_end: initial,
        terminal_fast_start: slow_end,
        windows,
        used_short_warmup_fallback: fallback,
    })
}

/// Bounds for the opt-in walnutpie-native initial macro-step search.
#[derive(Clone, Debug, PartialEq)]
pub struct InitialStepSearchConfig {
    probes: usize,
    max_steps: usize,
    max_target_calls: usize,
}

impl InitialStepSearchConfig {
    pub fn new(
        probes: NonZeroUsize,
        max_steps: NonZeroUsize,
        max_target_calls: NonZeroUsize,
    ) -> Result<Self, Error> {
        let probes = probes.get();
        let max_steps = max_steps.get();
        let max_target_calls = max_target_calls.get();
        if probes > max_target_calls {
            return Err(Error::configuration(
                "initial-step probes exceed the target-call limit",
            ));
        }
        probes.checked_mul(max_steps).ok_or_else(Error::overflow)?;
        Ok(Self {
            probes,
            max_steps,
            max_target_calls,
        })
    }

    pub fn probes(&self) -> usize {
        self.probes
    }
    pub fn max_steps(&self) -> usize {
        self.max_steps
    }
    pub fn max_target_calls(&self) -> usize {
        self.max_target_calls
    }
}

impl Default for InitialStepSearchConfig {
    fn default() -> Self {
        Self {
            probes: 4,
            max_steps: 16,
            max_target_calls: 1_024,
        }
    }
}

/// Work and outcome of an initial macro-step search.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct InitialStepSearchTelemetry {
    probes: usize,
    steps: usize,
    target_calls: usize,
    recoverable_target_failures: usize,
    micro_steps: usize,
    initial_step: f64,
    selected_step: f64,
}

impl InitialStepSearchTelemetry {
    pub fn probes(&self) -> usize {
        self.probes
    }
    pub fn steps(&self) -> usize {
        self.steps
    }
    pub fn target_calls(&self) -> usize {
        self.target_calls
    }
    pub fn recoverable_target_failures(&self) -> usize {
        self.recoverable_target_failures
    }
    pub fn micro_steps(&self) -> usize {
        self.micro_steps
    }
    pub fn initial_step(&self) -> f64 {
        self.initial_step
    }
    pub fn selected_step(&self) -> f64 {
        self.selected_step
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum StepSearchReason {
    Initial,
    MetricUpdate { window_index: usize },
    DualAveragingRestart { window_index: usize },
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct StepSearchEvent {
    reason: StepSearchReason,
    search: InitialStepSearchTelemetry,
}

impl StepSearchEvent {
    pub fn reason(&self) -> &StepSearchReason {
        &self.reason
    }
    pub fn search(&self) -> &InitialStepSearchTelemetry {
        &self.search
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum MetricUpdateOutcome {
    Installed,
    InsufficientSamples,
    IllConditionedFallback,
    FactorizationFallback,
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct AcceptanceStatisticSummary {
    count: usize,
    mean: Option<f64>,
    variance: Option<f64>,
    minimum: Option<f64>,
    maximum: Option<f64>,
}

impl AcceptanceStatisticSummary {
    pub fn count(&self) -> usize {
        self.count
    }
    pub fn mean(&self) -> Option<f64> {
        self.mean
    }
    pub fn variance(&self) -> Option<f64> {
        self.variance
    }
    pub fn minimum(&self) -> Option<f64> {
        self.minimum
    }
    pub fn maximum(&self) -> Option<f64> {
        self.maximum
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct DualAveragingTelemetry {
    iteration: usize,
    target: f64,
    mu: f64,
    h_bar: f64,
    log_step: f64,
    log_step_bar: f64,
}

impl DualAveragingTelemetry {
    pub fn iteration(&self) -> usize {
        self.iteration
    }
    pub fn target(&self) -> f64 {
        self.target
    }
    pub fn mu(&self) -> f64 {
        self.mu
    }
    pub fn h_bar(&self) -> f64 {
        self.h_bar
    }
    pub fn log_step(&self) -> f64 {
        self.log_step
    }
    pub fn log_step_bar(&self) -> f64 {
        self.log_step_bar
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct WarmupCheckpointTelemetry {
    transition: usize,
    phase: WarmupPhase,
    window_index: Option<usize>,
    step_before: f64,
    step_after: f64,
    current_coarse_endpoint: AcceptanceStatisticSummary,
    accepted_trajectory: AcceptanceStatisticSummary,
    dual_averaging: Option<DualAveragingTelemetry>,
    target_calls: usize,
    divergent: bool,
    refinement_attempts: usize,
    reverse_coarser_rejections: usize,
    unrefined_fraction: Option<f64>,
    max_error_after: f64,
}

impl WarmupCheckpointTelemetry {
    /// Fraction of attempted macro leaves that needed no refinement in this
    /// transition; `None` when no leaf was attempted.
    pub fn unrefined_fraction(&self) -> Option<f64> {
        self.unrefined_fraction
    }
    /// Local error threshold in force after this transition.
    pub fn max_error_after(&self) -> f64 {
        self.max_error_after
    }
    pub fn transition(&self) -> usize {
        self.transition
    }
    pub fn phase(&self) -> WarmupPhase {
        self.phase
    }
    pub fn window_index(&self) -> Option<usize> {
        self.window_index
    }
    pub fn step_before(&self) -> f64 {
        self.step_before
    }
    pub fn step_after(&self) -> f64 {
        self.step_after
    }
    pub fn current_coarse_endpoint(&self) -> AcceptanceStatisticSummary {
        self.current_coarse_endpoint
    }
    pub fn accepted_trajectory(&self) -> AcceptanceStatisticSummary {
        self.accepted_trajectory
    }
    pub fn dual_averaging(&self) -> Option<DualAveragingTelemetry> {
        self.dual_averaging
    }
    pub fn target_calls(&self) -> usize {
        self.target_calls
    }
    pub fn divergent(&self) -> bool {
        self.divergent
    }
    pub fn refinement_attempts(&self) -> usize {
        self.refinement_attempts
    }
    pub fn reverse_coarser_rejections(&self) -> usize {
        self.reverse_coarser_rejections
    }
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct MetricUpdateTelemetry {
    window_index: usize,
    transition: usize,
    sample_count: usize,
    outcome: MetricUpdateOutcome,
    mass_diagonal: Option<Vec<f64>>,
    mass_dense: Option<Vec<f64>>,
    shrinkage: f64,
    ridge: f64,
    condition_estimate: Option<f64>,
    cholesky_failures: usize,
    step_before: f64,
    step_after_search: Option<f64>,
    mass_diagonal_before: Option<Vec<f64>>,
    mass_dense_before: Option<Vec<f64>>,
    step_after_restart: Option<f64>,
    restart_reference_multiplier: Option<ResearchRestartReferenceMultiplier>,
    dual_averaging_after_restart: Option<DualAveragingTelemetry>,
}

impl MetricUpdateTelemetry {
    pub fn window_index(&self) -> usize {
        self.window_index
    }
    pub fn transition(&self) -> usize {
        self.transition
    }
    pub fn sample_count(&self) -> usize {
        self.sample_count
    }
    pub fn outcome(&self) -> MetricUpdateOutcome {
        self.outcome
    }
    pub fn mass_diagonal(&self) -> Option<&[f64]> {
        self.mass_diagonal.as_deref()
    }
    pub fn mass_dense(&self) -> Option<&[f64]> {
        self.mass_dense.as_deref()
    }
    pub fn shrinkage(&self) -> f64 {
        self.shrinkage
    }
    pub fn ridge(&self) -> f64 {
        self.ridge
    }
    pub fn condition_estimate(&self) -> Option<f64> {
        self.condition_estimate
    }
    pub fn cholesky_failures(&self) -> usize {
        self.cholesky_failures
    }
    pub fn step_before(&self) -> f64 {
        self.step_before
    }
    pub fn step_after_search(&self) -> Option<f64> {
        self.step_after_search
    }
    pub fn mass_diagonal_before(&self) -> Option<&[f64]> {
        self.mass_diagonal_before.as_deref()
    }
    pub fn mass_dense_before(&self) -> Option<&[f64]> {
        self.mass_dense_before.as_deref()
    }
    pub fn step_after_restart(&self) -> Option<f64> {
        self.step_after_restart
    }
    pub fn restart_reference_multiplier(&self) -> Option<ResearchRestartReferenceMultiplier> {
        self.restart_reference_multiplier
    }
    pub fn dual_averaging_after_restart(&self) -> Option<DualAveragingTelemetry> {
        self.dual_averaging_after_restart
    }
}

/// Classification of an error returned by a user target.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum TargetErrorKind {
    /// A target bug, invalid configuration, or other failure that aborts the run.
    Fatal,
    /// A mathematically negligible proposed region that is not representable.
    ///
    /// The kernel treats the proposed point as a zero-density point with a
    /// zero gradient (`logp = -inf`, `grad = 0`, exactly as upstream
    /// walnutpie maps a failed evaluation): the micro-step fails the endpoint
    /// tolerance and the leaf refines; only when every refinement level still
    /// ends in the region is the leaf rejected as refinement exhaustion. This
    /// must not be used for bugs, panics, incorrect gradients, or malformed
    /// target output.
    Recoverable,
}

/// Error returned by a user target.
///
/// [`TargetError::new`] constructs a fatal error for backward compatibility.
/// Use [`TargetError::recoverable`] only when a finite-coordinate proposal is
/// outside the target's numerically representable support and is intended to
/// have zero density.
#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct TargetError {
    kind: TargetErrorKind,
    message: Box<str>,
}

impl TargetError {
    /// Construct a fatal target error.
    pub fn new(message: impl Into<Box<str>>) -> Self {
        Self {
            kind: TargetErrorKind::Fatal,
            message: message.into(),
        }
    }

    /// Construct a recoverable zero-density proposal result.
    pub fn recoverable(message: impl Into<Box<str>>) -> Self {
        Self {
            kind: TargetErrorKind::Recoverable,
            message: message.into(),
        }
    }

    pub fn kind(&self) -> TargetErrorKind {
        self.kind
    }

    pub fn message(&self) -> &str {
        &self.message
    }
}

impl fmt::Display for TargetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for TargetError {}

/// Deterministic fused log-density/gradient target.
///
/// Implementations must be deterministic for a position during a run and
/// overwrite every component of `gradient`.
pub trait Target: Send + Sync {
    fn dimension(&self) -> usize;

    /// Deterministic constructor-only execution used by protocol-bound launch
    /// validation. The default is live execution. When true, budgeted
    /// multi-chain entry points complete their full admission/configuration
    /// path and return `Cancelled` before entering log-density evaluation.
    fn cancel_after_admission(&self) -> bool {
        false
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError>;
}

/// Shared exact runtime ceiling on started target callbacks.
///
/// Unlike the conservative constructor-admission bound, this counter limits
/// actual fused log-density/gradient callback starts. Once exhausted, no
/// additional wrapped target callback is entered. The counter is shared by
/// every chain using the same budget.
#[derive(Debug)]
pub struct TargetEvaluationBudget {
    maximum: usize,
    started: AtomicUsize,
}

/// Explicit constructor-admission ceiling used only with a shared runtime
/// [`TargetEvaluationBudget`].
///
/// This does not relax the limits on any unbudgeted entry point. Budgeted
/// preflight checks that this value covers the exact conservative multi-chain
/// bound and that the runtime budget is no larger than this admission ceiling.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct TargetEvaluationAdmissionLimit {
    maximum: usize,
}

impl TargetEvaluationAdmissionLimit {
    pub fn new(maximum: NonZeroUsize) -> Self {
        Self {
            maximum: maximum.get(),
        }
    }
    pub fn maximum(&self) -> usize {
        self.maximum
    }
}

impl TargetEvaluationBudget {
    pub fn new(maximum: NonZeroUsize) -> Self {
        Self {
            maximum: maximum.get(),
            started: AtomicUsize::new(0),
        }
    }
    pub fn maximum(&self) -> usize {
        self.maximum
    }
    pub fn started(&self) -> usize {
        self.started.load(Ordering::Acquire)
    }
    pub fn wrap<'a, T: Target>(&'a self, target: &'a T) -> BudgetedTarget<'a, T> {
        BudgetedTarget {
            target,
            budget: self,
        }
    }
    fn reserve(&self) -> bool {
        self.started
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |current| {
                (current < self.maximum).then_some(current + 1)
            })
            .is_ok()
    }
}

pub struct BudgetedTarget<'a, T> {
    target: &'a T,
    budget: &'a TargetEvaluationBudget,
}

impl<T: Target> Target for BudgetedTarget<'_, T> {
    fn dimension(&self) -> usize {
        self.target.dimension()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        if !self.budget.reserve() {
            return Err(TargetError::new(
                "runtime target-evaluation budget exhausted",
            ));
        }
        self.target.log_density_gradient(position, gradient)
    }
}

/// Cooperative cancellation checked at deterministic kernel safe points.
///
/// A target callback that never returns cannot be interrupted safely inside
/// the process. Applications requiring that guarantee must evaluate targets in
/// an isolated worker process and terminate that process on timeout.
pub trait Cancellation: Send + Sync {
    fn is_cancelled(&self) -> bool;
}

/// Kernel phase of a bounded proposal observation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProposalPhase {
    Initial,
    Forward,
    Reverse,
}
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProposalDirection {
    Forward,
    Backward,
}

/// Classification observed after a fused target evaluation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum ProposalTargetOutcome {
    Finite,
    Recoverable,
    Fatal,
    Nonfinite,
    Panicked,
    KernelNonfinite,
}

/// One synchronous, bounded research observation. Coordinate storage is
/// explicitly truncated to the configured prefix and exists only for the
/// duration of [`ProposalObserver::observe`].
#[derive(Clone, Debug)]
pub struct ProposalObservation {
    chain: usize,
    transition: usize,
    discarded: bool,
    phase: ProposalPhase,
    direction: Option<ProposalDirection>,
    refinement_level: Option<usize>,
    evaluation_in_attempt: usize,
    target_call: usize,
    phase_target_call: usize,
    coordinates: Box<[f64]>,
    coordinate_dimension: usize,
    kinetic: f64,
    potential: Option<f64>,
    initial_hamiltonian: Option<f64>,
    current_hamiltonian: Option<f64>,
    delta_h: Option<f64>,
    outcome: ProposalTargetOutcome,
}
impl ProposalObservation {
    pub fn chain(&self) -> usize {
        self.chain
    }
    pub fn transition(&self) -> usize {
        self.transition
    }
    pub fn is_discarded(&self) -> bool {
        self.discarded
    }
    pub fn phase(&self) -> ProposalPhase {
        self.phase
    }
    pub fn direction(&self) -> Option<ProposalDirection> {
        self.direction
    }
    pub fn refinement_level(&self) -> Option<usize> {
        self.refinement_level
    }
    pub fn evaluation_in_attempt(&self) -> usize {
        self.evaluation_in_attempt
    }
    pub fn target_call(&self) -> usize {
        self.target_call
    }
    pub fn phase_target_call(&self) -> usize {
        self.phase_target_call
    }
    pub fn coordinates(&self) -> &[f64] {
        &self.coordinates
    }
    pub fn coordinate_dimension(&self) -> usize {
        self.coordinate_dimension
    }
    pub fn coordinates_truncated(&self) -> bool {
        self.coordinates.len() != self.coordinate_dimension
    }
    pub fn kinetic(&self) -> f64 {
        self.kinetic
    }
    pub fn potential(&self) -> Option<f64> {
        self.potential
    }
    pub fn initial_hamiltonian(&self) -> Option<f64> {
        self.initial_hamiltonian
    }
    pub fn current_hamiltonian(&self) -> Option<f64> {
        self.current_hamiltonian
    }
    pub fn delta_h(&self) -> Option<f64> {
        self.delta_h
    }
    pub fn outcome(&self) -> ProposalTargetOutcome {
        self.outcome
    }
}

/// Synchronous observer for research telemetry. Calls are ordered within each
/// chain; parallel chains may call concurrently, so cross-chain ordering is not
/// promised. The sampler retains no observations. Only the explicitly bounded
/// coordinate prefix is allocated, while observer-owned allocations remain the
/// caller's responsibility and are outside [`ResourceLimits`].
///
/// An observer must not reenter a run using the same control. Reentrancy and
/// panics are contained as run errors without exposing partial sampler output.
pub trait ProposalObserver: Send + Sync {
    fn observe(&self, observation: &ProposalObservation);
}

/// Shared exact event ceiling and coordinate-prefix bound.
pub struct ProposalObservationControl<'a> {
    observer: &'a dyn ProposalObserver,
    maximum: usize,
    maximum_coordinates: usize,
    started: AtomicUsize,
}
impl<'a> ProposalObservationControl<'a> {
    pub fn new(
        observer: &'a dyn ProposalObserver,
        maximum: NonZeroUsize,
        maximum_coordinates: usize,
    ) -> Self {
        Self {
            observer,
            maximum: maximum.get(),
            maximum_coordinates,
            started: AtomicUsize::new(0),
        }
    }
    pub fn maximum(&self) -> usize {
        self.maximum
    }
    pub fn maximum_coordinates(&self) -> usize {
        self.maximum_coordinates
    }
    pub fn started(&self) -> usize {
        self.started.load(Ordering::Acquire)
    }
    fn reserve(&self) -> bool {
        self.started
            .fetch_update(Ordering::AcqRel, Ordering::Acquire, |x| {
                (x < self.maximum).then_some(x + 1)
            })
            .is_ok()
    }
}

/// Optional cooperative cancellation and wall-clock deadline.
#[derive(Clone, Copy, Default)]
pub struct RunControl<'a> {
    cancellation: Option<&'a dyn Cancellation>,
    deadline: Option<Instant>,
    proposal_observations: Option<&'a ProposalObservationControl<'a>>,
}

impl<'a> RunControl<'a> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn with_cancellation(mut self, cancellation: &'a dyn Cancellation) -> Self {
        self.cancellation = Some(cancellation);
        self
    }

    pub fn with_deadline(mut self, deadline: Instant) -> Self {
        self.deadline = Some(deadline);
        self
    }

    pub fn with_proposal_observations(
        mut self,
        observations: &'a ProposalObservationControl<'a>,
    ) -> Self {
        self.proposal_observations = Some(observations);
        self
    }

    pub fn with_timeout(self, timeout: Duration) -> Result<Self, Error> {
        let deadline = Instant::now()
            .checked_add(timeout)
            .ok_or_else(|| Error::configuration("deadline overflows Instant"))?;
        Ok(self.with_deadline(deadline))
    }

    pub fn deadline(&self) -> Option<Instant> {
        self.deadline
    }
}

/// Positive diagonal momentum covariance.
#[derive(Clone, Debug, PartialEq)]
pub struct DiagonalMass {
    diagonal: Vec<f64>,
}

impl DiagonalMass {
    pub fn identity(dimension: NonZeroUsize) -> Self {
        Self {
            diagonal: vec![1.0; dimension.get()],
        }
    }

    pub fn from_diagonal(diagonal: Vec<f64>) -> Result<Self, Error> {
        if diagonal.is_empty() {
            return Err(Error::configuration("mass dimension must be nonzero"));
        }
        if diagonal.iter().any(|value| {
            !value.is_finite()
                || *value <= 0.0
                || !value.recip().is_finite()
                || value.sqrt() > f64::MAX.sqrt() / 16.0
        }) {
            return Err(Error::configuration(
                "mass entries must be positive and safely representable",
            ));
        }
        Ok(Self { diagonal })
    }

    pub fn dimension(&self) -> usize {
        self.diagonal.len()
    }

    pub fn diagonal(&self) -> &[f64] {
        &self.diagonal
    }
}

/// Symmetric positive-definite dense momentum covariance (target precision).
///
/// Matrices are row-major and use the convention `p ~ N(0, M)`,
/// `K(p) = p' M^-1 p / 2`, and `dq/dt = M^-1 p`.
#[derive(Clone, Debug, PartialEq)]
pub struct DenseMass {
    matrix: Vec<f64>,
    chol_lower: Vec<f64>,
    inverse: Vec<f64>,
    dimension: usize,
}

impl DenseMass {
    /// Conservative default ceiling for cubic factorization and quadratic
    /// per-leapfrog work.
    pub const MAX_DIMENSION: usize = 256;

    pub fn identity(dimension: NonZeroUsize) -> Result<Self, Error> {
        let n = dimension.get();
        if n > Self::MAX_DIMENSION {
            return Err(Error::resource(
                "dense mass dimension exceeds its resource limit",
            ));
        }
        let mut matrix = vec![0.0; n * n];
        for i in 0..n {
            matrix[i * n + i] = 1.0;
        }
        Self::from_matrix(matrix, n)
    }

    /// Validate and factor a row-major symmetric positive-definite matrix.
    pub fn from_matrix(matrix: Vec<f64>, dimension: usize) -> Result<Self, Error> {
        if dimension == 0 || dimension > Self::MAX_DIMENSION {
            return Err(Error::resource(
                "dense mass dimension exceeds its resource limit",
            ));
        }
        if matrix.len()
            != dimension
                .checked_mul(dimension)
                .ok_or_else(Error::overflow)?
            || matrix.iter().any(|x| !x.is_finite())
        {
            return Err(Error::configuration(
                "dense mass must be a finite square matrix",
            ));
        }
        for i in 0..dimension {
            for j in 0..i {
                let a = matrix[i * dimension + j];
                let b = matrix[j * dimension + i];
                let scale = 1.0_f64.max(a.abs()).max(b.abs());
                if (a - b).abs() > 64.0 * f64::EPSILON * scale {
                    return Err(Error::configuration("dense mass must be symmetric"));
                }
            }
        }
        let chol_lower = cholesky(&matrix, dimension)
            .ok_or_else(|| Error::configuration("dense mass must be positive definite"))?;
        let inverse = inverse_from_cholesky(&chol_lower, dimension)
            .ok_or_else(|| Error::configuration("dense mass inverse is not representable"))?;
        Ok(Self {
            matrix,
            chol_lower,
            inverse,
            dimension,
        })
    }

    pub fn dimension(&self) -> usize {
        self.dimension
    }
    pub fn matrix(&self) -> &[f64] {
        &self.matrix
    }
    pub fn cholesky_lower(&self) -> &[f64] {
        &self.chol_lower
    }

    pub fn sample_momentum<R: Rng + ?Sized>(&self, rng: &mut R) -> Result<Vec<f64>, Error> {
        let normals: Vec<f64> = (0..self.dimension)
            .map(|_| StandardNormal.sample(rng))
            .collect();
        let momentum: Vec<f64> = (0..self.dimension)
            .map(|i| {
                (0..=i)
                    .map(|j| self.chol_lower[i * self.dimension + j] * normals[j])
                    .sum()
            })
            .collect();
        if momentum.iter().all(|x| x.is_finite()) {
            Ok(momentum)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "dense momentum refresh is not safely representable",
            ))
        }
    }

    pub fn kinetic_energy(&self, momentum: &[f64]) -> Result<f64, Error> {
        if momentum.len() != self.dimension || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration(
                "momentum must match dense mass dimension and be finite",
            ));
        }
        let velocity: Vec<f64> = self
            .inverse
            .chunks_exact(self.dimension)
            .map(|row| row.iter().zip(momentum).map(|(a, p)| a * p).sum())
            .collect();
        let energy = 0.5
            * momentum
                .iter()
                .zip(velocity)
                .map(|(p, v)| p * v)
                .sum::<f64>();
        if energy.is_finite() && energy >= 0.0 {
            Ok(energy)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "dense kinetic energy is not safely representable",
            ))
        }
    }

    pub fn drift(&self, momentum: &[f64]) -> Result<Vec<f64>, Error> {
        if momentum.len() != self.dimension || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration(
                "momentum must match dense mass dimension and be finite",
            ));
        }
        Ok(self
            .inverse
            .chunks_exact(self.dimension)
            .map(|row| row.iter().zip(momentum).map(|(a, p)| a * p).sum())
            .collect())
    }
}

impl MassOperator for DenseMass {
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        DenseMass::sample_momentum(self, rng).map_err(|error| ValidationError(error.to_string()))
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.drift(momentum)
            .expect("validated dense mass and momentum dimensions")
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        DenseMass::kinetic_energy(self, momentum)
            .expect("validated dense mass and momentum dimensions")
    }
    fn is_valid(&self) -> bool {
        true
    }
}

/// Block-diagonal momentum covariance with independently factorized contiguous
/// dense blocks. Each block obeys [`DenseMass::MAX_DIMENSION`], while the full
/// dimension may be larger. This preserves exact zero cross-block covariance
/// without allocating or factorizing a full dense matrix.
#[derive(Clone, Debug, PartialEq)]
pub struct BlockDiagonalMass {
    blocks: Vec<DenseMass>,
    offsets: Vec<usize>,
    dimension: usize,
    matrix_entries: usize,
}

impl BlockDiagonalMass {
    pub const MAX_BLOCKS: usize = 256;
    pub const MAX_TOTAL_DIMENSION: usize = 16_384;
    pub const MAX_MATRIX_ENTRIES: usize = 4_194_304;

    pub fn from_blocks(blocks: Vec<(Vec<f64>, usize)>) -> Result<Self, Error> {
        if blocks.is_empty() || blocks.len() > Self::MAX_BLOCKS {
            return Err(Error::resource(
                "block mass block count exceeds its resource limit",
            ));
        }
        let mut dense = Vec::with_capacity(blocks.len());
        let mut offsets = Vec::with_capacity(blocks.len() + 1);
        let mut dimension = 0usize;
        let mut matrix_entries = 0usize;
        offsets.push(0);
        for (matrix, block_dimension) in blocks {
            dimension = dimension
                .checked_add(block_dimension)
                .ok_or_else(Error::overflow)?;
            matrix_entries = matrix_entries
                .checked_add(
                    block_dimension
                        .checked_mul(block_dimension)
                        .ok_or_else(Error::overflow)?,
                )
                .ok_or_else(Error::overflow)?;
            if dimension > Self::MAX_TOTAL_DIMENSION || matrix_entries > Self::MAX_MATRIX_ENTRIES {
                return Err(Error::resource(
                    "block mass workspace exceeds its resource limit",
                ));
            }
            dense.push(DenseMass::from_matrix(matrix, block_dimension)?);
            offsets.push(dimension);
        }
        Ok(Self {
            blocks: dense,
            offsets,
            dimension,
            matrix_entries,
        })
    }

    pub fn dimension(&self) -> usize {
        self.dimension
    }
    pub fn block_dimensions(&self) -> Vec<usize> {
        self.blocks.iter().map(DenseMass::dimension).collect()
    }
    pub fn matrix_entries(&self) -> usize {
        self.matrix_entries
    }
    pub fn blocks(&self) -> &[DenseMass] {
        &self.blocks
    }

    pub fn sample_momentum<R: Rng + ?Sized>(&self, rng: &mut R) -> Result<Vec<f64>, Error> {
        let mut output = Vec::with_capacity(self.dimension);
        for block in &self.blocks {
            output.extend(block.sample_momentum(rng)?);
        }
        Ok(output)
    }

    pub fn drift(&self, momentum: &[f64]) -> Result<Vec<f64>, Error> {
        if momentum.len() != self.dimension || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration(
                "momentum must match block mass dimension and be finite",
            ));
        }
        let mut output = Vec::with_capacity(self.dimension);
        for (block, bounds) in self.blocks.iter().zip(self.offsets.windows(2)) {
            output.extend(block.drift(&momentum[bounds[0]..bounds[1]])?);
        }
        Ok(output)
    }

    pub fn kinetic_energy(&self, momentum: &[f64]) -> Result<f64, Error> {
        if momentum.len() != self.dimension || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration(
                "momentum must match block mass dimension and be finite",
            ));
        }
        let mut energy = 0.0;
        for (block, bounds) in self.blocks.iter().zip(self.offsets.windows(2)) {
            energy += block.kinetic_energy(&momentum[bounds[0]..bounds[1]])?;
        }
        if energy.is_finite() {
            Ok(energy)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "block kinetic energy is not safely representable",
            ))
        }
    }
}

impl MassOperator for BlockDiagonalMass {
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        BlockDiagonalMass::sample_momentum(self, rng)
            .map_err(|error| ValidationError(error.to_string()))
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.drift(momentum)
            .expect("validated block mass and momentum dimensions")
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        BlockDiagonalMass::kinetic_energy(self, momentum)
            .expect("validated block mass and momentum dimensions")
    }
    fn is_valid(&self) -> bool {
        true
    }
}

/// Exact linear-time structured covariance block.
#[derive(Clone, Debug, PartialEq)]
pub enum StructuredCovarianceBlock {
    /// Covariance `L L'` where `L` has a positive diagonal and one subdiagonal.
    BidiagonalCholesky {
        diagonal: Vec<f64>,
        subdiagonal: Vec<f64>,
    },
    /// `M[i,j] = scale[i] scale[j] rho^|i-j|`.
    ScaledAr1 { scale: Vec<f64>, rho: f64 },
}

impl StructuredCovarianceBlock {
    fn validate(self) -> Result<Self, Error> {
        match &self {
            Self::BidiagonalCholesky {
                diagonal,
                subdiagonal,
            } => {
                if diagonal.is_empty()
                    || subdiagonal.len() + 1 != diagonal.len()
                    || diagonal.iter().any(|x| !x.is_finite() || *x <= 0.0)
                    || subdiagonal.iter().any(|x| !x.is_finite())
                {
                    return Err(Error::configuration("invalid bidiagonal Cholesky block"));
                }
            }
            Self::ScaledAr1 { scale, rho } => {
                if scale.is_empty()
                    || scale.iter().any(|x| !x.is_finite() || *x <= 0.0)
                    || !rho.is_finite()
                    || rho.abs() >= 1.0
                {
                    return Err(Error::configuration("invalid scaled AR(1) block"));
                }
            }
        }
        Ok(self)
    }
    fn dimension(&self) -> usize {
        match self {
            Self::BidiagonalCholesky { diagonal, .. } => diagonal.len(),
            Self::ScaledAr1 { scale, .. } => scale.len(),
        }
    }
    fn multiply_lower(&self, z: &[f64]) -> Vec<f64> {
        match self {
            Self::BidiagonalCholesky {
                diagonal,
                subdiagonal,
            } => (0..z.len())
                .map(|i| {
                    diagonal[i] * z[i]
                        + if i > 0 {
                            subdiagonal[i - 1] * z[i - 1]
                        } else {
                            0.0
                        }
                })
                .collect::<Vec<_>>(),
            Self::ScaledAr1 { scale, rho } => {
                let innovation = (1.0 - rho * rho).sqrt();
                let mut state = z[0];
                let mut out = vec![scale[0] * state];
                for i in 1..z.len() {
                    state = rho * state + innovation * z[i];
                    out.push(scale[i] * state);
                }
                out
            }
        }
    }
    fn multiply_lower_transpose(&self, x: &[f64]) -> Vec<f64> {
        match self {
            Self::BidiagonalCholesky {
                diagonal,
                subdiagonal,
            } => (0..x.len())
                .map(|i| {
                    diagonal[i] * x[i]
                        + if i + 1 < x.len() {
                            subdiagonal[i] * x[i + 1]
                        } else {
                            0.0
                        }
                })
                .collect::<Vec<_>>(),
            Self::ScaledAr1 { scale, rho } => {
                let innovation = (1.0 - rho * rho).sqrt();
                let mut out = vec![0.0; x.len()];
                let mut suffix = 0.0;
                for i in (0..x.len()).rev() {
                    suffix = x[i] * scale[i] + rho * suffix;
                    out[i] = if i == 0 { suffix } else { innovation * suffix };
                }
                out
            }
        }
    }
    fn solve_lower(&self, rhs: &[f64]) -> Vec<f64> {
        match self {
            Self::BidiagonalCholesky {
                diagonal,
                subdiagonal,
            } => {
                let mut out = vec![0.0; rhs.len()];
                for i in 0..rhs.len() {
                    out[i] = (rhs[i]
                        - if i > 0 {
                            subdiagonal[i - 1] * out[i - 1]
                        } else {
                            0.0
                        })
                        / diagonal[i];
                }
                out
            }
            Self::ScaledAr1 { scale, rho } => {
                let innovation = (1.0 - rho * rho).sqrt();
                let mut out = Vec::with_capacity(rhs.len());
                out.push(rhs[0] / scale[0]);
                for i in 1..rhs.len() {
                    out.push((rhs[i] / scale[i] - rho * rhs[i - 1] / scale[i - 1]) / innovation);
                }
                out
            }
        }
    }
    fn solve_upper(&self, rhs: &[f64]) -> Vec<f64> {
        match self {
            Self::BidiagonalCholesky {
                diagonal,
                subdiagonal,
            } => {
                let mut out = vec![0.0; rhs.len()];
                for i in (0..rhs.len()).rev() {
                    out[i] = (rhs[i]
                        - if i + 1 < rhs.len() {
                            subdiagonal[i] * out[i + 1]
                        } else {
                            0.0
                        })
                        / diagonal[i];
                }
                out
            }
            Self::ScaledAr1 { scale, rho } => {
                let innovation = (1.0 - rho * rho).sqrt();
                (0..rhs.len())
                    .map(|i| {
                        let z = (if i == 0 { rhs[i] } else { rhs[i] / innovation })
                            - if i + 1 < rhs.len() {
                                rho * rhs[i + 1] / innovation
                            } else {
                                0.0
                            };
                        z / scale[i]
                    })
                    .collect()
            }
        }
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct StructuredBlockMass {
    blocks: Vec<StructuredCovarianceBlock>,
    offsets: Vec<usize>,
    dimension: usize,
}

impl StructuredBlockMass {
    pub fn new(blocks: Vec<StructuredCovarianceBlock>) -> Result<Self, Error> {
        if blocks.is_empty() || blocks.len() > BlockDiagonalMass::MAX_BLOCKS {
            return Err(Error::resource(
                "structured block count exceeds its resource limit",
            ));
        }
        let mut validated = Vec::with_capacity(blocks.len());
        let mut offsets = vec![0];
        let mut dimension = 0usize;
        for block in blocks {
            let block = block.validate()?;
            dimension = dimension
                .checked_add(block.dimension())
                .ok_or_else(Error::overflow)?;
            if dimension > BlockDiagonalMass::MAX_TOTAL_DIMENSION {
                return Err(Error::resource(
                    "structured dimension exceeds its resource limit",
                ));
            }
            offsets.push(dimension);
            validated.push(block);
        }
        Ok(Self {
            blocks: validated,
            offsets,
            dimension,
        })
    }
    pub fn dimension(&self) -> usize {
        self.dimension
    }
    pub fn block_dimensions(&self) -> Vec<usize> {
        self.blocks
            .iter()
            .map(StructuredCovarianceBlock::dimension)
            .collect()
    }
    pub fn covariance_diagonal(&self) -> Vec<f64> {
        self.blocks
            .iter()
            .flat_map(|block| match block {
                StructuredCovarianceBlock::BidiagonalCholesky {
                    diagonal,
                    subdiagonal,
                } => (0..diagonal.len())
                    .map(|i| {
                        diagonal[i] * diagonal[i]
                            + if i > 0 {
                                subdiagonal[i - 1] * subdiagonal[i - 1]
                            } else {
                                0.0
                            }
                    })
                    .collect::<Vec<_>>(),
                StructuredCovarianceBlock::ScaledAr1 { scale, .. } => {
                    scale.iter().map(|x| x * x).collect::<Vec<_>>()
                }
            })
            .collect()
    }
    pub fn sample_momentum<R: Rng + ?Sized>(&self, rng: &mut R) -> Result<Vec<f64>, Error> {
        let mut out = Vec::with_capacity(self.dimension);
        for block in &self.blocks {
            let z: Vec<f64> = (0..block.dimension())
                .map(|_| StandardNormal.sample(rng))
                .collect();
            out.extend(block.multiply_lower(&z));
        }
        Ok(out)
    }
    pub fn drift(&self, momentum: &[f64]) -> Result<Vec<f64>, Error> {
        if momentum.len() != self.dimension || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration("momentum must match structured mass"));
        }
        let mut out = Vec::with_capacity(self.dimension);
        for (block, bounds) in self.blocks.iter().zip(self.offsets.windows(2)) {
            let y = block.solve_lower(&momentum[bounds[0]..bounds[1]]);
            out.extend(block.solve_upper(&y));
        }
        Ok(out)
    }
    pub fn kinetic_energy(&self, momentum: &[f64]) -> Result<f64, Error> {
        let velocity = self.drift(momentum)?;
        let energy = 0.5
            * momentum
                .iter()
                .zip(velocity)
                .map(|(p, v)| p * v)
                .sum::<f64>();
        if energy.is_finite() && energy >= 0.0 {
            Ok(energy)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "structured kinetic energy is not representable",
            ))
        }
    }
}

impl MassOperator for StructuredBlockMass {
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        StructuredBlockMass::sample_momentum(self, rng)
            .map_err(|error| ValidationError(error.to_string()))
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.drift(momentum)
            .expect("validated structured mass and momentum dimensions")
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        StructuredBlockMass::kinetic_energy(self, momentum)
            .expect("validated structured mass and momentum dimensions")
    }
    fn is_valid(&self) -> bool {
        true
    }
}

/// SPD arrowhead covariance represented by the block Cholesky factor
/// `L = [[G, 0], [P U V', P]]`.
///
/// `G` is a small dense lower-triangular global factor, `P` is an O(T)
/// structured path factor, and `U V'` is a bounded-rank path/global coupling.
#[derive(Clone, Debug, PartialEq)]
pub struct LowRankArrowheadMass {
    global_lower: Vec<Vec<f64>>,
    path: StructuredCovarianceBlock,
    path_factors: Vec<Vec<f64>>,
    global_factors: Vec<Vec<f64>>,
    rank: usize,
    path_subspace: Option<PathSubspaceFactor>,
}

#[derive(Clone, Debug, PartialEq)]
struct PathSubspaceFactor {
    basis: Vec<Vec<f64>>,
    lower: Vec<Vec<f64>>,
}

impl LowRankArrowheadMass {
    pub const MAX_GLOBAL_DIMENSION: usize = 64;
    pub const MAX_RANK: usize = 16;

    pub fn new(
        global_lower: Vec<Vec<f64>>,
        path: StructuredCovarianceBlock,
        path_factors: Vec<Vec<f64>>,
        global_factors: Vec<Vec<f64>>,
    ) -> Result<Self, Error> {
        let global_dimension = global_lower.len();
        if global_dimension == 0 || global_dimension > Self::MAX_GLOBAL_DIMENSION {
            return Err(Error::resource("arrowhead global dimension exceeds limit"));
        }
        if global_lower.iter().enumerate().any(|(i, row)| {
            row.len() != global_dimension
                || row.iter().any(|x| !x.is_finite())
                || row[i] <= 0.0
                || row[i + 1..].iter().any(|x| *x != 0.0)
        }) {
            return Err(Error::configuration(
                "arrowhead global factor must be finite lower triangular",
            ));
        }
        let path = path.validate()?;
        let path_dimension = path.dimension();
        let rank = path_factors.first().map_or(0, Vec::len);
        if rank == 0 || rank > Self::MAX_RANK {
            return Err(Error::resource("arrowhead rank exceeds limit"));
        }
        if path_factors.len() != path_dimension
            || global_factors.len() != global_dimension
            || path_factors
                .iter()
                .chain(&global_factors)
                .any(|row| row.len() != rank || row.iter().any(|x| !x.is_finite()))
            || global_dimension
                .checked_add(path_dimension)
                .ok_or_else(Error::overflow)?
                > BlockDiagonalMass::MAX_TOTAL_DIMENSION
        {
            return Err(Error::configuration(
                "arrowhead factors have invalid dimensions or values",
            ));
        }
        Ok(Self {
            global_lower,
            path,
            path_factors,
            global_factors,
            rank,
            path_subspace: None,
        })
    }

    /// Construct an arrowhead factor whose path diagonal block is `P Q`,
    /// where `Q = I + V (S-I) V'`, `V'V=I`, and `S` is finite lower
    /// triangular with positive diagonal.
    pub fn new_with_path_subspace(
        global_lower: Vec<Vec<f64>>,
        path: StructuredCovarianceBlock,
        path_factors: Vec<Vec<f64>>,
        global_factors: Vec<Vec<f64>>,
        basis: Vec<Vec<f64>>,
        subspace_lower: Vec<Vec<f64>>,
    ) -> Result<Self, Error> {
        let mut mass = Self::new(global_lower, path, path_factors, global_factors)?;
        let path_dimension = mass.path.dimension();
        let rank = mass.rank;
        if basis.len() != path_dimension
            || basis
                .iter()
                .any(|row| row.len() != rank || row.iter().any(|value| !value.is_finite()))
            || subspace_lower.len() != rank
            || subspace_lower.iter().enumerate().any(|(i, row)| {
                row.len() != rank
                    || row.iter().any(|value| !value.is_finite())
                    || row[i] <= 0.0
                    || row[i + 1..].iter().any(|value| *value != 0.0)
            })
        {
            return Err(Error::configuration(
                "arrowhead path-subspace factor has invalid dimensions or values",
            ));
        }
        for i in 0..rank {
            for j in 0..rank {
                let dot = basis.iter().map(|row| row[i] * row[j]).sum::<f64>();
                let expected = if i == j { 1.0 } else { 0.0 };
                if (dot - expected).abs() > 1.0e-10 {
                    return Err(Error::configuration(
                        "arrowhead path-subspace basis must be orthonormal",
                    ));
                }
            }
        }
        mass.path_subspace = Some(PathSubspaceFactor {
            basis,
            lower: subspace_lower,
        });
        Ok(mass)
    }

    pub fn dimension(&self) -> usize {
        self.global_lower.len() + self.path.dimension()
    }

    pub fn rank(&self) -> usize {
        self.rank
    }

    /// Structured path factor used by this mass.
    pub fn path(&self) -> &StructuredCovarianceBlock {
        &self.path
    }

    fn lower_solve(matrix: &[Vec<f64>], rhs: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0; rhs.len()];
        for i in 0..rhs.len() {
            out[i] = (rhs[i] - (0..i).map(|j| matrix[i][j] * out[j]).sum::<f64>()) / matrix[i][i];
        }
        out
    }

    fn upper_solve(matrix: &[Vec<f64>], rhs: &[f64]) -> Vec<f64> {
        let mut out = vec![0.0; rhs.len()];
        for i in (0..rhs.len()).rev() {
            out[i] = (rhs[i]
                - (i + 1..rhs.len())
                    .map(|j| matrix[j][i] * out[j])
                    .sum::<f64>())
                / matrix[i][i];
        }
        out
    }

    fn multiply_global_lower(&self, z: &[f64]) -> Vec<f64> {
        (0..z.len())
            .map(|i| (0..=i).map(|j| self.global_lower[i][j] * z[j]).sum())
            .collect()
    }

    fn coupling_times_global(&self, z: &[f64]) -> Vec<f64> {
        let latent = (0..self.rank)
            .map(|k| {
                self.global_factors
                    .iter()
                    .zip(z)
                    .map(|(row, x)| row[k] * x)
                    .sum::<f64>()
            })
            .collect::<Vec<_>>();
        self.path_factors
            .iter()
            .map(|row| row.iter().zip(&latent).map(|(a, b)| a * b).sum())
            .collect()
    }

    fn apply_path_subspace(&self, vector: &[f64]) -> Vec<f64> {
        let Some(factor) = &self.path_subspace else {
            return vector.to_vec();
        };
        let projected = (0..self.rank)
            .map(|k| {
                factor
                    .basis
                    .iter()
                    .zip(vector)
                    .map(|(row, value)| row[k] * value)
                    .sum::<f64>()
            })
            .collect::<Vec<_>>();
        let transformed = (0..self.rank)
            .map(|i| {
                (0..=i)
                    .map(|j| factor.lower[i][j] * projected[j])
                    .sum::<f64>()
            })
            .collect::<Vec<_>>();
        vector
            .iter()
            .enumerate()
            .map(|(i, value)| {
                value
                    + (0..self.rank)
                        .map(|k| factor.basis[i][k] * (transformed[k] - projected[k]))
                        .sum::<f64>()
            })
            .collect()
    }

    fn solve_path_subspace(&self, vector: &[f64], transpose: bool) -> Vec<f64> {
        let Some(factor) = &self.path_subspace else {
            return vector.to_vec();
        };
        let projected = (0..self.rank)
            .map(|k| {
                factor
                    .basis
                    .iter()
                    .zip(vector)
                    .map(|(row, value)| row[k] * value)
                    .sum::<f64>()
            })
            .collect::<Vec<_>>();
        let solved = if transpose {
            Self::upper_solve(&factor.lower, &projected)
        } else {
            Self::lower_solve(&factor.lower, &projected)
        };
        vector
            .iter()
            .enumerate()
            .map(|(i, value)| {
                value
                    + (0..self.rank)
                        .map(|k| factor.basis[i][k] * (solved[k] - projected[k]))
                        .sum::<f64>()
            })
            .collect()
    }

    pub fn sample_momentum<R: Rng + ?Sized>(&self, rng: &mut R) -> Result<Vec<f64>, Error> {
        let global_z = (0..self.global_lower.len())
            .map(|_| StandardNormal.sample(rng))
            .collect::<Vec<_>>();
        let path_z = (0..self.path.dimension())
            .map(|_| StandardNormal.sample(rng))
            .collect::<Vec<_>>();
        let global = self.multiply_global_lower(&global_z);
        let coupling = self.coupling_times_global(&global_z);
        let path_z = self.apply_path_subspace(&path_z);
        let path_latent = path_z
            .iter()
            .zip(coupling)
            .map(|(x, y)| x + y)
            .collect::<Vec<_>>();
        let mut out = global;
        out.extend(self.path.multiply_lower(&path_latent));
        if out.iter().all(|x| x.is_finite()) {
            Ok(out)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "arrowhead momentum is not representable",
            ))
        }
    }

    pub fn drift(&self, momentum: &[f64]) -> Result<Vec<f64>, Error> {
        let global_dimension = self.global_lower.len();
        if momentum.len() != self.dimension() || momentum.iter().any(|x| !x.is_finite()) {
            return Err(Error::configuration("momentum must match arrowhead mass"));
        }
        let global_z = Self::lower_solve(&self.global_lower, &momentum[..global_dimension]);
        let path_raw = self.path.solve_lower(&momentum[global_dimension..]);
        let coupling = self.coupling_times_global(&global_z);
        let path_z = path_raw
            .iter()
            .zip(coupling)
            .map(|(x, y)| x - y)
            .collect::<Vec<_>>();
        let path_z = self.solve_path_subspace(&path_z, false);
        let path_transposed = self.solve_path_subspace(&path_z, true);
        let path_velocity = self.path.solve_upper(&path_transposed);
        let latent = (0..self.rank)
            .map(|k| {
                self.path_factors
                    .iter()
                    .zip(&path_transposed)
                    .map(|(row, x)| row[k] * x)
                    .sum::<f64>()
            })
            .collect::<Vec<_>>();
        let correction = self
            .global_factors
            .iter()
            .map(|row| row.iter().zip(&latent).map(|(a, b)| a * b).sum::<f64>())
            .collect::<Vec<_>>();
        let global_rhs = global_z
            .iter()
            .zip(correction)
            .map(|(x, y)| x - y)
            .collect::<Vec<_>>();
        let mut out = Self::upper_solve(&self.global_lower, &global_rhs);
        out.extend(path_velocity);
        if out.iter().all(|x| x.is_finite()) {
            Ok(out)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "arrowhead velocity is not representable",
            ))
        }
    }

    pub fn kinetic_energy(&self, momentum: &[f64]) -> Result<f64, Error> {
        let velocity = self.drift(momentum)?;
        let energy = 0.5
            * momentum
                .iter()
                .zip(velocity)
                .map(|(p, v)| p * v)
                .sum::<f64>();
        if energy.is_finite() && energy >= 0.0 {
            Ok(energy)
        } else {
            Err(Error::new(
                ErrorKind::Numerical,
                "arrowhead kinetic energy is not representable",
            ))
        }
    }
}

impl MassOperator for LowRankArrowheadMass {
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        LowRankArrowheadMass::sample_momentum(self, rng)
            .map_err(|error| ValidationError(error.to_string()))
    }

    fn dimension(&self) -> usize {
        self.dimension()
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.drift(momentum)
            .expect("validated arrowhead mass and momentum dimensions")
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        LowRankArrowheadMass::kinetic_energy(self, momentum)
            .expect("validated arrowhead mass and momentum dimensions")
    }
    fn is_valid(&self) -> bool {
        true
    }
}

/// Metric accepted by the versioned direct-original-q execution APIs.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub enum DirectOriginalQMass {
    Dense(DenseMass),
    BlockDiagonal(BlockDiagonalMass),
    StructuredPath(StructuredBlockMass),
    LowRankArrowhead(LowRankArrowheadMass),
}

impl DirectOriginalQMass {
    pub fn dimension(&self) -> usize {
        MassOperator::dimension(self)
    }
}

impl MassOperator for DirectOriginalQMass {
    fn dimension(&self) -> usize {
        match self {
            Self::Dense(value) => value.dimension(),
            Self::BlockDiagonal(value) => value.dimension(),
            Self::StructuredPath(value) => value.dimension(),
            Self::LowRankArrowhead(value) => value.dimension(),
        }
    }
    fn sample_momentum(&self, rng: &mut dyn rand::RngCore) -> Result<Vec<f64>, ValidationError> {
        match self {
            Self::Dense(value) => MassOperator::sample_momentum(value, rng),
            Self::BlockDiagonal(value) => MassOperator::sample_momentum(value, rng),
            Self::StructuredPath(value) => MassOperator::sample_momentum(value, rng),
            Self::LowRankArrowhead(value) => MassOperator::sample_momentum(value, rng),
        }
    }
    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        match self {
            Self::Dense(value) => MassOperator::velocity(value, momentum),
            Self::BlockDiagonal(value) => MassOperator::velocity(value, momentum),
            Self::StructuredPath(value) => MassOperator::velocity(value, momentum),
            Self::LowRankArrowhead(value) => MassOperator::velocity(value, momentum),
        }
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        match self {
            Self::Dense(value) => MassOperator::kinetic_energy(value, momentum),
            Self::BlockDiagonal(value) => MassOperator::kinetic_energy(value, momentum),
            Self::StructuredPath(value) => MassOperator::kinetic_energy(value, momentum),
            Self::LowRankArrowhead(value) => MassOperator::kinetic_energy(value, momentum),
        }
    }
    fn is_valid(&self) -> bool {
        true
    }
}

fn cholesky(matrix: &[f64], n: usize) -> Option<Vec<f64>> {
    let mut lower = vec![0.0; n * n];
    for i in 0..n {
        for j in 0..=i {
            let mut value = matrix[i * n + j];
            for k in 0..j {
                value -= lower[i * n + k] * lower[j * n + k];
            }
            if j == i {
                if !value.is_finite() || value <= 0.0 {
                    return None;
                }
                lower[i * n + j] = value.sqrt();
            } else {
                lower[i * n + j] = value / lower[j * n + j];
            }
        }
    }
    Some(lower)
}

fn inverse_from_cholesky(lower: &[f64], n: usize) -> Option<Vec<f64>> {
    let mut inverse = vec![0.0; n * n];
    let mut column = vec![0.0; n];
    let mut y = vec![0.0; n];
    for c in 0..n {
        y.fill(0.0);
        for i in 0..n {
            let rhs = if i == c { 1.0 } else { 0.0 };
            let sum: f64 = (0..i).map(|k| lower[i * n + k] * y[k]).sum();
            y[i] = (rhs - sum) / lower[i * n + i];
        }
        column.fill(0.0);
        for i in (0..n).rev() {
            let sum: f64 = (i + 1..n).map(|k| lower[k * n + i] * column[k]).sum();
            column[i] = (y[i] - sum) / lower[i * n + i];
        }
        for r in 0..n {
            inverse[r * n + c] = column[r];
        }
    }
    inverse.iter().all(|x| x.is_finite()).then_some(inverse)
}

/// Checked production resource ceilings. Values can only be tightened.
///
/// `max_result_bytes` covers retained samples, mandatory transition
/// diagnostics, telemetry and output containers. `max_working_bytes` covers a
/// conservative all-chains-live bound for copied initial positions, inverse
/// mass, momentum, gradients, states, spans, and transition workspaces.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct ResourceLimits {
    max_dimension: usize,
    max_chains: usize,
    max_total_transitions: usize,
    max_target_evaluations: usize,
    max_result_bytes: usize,
    max_working_bytes: usize,
}

impl Default for ResourceLimits {
    fn default() -> Self {
        Self {
            max_dimension: 4096,
            max_chains: 64,
            max_total_transitions: 1_000_000,
            max_target_evaluations: CONSERVATIVE_MAX_TARGET_EVALUATIONS,
            max_result_bytes: 512 * 1024 * 1024,
            max_working_bytes: 512 * 1024 * 1024,
        }
    }
}

impl ResourceLimits {
    pub fn new(
        max_dimension: NonZeroUsize,
        max_chains: NonZeroUsize,
        max_total_transitions: NonZeroUsize,
        max_target_evaluations: NonZeroUsize,
        max_result_bytes: NonZeroUsize,
        max_working_bytes: NonZeroUsize,
    ) -> Result<Self, Error> {
        let limits = Self {
            max_dimension: max_dimension.get(),
            max_chains: max_chains.get(),
            max_total_transitions: max_total_transitions.get(),
            max_target_evaluations: max_target_evaluations.get(),
            max_result_bytes: max_result_bytes.get(),
            max_working_bytes: max_working_bytes.get(),
        };
        let defaults = Self::default();
        if limits.max_dimension > defaults.max_dimension
            || limits.max_chains > defaults.max_chains
            || limits.max_total_transitions > defaults.max_total_transitions
            || limits.max_target_evaluations > defaults.max_target_evaluations
            || limits.max_result_bytes > defaults.max_result_bytes
            || limits.max_working_bytes > defaults.max_working_bytes
        {
            return Err(Error::configuration(
                "resource limits may tighten, but not exceed, conservative defaults",
            ));
        }
        Ok(limits)
    }

    pub fn max_dimension(&self) -> usize {
        self.max_dimension
    }
    pub fn max_chains(&self) -> usize {
        self.max_chains
    }
    pub fn max_total_transitions(&self) -> usize {
        self.max_total_transitions
    }
    pub fn max_target_evaluations(&self) -> usize {
        self.max_target_evaluations
    }
    pub fn max_result_bytes(&self) -> usize {
        self.max_result_bytes
    }
    pub fn max_working_bytes(&self) -> usize {
        self.max_working_bytes
    }
}

/// Explicit research-only opt-in that raises only the target-evaluation bound.
///
/// Values must exceed [`CONSERVATIVE_MAX_TARGET_EVALUATIONS`] and cannot exceed
/// the hard [`RESEARCH_MAX_TARGET_EVALUATIONS`] ceiling. All arithmetic used to
/// calculate the preflight bound remains checked. This opt-in does not change
/// any other [`ResourceLimits`] field or runtime control behavior.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ResearchTargetEvaluationLimit {
    max_target_evaluations: usize,
}

impl ResearchTargetEvaluationLimit {
    pub fn new(max_target_evaluations: NonZeroUsize) -> Result<Self, Error> {
        let value = max_target_evaluations.get();
        if value <= CONSERVATIVE_MAX_TARGET_EVALUATIONS {
            return Err(Error::configuration(
                "research target-evaluation limit must exceed the conservative default",
            ));
        }
        if value > RESEARCH_MAX_TARGET_EVALUATIONS {
            return Err(Error::configuration(
                "research target-evaluation limit exceeds the hard research ceiling",
            ));
        }
        Ok(Self {
            max_target_evaluations: value,
        })
    }

    pub fn max_target_evaluations(&self) -> usize {
        self.max_target_evaluations
    }
}

/// Provenance for the target-evaluation ceiling recorded in run metadata.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum TargetEvaluationLimitProvenance {
    ConservativeDefault,
    TightenedProductionLimit,
    ExplicitResearchOptIn,
    ExplicitBudgetedAdmission,
}

/// Fixed-count run configuration. Discarded transitions do not adapt anything.
#[derive(Clone, Debug, PartialEq)]
pub struct RunConfig {
    discarded: usize,
    retained: usize,
    seed: u64,
    max_maximum_depth_stops: usize,
    limits: ResourceLimits,
    tuning: KernelTuning,
    warmup: Option<WarmupConfig>,
    research_target_evaluation_limit: Option<ResearchTargetEvaluationLimit>,
    capture_acceptance: bool,
    outer_orbit_selection: OuterOrbitSelection,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PreflightReport {
    dimension: usize,
    chains: usize,
    total_transitions: usize,
    worst_case_target_evaluations: usize,
    admission_ceiling: usize,
}

impl PreflightReport {
    pub fn dimension(&self) -> usize {
        self.dimension
    }
    pub fn chains(&self) -> usize {
        self.chains
    }
    pub fn total_transitions(&self) -> usize {
        self.total_transitions
    }
    pub fn worst_case_target_evaluations(&self) -> usize {
        self.worst_case_target_evaluations
    }
    pub fn admission_ceiling(&self) -> usize {
        self.admission_ceiling
    }
}

impl RunConfig {
    pub fn new(discarded: usize, retained: NonZeroUsize, seed: u64) -> Self {
        Self {
            discarded,
            retained: retained.get(),
            seed,
            max_maximum_depth_stops: usize::MAX,
            limits: ResourceLimits::default(),
            tuning: KernelTuning::default(),
            warmup: None,
            research_target_evaluation_limit: None,
            capture_acceptance: false,
            outer_orbit_selection: OuterOrbitSelection::BiasedProgressive,
        }
    }

    /// Select the outer-orbit candidate rule for a clean-room research
    /// ablation. This does not alter recursive subtree selection.
    pub fn with_research_outer_orbit_selection(mut self, selection: OuterOrbitSelection) -> Self {
        self.outer_orbit_selection = selection;
        self
    }

    pub fn with_limits(mut self, limits: ResourceLimits) -> Self {
        self.limits = limits;
        self
    }

    /// Use validated fixed-kernel tuning for this run.
    pub fn with_tuning(mut self, tuning: KernelTuning) -> Self {
        self.tuning = tuning;
        self
    }

    /// Enable adaptation during `discarded` transitions.
    pub fn with_warmup(mut self, warmup: WarmupConfig) -> Self {
        self.warmup = Some(warmup);
        self
    }

    /// Raise only the target-evaluation preflight ceiling for bounded research.
    pub fn with_research_target_evaluation_limit(
        mut self,
        limit: ResearchTargetEvaluationLimit,
    ) -> Self {
        self.research_target_evaluation_limit = Some(limit);
        self
    }

    /// Exact conservative constructor-admission bound for this configuration.
    ///
    /// This is not a runtime counter: early stopping normally makes observed
    /// work much smaller. Use [`TargetEvaluationBudget`] when actual callback
    /// starts also require a hard ceiling.
    pub fn worst_case_target_evaluations(&self, chain_count: NonZeroUsize) -> Result<usize, Error> {
        let transitions = self
            .discarded
            .checked_add(self.retained)
            .and_then(|count| count.checked_mul(chain_count.get()))
            .ok_or_else(Error::overflow)?;
        let transition_evaluations = transitions
            .checked_mul(self.tuning.max_target_calls_per_transition()?)
            .ok_or_else(Error::overflow)?;
        let schedule = self
            .warmup
            .as_ref()
            .map(|warmup| warmup_schedule(self.discarded, &warmup.windows))
            .transpose()?;
        let searches = self
            .warmup
            .as_ref()
            .and_then(|warmup| {
                warmup.initial_step_search.as_ref().map(|search| {
                    let restarts = if warmup.adapt_mass && warmup.adapt_step_size {
                        schedule.as_ref().map_or(0, |schedule| {
                            schedule
                                .windows
                                .iter()
                                .filter(|window| window.end < self.discarded)
                                .count()
                        })
                    } else {
                        0
                    };
                    restarts
                        .checked_add(1)
                        .and_then(|count| count.checked_mul(search.max_target_calls))
                        .ok_or_else(Error::overflow)
                })
            })
            .transpose()?
            .unwrap_or(0)
            .checked_mul(chain_count.get())
            .ok_or_else(Error::overflow)?;
        transition_evaluations
            .checked_add(searches)
            .ok_or_else(Error::overflow)
    }

    /// Fail the run when completed transitions exceed this maximum-depth count.
    pub fn with_maximum_depth_stop_limit(mut self, limit: usize) -> Self {
        self.max_maximum_depth_stops = limit;
        self
    }

    pub fn discarded(&self) -> usize {
        self.discarded
    }
    pub fn retained(&self) -> usize {
        self.retained
    }
    pub fn seed(&self) -> u64 {
        self.seed
    }
    pub fn maximum_depth_stop_limit(&self) -> usize {
        self.max_maximum_depth_stops
    }
    pub fn limits(&self) -> &ResourceLimits {
        &self.limits
    }
    pub fn tuning(&self) -> &KernelTuning {
        &self.tuning
    }
    pub fn warmup(&self) -> Option<&WarmupConfig> {
        self.warmup.as_ref()
    }
    pub fn research_target_evaluation_limit(&self) -> Option<ResearchTargetEvaluationLimit> {
        self.research_target_evaluation_limit
    }
}

/// Why a transition stopped extending its orbit.
///
/// Since kernel revision `v10`, [`TargetError::recoverable`] results no longer
/// produce `InvalidEvaluation`: a zero-density point fails the endpoint
/// tolerance and refines like any over-tolerance micro-step, so a leaf that
/// cannot escape the zero-density region at any level stops as
/// [`StopReason::RefinementExhausted`]. `InvalidEvaluation` is retained for
/// API compatibility and for internal abort paths (cancellation, deadline,
/// target budget, observer panic); a successful run cannot report it because
/// those paths all fail the call.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum StopReason {
    MaximumDepth,
    OuterUTurn,
    RecursiveUTurn,
    RefinementExhausted,
    ReverseCoarserAccepted,
    InvalidEvaluation,
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct TransitionDiagnostics {
    depth: usize,
    stop: StopReason,
    target_evaluations: usize,
    direction_draws: usize,
    uniform_draws: usize,
    leaves_attempted: usize,
    leaves_built: usize,
    recoverable_target_failures: usize,
    zero_density_evaluations: usize,
    initial_hamiltonian: f64,
    minimum_hamiltonian: f64,
    maximum_hamiltonian: f64,
    maximum_absolute_energy_error: f64,
    divergent: bool,
    selected_refinement_level: Option<usize>,
    refinement_attempts: usize,
    reverse_coarser_rejections: usize,
    final_uturn_forward_dot: Option<f64>,
    final_uturn_backward_dot: Option<f64>,
    trajectory_macro_length: f64,
}

impl TransitionDiagnostics {
    pub fn depth(&self) -> usize {
        self.depth
    }
    pub fn stop(&self) -> StopReason {
        self.stop
    }
    pub fn target_evaluations(&self) -> usize {
        self.target_evaluations
    }
    pub fn direction_draws(&self) -> usize {
        self.direction_draws
    }
    pub fn uniform_draws(&self) -> usize {
        self.uniform_draws
    }
    pub fn leaves_attempted(&self) -> usize {
        self.leaves_attempted
    }
    pub fn leaves_built(&self) -> usize {
        self.leaves_built
    }
    /// Recoverable target failures encountered by this transition.
    pub fn recoverable_target_failures(&self) -> usize {
        self.recoverable_target_failures
    }
    /// Fused calls that returned a zero-density point and therefore refined
    /// (or exhausted refinement) instead of stopping the transition. Equal to
    /// [`Self::recoverable_target_failures`] for facade-run targets.
    pub fn zero_density_evaluations(&self) -> usize {
        self.zero_density_evaluations
    }
    pub fn initial_hamiltonian(&self) -> f64 {
        self.initial_hamiltonian
    }
    pub fn minimum_hamiltonian(&self) -> f64 {
        self.minimum_hamiltonian
    }
    pub fn maximum_hamiltonian(&self) -> f64 {
        self.maximum_hamiltonian
    }
    pub fn maximum_absolute_energy_error(&self) -> f64 {
        self.maximum_absolute_energy_error
    }
    pub fn divergent(&self) -> bool {
        self.divergent
    }
    /// Maximum zero-based refinement level selected by any accepted leaf.
    ///
    /// Returns `None` when the transition accepted no leaf.
    pub fn selected_refinement_level(&self) -> Option<usize> {
        self.selected_refinement_level
    }
    /// Total forward refinement attempts across all attempted leaves.
    pub fn refinement_attempts(&self) -> usize {
        self.refinement_attempts
    }
    /// Leaves rejected because a coarser reverse trajectory passed.
    pub fn reverse_coarser_rejections(&self) -> usize {
        self.reverse_coarser_rejections
    }
    pub fn final_uturn_forward_dot(&self) -> Option<f64> {
        self.final_uturn_forward_dot
    }
    pub fn final_uturn_backward_dot(&self) -> Option<f64> {
        self.final_uturn_backward_dot
    }
    pub fn final_uturn_margin(&self) -> Option<f64> {
        self.final_uturn_forward_dot
            .into_iter()
            .chain(self.final_uturn_backward_dot)
            .reduce(f64::min)
    }
    pub fn trajectory_macro_length(&self) -> f64 {
        self.trajectory_macro_length
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
#[non_exhaustive]
pub struct WorkTotals {
    transitions: usize,
    momentum_refreshes: usize,
    standard_normal_components: usize,
    target_calls_initial: usize,
    target_calls_forward: usize,
    target_calls_reverse: usize,
    forward_refinement_attempts: usize,
    forward_micro_steps_executed: usize,
    reverse_coarsening_attempts: usize,
    reverse_micro_steps_executed: usize,
    leaves_attempted: usize,
    leaves_built: usize,
    direction_draws: usize,
    uniform_draws: usize,
    maximum_depth_stops: usize,
    recoverable_target_failures: usize,
    zero_density_evaluations: usize,
    divergences: usize,
    invalid_evaluation_stops: usize,
    refinement_exhaustion_stops: usize,
    reverse_coarser_stops: usize,
    reverse_coarser_rejections: usize,
}

impl WorkTotals {
    pub fn transitions(&self) -> usize {
        self.transitions
    }
    pub fn momentum_refreshes(&self) -> usize {
        self.momentum_refreshes
    }
    pub fn standard_normal_components(&self) -> usize {
        self.standard_normal_components
    }
    pub fn target_calls_initial(&self) -> usize {
        self.target_calls_initial
    }
    pub fn target_calls_forward(&self) -> usize {
        self.target_calls_forward
    }
    pub fn target_calls_reverse(&self) -> usize {
        self.target_calls_reverse
    }
    pub fn target_calls_total(&self) -> usize {
        self.target_calls_initial + self.target_calls_forward + self.target_calls_reverse
    }
    pub fn forward_refinement_attempts(&self) -> usize {
        self.forward_refinement_attempts
    }
    pub fn forward_micro_steps_executed(&self) -> usize {
        self.forward_micro_steps_executed
    }
    pub fn reverse_coarsening_attempts(&self) -> usize {
        self.reverse_coarsening_attempts
    }
    pub fn reverse_micro_steps_executed(&self) -> usize {
        self.reverse_micro_steps_executed
    }
    pub fn leaves_attempted(&self) -> usize {
        self.leaves_attempted
    }
    pub fn leaves_built(&self) -> usize {
        self.leaves_built
    }
    pub fn direction_draws(&self) -> usize {
        self.direction_draws
    }
    pub fn uniform_draws(&self) -> usize {
        self.uniform_draws
    }
    pub fn maximum_depth_stops(&self) -> usize {
        self.maximum_depth_stops
    }
    /// Recoverable target failures in this work partition.
    pub fn recoverable_target_failures(&self) -> usize {
        self.recoverable_target_failures
    }
    /// Fused calls that returned a zero-density point and refined instead of
    /// stopping a transition (kernel revision `v10` semantics).
    pub fn zero_density_evaluations(&self) -> usize {
        self.zero_density_evaluations
    }
    pub fn divergences(&self) -> usize {
        self.divergences
    }
    pub fn invalid_evaluation_stops(&self) -> usize {
        self.invalid_evaluation_stops
    }
    pub fn refinement_exhaustion_stops(&self) -> usize {
        self.refinement_exhaustion_stops
    }
    pub fn reverse_coarser_stops(&self) -> usize {
        self.reverse_coarser_stops
    }
    pub fn reverse_coarser_rejections(&self) -> usize {
        self.reverse_coarser_rejections
    }

    fn add_transition(
        &mut self,
        dimension: usize,
        work: &TransitionWorkTelemetry,
        uniform_draws: usize,
        recoverable_target_failures: usize,
        diagnostics: &crate::kernel::TransitionDiagnostics,
    ) -> Result<(), Error> {
        macro_rules! add {
            ($field:ident, $value:expr) => {
                self.$field = self
                    .$field
                    .checked_add($value)
                    .ok_or_else(Error::overflow)?
            };
        }
        add!(transitions, 1);
        add!(momentum_refreshes, 1);
        add!(standard_normal_components, dimension);
        add!(target_calls_initial, work.fused_calls.initial);
        add!(target_calls_forward, work.fused_calls.forward);
        add!(target_calls_reverse, work.fused_calls.reverse);
        add!(
            forward_refinement_attempts,
            work.forward_refinement_attempts
        );
        add!(
            forward_micro_steps_executed,
            work.forward_micro_steps_executed
        );
        add!(
            reverse_coarsening_attempts,
            work.reverse_coarsening_attempts
        );
        add!(
            reverse_micro_steps_executed,
            work.reverse_micro_steps_executed
        );
        add!(leaves_attempted, work.leaves_attempted);
        add!(leaves_built, work.leaves_built);
        add!(direction_draws, work.direction_draws);
        add!(uniform_draws, uniform_draws);
        add!(maximum_depth_stops, work.stops.max_depth);
        add!(recoverable_target_failures, recoverable_target_failures);
        add!(
            zero_density_evaluations,
            diagnostics.zero_density_evaluations
        );
        add!(divergences, usize::from(diagnostics.divergent));
        add!(
            invalid_evaluation_stops,
            usize::from(matches!(
                diagnostics.stop,
                TransitionStop::Recursive(SpanStop::Leaf(Rejection::InvalidEvaluation))
            ))
        );
        add!(
            refinement_exhaustion_stops,
            usize::from(matches!(
                diagnostics.stop,
                TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted))
            ))
        );
        add!(
            reverse_coarser_stops,
            usize::from(matches!(
                diagnostics.stop,
                TransitionStop::Recursive(SpanStop::Leaf(Rejection::ReverseCoarserAccepted))
            ))
        );
        add!(
            reverse_coarser_rejections,
            diagnostics.reverse_coarser_rejections
        );
        Ok(())
    }
}

#[derive(Clone, Debug, Default, PartialEq)]
#[non_exhaustive]
pub struct RunTelemetry {
    discarded: WorkTotals,
    retained: WorkTotals,
    total: WorkTotals,
    initial_step_search: Option<InitialStepSearchTelemetry>,
    initial_fast: WorkTotals,
    slow: WorkTotals,
    terminal_fast: WorkTotals,
    step_searches: Vec<StepSearchEvent>,
    metric_updates: Vec<MetricUpdateTelemetry>,
    acceptance_values: Vec<Option<f64>>,
    warmup_checkpoints: Vec<WarmupCheckpointTelemetry>,
    paper_adaptation_updates: Vec<PaperAdaptationUpdate>,
}

impl RunTelemetry {
    /// Paper-rule update points, in transition order; empty unless
    /// [`WarmupConfig::with_paper_adaptation`] was used.
    pub fn paper_adaptation_updates(&self) -> &[PaperAdaptationUpdate] {
        &self.paper_adaptation_updates
    }
    pub fn discarded(&self) -> &WorkTotals {
        &self.discarded
    }
    pub fn retained(&self) -> &WorkTotals {
        &self.retained
    }
    pub fn total(&self) -> &WorkTotals {
        &self.total
    }
    pub fn initial_step_search(&self) -> Option<&InitialStepSearchTelemetry> {
        self.initial_step_search.as_ref()
    }
    pub fn initial_fast(&self) -> &WorkTotals {
        &self.initial_fast
    }
    pub fn slow(&self) -> &WorkTotals {
        &self.slow
    }
    pub fn terminal_fast(&self) -> &WorkTotals {
        &self.terminal_fast
    }
    pub fn step_searches(&self) -> &[StepSearchEvent] {
        &self.step_searches
    }
    pub fn metric_updates(&self) -> &[MetricUpdateTelemetry] {
        &self.metric_updates
    }
    pub fn warmup_checkpoints(&self) -> &[WarmupCheckpointTelemetry] {
        &self.warmup_checkpoints
    }
    pub fn adaptation_target_calls(&self) -> usize {
        self.step_searches
            .iter()
            .map(|event| event.search.target_calls)
            .sum()
    }
    pub fn target_calls_including_adaptation(&self) -> usize {
        self.total
            .target_calls_total()
            .saturating_add(self.adaptation_target_calls())
    }
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct RunMetadata {
    algorithm_revision: &'static str,
    crate_version: &'static str,
    rng_implementation: &'static str,
    seed_derivation: &'static str,
    base_seed: u64,
    effective_seed: u64,
    dimension: usize,
    discarded: usize,
    retained: usize,
    maximum_depth_stop_limit: usize,
    step_size: f64,
    min_micro_steps: usize,
    max_refinement_levels: usize,
    max_error: f64,
    divergence_threshold: f64,
    max_depth: usize,
    initial_position: Vec<f64>,
    thread_count: usize,
    mass_diagonal: Vec<f64>,
    initial_mass_diagonal: Vec<f64>,
    warmup: Option<WarmupConfig>,
    warmup_schedule: Option<WarmupScheduleMetadata>,
    initial_step_search: Option<InitialStepSearchTelemetry>,
    tuning: KernelTuning,
    initial_tuning: KernelTuning,
    limits: ResourceLimits,
    effective_max_target_evaluations: usize,
    target_evaluation_limit_provenance: TargetEvaluationLimitProvenance,
}

impl RunMetadata {
    pub fn algorithm_revision(&self) -> &str {
        self.algorithm_revision
    }
    pub fn crate_version(&self) -> &str {
        self.crate_version
    }
    pub fn rng_implementation(&self) -> &str {
        self.rng_implementation
    }
    pub fn seed_derivation(&self) -> &str {
        self.seed_derivation
    }
    pub fn base_seed(&self) -> u64 {
        self.base_seed
    }
    pub fn effective_seed(&self) -> u64 {
        self.effective_seed
    }
    pub fn dimension(&self) -> usize {
        self.dimension
    }
    pub fn discarded(&self) -> usize {
        self.discarded
    }
    pub fn retained(&self) -> usize {
        self.retained
    }
    pub fn maximum_depth_stop_limit(&self) -> usize {
        self.maximum_depth_stop_limit
    }
    pub fn qualified_step_size(&self) -> f64 {
        self.step_size
    }
    pub fn min_micro_steps(&self) -> usize {
        self.min_micro_steps
    }
    pub fn max_refinement_levels(&self) -> usize {
        self.max_refinement_levels
    }
    pub fn max_error(&self) -> f64 {
        self.max_error
    }
    pub fn divergence_threshold(&self) -> f64 {
        self.divergence_threshold
    }
    pub fn max_depth(&self) -> usize {
        self.max_depth
    }
    pub fn initial_position(&self) -> &[f64] {
        &self.initial_position
    }
    pub fn thread_count(&self) -> usize {
        self.thread_count
    }
    pub fn mass_diagonal(&self) -> &[f64] {
        &self.mass_diagonal
    }
    pub fn initial_mass_diagonal(&self) -> &[f64] {
        &self.initial_mass_diagonal
    }
    pub fn warmup(&self) -> Option<&WarmupConfig> {
        self.warmup.as_ref()
    }
    pub fn warmup_schedule(&self) -> Option<&WarmupScheduleMetadata> {
        self.warmup_schedule.as_ref()
    }
    pub fn initial_step_search(&self) -> Option<&InitialStepSearchTelemetry> {
        self.initial_step_search.as_ref()
    }
    pub fn tuning(&self) -> &KernelTuning {
        &self.tuning
    }
    pub fn initial_tuning(&self) -> &KernelTuning {
        &self.initial_tuning
    }
    pub fn limits(&self) -> &ResourceLimits {
        &self.limits
    }
    pub fn effective_max_target_evaluations(&self) -> usize {
        self.effective_max_target_evaluations
    }
    pub fn target_evaluation_limit_provenance(&self) -> TargetEvaluationLimitProvenance {
        self.target_evaluation_limit_provenance
    }
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct ChainOutput {
    samples: Vec<f64>,
    retained: usize,
    dimension: usize,
    diagnostics: Vec<TransitionDiagnostics>,
    telemetry: RunTelemetry,
    metadata: RunMetadata,
}

impl ChainOutput {
    /// Retained samples flattened in draw-major order: `[draw][parameter]`.
    pub fn samples(&self) -> &[f64] {
        &self.samples
    }
    pub fn sample(&self, draw: usize) -> Option<&[f64]> {
        let start = draw.checked_mul(self.dimension)?;
        let end = start.checked_add(self.dimension)?;
        self.samples.get(start..end)
    }
    pub fn retained(&self) -> usize {
        self.retained
    }
    pub fn dimension(&self) -> usize {
        self.dimension
    }
    /// Diagnostics in transition order: discarded first, then retained.
    pub fn diagnostics(&self) -> &[TransitionDiagnostics] {
        &self.diagnostics
    }
    pub fn telemetry(&self) -> &RunTelemetry {
        &self.telemetry
    }
    pub fn metadata(&self) -> &RunMetadata {
        &self.metadata
    }
}

#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub struct MultiChainOutput {
    chains: Vec<ChainOutput>,
    base_seed: u64,
    algorithm_revision: &'static str,
}

impl MultiChainOutput {
    /// Chains in input/chain-index order, independent of Rayon scheduling.
    pub fn chains(&self) -> &[ChainOutput] {
        &self.chains
    }
    pub fn base_seed(&self) -> u64 {
        self.base_seed
    }
    pub fn algorithm_revision(&self) -> &str {
        self.algorithm_revision
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum ErrorKind {
    Configuration,
    ResourceLimit,
    Target,
    Numerical,
    Cancelled,
    DeadlineExceeded,
    Panic,
    Unhealthy,
    Overflow,
    Internal,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum ControlStop {
    Cancelled,
    Deadline,
    Panic,
}

struct ExecutionControl<'a> {
    public: &'a RunControl<'a>,
    failed_chain: Option<&'a AtomicUsize>,
    chain: usize,
}

impl ExecutionControl<'_> {
    fn check(&self) -> Result<(), ControlStop> {
        if self
            .failed_chain
            .is_some_and(|failed| self.chain > failed.load(Ordering::Acquire))
        {
            return Err(ControlStop::Cancelled);
        }
        if let Some(cancellation) = self.public.cancellation {
            match catch_unwind(AssertUnwindSafe(|| cancellation.is_cancelled())) {
                Ok(true) => return Err(ControlStop::Cancelled),
                Ok(false) => {}
                Err(_) => return Err(ControlStop::Panic),
            }
        }
        if self.public.deadline.is_some_and(|at| Instant::now() >= at) {
            return Err(ControlStop::Deadline);
        }
        Ok(())
    }
}

struct ObservationInput<'a> {
    transition: usize,
    discarded: bool,
    context: Option<crate::kernel::EvaluationContext>,
    theta: &'a [f64],
    log_density: Option<f64>,
    outcome: ProposalTargetOutcome,
    target_call: usize,
    phase_target_call: usize,
}
fn emit_proposal_observation(
    control: &ExecutionControl<'_>,
    input: ObservationInput<'_>,
) -> Result<(), ControlStop> {
    let ObservationInput {
        transition,
        discarded,
        context,
        theta,
        log_density,
        outcome,
        target_call,
        phase_target_call,
    } = input;
    let Some(observations) = control.public.proposal_observations else {
        return Ok(());
    };
    if !observations.reserve() {
        return Ok(());
    }
    let context = context.unwrap_or(crate::kernel::EvaluationContext {
        phase: EvaluationPhase::Initial,
        direction: None,
        refinement_level: None,
        evaluation_in_attempt: 0,
        kinetic: f64::NAN,
        initial_hamiltonian: None,
    });
    let potential = log_density.filter(|x| x.is_finite()).map(|x| -x);
    let current = potential
        .filter(|_| context.kinetic.is_finite())
        .map(|x| x + context.kinetic);
    let initial = context.initial_hamiltonian.or_else(|| {
        (context.phase == EvaluationPhase::Initial)
            .then_some(current)
            .flatten()
    });
    let observation = ProposalObservation {
        chain: control.chain,
        transition,
        discarded,
        phase: match context.phase {
            EvaluationPhase::Initial => ProposalPhase::Initial,
            EvaluationPhase::Forward => ProposalPhase::Forward,
            EvaluationPhase::Reverse => ProposalPhase::Reverse,
        },
        direction: context.direction.map(|x| match x {
            Direction::Forward => ProposalDirection::Forward,
            Direction::Backward => ProposalDirection::Backward,
        }),
        refinement_level: context.refinement_level,
        evaluation_in_attempt: context.evaluation_in_attempt,
        target_call,
        phase_target_call,
        coordinates: theta[..theta.len().min(observations.maximum_coordinates)].into(),
        coordinate_dimension: theta.len(),
        kinetic: context.kinetic,
        potential,
        initial_hamiltonian: initial,
        current_hamiltonian: current,
        delta_h: initial.zip(current).map(|(a, b)| b - a),
        outcome,
    };
    thread_local! {static OBSERVER_ACTIVE:Cell<bool>=const{Cell::new(false)};}
    OBSERVER_ACTIVE.with(|active| {
        if active.replace(true) {
            return Err(ControlStop::Panic);
        }
        let result = catch_unwind(AssertUnwindSafe(|| {
            observations.observer.observe(&observation)
        }))
        .map_err(|_| ControlStop::Panic);
        active.set(false);
        result
    })
}

fn control_error(stop: ControlStop) -> Error {
    match stop {
        ControlStop::Cancelled => Error::new(ErrorKind::Cancelled, "sampling was cancelled"),
        ControlStop::Deadline => Error::new(
            ErrorKind::DeadlineExceeded,
            "sampling deadline was exceeded",
        ),
        ControlStop::Panic => Error::new(ErrorKind::Panic, "cancellation callback panicked"),
    }
}

#[derive(Debug)]
#[non_exhaustive]
pub struct Error {
    kind: ErrorKind,
    message: Box<str>,
    chain: Option<usize>,
    transition: Option<usize>,
    target_source: Option<TargetError>,
}

impl Error {
    fn new(kind: ErrorKind, message: impl Into<Box<str>>) -> Self {
        Self {
            kind,
            message: message.into(),
            chain: None,
            transition: None,
            target_source: None,
        }
    }

    fn configuration(message: impl Into<Box<str>>) -> Self {
        Self::new(ErrorKind::Configuration, message)
    }
    fn resource(message: impl Into<Box<str>>) -> Self {
        Self::new(ErrorKind::ResourceLimit, message)
    }
    fn overflow() -> Self {
        Self::new(ErrorKind::Overflow, "checked arithmetic overflow")
    }
    fn internal(error: ValidationError) -> Self {
        Self::new(ErrorKind::Internal, error.0)
    }
    fn at_transition(mut self, transition: usize) -> Self {
        self.transition = Some(transition);
        self
    }
    fn at_chain(mut self, chain: usize) -> Self {
        self.chain = Some(chain);
        self
    }

    pub fn kind(&self) -> ErrorKind {
        self.kind
    }
    pub fn message(&self) -> &str {
        &self.message
    }
    pub fn chain(&self) -> Option<usize> {
        self.chain
    }
    pub fn transition(&self) -> Option<usize> {
        self.transition
    }
    pub fn target_source(&self) -> Option<&TargetError> {
        self.target_source.as_ref()
    }
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.message)
    }
}

impl std::error::Error for Error {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        self.target_source
            .as_ref()
            .map(|source| source as &(dyn std::error::Error + 'static))
    }
}

struct KernelRng<'a, 'b> {
    rng: &'a mut SmallRng,
    control: &'a ExecutionControl<'b>,
    stopped: &'a mut Option<ControlStop>,
}

impl Uniform01 for KernelRng<'_, '_> {
    fn uniform_01(&mut self) -> Result<f64, ValidationError> {
        if let Err(stop) = self.control.check() {
            *self.stopped = Some(stop);
            return Err(ValidationError("execution stopped".into()));
        }
        Ok(self.rng.random())
    }
}

impl TransitionRng for KernelRng<'_, '_> {
    fn direction(&mut self) -> Result<Direction, ValidationError> {
        if let Err(stop) = self.control.check() {
            *self.stopped = Some(stop);
            return Err(ValidationError("execution stopped".into()));
        }
        Ok(if self.rng.random() {
            Direction::Forward
        } else {
            Direction::Backward
        })
    }
}

#[cfg(test)]
fn tuning() -> TransitionTuning {
    KernelTuning::default().transition_tuning()
}

struct DualAveraging {
    target: f64,
    mu: f64,
    log_step: f64,
    log_step_bar: f64,
    h_bar: f64,
    iteration: usize,
}

fn acceptance_summary(values: impl Iterator<Item = f64>) -> AcceptanceStatisticSummary {
    let mut count = 0usize;
    let mut mean = 0.0;
    let mut m2 = 0.0;
    let mut minimum = f64::INFINITY;
    let mut maximum = f64::NEG_INFINITY;
    for value in values {
        count += 1;
        let delta = value - mean;
        mean += delta / count as f64;
        m2 += delta * (value - mean);
        minimum = minimum.min(value);
        maximum = maximum.max(value);
    }
    if count == 0 {
        AcceptanceStatisticSummary::default()
    } else {
        AcceptanceStatisticSummary {
            count,
            mean: Some(mean),
            variance: Some(m2 / count as f64),
            minimum: Some(minimum),
            maximum: Some(maximum),
        }
    }
}

impl DualAveraging {
    fn new(step: f64, target: f64) -> Self {
        Self::with_reference(step, target, 10.0)
    }

    fn restart(
        step: f64,
        target: f64,
        reference_multiplier: ResearchRestartReferenceMultiplier,
    ) -> Self {
        Self::with_reference(step, target, reference_multiplier.value())
    }

    fn with_reference(step: f64, target: f64, reference_multiplier: f64) -> Self {
        Self {
            target,
            mu: (reference_multiplier * step).ln(),
            log_step: step.ln(),
            log_step_bar: step.ln(),
            h_bar: 0.0,
            iteration: 0,
        }
    }

    fn update(&mut self, acceptance: f64) -> f64 {
        self.iteration += 1;
        let t = self.iteration as f64;
        let eta = 1.0 / (t + 10.0);
        self.h_bar = (1.0 - eta) * self.h_bar + eta * (self.target - acceptance);
        self.log_step = self.mu - t.sqrt() / 0.05 * self.h_bar;
        let weight = t.powf(-0.75);
        self.log_step_bar = weight * self.log_step + (1.0 - weight) * self.log_step_bar;
        self.log_step.exp().clamp(f64::MIN_POSITIVE, 1.0e6)
    }

    fn final_step(&self) -> f64 {
        self.log_step_bar.exp().clamp(f64::MIN_POSITIVE, 1.0e6)
    }

    fn telemetry(&self) -> DualAveragingTelemetry {
        DualAveragingTelemetry {
            iteration: self.iteration,
            target: self.target,
            mu: self.mu,
            h_bar: self.h_bar,
            log_step: self.log_step,
            log_step_bar: self.log_step_bar,
        }
    }
}

struct DiagonalVariance {
    count: usize,
    mean: Vec<f64>,
    m2: Vec<f64>,
}

#[derive(Clone)]
struct DenseCovariance {
    count: usize,
    mean: Vec<f64>,
    m2: Vec<f64>,
}

impl DenseCovariance {
    fn new(dimension: usize) -> Self {
        Self {
            count: 0,
            mean: vec![0.0; dimension],
            m2: vec![0.0; dimension * dimension],
        }
    }

    fn update(&mut self, position: &[f64]) {
        self.count += 1;
        let n = self.count as f64;
        let delta: Vec<f64> = position
            .iter()
            .zip(&self.mean)
            .map(|(x, mean)| x - mean)
            .collect();
        for (mean, d) in self.mean.iter_mut().zip(&delta) {
            *mean += d / n;
        }
        let n_dim = self.mean.len();
        for (i, delta_i) in delta.iter().enumerate() {
            for (j, position_j) in position.iter().enumerate().take(i + 1) {
                let value = delta_i * (position_j - self.mean[j]);
                self.m2[i * n_dim + j] += value;
                if i != j {
                    self.m2[j * n_dim + i] += value;
                }
            }
        }
    }

    fn merge(&mut self, other: &Self) -> Result<(), Error> {
        if other.count == 0 {
            return Ok(());
        }
        if self.count == 0 {
            self.clone_from(other);
            return Ok(());
        }
        if self.mean.len() != other.mean.len() {
            return Err(Error::new(
                ErrorKind::Internal,
                "covariance summary dimensions differ",
            ));
        }
        let combined = self
            .count
            .checked_add(other.count)
            .ok_or_else(Error::overflow)?;
        let left = self.count as f64;
        let right = other.count as f64;
        let total = combined as f64;
        let delta: Vec<f64> = other
            .mean
            .iter()
            .zip(&self.mean)
            .map(|(right, left)| right - left)
            .collect();
        for (mean, (other_mean, delta)) in self.mean.iter_mut().zip(other.mean.iter().zip(&delta)) {
            *mean = (*mean * left + *other_mean * right) / total;
            debug_assert!((*mean - (*other_mean - delta * left / total)).abs() < 1.0e-8);
        }
        let scale = left * right / total;
        let dimension = self.mean.len();
        for i in 0..dimension {
            for j in 0..dimension {
                self.m2[i * dimension + j] +=
                    other.m2[i * dimension + j] + delta[i] * delta[j] * scale;
            }
        }
        self.count = combined;
        Ok(())
    }

    fn precision_candidate(
        &self,
    ) -> (
        MetricUpdateOutcome,
        Option<DenseMass>,
        f64,
        f64,
        Option<f64>,
        usize,
    ) {
        let n_dim = self.mean.len();
        let minimum = (n_dim + 1).max(20);
        if self.count < minimum {
            return (
                MetricUpdateOutcome::InsufficientSamples,
                None,
                0.0,
                0.0,
                None,
                0,
            );
        }
        let n = self.count as f64;
        // Full covariance estimation needs dimension-aware shrinkage: with
        // only O(d) warmup draws, a near-unregularized inverse is unstable.
        let shrinkage = (n_dim as f64 / (n + n_dim as f64)).clamp(0.05, 0.8);
        let mut covariance: Vec<f64> = self.m2.iter().map(|x| x / (n - 1.0)).collect();
        let mean_diagonal =
            (0..n_dim).map(|i| covariance[i * n_dim + i]).sum::<f64>() / n_dim as f64;
        for i in 0..n_dim {
            for j in 0..n_dim {
                if i != j {
                    covariance[i * n_dim + j] *= 1.0 - shrinkage;
                }
            }
        }
        let base_ridge = (mean_diagonal.abs().max(1.0) * 1.0e-10).max(f64::MIN_POSITIVE);
        let mut ridge = base_ridge;
        let mut failures = 0;
        let mut last_condition = None;
        for _ in 0..10 {
            let mut regularized = covariance.clone();
            for i in 0..n_dim {
                regularized[i * n_dim + i] = (1.0 - shrinkage) * regularized[i * n_dim + i]
                    + shrinkage * mean_diagonal.max(MIN_ADAPTATION_VARIANCE)
                    + ridge;
            }
            let Some(chol) = cholesky(&regularized, n_dim) else {
                failures += 1;
                ridge *= 10.0;
                continue;
            };
            let (minimum_pivot, maximum_pivot) = (0..n_dim)
                .map(|i| chol[i * n_dim + i])
                .fold((f64::INFINITY, 0.0_f64), |(lo, hi), x| {
                    (lo.min(x), hi.max(x))
                });
            let condition = (maximum_pivot / minimum_pivot).powi(2);
            last_condition = Some(condition);
            if condition > 1.0e6 {
                ridge *= 10.0;
                continue;
            }
            let Some(precision) = inverse_from_cholesky(&chol, n_dim) else {
                failures += 1;
                ridge *= 10.0;
                continue;
            };
            match DenseMass::from_matrix(precision, n_dim) {
                Ok(candidate) => {
                    return (
                        MetricUpdateOutcome::Installed,
                        Some(candidate),
                        shrinkage,
                        ridge,
                        last_condition,
                        failures,
                    );
                }
                Err(_) => {
                    failures += 1;
                    ridge *= 10.0;
                }
            }
        }
        let outcome = if failures > 0 {
            MetricUpdateOutcome::FactorizationFallback
        } else {
            MetricUpdateOutcome::IllConditionedFallback
        };
        (outcome, None, shrinkage, ridge, last_condition, failures)
    }
}

impl DiagonalVariance {
    fn new(dimension: usize) -> Self {
        Self {
            count: 0,
            mean: vec![0.0; dimension],
            m2: vec![0.0; dimension],
        }
    }

    fn update(&mut self, position: &[f64]) {
        self.count += 1;
        let n = self.count as f64;
        for ((mean, m2), value) in self.mean.iter_mut().zip(&mut self.m2).zip(position) {
            let delta = value - *mean;
            *mean += delta / n;
            *m2 += delta * (value - *mean);
        }
    }

    fn regularized_mass(&self) -> Option<Vec<f64>> {
        if self.count < 2 {
            return None;
        }
        let n = self.count as f64;
        Some(
            self.m2
                .iter()
                .map(|m2| {
                    ((n / (n + 5.0)) * (m2 / (n - 1.0)) + 5.0 / (n + 5.0))
                        .max(MIN_ADAPTATION_VARIANCE)
                        .recip()
                })
                .collect(),
        )
    }
}

fn inverse_mass(mass: &DiagonalMass) -> Result<Vec<f64>, Error> {
    mass.diagonal
        .iter()
        .map(|value| {
            let inverse = value.recip();
            if inverse.is_finite() && inverse > 0.0 {
                Ok(inverse)
            } else {
                Err(Error::configuration(
                    "mass entries must have finite positive reciprocals",
                ))
            }
        })
        .collect()
}

fn validate<'a, T, I>(
    target: &T,
    chain_count: usize,
    initial_positions: I,
    mass: &DiagonalMass,
    config: &RunConfig,
) -> Result<(usize, usize, usize), Error>
where
    T: Target,
    I: IntoIterator<Item = &'a [f64]>,
{
    validate_with_admission(target, chain_count, initial_positions, mass, config, None)
}

fn validate_with_admission<'a, T, I>(
    target: &T,
    chain_count: usize,
    initial_positions: I,
    mass: &DiagonalMass,
    config: &RunConfig,
    budgeted_admission_ceiling: Option<usize>,
) -> Result<(usize, usize, usize), Error>
where
    T: Target,
    I: IntoIterator<Item = &'a [f64]>,
{
    let dimension = catch_unwind(AssertUnwindSafe(|| target.dimension()))
        .map_err(|_| Error::new(ErrorKind::Panic, "target dimension callback panicked"))?;
    if dimension == 0 || dimension > config.limits.max_dimension {
        return Err(Error::resource(
            "target dimension exceeds its resource limit",
        ));
    }
    if mass.dimension() != dimension {
        return Err(Error::configuration(
            "target and diagonal mass dimensions differ",
        ));
    }
    if config.warmup.is_some() && config.discarded == 0 {
        return Err(Error::configuration(
            "warmup requires at least one discarded transition",
        ));
    }
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.paper_adaptation.is_some())
        && config.tuning.max_refinement_levels < 2
    {
        return Err(Error::configuration(
            "paper adaptation requires at least two refinement levels",
        ));
    }
    if config.warmup.as_ref().is_some_and(|warmup| {
        warmup
            .warmup_telemetry_checkpoints
            .last()
            .is_some_and(|checkpoint| *checkpoint >= config.discarded)
    }) {
        return Err(Error::configuration(
            "warmup telemetry checkpoint lies outside discarded transitions",
        ));
    }
    if chain_count == 0 || chain_count > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    if initial_positions
        .into_iter()
        .any(|position| position.len() != dimension || position.iter().any(|x| !x.is_finite()))
    {
        return Err(Error::configuration(
            "initial positions must match the target dimension and be finite",
        ));
    }
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let total_transitions = transitions
        .checked_mul(chain_count)
        .ok_or_else(Error::overflow)?;
    if total_transitions > config.limits.max_total_transitions {
        return Err(Error::resource(
            "transition count exceeds its resource limit",
        ));
    }
    let schedule = config
        .warmup
        .as_ref()
        .map(|warmup| warmup_schedule(config.discarded, &warmup.windows))
        .transpose()?;
    let evaluations = config.worst_case_target_evaluations(
        NonZeroUsize::new(chain_count).ok_or_else(Error::overflow)?,
    )?;
    if budgeted_admission_ceiling.is_some() && config.research_target_evaluation_limit.is_some() {
        return Err(Error::configuration(
            "budgeted admission cannot be combined with a research target-evaluation limit",
        ));
    }
    let effective_max_target_evaluations = budgeted_admission_ceiling.unwrap_or_else(|| {
        config
            .research_target_evaluation_limit
            .map_or(config.limits.max_target_evaluations, |limit| {
                limit.max_target_evaluations
            })
    });
    if evaluations > effective_max_target_evaluations {
        return Err(Error::resource(
            "target-evaluation bound exceeds its resource limit",
        ));
    }
    let sample_bytes = config
        .retained
        .checked_mul(dimension)
        .and_then(|value| value.checked_mul(chain_count))
        .and_then(|value| value.checked_mul(size_of::<f64>()))
        .ok_or_else(Error::overflow)?;
    let diagnostics_bytes = total_transitions
        .checked_mul(size_of::<TransitionDiagnostics>())
        .ok_or_else(Error::overflow)?;
    let metadata_vector_bytes = chain_count
        .checked_mul(dimension)
        .and_then(|value| value.checked_mul(size_of::<f64>() * 3))
        .ok_or_else(Error::overflow)?;
    let update_count = schedule.as_ref().map_or(0, |value| value.windows.len());
    let paper_update_count = if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.paper_adaptation.is_some())
    {
        update_count.checked_add(1).ok_or_else(Error::overflow)?
    } else {
        0
    };
    let search_event_count = config
        .warmup
        .as_ref()
        .and_then(|warmup| warmup.initial_step_search.as_ref().map(|_| warmup))
        .map_or(0, |warmup| {
            1 + if warmup.adapt_mass && warmup.adapt_step_size {
                schedule.as_ref().map_or(0, |schedule| {
                    schedule
                        .windows
                        .iter()
                        .filter(|window| window.end < config.discarded)
                        .count()
                })
            } else {
                0
            }
        });
    let adaptation_vector_bytes = chain_count
        .checked_mul(
            update_count
                .checked_mul(size_of::<MetricUpdateTelemetry>())
                .and_then(|value| {
                    value.checked_add(
                        update_count
                            .checked_mul(dimension)?
                            .checked_mul(size_of::<f64>() * 2)?,
                    )
                })
                .and_then(|value| {
                    value.checked_add(search_event_count.checked_mul(size_of::<StepSearchEvent>())?)
                })
                .and_then(|value| {
                    value.checked_add(update_count.checked_mul(size_of::<WarmupWindowMetadata>())?)
                })
                .and_then(|value| {
                    value.checked_add(
                        config
                            .warmup
                            .as_ref()
                            .map_or(0, |warmup| warmup.warmup_telemetry_checkpoints.len())
                            .checked_mul(size_of::<WarmupCheckpointTelemetry>())?,
                    )
                })
                .and_then(|value| {
                    // Paper rules report one update per slow window plus the
                    // initial-fast boundary.
                    value.checked_add(
                        paper_update_count.checked_mul(size_of::<PaperAdaptationUpdate>())?,
                    )
                })
                .ok_or_else(Error::overflow)?,
        )
        .ok_or_else(Error::overflow)?;
    let result_bytes = sample_bytes
        .checked_add(diagnostics_bytes)
        .and_then(|value| value.checked_add(metadata_vector_bytes))
        .and_then(|value| value.checked_add(chain_count.checked_mul(size_of::<ChainOutput>())?))
        .and_then(|value| value.checked_add(size_of::<MultiChainOutput>()))
        .and_then(|value| value.checked_add(chain_count.checked_mul(size_of::<RunTelemetry>())?))
        .and_then(|value| value.checked_add(adaptation_vector_bytes))
        .ok_or_else(Error::overflow)?;
    if result_bytes > config.limits.max_result_bytes {
        return Err(Error::resource("result data exceeds its resource limit"));
    }
    // The validated kernel uses dimension-sized vectors and bounded depth-three
    // span/state storage. 128 f64 slots per coordinate plus 16 KiB per chain
    // intentionally overbounds current copied inputs and transient workspaces.
    // The paper delta rule buffers at most one orbit energy range per
    // discarded transition of the longest window; bound it by all discarded
    // transitions.
    let paper_buffer_bytes = if paper_update_count > 0 {
        config
            .discarded
            .checked_mul(size_of::<f64>())
            .ok_or_else(Error::overflow)?
    } else {
        0
    };
    let working_bytes = dimension
        .checked_mul(size_of::<f64>())
        .and_then(|value| value.checked_mul(128))
        .and_then(|value| value.checked_add(16 * 1024))
        .and_then(|value| value.checked_add(paper_buffer_bytes))
        .and_then(|value| value.checked_mul(chain_count))
        .ok_or_else(Error::overflow)?;
    if working_bytes > config.limits.max_working_bytes {
        return Err(Error::resource(
            "temporary working data exceeds its resource limit",
        ));
    }
    inverse_mass(mass)?;
    Ok((dimension, transitions, total_transitions))
}

/// Validate a complete diagonal multi-chain configuration without sampling.
pub fn preflight_chains<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    let (dimension, _, total_transitions) = validate(
        target,
        initial_positions.len(),
        initial_positions.iter().map(Vec::as_slice),
        mass,
        config,
    )?;
    let chains = initial_positions.len();
    Ok(PreflightReport {
        dimension,
        chains,
        total_transitions,
        worst_case_target_evaluations: config.worst_case_target_evaluations(
            NonZeroUsize::new(chains).ok_or_else(Error::overflow)?,
        )?,
        admission_ceiling: config
            .research_target_evaluation_limit
            .map_or(config.limits.max_target_evaluations, |x| {
                x.max_target_evaluations
            }),
    })
}

/// Validate a diagonal multi-chain run against an explicit admission ceiling
/// and a smaller exact shared runtime callback cap, without entering a target
/// log-density/gradient callback.
pub fn preflight_chains_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<PreflightReport, Error> {
    if budget.maximum() > admission_limit.maximum() {
        return Err(Error::configuration(
            "runtime target-evaluation budget exceeds its admission ceiling",
        ));
    }
    let (dimension, _, total_transitions) = validate_with_admission(
        target,
        initial_positions.len(),
        initial_positions.iter().map(Vec::as_slice),
        mass,
        config,
        Some(admission_limit.maximum()),
    )?;
    let chains = initial_positions.len();
    Ok(PreflightReport {
        dimension,
        chains,
        total_transitions,
        worst_case_target_evaluations: config.worst_case_target_evaluations(
            NonZeroUsize::new(chains).ok_or_else(Error::overflow)?,
        )?,
        admission_ceiling: admission_limit.maximum(),
    })
}

/// Validate a dense multi-chain run and its adaptation workspace against
/// explicit admission/runtime callback caps without entering the target.
pub fn preflight_chains_dense_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DenseMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<PreflightReport, Error> {
    if budget.maximum() > admission_limit.maximum() {
        return Err(Error::configuration(
            "runtime target-evaluation budget exceeds its admission ceiling",
        ));
    }
    if initial_positions.is_empty() || initial_positions.len() > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    let dimension = catch_unwind(AssertUnwindSafe(|| target.dimension()))
        .map_err(|_| Error::new(ErrorKind::Panic, "target dimension callback panicked"))?;
    if dimension != mass.dimension
        || initial_positions.iter().any(|position| {
            position.len() != dimension || position.iter().any(|value| !value.is_finite())
        })
    {
        return Err(Error::configuration(
            "initial positions, target, and dense mass dimensions must match and be finite",
        ));
    }
    let chains = initial_positions.len();
    let total_transitions = config
        .discarded
        .checked_add(config.retained)
        .and_then(|count| count.checked_mul(chains))
        .ok_or_else(Error::overflow)?;
    if total_transitions > config.limits.max_total_transitions {
        return Err(Error::resource(
            "transition count exceeds its resource limit",
        ));
    }
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        let dense_bytes = dimension
            .checked_mul(dimension)
            .and_then(|x| x.checked_mul(size_of::<f64>() * 6))
            .ok_or_else(Error::overflow)?;
        if dense_bytes > config.limits.max_working_bytes {
            return Err(Error::resource(
                "dense adaptation workspace exceeds its resource limit",
            ));
        }
    }
    let worst_case_target_evaluations = config
        .worst_case_target_evaluations(NonZeroUsize::new(chains).ok_or_else(Error::overflow)?)?;
    if worst_case_target_evaluations > admission_limit.maximum() {
        return Err(Error::resource(
            "worst-case target evaluations exceed the explicit admission ceiling",
        ));
    }
    Ok(PreflightReport {
        dimension,
        chains,
        total_transitions,
        worst_case_target_evaluations,
        admission_ceiling: admission_limit.maximum(),
    })
}

fn map_stop(stop: TransitionStop) -> StopReason {
    match stop {
        TransitionStop::MaxDepth => StopReason::MaximumDepth,
        TransitionStop::OuterUTurn => StopReason::OuterUTurn,
        TransitionStop::Recursive(SpanStop::UTurn) => StopReason::RecursiveUTurn,
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted)) => {
            StopReason::RefinementExhausted
        }
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::ReverseCoarserAccepted)) => {
            StopReason::ReverseCoarserAccepted
        }
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::InvalidEvaluation)) => {
            StopReason::InvalidEvaluation
        }
    }
}

/// Execute a reasonable-step search from an already evaluated position.
///
/// `input.rho` is the first probe momentum. Remaining probe momenta are drawn
/// once from `rng` and reused at every candidate step. Thus the search neither
/// re-evaluates the initial position nor changes its random consumption when
/// the number of candidate steps changes.
#[allow(clippy::too_many_arguments)]
fn search_step_from_evaluated<T: Target>(
    target: &T,
    input: EvaluatedTransitionInput,
    mass: &dyn MassOperator,
    tuning: KernelTuning,
    target_acceptance: f64,
    config: &InitialStepSearchConfig,
    rng: &mut SmallRng,
    control: &ExecutionControl<'_>,
    transition: usize,
    discarded: bool,
    work: &mut WorkTotals,
) -> Result<(f64, InitialStepSearchTelemetry), Error> {
    if input.theta.len() != mass.dimension()
        || input.rho.len() != mass.dimension()
        || input.grad.len() != mass.dimension()
        || !input.log_prob.is_finite()
        || input.theta.iter().any(|x| !x.is_finite())
        || input.rho.iter().any(|x| !x.is_finite())
        || input.grad.iter().any(|x| !x.is_finite())
        || !mass.is_valid()
    {
        return Err(Error::configuration(
            "cached step-search state and mass must be finite and dimensionally compatible",
        ));
    }
    let mut momenta = Vec::with_capacity(config.probes);
    momenta.push(input.rho);
    for _ in 1..config.probes {
        control.check().map_err(control_error)?;
        momenta.push(mass.sample_momentum(rng).map_err(Error::internal)?);
    }
    work.momentum_refreshes = work
        .momentum_refreshes
        .checked_add(config.probes)
        .ok_or_else(Error::overflow)?;
    work.standard_normal_components = work
        .standard_normal_components
        .checked_add(
            mass.dimension()
                .checked_mul(config.probes)
                .ok_or_else(Error::overflow)?,
        )
        .ok_or_else(Error::overflow)?;

    let mut telemetry = InitialStepSearchTelemetry {
        probes: config.probes,
        initial_step: tuning.step_size,
        selected_step: tuning.step_size,
        ..InitialStepSearchTelemetry::default()
    };
    let mut adequate = None;
    let mut inadequate = None;
    let mut smallest_tried = tuning.step_size;
    let mut observed_phase_calls = [0usize; 3];

    'search: for search_index in 0..config.max_steps {
        let step = match (adequate, inadequate, search_index) {
            (Some(lo), Some(hi), _) => ((f64::ln(lo) + f64::ln(hi)) * 0.5).exp(),
            (_, _, 0) => tuning.step_size,
            (None, Some(hi), _) => hi * 0.25,
            (Some(lo), None, _) => lo * 4.0,
            _ => unreachable!(),
        };
        if !step.is_finite() || step <= 0.0 {
            break;
        }
        smallest_tried = smallest_tried.min(step);
        let mut sum = 0.0;
        let mut all_coarsest_accepted = true;
        for momentum in &momenta {
            control.check().map_err(control_error)?;
            if telemetry.target_calls >= config.max_target_calls {
                break 'search;
            }
            let state = State {
                theta: input.theta.clone(),
                rho: momentum.clone(),
                log_prob: input.log_prob,
                grad: input.grad.clone(),
            };
            let mut fatal = None;
            let mut malformed = false;
            let mut stopped = None;
            let mut observer_panicked = false;
            let mut budget_exhausted = false;
            let mut eval = |theta: &[f64]| {
                let context = take_evaluation_context();
                let phase_index = match context.map(|x| x.phase).unwrap_or(EvaluationPhase::Initial)
                {
                    EvaluationPhase::Initial => 0,
                    EvaluationPhase::Forward => 1,
                    EvaluationPhase::Reverse => 2,
                };
                if telemetry.target_calls >= config.max_target_calls {
                    budget_exhausted = true;
                    return (f64::NAN, vec![f64::NAN; mass.dimension()]);
                }
                telemetry.target_calls += 1;
                observed_phase_calls[phase_index] += 1;
                let mut gradient = vec![f64::NAN; mass.dimension()];
                if let Err(stop) = control.check() {
                    stopped = Some(stop);
                    return (f64::NAN, gradient);
                }
                if theta.len() != mass.dimension() || theta.iter().any(|value| !value.is_finite()) {
                    malformed = true;
                    return (f64::NAN, gradient);
                }
                let evaluated = catch_unwind(AssertUnwindSafe(|| {
                    target.log_density_gradient(theta, &mut gradient)
                }));
                let (log_density, outcome) = match evaluated {
                    Ok(Ok(log_density))
                        if log_density.is_finite()
                            && gradient.iter().all(|value| value.is_finite()) =>
                    {
                        (log_density, ProposalTargetOutcome::Finite)
                    }
                    Ok(Ok(_)) => {
                        malformed = true;
                        (f64::NAN, ProposalTargetOutcome::Nonfinite)
                    }
                    Ok(Err(error)) if error.kind == TargetErrorKind::Recoverable => {
                        telemetry.recoverable_target_failures += 1;
                        gradient.fill(0.0);
                        (f64::NEG_INFINITY, ProposalTargetOutcome::Recoverable)
                    }
                    Ok(Err(error)) => {
                        fatal = Some(error);
                        (f64::NAN, ProposalTargetOutcome::Fatal)
                    }
                    Err(_) => {
                        fatal = Some(TargetError::new("target callback panicked"));
                        (f64::NAN, ProposalTargetOutcome::Panicked)
                    }
                };
                if emit_proposal_observation(
                    control,
                    ObservationInput {
                        transition,
                        discarded,
                        context,
                        theta,
                        log_density: log_density.is_finite().then_some(log_density),
                        outcome,
                        target_call: telemetry.target_calls,
                        phase_target_call: observed_phase_calls[phase_index],
                    },
                )
                .is_err()
                {
                    observer_panicked = true;
                    return (f64::NAN, gradient);
                }
                (log_density, gradient)
            };
            let result = macro_leaf(
                &state,
                mass,
                FixedTuning {
                    step_size: step,
                    max_refinement_levels: 1,
                    min_micro_steps: tuning.min_micro_steps,
                    max_error: tuning.max_error,
                    divergence_threshold: tuning.divergence_threshold,
                },
                Direction::Forward,
                &mut eval,
            );
            if let Some(stop) = stopped {
                return Err(control_error(stop));
            }
            if observer_panicked {
                return Err(Error::new(ErrorKind::Panic, "proposal observer panicked"));
            }
            if let Some(source) = fatal {
                let kind = if source.message() == "target callback panicked" {
                    ErrorKind::Panic
                } else {
                    ErrorKind::Target
                };
                return Err(Error {
                    kind,
                    message: "target evaluation failed during step search".into(),
                    chain: None,
                    transition: Some(transition),
                    target_source: Some(source),
                });
            }
            if malformed {
                return Err(Error::new(
                    ErrorKind::Target,
                    "target returned a nonfinite value during step search",
                ));
            }
            let result = result.map_err(Error::internal)?;
            telemetry.micro_steps = telemetry
                .micro_steps
                .checked_add(result.forward_evaluations + result.reverse_evaluations)
                .ok_or_else(Error::overflow)?;
            all_coarsest_accepted &= result.rejection.is_none();
            sum += result.adaptation_value;
            if budget_exhausted {
                break 'search;
            }
        }
        telemetry.steps += 1;
        if all_coarsest_accepted && sum / config.probes as f64 >= target_acceptance {
            adequate = Some(step);
            telemetry.selected_step = step;
        } else {
            inadequate = Some(step);
        }
        if adequate.is_some() && inadequate.is_some() {
            break;
        }
    }
    work.target_calls_forward = work
        .target_calls_forward
        .checked_add(observed_phase_calls[1])
        .ok_or_else(Error::overflow)?;
    work.target_calls_reverse = work
        .target_calls_reverse
        .checked_add(observed_phase_calls[2])
        .ok_or_else(Error::overflow)?;
    work.forward_micro_steps_executed = work
        .forward_micro_steps_executed
        .checked_add(observed_phase_calls[1])
        .ok_or_else(Error::overflow)?;
    work.reverse_micro_steps_executed = work
        .reverse_micro_steps_executed
        .checked_add(observed_phase_calls[2])
        .ok_or_else(Error::overflow)?;
    work.recoverable_target_failures = work
        .recoverable_target_failures
        .checked_add(telemetry.recoverable_target_failures)
        .ok_or_else(Error::overflow)?;
    let selected = adequate.unwrap_or(smallest_tried);
    telemetry.selected_step = selected;
    Ok((selected, telemetry))
}

#[allow(clippy::too_many_arguments)]
fn search_initial_step<T: Target>(
    target: &T,
    position: &[f64],
    mass: &DiagonalMass,
    inverse_mass: &[f64],
    tuning: KernelTuning,
    target_acceptance: f64,
    config: &InitialStepSearchConfig,
    seed: u64,
    control: &ExecutionControl<'_>,
) -> Result<(f64, InitialStepSearchTelemetry), Error> {
    let mut probe_rng = SmallRng::seed_from_u64(seed ^ 0x69d2_343f_d15e_a5b9);
    let mut momenta = Vec::with_capacity(config.probes);
    for _ in 0..config.probes {
        let mut momentum = Vec::with_capacity(position.len());
        for value in mass.diagonal() {
            let normal: f64 = StandardNormal.sample(&mut probe_rng);
            momentum.push(normal * value.sqrt());
        }
        momenta.push(momentum);
    }

    let mut telemetry = InitialStepSearchTelemetry {
        probes: config.probes,
        initial_step: tuning.step_size,
        selected_step: tuning.step_size,
        ..InitialStepSearchTelemetry::default()
    };
    // Search for the largest observed step that is both accepted at the
    // coarsest level and meets the requested acceptance rate.  Refinement must
    // not make an over-large macro step look suitable for adaptation.
    let mut adequate: Option<f64> = None;
    let mut inadequate: Option<f64> = None;
    let mut smallest_tried = tuning.step_size;

    for search_step in 0..config.max_steps {
        let step = match (adequate, inadequate, search_step) {
            (Some(lo), Some(hi), _) => ((lo.ln() + hi.ln()) * 0.5).exp(),
            (_, _, 0) => tuning.step_size,
            (None, Some(hi), _) => hi * 0.25,
            (Some(lo), None, _) => lo * 4.0,
            _ => unreachable!(),
        };
        if !step.is_finite() || step <= 0.0 {
            break;
        }
        smallest_tried = smallest_tried.min(step);

        let mut sum = 0.0;
        let mut all_coarsest_accepted = true;
        for momentum in &momenta {
            control.check().map_err(control_error)?;
            if telemetry.target_calls >= config.max_target_calls {
                let selected = adequate.unwrap_or(smallest_tried);
                telemetry.selected_step = selected;
                return Ok((selected, telemetry));
            }
            let mut gradient = vec![f64::NAN; position.len()];
            let log_prob = target
                .log_density_gradient(position, &mut gradient)
                .map_err(|source| Error {
                    kind: ErrorKind::Target,
                    message: if source.kind == TargetErrorKind::Recoverable {
                        "current position is not evaluable during initial-step search".into()
                    } else {
                        "target evaluation failed during initial-step search".into()
                    },
                    chain: None,
                    transition: None,
                    target_source: Some(source),
                })?;
            telemetry.target_calls += 1;
            if !log_prob.is_finite() || gradient.iter().any(|value| !value.is_finite()) {
                return Err(Error::new(
                    ErrorKind::Target,
                    "target returned a nonfinite value during initial-step search",
                ));
            }
            let state = State {
                theta: position.to_vec(),
                rho: momentum.clone(),
                log_prob,
                grad: gradient,
            };
            let mut target_failure = None;
            let mut malformed_target_output = false;
            let mut eval = |theta: &[f64]| {
                if telemetry.target_calls >= config.max_target_calls
                    || theta.iter().any(|value| !value.is_finite())
                {
                    return (f64::NAN, vec![f64::NAN; theta.len()]);
                }
                let mut gradient = vec![f64::NAN; theta.len()];
                telemetry.target_calls += 1;
                match target.log_density_gradient(theta, &mut gradient) {
                    Ok(log_prob)
                        if log_prob.is_finite()
                            && gradient.iter().all(|value| value.is_finite()) =>
                    {
                        (log_prob, gradient)
                    }
                    Ok(_) => {
                        malformed_target_output = true;
                        (f64::NAN, gradient)
                    }
                    Err(error) if error.kind == TargetErrorKind::Recoverable => {
                        telemetry.recoverable_target_failures += 1;
                        // Upstream semantics: a failed evaluation is a
                        // zero-density point with a zero gradient.
                        (f64::NEG_INFINITY, vec![0.0; theta.len()])
                    }
                    Err(error) => {
                        target_failure = Some(error);
                        (f64::NAN, gradient)
                    }
                }
            };
            let result = macro_leaf(
                &state,
                inverse_mass,
                FixedTuning {
                    step_size: step,
                    max_refinement_levels: 1,
                    min_micro_steps: tuning.min_micro_steps,
                    max_error: tuning.max_error,
                    divergence_threshold: tuning.divergence_threshold,
                },
                Direction::Forward,
                &mut eval,
            );
            if let Some(source) = target_failure {
                return Err(Error {
                    kind: ErrorKind::Target,
                    message: "target evaluation failed during initial-step search".into(),
                    chain: None,
                    transition: None,
                    target_source: Some(source),
                });
            }
            let result = result.map_err(Error::internal)?;
            if malformed_target_output {
                return Err(Error::new(
                    ErrorKind::Target,
                    "target returned a nonfinite value during initial-step search",
                ));
            }
            telemetry.micro_steps = telemetry
                .micro_steps
                .checked_add(result.forward_evaluations + result.reverse_evaluations)
                .ok_or_else(Error::overflow)?;
            all_coarsest_accepted &= result.rejection.is_none();
            sum += result.adaptation_value;
        }
        telemetry.steps += 1;
        let signal = sum / config.probes as f64;
        if all_coarsest_accepted && signal >= target_acceptance {
            adequate = Some(step);
            telemetry.selected_step = step;
        } else {
            inadequate = Some(step);
        }

        // A bracket is sufficient: use its adequate (smaller, conservative)
        // endpoint. Further noisy bisection only creates chain instability.
        if adequate.is_some() && inadequate.is_some() {
            break;
        }
    }
    // If the configured search budget cannot find an adequate endpoint, retain
    // the smallest tried step rather than an inadequate initial one.
    let selected = adequate.unwrap_or(smallest_tried);
    telemetry.selected_step = selected;
    Ok((selected, telemetry))
}

struct PersistentChainContext {
    rng: SmallRng,
    cached_state: Option<SelectedState>,
}

impl PersistentChainContext {
    fn new(seed: u64) -> Self {
        Self {
            rng: SmallRng::seed_from_u64(seed),
            cached_state: None,
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn run_chain<T: Target>(
    target: &T,
    dimension: usize,
    initial_position: &[f64],
    mass: &DiagonalMass,
    fixed_mass: Option<&dyn MassOperator>,
    direct_boundary_hook: bool,
    config: &RunConfig,
    seed: u64,
    thread_count: usize,
    control: &ExecutionControl<'_>,
    shared_initial_step_search: Option<&(f64, InitialStepSearchTelemetry)>,
    persistent: Option<&mut PersistentChainContext>,
) -> Result<ChainOutput, Error> {
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let initial_mass = mass.diagonal.clone();
    let mut active_mass = mass.clone();
    let mut inverse_mass = inverse_mass(&active_mass)?;
    let mut active_tuning = config.tuning;
    let schedule = config
        .warmup
        .as_ref()
        .map(|warmup| warmup_schedule(config.discarded, &warmup.windows))
        .transpose()?;
    let initial_step_search = if let Some((step, telemetry)) = shared_initial_step_search {
        active_tuning.step_size = *step;
        Some(telemetry.clone())
    } else if let Some((warmup, search)) = config.warmup.as_ref().and_then(|warmup| {
        warmup
            .initial_step_search
            .as_ref()
            .map(|search| (warmup, search))
    }) {
        let (step, telemetry) = search_initial_step(
            target,
            initial_position,
            &active_mass,
            &inverse_mass,
            active_tuning,
            warmup.target_acceptance,
            search,
            seed,
            control,
        )?;
        active_tuning.step_size = step;
        Some(telemetry)
    } else {
        None
    };
    let mut dual_averaging = config
        .warmup
        .as_ref()
        .filter(|warmup| warmup.adapt_step_size)
        .map(|warmup| DualAveraging::new(active_tuning.step_size, step_adaptation_target(warmup)));
    let mut variance = DiagonalVariance::new(dimension);
    let mut paper_window = PaperWindow::new();
    let sample_len = config
        .retained
        .checked_mul(dimension)
        .ok_or_else(Error::overflow)?;
    let mut samples = Vec::new();
    samples
        .try_reserve_exact(sample_len)
        .map_err(|_| Error::resource("sample allocation failed"))?;
    let mut diagnostics = Vec::new();
    diagnostics
        .try_reserve_exact(transitions)
        .map_err(|_| Error::resource("diagnostics allocation failed"))?;

    let mut local_rng = SmallRng::seed_from_u64(seed);
    let mut local_cache = None;
    let use_persistent_cache = persistent.is_some();
    let (rng, cached_state) = match persistent {
        Some(context) => (&mut context.rng, &mut context.cached_state),
        None => (&mut local_rng, &mut local_cache),
    };
    let mut position = cached_state
        .as_ref()
        .map_or_else(|| initial_position.to_vec(), |state| state.theta.clone());
    let mut telemetry = RunTelemetry {
        initial_step_search: initial_step_search.clone(),
        step_searches: initial_step_search
            .clone()
            .map(|search| {
                vec![StepSearchEvent {
                    reason: StepSearchReason::Initial,
                    search,
                }]
            })
            .unwrap_or_default(),
        warmup_checkpoints: Vec::with_capacity(
            config
                .warmup
                .as_ref()
                .map_or(0, |warmup| warmup.warmup_telemetry_checkpoints.len()),
        ),
        ..RunTelemetry::default()
    };
    for transition_index in 0..transitions {
        let step_before_transition = active_tuning.step_size;
        control
            .check()
            .map_err(control_error)
            .map_err(|error| error.at_transition(transition_index))?;
        let momentum = if let Some(operator) = fixed_mass {
            operator
                .sample_momentum(&mut *rng)
                .map_err(Error::internal)
                .map_err(|error| error.at_transition(transition_index))?
        } else {
            let mut momentum = Vec::new();
            momentum
                .try_reserve_exact(dimension)
                .map_err(|_| Error::resource("momentum allocation failed"))?;
            for (mass_value, inverse_mass_value) in active_mass.diagonal().iter().zip(&inverse_mass)
            {
                let normal: f64 = StandardNormal.sample(&mut *rng);
                let mass_scale = mass_value.sqrt();
                if !normal.is_finite()
                    || normal.abs() > f64::MAX / mass_scale
                    || normal.abs() * mass_scale > f64::MAX.sqrt()
                {
                    return Err(Error::new(
                        ErrorKind::Numerical,
                        "momentum refresh is not safely representable",
                    )
                    .at_transition(transition_index));
                }
                let value = normal * mass_scale;
                let square = value * value;
                if square > f64::MAX / inverse_mass_value {
                    return Err(Error::new(
                        ErrorKind::Numerical,
                        "momentum kinetic energy is not safely representable",
                    )
                    .at_transition(transition_index));
                }
                momentum.push(value);
            }
            momentum
        };
        let transition_mass: &dyn MassOperator = fixed_mass.unwrap_or(&inverse_mass);

        let mut target_failure = None;
        let mut numerical_failure = false;
        let mut control_failure = None;
        let mut target_panic = false;
        let mut observer_panic = false;
        let mut recoverable_target_failure = None;
        let mut recoverable_target_failures = 0usize;
        let mut observed_target_calls = 0usize;
        let mut observed_phase_calls = [0usize; 3];
        let mut eval = |theta: &[f64]| {
            let context = take_evaluation_context();
            observed_target_calls = observed_target_calls.saturating_add(1);
            let phase_index = match context.map(|x| x.phase).unwrap_or(EvaluationPhase::Initial) {
                EvaluationPhase::Initial => 0,
                EvaluationPhase::Forward => 1,
                EvaluationPhase::Reverse => 2,
            };
            observed_phase_calls[phase_index] = observed_phase_calls[phase_index].saturating_add(1);
            macro_rules! observe {
                ($outcome:expr,$log:expr,$gradient:ident) => {
                    if emit_proposal_observation(
                        control,
                        ObservationInput {
                            transition: transition_index,
                            discarded: transition_index < config.discarded,
                            context,
                            theta,
                            log_density: $log,
                            outcome: $outcome,
                            target_call: observed_target_calls,
                            phase_target_call: observed_phase_calls[phase_index],
                        },
                    )
                    .is_err()
                    {
                        observer_panic = true;
                        $gradient.fill(f64::NAN);
                    }
                };
            }
            let mut gradient = vec![f64::NAN; dimension];
            if observer_panic {
                return (f64::NAN, gradient);
            }
            if let Err(stop) = control.check() {
                control_failure = Some(stop);
                return (f64::NAN, gradient);
            }
            if theta.len() != dimension || theta.iter().any(|value| !value.is_finite()) {
                numerical_failure = true;
                observe!(ProposalTargetOutcome::KernelNonfinite, None, gradient);
                return (f64::NAN, gradient);
            }
            let evaluated = catch_unwind(AssertUnwindSafe(|| {
                target.log_density_gradient(theta, &mut gradient)
            }));
            if let Err(stop) = control.check() {
                control_failure = Some(stop);
                return (f64::NAN, gradient);
            }
            let evaluated = match evaluated {
                Ok(value) => value,
                Err(_) => {
                    target_panic = true;
                    observe!(ProposalTargetOutcome::Panicked, None, gradient);
                    return (f64::NAN, gradient);
                }
            };
            match evaluated {
                Ok(log_density)
                    if log_density.is_finite()
                        && gradient.iter().all(|value| value.is_finite()) =>
                {
                    observe!(ProposalTargetOutcome::Finite, Some(log_density), gradient);
                    (log_density, gradient)
                }
                Ok(_) => {
                    target_failure = Some(TargetError::new("target returned a nonfinite value"));
                    observe!(ProposalTargetOutcome::Nonfinite, None, gradient);
                    (f64::NAN, gradient)
                }
                Err(error) if error.kind == TargetErrorKind::Recoverable => {
                    recoverable_target_failures += 1;
                    recoverable_target_failure = Some(error);
                    observe!(ProposalTargetOutcome::Recoverable, None, gradient);
                    // Upstream semantics (`walnutpie/util.hpp`): a failed
                    // evaluation is a zero-density point with a zero
                    // gradient. The kernel refines through it instead of
                    // stopping the transition.
                    gradient.fill(0.0);
                    (f64::NEG_INFINITY, gradient)
                }
                Err(error) => {
                    target_failure = Some(error);
                    observe!(ProposalTargetOutcome::Fatal, None, gradient);
                    (f64::NAN, gradient)
                }
            }
        };
        let mut rng_stop = None;
        let (result, work, acceptance, current_summary, accepted_summary, final_uturn) =
            {
                let mut kernel_rng = KernelRng {
                    rng,
                    control,
                    stopped: &mut rng_stop,
                };
                let cached_input = use_persistent_cache
                    .then_some(cached_state.as_ref())
                    .flatten()
                    .map(|state| EvaluatedTransitionInput {
                        theta: position.clone(),
                        rho: momentum.clone(),
                        log_prob: state.log_prob,
                        grad: state.grad.clone(),
                    });
                let input = TransitionInput {
                    theta: position,
                    rho: momentum,
                };
                if (config.warmup.is_some() && transition_index < config.discarded)
                    || config.capture_acceptance
                {
                    let traced = if let Some(cached) = cached_input {
                        transition_w_from_evaluated_traced_with_telemetry_and_outer_policy(
                            &mut kernel_rng,
                            cached,
                            transition_mass,
                            active_tuning.transition_tuning(),
                            &mut eval,
                            config.outer_orbit_selection.into(),
                        )
                    } else {
                        transition_w_traced_with_telemetry_and_outer_policy(
                            &mut kernel_rng,
                            input,
                            transition_mass,
                            active_tuning.transition_tuning(),
                            &mut eval,
                            config.outer_orbit_selection.into(),
                        )
                    };
                    match traced {
                        Ok(output) => {
                            let current_summary = acceptance_summary(
                                output
                                    .events
                                    .iter()
                                    .filter_map(|event| event.adaptation_value),
                            );
                            let accepted_summary =
                                acceptance_summary(output.events.iter().filter_map(|event| {
                                    event.accepted_trajectory_adaptation_value
                                }));
                            let adaptation = match config
                                .warmup
                                .as_ref()
                                .map(|warmup| warmup.dual_averaging_acceptance)
                            {
                                Some(DualAveragingAcceptance::AcceptedTrajectory) => {
                                    accepted_summary.mean
                                }
                                _ => current_summary.mean,
                            };
                            let final_uturn = output
                                .events
                                .iter()
                                .rev()
                                .find(|event| event.event == "outer_uturn_predicate")
                                .map(|event| (event.forward_dot, event.backward_dot));
                            (
                                Ok(output.result),
                                Some(output.work),
                                adaptation,
                                current_summary,
                                accepted_summary,
                                final_uturn,
                            )
                        }
                        Err(error) => (
                            Err(error),
                            None,
                            None,
                            AcceptanceStatisticSummary::default(),
                            AcceptanceStatisticSummary::default(),
                            None,
                        ),
                    }
                } else {
                    let transitioned = if let Some(cached) = cached_input {
                        transition_w_from_evaluated_with_telemetry_and_outer_policy(
                            &mut kernel_rng,
                            cached,
                            transition_mass,
                            active_tuning.transition_tuning(),
                            &mut eval,
                            config.outer_orbit_selection.into(),
                        )
                    } else {
                        transition_w_with_telemetry_and_outer_policy(
                            &mut kernel_rng,
                            input,
                            transition_mass,
                            active_tuning.transition_tuning(),
                            &mut eval,
                            config.outer_orbit_selection.into(),
                        )
                    };
                    match transitioned {
                        Ok(output) => (
                            Ok(output.result),
                            Some(output.work),
                            None,
                            AcceptanceStatisticSummary::default(),
                            AcceptanceStatisticSummary::default(),
                            None,
                        ),
                        Err(error) => (
                            Err(error),
                            None,
                            None,
                            AcceptanceStatisticSummary::default(),
                            AcceptanceStatisticSummary::default(),
                            None,
                        ),
                    }
                }
            };
        if control_failure.is_none()
            && rng_stop.is_none()
            && let Err(stop) = control.check()
        {
            control_failure = Some(stop);
        }
        if let Some(stop) = control_failure.or(rng_stop) {
            return Err(control_error(stop).at_transition(transition_index));
        }
        if observer_panic {
            return Err(Error::new(ErrorKind::Panic, "proposal observer panicked")
                .at_transition(transition_index));
        }
        if target_panic {
            return Err(Error::new(ErrorKind::Panic, "target callback panicked")
                .at_transition(transition_index));
        }
        if let Some(source) = target_failure {
            return Err(Error {
                kind: ErrorKind::Target,
                message: "target evaluation failed".into(),
                chain: None,
                transition: Some(transition_index),
                target_source: Some(source),
            });
        }
        if numerical_failure {
            return Err(Error::new(
                ErrorKind::Numerical,
                "kernel attempted a nonfinite target position",
            )
            .at_transition(transition_index));
        }
        if result.is_err() && recoverable_target_failures != 0 {
            return Err(Error {
                kind: ErrorKind::Target,
                message: "current position is not evaluable".into(),
                chain: None,
                transition: Some(transition_index),
                target_source: recoverable_target_failure,
            });
        }
        let result = result
            .map_err(Error::internal)
            .map_err(|error| error.at_transition(transition_index))?;
        let work =
            work.ok_or_else(|| Error::new(ErrorKind::Internal, "missing transition work"))?;
        let unrefined_fraction = unrefined_leaf_fraction(&work);
        if use_persistent_cache {
            *cached_state = Some(result.selected.clone());
        }
        position = result.selected.theta;
        let internal = result.diagnostics;
        let public = TransitionDiagnostics {
            depth: internal.depth,
            stop: map_stop(internal.stop),
            target_evaluations: internal.target_evaluations,
            direction_draws: internal.direction_draws,
            uniform_draws: internal.uniform_draws,
            leaves_attempted: internal.leaves_attempted,
            leaves_built: internal.leaves_built,
            recoverable_target_failures,
            zero_density_evaluations: internal.zero_density_evaluations,
            initial_hamiltonian: internal.initial_hamiltonian,
            minimum_hamiltonian: internal.minimum_hamiltonian,
            maximum_hamiltonian: internal.maximum_hamiltonian,
            maximum_absolute_energy_error: internal.maximum_absolute_energy_error,
            divergent: internal.divergent,
            selected_refinement_level: internal.selected_refinement_level,
            refinement_attempts: internal.refinement_attempts,
            reverse_coarser_rejections: internal.reverse_coarser_rejections,
            final_uturn_forward_dot: final_uturn.and_then(|value| value.0),
            final_uturn_backward_dot: final_uturn.and_then(|value| value.1),
            trajectory_macro_length: internal.leaves_built as f64 * step_before_transition,
        };
        let partition = if transition_index < config.discarded {
            &mut telemetry.discarded
        } else {
            samples.extend_from_slice(&position);
            &mut telemetry.retained
        };
        partition.add_transition(
            dimension,
            &work,
            internal.uniform_draws,
            recoverable_target_failures,
            &internal,
        )?;
        telemetry.total.add_transition(
            dimension,
            &work,
            internal.uniform_draws,
            recoverable_target_failures,
            &internal,
        )?;
        if transition_index < config.discarded
            && let Some(schedule) = &schedule
        {
            let phase = schedule
                .phase_at(transition_index)
                .expect("discarded transition has a warmup phase");
            let phase_work = match phase {
                WarmupPhase::InitialFast => &mut telemetry.initial_fast,
                WarmupPhase::SlowWindow => &mut telemetry.slow,
                WarmupPhase::TerminalFast => &mut telemetry.terminal_fast,
            };
            phase_work.add_transition(
                dimension,
                &work,
                internal.uniform_draws,
                recoverable_target_failures,
                &internal,
            )?;
        }
        if telemetry.total.maximum_depth_stops > config.max_maximum_depth_stops {
            return Err(Error::new(
                ErrorKind::Unhealthy,
                "maximum-depth stop limit was exceeded",
            )
            .at_transition(transition_index));
        }
        diagnostics.push(public);
        if direct_boundary_hook
            && transition_index < config.discarded
            && (transition_index + 1 == config.discarded
                || schedule.as_ref().is_some_and(|schedule| {
                    schedule
                        .windows
                        .iter()
                        .any(|window| window.end == transition_index + 1)
                }))
        {
            // Version-one installation seam: retaining the same immutable
            // operator is deliberately a no-op and consumes no RNG/work.
            debug_assert!(fixed_mass.is_some());
        }
        if config.capture_acceptance {
            telemetry.acceptance_values.push(acceptance);
        }

        if transition_index < config.discarded
            && let Some(warmup) = &config.warmup
        {
            let window_index = schedule.as_ref().and_then(|schedule| {
                schedule.windows.iter().position(|window| {
                    transition_index >= window.start && transition_index < window.end
                })
            });
            if warmup.adapt_mass && window_index.is_some() {
                variance.update(&position);
            }
            let step_statistic = if let Some(paper) = warmup.paper_adaptation.as_ref() {
                paper_window.step_statistic(paper.step_statistic, unrefined_fraction)
            } else {
                acceptance
            };
            if warmup.adapt_step_size
                && let (Some(dual), Some(statistic)) = (&mut dual_averaging, step_statistic)
            {
                active_tuning.step_size = dual.update(statistic);
                if warmup.paper_adaptation.is_some() {
                    active_tuning.step_size =
                        clamp_paper_step(active_tuning.step_size, config.tuning.step_size);
                }
            }
            if warmup.adapt_mass
                && let Some(window_index) = window_index
                && schedule.as_ref().expect("warmup schedule").windows[window_index].end
                    == transition_index + 1
            {
                let sample_count = variance.count;
                let step_before = active_tuning.step_size;
                let mut update = MetricUpdateTelemetry {
                    window_index,
                    transition: transition_index,
                    sample_count,
                    outcome: MetricUpdateOutcome::InsufficientSamples,
                    mass_diagonal: None,
                    mass_dense: None,
                    shrinkage: 0.0,
                    ridge: 0.0,
                    condition_estimate: None,
                    cholesky_failures: 0,
                    step_before,
                    step_after_search: None,
                    mass_diagonal_before: Some(active_mass.diagonal.clone()),
                    mass_dense_before: None,
                    step_after_restart: None,
                    restart_reference_multiplier: None,
                    dual_averaging_after_restart: None,
                };
                if let Some(diagonal) = variance.regularized_mass() {
                    // Build and validate both candidates before changing either
                    // half of the active metric pair.
                    let candidate_mass = DiagonalMass::from_diagonal(diagonal)?;
                    let candidate_inverse = self::inverse_mass(&candidate_mass)?;
                    active_mass = candidate_mass;
                    inverse_mass = candidate_inverse;
                    update.outcome = MetricUpdateOutcome::Installed;
                    update.mass_diagonal = Some(active_mass.diagonal.clone());

                    let is_final = transition_index + 1 == config.discarded;
                    if warmup.adapt_step_size && !is_final {
                        if let Some(search) = &warmup.initial_step_search {
                            let event_index = telemetry.step_searches.len();
                            let (step, search_telemetry) = search_initial_step(
                                target,
                                &position,
                                &active_mass,
                                &inverse_mass,
                                active_tuning,
                                warmup.target_acceptance,
                                search,
                                search_event_seed(seed, event_index),
                                control,
                            )
                            .map_err(|error| error.at_transition(transition_index))?;
                            active_tuning.step_size = step;
                            update.step_after_search = Some(step);
                            telemetry.step_searches.push(StepSearchEvent {
                                reason: StepSearchReason::MetricUpdate { window_index },
                                search: search_telemetry,
                            });
                        }
                        dual_averaging = Some(DualAveraging::restart(
                            active_tuning.step_size,
                            step_adaptation_target(warmup),
                            warmup.research_restart_reference_multiplier,
                        ));
                        update.step_after_restart = Some(active_tuning.step_size);
                        update.restart_reference_multiplier =
                            Some(warmup.research_restart_reference_multiplier);
                        update.dual_averaging_after_restart =
                            dual_averaging.as_ref().map(DualAveraging::telemetry);
                    }
                }
                telemetry.metric_updates.push(update);
                variance = DiagonalVariance::new(dimension);
            }
            if let Some(paper) = warmup.paper_adaptation.as_ref() {
                paper_window.record(
                    internal.maximum_hamiltonian - internal.minimum_hamiltonian,
                    unrefined_fraction,
                );
                let schedule = schedule.as_ref().expect("warmup schedule");
                let is_final = transition_index + 1 == config.discarded;
                let boundary = if transition_index + 1 == schedule.initial_fast_end {
                    Some(None)
                } else {
                    window_index
                        .filter(|index| schedule.windows[*index].end == transition_index + 1)
                        .map(Some)
                };
                if let Some(window_index) = boundary
                    && !is_final
                {
                    let step_before = active_tuning.step_size;
                    let max_error_before = active_tuning.max_error;
                    let (orbits, inflation_quantile, energy_range_quantile, candidate, outcome) =
                        paper_window.candidate(paper, max_error_before);
                    let mut dual_averaging_restarted = false;
                    if let Some(max_error) = candidate {
                        active_tuning.max_error = max_error;
                        if warmup.adapt_step_size
                            && paper.restart_policy
                                == PaperRestartPolicy::RestartOnLocalErrorInstall
                        {
                            dual_averaging = Some(DualAveraging::restart(
                                active_tuning.step_size,
                                paper.unrefined_fraction_target,
                                warmup.research_restart_reference_multiplier,
                            ));
                            dual_averaging_restarted = true;
                        }
                    }
                    telemetry
                        .paper_adaptation_updates
                        .push(PaperAdaptationUpdate {
                            transition: transition_index,
                            window_index,
                            orbits,
                            inflation_quantile,
                            energy_range_quantile,
                            max_error_before,
                            max_error_after: active_tuning.max_error,
                            unrefined_fraction_mean: paper_window.unrefined_mean(),
                            step_before,
                            step_after: active_tuning.step_size,
                            outcome,
                            step_statistic,
                            dual_averaging_restarted,
                            transitions_without_statistic: paper_window.without_statistic,
                        });
                    paper_window.reset();
                    if window_index.is_none() {
                        // End of the initial fast phase: the cumulative
                        // statistic starts afresh from the first slow window.
                        paper_window.reset_cumulative();
                    }
                }
            }
            if transition_index + 1 == config.discarded
                && let Some(dual) = &dual_averaging
            {
                active_tuning.step_size = dual.final_step();
                if warmup.paper_adaptation.is_some() {
                    active_tuning.step_size =
                        clamp_paper_step(active_tuning.step_size, config.tuning.step_size);
                }
            }
            if warmup
                .warmup_telemetry_checkpoints
                .binary_search(&transition_index)
                .is_ok()
            {
                let schedule = schedule.as_ref().expect("warmup schedule");
                telemetry
                    .warmup_checkpoints
                    .push(WarmupCheckpointTelemetry {
                        transition: transition_index,
                        phase: schedule
                            .phase_at(transition_index)
                            .expect("warmup transition has phase"),
                        window_index,
                        step_before: step_before_transition,
                        step_after: active_tuning.step_size,
                        current_coarse_endpoint: current_summary,
                        accepted_trajectory: accepted_summary,
                        dual_averaging: dual_averaging.as_ref().map(DualAveraging::telemetry),
                        target_calls: internal.target_evaluations,
                        divergent: internal.divergent,
                        refinement_attempts: internal.refinement_attempts,
                        reverse_coarser_rejections: internal.reverse_coarser_rejections,
                        unrefined_fraction,
                        max_error_after: active_tuning.max_error,
                    });
            }
        }
    }
    control.check().map_err(control_error)?;

    Ok(ChainOutput {
        samples,
        retained: config.retained,
        dimension,
        diagnostics,
        telemetry,
        metadata: RunMetadata {
            algorithm_revision: ALGORITHM_REVISION,
            crate_version: env!("CARGO_PKG_VERSION"),
            rng_implementation: "rand::rngs::SmallRng + rand_distr::StandardNormal (Cargo.lock)",
            seed_derivation: "splitmix64(base_seed + chain_index)",
            base_seed: config.seed,
            effective_seed: seed,
            dimension,
            discarded: config.discarded,
            retained: config.retained,
            maximum_depth_stop_limit: config.max_maximum_depth_stops,
            step_size: active_tuning.step_size,
            min_micro_steps: active_tuning.min_micro_steps,
            max_refinement_levels: active_tuning.max_refinement_levels,
            max_error: active_tuning.max_error,
            divergence_threshold: active_tuning.divergence_threshold,
            max_depth: active_tuning.max_depth,
            initial_position: initial_position.to_vec(),
            thread_count,
            mass_diagonal: active_mass.diagonal.clone(),
            initial_mass_diagonal: initial_mass,
            warmup: config.warmup.clone(),
            warmup_schedule: schedule,
            initial_step_search,
            tuning: active_tuning,
            initial_tuning: config.tuning,
            limits: config.limits.clone(),
            effective_max_target_evaluations: config
                .research_target_evaluation_limit
                .map_or(config.limits.max_target_evaluations, |limit| {
                    limit.max_target_evaluations
                }),
            target_evaluation_limit_provenance: if config.research_target_evaluation_limit.is_some()
            {
                TargetEvaluationLimitProvenance::ExplicitResearchOptIn
            } else if config.limits.max_target_evaluations < CONSERVATIVE_MAX_TARGET_EVALUATIONS {
                TargetEvaluationLimitProvenance::TightenedProductionLimit
            } else {
                TargetEvaluationLimitProvenance::ConservativeDefault
            },
        },
    })
}

/// Sample chain zero using the stable effective seed
/// `splitmix64(config.seed() + 0)`.
pub fn sample<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DiagonalMass,
    config: &RunConfig,
) -> Result<ChainOutput, Error> {
    sample_with_control(target, initial_position, mass, config, &RunControl::new())
}

struct DenseCoordinates<'a, T> {
    target: &'a T,
    mass: &'a DenseMass,
}

impl<T: Target> Target for DenseCoordinates<'_, T> {
    fn dimension(&self) -> usize {
        self.mass.dimension
    }

    fn log_density_gradient(
        &self,
        transformed: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let position = solve_upper(&self.mass.chol_lower, transformed, self.mass.dimension);
        let mut original_gradient = vec![f64::NAN; self.mass.dimension];
        let value = self
            .target
            .log_density_gradient(&position, &mut original_gradient)?;
        let transformed_gradient = solve_lower(
            &self.mass.chol_lower,
            &original_gradient,
            self.mass.dimension,
        );
        gradient.copy_from_slice(&transformed_gradient);
        Ok(value)
    }
}

fn multiply_lower_transpose(lower: &[f64], vector: &[f64], n: usize) -> Vec<f64> {
    (0..n)
        .map(|i| (i..n).map(|j| lower[j * n + i] * vector[j]).sum())
        .collect()
}

fn solve_lower(lower: &[f64], rhs: &[f64], n: usize) -> Vec<f64> {
    let mut result = vec![0.0; n];
    for i in 0..n {
        let sum: f64 = (0..i).map(|j| lower[i * n + j] * result[j]).sum();
        result[i] = (rhs[i] - sum) / lower[i * n + i];
    }
    result
}

fn solve_upper(lower: &[f64], rhs: &[f64], n: usize) -> Vec<f64> {
    let mut result = vec![0.0; n];
    for i in (0..n).rev() {
        let sum: f64 = (i + 1..n).map(|j| lower[j * n + i] * result[j]).sum();
        result[i] = (rhs[i] - sum) / lower[i * n + i];
    }
    result
}

fn restore_dense_coordinates(output: &mut ChainOutput, mass: &DenseMass) {
    for draw in output.samples.chunks_exact_mut(mass.dimension) {
        let restored = solve_upper(&mass.chol_lower, draw, mass.dimension);
        draw.copy_from_slice(&restored);
    }
    output.metadata.initial_position = solve_upper(
        &mass.chol_lower,
        &output.metadata.initial_position,
        mass.dimension,
    );
}

struct BlockDenseCoordinates<'a, T> {
    target: &'a T,
    mass: &'a BlockDiagonalMass,
}

fn block_solve_upper(mass: &BlockDiagonalMass, vector: &[f64]) -> Vec<f64> {
    let mut output = Vec::with_capacity(mass.dimension);
    for (block, bounds) in mass.blocks.iter().zip(mass.offsets.windows(2)) {
        output.extend(solve_upper(
            &block.chol_lower,
            &vector[bounds[0]..bounds[1]],
            block.dimension,
        ));
    }
    output
}

fn block_solve_lower(mass: &BlockDiagonalMass, vector: &[f64]) -> Vec<f64> {
    let mut output = Vec::with_capacity(mass.dimension);
    for (block, bounds) in mass.blocks.iter().zip(mass.offsets.windows(2)) {
        output.extend(solve_lower(
            &block.chol_lower,
            &vector[bounds[0]..bounds[1]],
            block.dimension,
        ));
    }
    output
}

fn block_multiply_lower_transpose(mass: &BlockDiagonalMass, vector: &[f64]) -> Vec<f64> {
    let mut output = Vec::with_capacity(mass.dimension);
    for (block, bounds) in mass.blocks.iter().zip(mass.offsets.windows(2)) {
        output.extend(multiply_lower_transpose(
            &block.chol_lower,
            &vector[bounds[0]..bounds[1]],
            block.dimension,
        ));
    }
    output
}

impl<T: Target> Target for BlockDenseCoordinates<'_, T> {
    fn dimension(&self) -> usize {
        self.mass.dimension
    }
    fn log_density_gradient(
        &self,
        transformed: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let position = block_solve_upper(self.mass, transformed);
        let mut original_gradient = vec![f64::NAN; self.mass.dimension];
        let value = self
            .target
            .log_density_gradient(&position, &mut original_gradient)?;
        gradient.copy_from_slice(&block_solve_lower(self.mass, &original_gradient));
        Ok(value)
    }
}

fn restore_block_coordinates(output: &mut ChainOutput, mass: &BlockDiagonalMass) {
    for draw in output.samples.chunks_exact_mut(mass.dimension) {
        let restored = block_solve_upper(mass, draw);
        draw.copy_from_slice(&restored);
    }
    output.metadata.initial_position = block_solve_upper(mass, &output.metadata.initial_position);
}

struct StructuredCoordinates<'a, T> {
    target: &'a T,
    mass: &'a StructuredBlockMass,
}
fn structured_map(
    mass: &StructuredBlockMass,
    vector: &[f64],
    operation: fn(&StructuredCovarianceBlock, &[f64]) -> Vec<f64>,
) -> Vec<f64> {
    let mut out = Vec::with_capacity(mass.dimension);
    for (block, bounds) in mass.blocks.iter().zip(mass.offsets.windows(2)) {
        out.extend(operation(block, &vector[bounds[0]..bounds[1]]));
    }
    out
}
impl<T: Target> Target for StructuredCoordinates<'_, T> {
    fn dimension(&self) -> usize {
        self.mass.dimension
    }
    fn log_density_gradient(
        &self,
        transformed: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let position = structured_map(
            self.mass,
            transformed,
            StructuredCovarianceBlock::solve_upper,
        );
        let mut original = vec![f64::NAN; self.mass.dimension];
        let value = self.target.log_density_gradient(&position, &mut original)?;
        gradient.copy_from_slice(&structured_map(
            self.mass,
            &original,
            StructuredCovarianceBlock::solve_lower,
        ));
        Ok(value)
    }
}

pub fn sample_chains_structured<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &StructuredBlockMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    if config.warmup.as_ref().is_some_and(|w| w.adapt_mass) {
        return Err(Error::configuration(
            "structured mass adaptation is unsupported",
        ));
    }
    let transformed: Vec<Vec<f64>> = initial_positions
        .iter()
        .map(|p| structured_map(mass, p, StructuredCovarianceBlock::multiply_lower_transpose))
        .collect();
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    let mapped = StructuredCoordinates { target, mass };
    let mut output = sample_chains(&mapped, &transformed, &identity, config, max_threads)?;
    for chain in &mut output.chains {
        for draw in chain.samples.chunks_exact_mut(mass.dimension) {
            let restored = structured_map(mass, draw, StructuredCovarianceBlock::solve_upper);
            draw.copy_from_slice(&restored);
        }
        chain.metadata.initial_position = structured_map(
            mass,
            &chain.metadata.initial_position,
            StructuredCovarianceBlock::solve_upper,
        );
    }
    Ok(output)
}

/// Sample structured-metric chains with the same optional research controls as
/// [`sample_chains_with_control`].
pub fn sample_chains_structured_with_control<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &StructuredBlockMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    if config.warmup.as_ref().is_some_and(|w| w.adapt_mass) {
        return Err(Error::configuration(
            "structured mass adaptation is unsupported",
        ));
    }
    let transformed: Vec<Vec<f64>> = initial_positions
        .iter()
        .map(|p| structured_map(mass, p, StructuredCovarianceBlock::multiply_lower_transpose))
        .collect();
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    let mapped = StructuredCoordinates { target, mass };
    let mut output = sample_chains_with_control(
        &mapped,
        &transformed,
        &identity,
        config,
        max_threads,
        control,
    )?;
    for chain in &mut output.chains {
        for draw in chain.samples.chunks_exact_mut(mass.dimension) {
            let restored = structured_map(mass, draw, StructuredCovarianceBlock::solve_upper);
            draw.copy_from_slice(&restored);
        }
        chain.metadata.initial_position = structured_map(
            mass,
            &chain.metadata.initial_position,
            StructuredCovarianceBlock::solve_upper,
        );
    }
    Ok(output)
}

/// Validate the complete constructor path for frozen structured-metric chains
/// without evaluating the target.
pub fn preflight_chains_structured<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &StructuredBlockMass,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if target.dimension() != mass.dimension {
        return Err(Error::configuration(
            "target and structured mass dimensions differ",
        ));
    }
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "structured mass adaptation is unsupported",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    preflight_chains(target, initial_positions, &identity, config)
}

/// Validate a complete block-dense multi-chain configuration without sampling.
pub fn preflight_chains_block_dense<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &BlockDiagonalMass,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if target.dimension() != mass.dimension {
        return Err(Error::configuration(
            "target and block mass dimensions differ",
        ));
    }
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "block mass adaptation is unsupported; provide a frozen block metric",
        ));
    }
    let workspace = mass
        .matrix_entries
        .checked_mul(size_of::<f64>() * 3)
        .ok_or_else(Error::overflow)?;
    if workspace > config.limits.max_working_bytes {
        return Err(Error::resource(
            "block mass workspace exceeds the run resource limit",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    preflight_chains(target, initial_positions, &identity, config)
}

/// Sample one chain using a fixed block-diagonal dense Euclidean metric.
///
/// Mass adaptation is intentionally rejected: block construction or
/// adaptation must be explicit and frozen before calling this routine.
pub fn sample_block_dense<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &BlockDiagonalMass,
    config: &RunConfig,
) -> Result<ChainOutput, Error> {
    if target.dimension() != mass.dimension || initial_position.len() != mass.dimension {
        return Err(Error::configuration(
            "target and block mass dimensions differ",
        ));
    }
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "block mass adaptation is unsupported; provide a frozen block metric",
        ));
    }
    let workspace = mass
        .matrix_entries
        .checked_mul(size_of::<f64>() * 3)
        .ok_or_else(Error::overflow)?;
    if workspace > config.limits.max_working_bytes {
        return Err(Error::resource(
            "block mass workspace exceeds the run resource limit",
        ));
    }
    let transformed = block_multiply_lower_transpose(mass, initial_position);
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    let mut output = sample(
        &BlockDenseCoordinates { target, mass },
        &transformed,
        &identity,
        config,
    )?;
    restore_block_coordinates(&mut output, mass);
    Ok(output)
}

/// Sample explicitly initialized chains using a frozen block-diagonal metric.
pub fn sample_chains_block_dense<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &BlockDiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    if initial_positions.is_empty() || initial_positions.len() > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    let threads = max_threads.get().min(initial_positions.len());
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .and_then(|count| count.checked_mul(initial_positions.len()))
        .ok_or_else(Error::overflow)?;
    if transitions > config.limits.max_total_transitions {
        return Err(Error::resource(
            "transition count exceeds its resource limit",
        ));
    }
    if threads > config.limits.max_chains {
        return Err(Error::resource("thread count exceeds its resource limit"));
    }
    let execute = |chain: usize, position: &Vec<f64>| {
        let mut chain_config = config.clone();
        chain_config.seed = config.seed.wrapping_add(chain as u64);
        sample_block_dense(target, position, mass, &chain_config)
            .map(|mut output| {
                output.metadata.base_seed = config.seed;
                output.metadata.effective_seed = chain_seed(config.seed, chain);
                output.metadata.thread_count = threads;
                output
            })
            .map_err(|error| error.at_chain(chain))
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| {
            pool.install(|| {
                initial_positions
                    .par_iter()
                    .enumerate()
                    .map(|(chain, position)| execute(chain, position))
                    .collect::<Vec<_>>()
            })
        }))
        .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    Ok(MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: ALGORITHM_REVISION,
    })
}

fn add_work(left: &mut WorkTotals, right: &WorkTotals) -> Result<(), Error> {
    macro_rules! add {
        ($field:ident) => {
            left.$field = left
                .$field
                .checked_add(right.$field)
                .ok_or_else(Error::overflow)?
        };
    }
    add!(transitions);
    add!(momentum_refreshes);
    add!(standard_normal_components);
    add!(target_calls_initial);
    add!(target_calls_forward);
    add!(target_calls_reverse);
    add!(forward_refinement_attempts);
    add!(forward_micro_steps_executed);
    add!(reverse_coarsening_attempts);
    add!(reverse_micro_steps_executed);
    add!(leaves_attempted);
    add!(leaves_built);
    add!(direction_draws);
    add!(uniform_draws);
    add!(maximum_depth_stops);
    add!(recoverable_target_failures);
    Ok(())
}

fn sample_dense_fixed<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DenseMass,
    config: &RunConfig,
    run_control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    let transformed = multiply_lower_transpose(&mass.chol_lower, initial_position, mass.dimension);
    let identity = DiagonalMass::identity(NonZeroUsize::new(mass.dimension).unwrap());
    let mut fixed_config = config.clone();
    fixed_config.warmup = fixed_config.warmup.filter(|warmup| !warmup.adapt_mass);
    let mut output = sample_with_control(
        &DenseCoordinates { target, mass },
        &transformed,
        &identity,
        &fixed_config,
        run_control,
    )?;
    restore_dense_coordinates(&mut output, mass);
    Ok(output)
}

/// Sample with a fixed dense Euclidean metric. This is a statically dispatched
/// Cholesky coordinate map, so the kernel's drift, energy and U-turn tests are
/// exactly metric-aware without virtual calls in hot loops.
pub fn sample_dense<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DenseMass,
    config: &RunConfig,
) -> Result<ChainOutput, Error> {
    sample_dense_with_control(target, initial_position, mass, config, &RunControl::new())
}

pub fn sample_dense_with_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DenseMass,
    config: &RunConfig,
    run_control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    if target.dimension() != mass.dimension || initial_position.len() != mass.dimension {
        return Err(Error::configuration(
            "target and dense mass dimensions differ",
        ));
    }
    let Some(warmup) = config.warmup.as_ref().filter(|warmup| warmup.adapt_mass) else {
        return sample_dense_fixed(target, initial_position, mass, config, run_control);
    };
    reject_paper_adaptation(config, "dense adaptive")?;
    if config.discarded == 0 {
        return Err(Error::configuration(
            "dense warmup requires at least one discarded transition",
        ));
    }
    let schedule = warmup_schedule(config.discarded, &warmup.windows)?;
    let dense_bytes = mass
        .dimension
        .checked_mul(mass.dimension)
        .and_then(|x| x.checked_mul(size_of::<f64>() * 6))
        .ok_or_else(Error::overflow)?;
    if dense_bytes > config.limits.max_working_bytes {
        return Err(Error::resource(
            "dense adaptation workspace exceeds its resource limit",
        ));
    }

    let mut active_mass = mass.clone();
    let mut position = initial_position.to_vec();
    let mut discarded_work = WorkTotals::default();
    let mut initial_fast = WorkTotals::default();
    let mut slow = WorkTotals::default();
    let mut terminal_fast = WorkTotals::default();
    let mut diagnostics = Vec::with_capacity(config.discarded + config.retained);
    let mut updates = Vec::new();
    let mut restart_events = Vec::new();
    let mut segment_index = 0usize;
    let mut active_step = config.tuning.step_size;
    if let Some(search) = &warmup.initial_step_search {
        let transformed =
            multiply_lower_transpose(&active_mass.chol_lower, &position, active_mass.dimension);
        let identity = DiagonalMass::identity(NonZeroUsize::new(active_mass.dimension).unwrap());
        let inverse = inverse_mass(&identity)?;
        let control = ExecutionControl {
            public: run_control,
            failed_chain: None,
            chain: 0,
        };
        let (step, search_telemetry) = search_initial_step(
            &DenseCoordinates {
                target,
                mass: &active_mass,
            },
            &transformed,
            &identity,
            &inverse,
            config.tuning,
            warmup.target_acceptance,
            search,
            chain_seed(config.seed, 0),
            &control,
        )?;
        active_step = step;
        restart_events.push(StepSearchEvent {
            reason: StepSearchReason::Initial,
            search: search_telemetry,
        });
    }
    let mut dual_averaging = warmup
        .adapt_step_size
        .then(|| DualAveraging::new(active_step, warmup.target_acceptance));

    let mut run_segment = |start: usize,
                           end: usize,
                           phase: WarmupPhase,
                           collect: bool,
                           active_mass: &DenseMass,
                           position: &mut Vec<f64>,
                           active_step: &mut f64,
                           dual_averaging: &mut Option<DualAveraging>|
     -> Result<Option<DenseCovariance>, Error> {
        if start == end {
            return Ok(None);
        }
        let mut covariance = collect.then(|| DenseCovariance::new(mass.dimension));
        for transition in start..end {
            let mut transition_config = config.clone();
            transition_config.discarded = 0;
            transition_config.retained = 1;
            transition_config.seed =
                splitmix64(config.seed ^ transition as u64 ^ segment_index as u64);
            transition_config.warmup = None;
            transition_config.capture_acceptance = true;
            transition_config.tuning.step_size = *active_step;
            segment_index += 1;
            let output = sample_dense_fixed(
                target,
                position,
                active_mass,
                &transition_config,
                run_control,
            )?;
            let work = output.telemetry.total.clone();
            add_work(&mut discarded_work, &work)?;
            match phase {
                WarmupPhase::InitialFast => add_work(&mut initial_fast, &work)?,
                WarmupPhase::SlowWindow => add_work(&mut slow, &work)?,
                WarmupPhase::TerminalFast => add_work(&mut terminal_fast, &work)?,
            }
            diagnostics.extend(output.diagnostics);
            let draw = output.samples.as_slice();
            if let Some(accumulator) = &mut covariance {
                accumulator.update(draw);
            }
            position.copy_from_slice(draw);
            if let (Some(dual), Some(acceptance)) = (
                dual_averaging.as_mut(),
                output.telemetry.acceptance_values[0],
            ) {
                *active_step = dual.update(acceptance);
            }
        }
        Ok(covariance)
    };

    run_segment(
        0,
        schedule.initial_fast_end,
        WarmupPhase::InitialFast,
        false,
        &active_mass,
        &mut position,
        &mut active_step,
        &mut dual_averaging,
    )?;
    for (window_index, window) in schedule.windows.iter().enumerate() {
        let covariance = run_segment(
            window.start,
            window.end,
            WarmupPhase::SlowWindow,
            true,
            &active_mass,
            &mut position,
            &mut active_step,
            &mut dual_averaging,
        )?
        .expect("nonempty metric window");
        let (outcome, candidate, shrinkage, ridge, condition, failures) =
            covariance.precision_candidate();
        let step_before = active_step;
        let mass_dense_before = active_mass.matrix.clone();
        let mut step_after_search = None;
        let mut dual_averaging_after_restart = None;
        let installed = candidate.as_ref().map(|value| value.matrix.clone());
        if let Some(candidate) = candidate {
            active_mass = candidate;
            if warmup.adapt_step_size {
                if let Some(search) = &warmup.initial_step_search
                    && window.end < config.discarded
                {
                    let transformed = multiply_lower_transpose(
                        &active_mass.chol_lower,
                        &position,
                        active_mass.dimension,
                    );
                    let identity =
                        DiagonalMass::identity(NonZeroUsize::new(active_mass.dimension).unwrap());
                    let inverse = inverse_mass(&identity)?;
                    let control = ExecutionControl {
                        public: run_control,
                        failed_chain: None,
                        chain: 0,
                    };
                    let (step, search_telemetry) = search_initial_step(
                        &DenseCoordinates {
                            target,
                            mass: &active_mass,
                        },
                        &transformed,
                        &identity,
                        &inverse,
                        KernelTuning {
                            step_size: active_step,
                            ..config.tuning
                        },
                        warmup.target_acceptance,
                        search,
                        search_event_seed(config.seed, restart_events.len()),
                        &control,
                    )?;
                    active_step = step;
                    step_after_search = Some(step);
                    restart_events.push(StepSearchEvent {
                        reason: StepSearchReason::MetricUpdate { window_index },
                        search: search_telemetry,
                    });
                }
                dual_averaging = Some(DualAveraging::restart(
                    active_step,
                    warmup.target_acceptance,
                    warmup.research_restart_reference_multiplier,
                ));
                dual_averaging_after_restart =
                    dual_averaging.as_ref().map(DualAveraging::telemetry);
                restart_events.push(StepSearchEvent {
                    reason: StepSearchReason::DualAveragingRestart { window_index },
                    search: InitialStepSearchTelemetry {
                        initial_step: active_step,
                        selected_step: active_step,
                        ..InitialStepSearchTelemetry::default()
                    },
                });
            }
        }
        updates.push(MetricUpdateTelemetry {
            window_index,
            transition: window.end - 1,
            sample_count: covariance.count,
            outcome,
            mass_diagonal: None,
            mass_dense: installed,
            shrinkage,
            ridge,
            condition_estimate: condition,
            cholesky_failures: failures,
            step_before,
            step_after_search,
            mass_diagonal_before: None,
            mass_dense_before: Some(mass_dense_before),
            step_after_restart: dual_averaging_after_restart.map(|_| active_step),
            restart_reference_multiplier: dual_averaging_after_restart
                .map(|_| warmup.research_restart_reference_multiplier),
            dual_averaging_after_restart,
        });
    }
    run_segment(
        schedule.terminal_fast_start,
        config.discarded,
        WarmupPhase::TerminalFast,
        false,
        &active_mass,
        &mut position,
        &mut active_step,
        &mut dual_averaging,
    )?;
    if let Some(dual) = &dual_averaging {
        active_step = dual.final_step();
    }

    let mut retained_config = config.clone();
    retained_config.discarded = 0;
    retained_config.warmup = None;
    retained_config.capture_acceptance = false;
    retained_config.tuning.step_size = active_step;
    retained_config.seed = splitmix64(config.seed ^ segment_index as u64);
    let mut output = sample_dense_fixed(
        target,
        &position,
        &active_mass,
        &retained_config,
        run_control,
    )?;
    let retained_work = output.telemetry.total.clone();
    let mut total = discarded_work.clone();
    add_work(&mut total, &retained_work)?;
    diagnostics.extend(std::mem::take(&mut output.diagnostics));
    output.diagnostics = diagnostics;
    output.telemetry.discarded = discarded_work;
    output.telemetry.retained = retained_work;
    output.telemetry.total = total;
    output.telemetry.initial_fast = initial_fast;
    output.telemetry.slow = slow;
    output.telemetry.terminal_fast = terminal_fast;
    output.telemetry.metric_updates = updates;
    output.telemetry.step_searches = restart_events;
    output.metadata.discarded = config.discarded;
    output.metadata.initial_position = initial_position.to_vec();
    output.metadata.warmup = Some(warmup.clone());
    output.metadata.warmup_schedule = Some(schedule);
    output.metadata.step_size = active_step;
    output.metadata.tuning.step_size = active_step;
    Ok(output)
}

/// Sample explicitly initialized chains with a dense Euclidean metric.
///
/// Chains use `splitmix64(config.seed() + chain_index)` and are returned in
/// chain-index order independently of Rayon scheduling.
pub fn sample_chains_dense<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DenseMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    sample_chains_dense_with_control(
        target,
        initial_positions,
        mass,
        config,
        max_threads,
        &RunControl::new(),
    )
}

/// Dense multi-chain sampling with cooperative cancellation/deadline control.
pub fn sample_chains_dense_with_control<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DenseMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        reject_paper_adaptation(config, "dense adaptive")?;
    }
    if initial_positions.is_empty() || initial_positions.len() > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    let dimension = catch_unwind(AssertUnwindSafe(|| target.dimension()))
        .map_err(|_| Error::new(ErrorKind::Panic, "target dimension callback panicked"))?;
    if dimension != mass.dimension
        || initial_positions.iter().any(|position| {
            position.len() != dimension || position.iter().any(|value| !value.is_finite())
        })
    {
        return Err(Error::configuration(
            "initial positions, target, and dense mass dimensions must match and be finite",
        ));
    }
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .and_then(|count| count.checked_mul(initial_positions.len()))
        .ok_or_else(Error::overflow)?;
    if transitions > config.limits.max_total_transitions {
        return Err(Error::resource(
            "transition count exceeds its resource limit",
        ));
    }
    let threads = max_threads.get().min(initial_positions.len());
    if threads > config.limits.max_chains {
        return Err(Error::resource("thread count exceeds its resource limit"));
    }

    let execute = |chain: usize, position: &Vec<f64>| {
        let mut chain_config = config.clone();
        chain_config.seed = config.seed.wrapping_add(chain as u64);
        sample_dense_with_control(target, position, mass, &chain_config, run_control)
            .map(|mut output| {
                output.metadata.base_seed = config.seed;
                output.metadata.effective_seed = chain_seed(config.seed, chain);
                output.metadata.thread_count = threads;
                output
            })
            .map_err(|error| error.at_chain(chain))
    };
    let run = || {
        initial_positions
            .par_iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| pool.install(run)))
            .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    Ok(MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: ALGORITHM_REVISION,
    })
}

/// Sample one chain with cooperative cancellation/deadline control.
pub fn sample_with_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DiagonalMass,
    config: &RunConfig,
    run_control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    let (dimension, _, _) = validate(target, 1, std::iter::once(initial_position), mass, config)?;
    let control = ExecutionControl {
        public: run_control,
        failed_chain: None,
        chain: 0,
    };
    control.check().map_err(control_error)?;
    catch_unwind(AssertUnwindSafe(|| {
        run_chain(
            target,
            dimension,
            initial_position,
            mass,
            None,
            false,
            config,
            chain_seed(config.seed, 0),
            1,
            &control,
            None,
            None,
        )
    }))
    .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "sampling worker panicked")))
}

fn sample_operator_fixed_with_control<T: Target, M: MassOperator>(
    target: &T,
    initial_position: &[f64],
    mass: &M,
    config: &RunConfig,
    run_control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "fixed operator driver does not permit mass adaptation",
        ));
    }
    let identity =
        DiagonalMass::identity(NonZeroUsize::new(mass.dimension()).ok_or_else(Error::overflow)?);
    let (dimension, _, _) = validate(
        target,
        1,
        std::iter::once(initial_position),
        &identity,
        config,
    )?;
    let control = ExecutionControl {
        public: run_control,
        failed_chain: None,
        chain: 0,
    };
    control.check().map_err(control_error)?;
    let mut output = catch_unwind(AssertUnwindSafe(|| {
        run_chain(
            target,
            dimension,
            initial_position,
            &identity,
            Some(mass),
            true,
            config,
            chain_seed(config.seed, 0),
            1,
            &control,
            None,
            None,
        )
    }))
    .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "sampling worker panicked")))?;
    output.metadata.algorithm_revision = DIRECT_ORIGINAL_Q_REVISION;
    Ok(output)
}

/// Sample with a fixed metric directly in the target's original `q`
/// coordinates. This API uses [`DIRECT_ORIGINAL_Q_REVISION`].
pub fn sample_direct_original_q<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
) -> Result<ChainOutput, Error> {
    sample_direct_original_q_with_control(
        target,
        initial_position,
        mass,
        config,
        &RunControl::new(),
    )
}

pub fn sample_direct_original_q_with_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    sample_operator_fixed_with_control(target, initial_position, mass, config, control)
}

/// Deterministic projected-covariance adaptation for one global/path
/// arrowhead mass. Coordinates must be `[globals, path]`; projections are
/// columns of an orthonormal basis in the base-whitened path coordinates
/// `y = P' q_path`.
#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedArrowheadWarmup {
    basis: Vec<Vec<f64>>,
    minimum_samples: usize,
    shrinkage: f64,
    ridge: f64,
    maximum_condition: f64,
}

impl ProjectedArrowheadWarmup {
    pub fn new(
        basis: Vec<Vec<f64>>,
        minimum_samples: NonZeroUsize,
        shrinkage: f64,
        ridge: f64,
        maximum_condition: f64,
    ) -> Result<Self, Error> {
        let rank = basis.first().map_or(0, Vec::len);
        if basis.is_empty()
            || rank == 0
            || rank > LowRankArrowheadMass::MAX_RANK
            || basis
                .iter()
                .any(|row| row.len() != rank || row.iter().any(|value| !value.is_finite()))
            || !shrinkage.is_finite()
            || !(0.0..=1.0).contains(&shrinkage)
            || !ridge.is_finite()
            || ridge <= 0.0
            || !maximum_condition.is_finite()
            || maximum_condition < 1.0
        {
            return Err(Error::configuration(
                "invalid projected arrowhead warmup configuration",
            ));
        }
        for i in 0..rank {
            for j in 0..rank {
                let dot = basis.iter().map(|row| row[i] * row[j]).sum::<f64>();
                if (dot - usize::from(i == j) as f64).abs() > 1.0e-10 {
                    return Err(Error::configuration(
                        "projected warmup basis must be orthonormal",
                    ));
                }
            }
        }
        Ok(Self {
            basis,
            minimum_samples: minimum_samples.get(),
            shrinkage,
            ridge,
            maximum_condition,
        })
    }

    pub fn rank(&self) -> usize {
        self.basis[0].len()
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub enum ProjectedMetricOutcome {
    Installed,
    InsufficientSamples,
    NonfiniteFallback,
    FactorizationFallback,
    IllConditionedFallback,
}

#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedMetricUpdate {
    window_index: usize,
    transition: usize,
    sample_count: usize,
    generation: usize,
    rank: usize,
    outcome: ProjectedMetricOutcome,
    shrinkage: f64,
    ridge: f64,
    condition_estimate: Option<f64>,
    factorization_failures: usize,
    step_before: f64,
    step_after_restart: Option<f64>,
}

impl ProjectedMetricUpdate {
    pub fn window_index(&self) -> usize {
        self.window_index
    }
    pub fn transition(&self) -> usize {
        self.transition
    }
    pub fn sample_count(&self) -> usize {
        self.sample_count
    }
    pub fn generation(&self) -> usize {
        self.generation
    }
    pub fn rank(&self) -> usize {
        self.rank
    }
    pub fn outcome(&self) -> ProjectedMetricOutcome {
        self.outcome
    }
    pub fn shrinkage(&self) -> f64 {
        self.shrinkage
    }
    pub fn ridge(&self) -> f64 {
        self.ridge
    }
    pub fn condition_estimate(&self) -> Option<f64> {
        self.condition_estimate
    }
    pub fn factorization_failures(&self) -> usize {
        self.factorization_failures
    }
    pub fn step_before(&self) -> f64 {
        self.step_before
    }
    pub fn step_after_restart(&self) -> Option<f64> {
        self.step_after_restart
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct ProjectedArrowheadOutput {
    chain: ChainOutput,
    metric_updates: Vec<ProjectedMetricUpdate>,
    final_mass: LowRankArrowheadMass,
}

#[derive(Clone, Debug, PartialEq)]
pub struct PooledProjectedArrowheadOutput {
    chains: MultiChainOutput,
    metric_updates: Vec<ProjectedMetricUpdate>,
    final_mass: LowRankArrowheadMass,
    final_steps: Vec<f64>,
}

impl PooledProjectedArrowheadOutput {
    pub fn chains(&self) -> &MultiChainOutput {
        &self.chains
    }
    pub fn metric_updates(&self) -> &[ProjectedMetricUpdate] {
        &self.metric_updates
    }
    pub fn final_mass(&self) -> &LowRankArrowheadMass {
        &self.final_mass
    }
    pub fn final_steps(&self) -> &[f64] {
        &self.final_steps
    }
}

impl ProjectedArrowheadOutput {
    pub fn chain(&self) -> &ChainOutput {
        &self.chain
    }
    pub fn metric_updates(&self) -> &[ProjectedMetricUpdate] {
        &self.metric_updates
    }
    pub fn final_mass(&self) -> &LowRankArrowheadMass {
        &self.final_mass
    }
}

struct ProjectedCovariance {
    covariance: DenseCovariance,
    global_dimension: usize,
    basis: Vec<Vec<f64>>,
    path: StructuredCovarianceBlock,
}

impl ProjectedCovariance {
    fn new(
        global_dimension: usize,
        specification: &ProjectedArrowheadWarmup,
        path: &StructuredCovarianceBlock,
    ) -> Self {
        Self {
            covariance: DenseCovariance::new(global_dimension + specification.rank()),
            global_dimension,
            basis: specification.basis.clone(),
            path: path.clone(),
        }
    }

    fn update(&mut self, position: &[f64]) {
        let whitened = self
            .path
            .multiply_lower_transpose(&position[self.global_dimension..]);
        let rank = self.basis[0].len();
        let mut selected = position[..self.global_dimension].to_vec();
        selected.extend((0..rank).map(|k| {
            self.basis
                .iter()
                .zip(&whitened)
                .map(|(row, y)| row[k] * y)
                .sum::<f64>()
        }));
        self.covariance.update(&selected);
    }

    fn candidate(
        &self,
        specification: &ProjectedArrowheadWarmup,
    ) -> (
        ProjectedMetricOutcome,
        Option<LowRankArrowheadMass>,
        Option<f64>,
        usize,
    ) {
        if self.covariance.count < specification.minimum_samples {
            return (ProjectedMetricOutcome::InsufficientSamples, None, None, 0);
        }
        let dimension = self.covariance.mean.len();
        let denominator = (self.covariance.count - 1) as f64;
        let mut covariance: Vec<f64> = self.covariance.m2.iter().map(|x| x / denominator).collect();
        if covariance.iter().any(|x| !x.is_finite()) {
            return (ProjectedMetricOutcome::NonfiniteFallback, None, None, 0);
        }
        for i in 0..dimension {
            for j in 0..dimension {
                if i != j {
                    covariance[i * dimension + j] *= 1.0 - specification.shrinkage;
                }
            }
            covariance[i * dimension + i] =
                covariance[i * dimension + i].max(MIN_ADAPTATION_VARIANCE) + specification.ridge;
        }
        let Some(covariance_chol) = cholesky(&covariance, dimension) else {
            return (ProjectedMetricOutcome::FactorizationFallback, None, None, 1);
        };
        let minimum = (0..dimension)
            .map(|i| covariance_chol[i * dimension + i])
            .fold(f64::INFINITY, f64::min);
        let maximum = (0..dimension)
            .map(|i| covariance_chol[i * dimension + i])
            .fold(0.0_f64, f64::max);
        let condition = (maximum / minimum).powi(2);
        if !condition.is_finite() || condition > specification.maximum_condition {
            return (
                ProjectedMetricOutcome::IllConditionedFallback,
                None,
                Some(condition),
                0,
            );
        }
        let Some(precision) = inverse_from_cholesky(&covariance_chol, dimension) else {
            return (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            );
        };
        let Some(lower) = cholesky(&precision, dimension) else {
            return (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            );
        };
        let global = self.global_dimension;
        let rank = specification.rank();
        let global_lower = (0..global)
            .map(|i| {
                (0..global)
                    .map(|j| {
                        if j <= i {
                            lower[i * dimension + j]
                        } else {
                            0.0
                        }
                    })
                    .collect()
            })
            .collect();
        let subspace_lower = (0..rank)
            .map(|i| {
                (0..rank)
                    .map(|j| {
                        if j <= i {
                            lower[(global + i) * dimension + global + j]
                        } else {
                            0.0
                        }
                    })
                    .collect()
            })
            .collect();
        let global_factors = (0..global)
            .map(|j| {
                (0..rank)
                    .map(|k| lower[(global + k) * dimension + j])
                    .collect()
            })
            .collect();
        let candidate = LowRankArrowheadMass::new_with_path_subspace(
            global_lower,
            self.path.clone(),
            specification.basis.clone(),
            global_factors,
            specification.basis.clone(),
            subspace_lower,
        )
        .ok();
        match candidate {
            Some(value) => (
                ProjectedMetricOutcome::Installed,
                Some(value),
                Some(condition),
                0,
            ),
            None => (
                ProjectedMetricOutcome::FactorizationFallback,
                None,
                Some(condition),
                1,
            ),
        }
    }
}

/// Run per-chain projected arrowhead adaptation at exact slow-window
/// boundaries. Every segment ends at a transition boundary; therefore
/// momentum is discarded while numeric `q` is copied unchanged. Candidate
/// construction and fallback consume neither target calls nor random draws.
pub fn sample_projected_arrowhead<T: Target>(
    target: &T,
    initial_position: &[f64],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
    control: &RunControl<'_>,
) -> Result<ProjectedArrowheadOutput, Error> {
    let warmup = config
        .warmup
        .as_ref()
        .ok_or_else(|| Error::configuration("projected arrowhead adaptation requires warmup"))?;
    reject_paper_adaptation(config, "projected arrowhead")?;
    if !warmup.adapt_mass {
        return Err(Error::configuration(
            "projected arrowhead mass adaptation is disabled",
        ));
    }
    let global = initial_mass.global_lower.len();
    if global != 6
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_position.len() != initial_mass.dimension()
        || target.dimension() != initial_mass.dimension()
    {
        return Err(Error::configuration(
            "projected arrowhead warmup requires six leading globals and a matching path basis",
        ));
    }
    let schedule = warmup_schedule(config.discarded, &warmup.windows)?;
    let selected = global
        .checked_add(specification.rank())
        .ok_or_else(Error::overflow)?;
    let workspace = selected
        .checked_mul(selected)
        .and_then(|x| x.checked_mul(size_of::<f64>() * 4))
        .and_then(|x| {
            x.checked_add(initial_mass.dimension() * specification.rank() * size_of::<f64>() * 2)
        })
        .ok_or_else(Error::overflow)?;
    if workspace > config.limits.max_working_bytes {
        return Err(Error::resource(
            "projected adaptation workspace exceeds its resource limit",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(initial_mass.dimension()).unwrap());
    validate(
        target,
        1,
        std::iter::once(initial_position),
        &identity,
        config,
    )?;

    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let mut position = initial_position.to_vec();
    let mut active_mass = initial_mass.clone();
    let mut active_step = config.tuning.step_size;
    let mut dual = warmup
        .adapt_step_size
        .then(|| DualAveraging::new(active_step, warmup.target_acceptance));
    let mut updates = Vec::with_capacity(schedule.windows.len());
    let mut accumulator: Option<ProjectedCovariance> = None;
    let mut generation = 0usize;
    let mut combined: Option<ChainOutput> = None;
    let mut step_searches = Vec::new();
    let boundary_control = ExecutionControl {
        public: control,
        failed_chain: None,
        chain: 0,
    };
    let mut persistent = PersistentChainContext::new(chain_seed(config.seed, 0));

    for transition in 0..transitions {
        let window_index = schedule
            .windows
            .iter()
            .position(|w| transition >= w.start && transition < w.end);
        if window_index.is_some() && accumulator.is_none() {
            accumulator = Some(ProjectedCovariance::new(
                global,
                specification,
                active_mass.path(),
            ));
        }
        let mut one = config.clone();
        one.discarded = 0;
        one.retained = 1;
        one.warmup = None;
        one.capture_acceptance = true;
        one.tuning.step_size = active_step;
        let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
        let mut output = run_chain(
            target,
            initial_mass.dimension(),
            &position,
            &identity,
            Some(&direct),
            false,
            &one,
            chain_seed(config.seed, 0),
            1,
            &boundary_control,
            None,
            Some(&mut persistent),
        )
        .map_err(|error| error.at_transition(transition))?;
        let mut transition_work = output.telemetry.total.clone();
        let next = output.samples.clone();
        position.copy_from_slice(&next);
        if let Some(value) = &mut accumulator {
            value.update(&position);
        }
        if let (Some(dual), Some(acceptance)) = (&mut dual, output.telemetry.acceptance_values[0]) {
            active_step = dual.update(acceptance);
        }
        if let Some(index) = window_index
            && schedule.windows[index].end == transition + 1
        {
            boundary_control.check().map_err(control_error)?;
            let collector = accumulator.take().expect("slow-window accumulator");
            let step_before = active_step;
            let sample_count = collector.covariance.count;
            let (outcome, candidate, condition, failures) = collector.candidate(specification);
            boundary_control.check().map_err(control_error)?;
            if let Some(candidate) = candidate {
                active_mass = candidate;
                generation += 1;
                if warmup.adapt_step_size && transition + 1 < config.discarded {
                    if let Some(search) = &warmup.initial_step_search {
                        let cached = persistent.cached_state.as_ref().ok_or_else(|| {
                            Error::new(
                                ErrorKind::Internal,
                                "projected boundary lost its evaluated state",
                            )
                        })?;
                        let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
                        let momentum = direct
                            .sample_momentum(&mut persistent.rng)
                            .map_err(Error::internal)?;
                        let (step, diagnostics) = search_step_from_evaluated(
                            target,
                            EvaluatedTransitionInput {
                                theta: cached.theta.clone(),
                                rho: momentum,
                                log_prob: cached.log_prob,
                                grad: cached.grad.clone(),
                            },
                            &direct,
                            KernelTuning {
                                step_size: active_step,
                                ..config.tuning
                            },
                            warmup.target_acceptance,
                            search,
                            &mut persistent.rng,
                            &boundary_control,
                            transition,
                            true,
                            &mut transition_work,
                        )
                        .map_err(|error| error.at_transition(transition))?;
                        active_step = step;
                        step_searches.push(StepSearchEvent {
                            reason: StepSearchReason::MetricUpdate {
                                window_index: index,
                            },
                            search: diagnostics,
                        });
                    }
                    dual = Some(DualAveraging::restart(
                        active_step,
                        warmup.target_acceptance,
                        warmup.research_restart_reference_multiplier,
                    ));
                }
            }
            updates.push(ProjectedMetricUpdate {
                window_index: index,
                transition,
                sample_count,
                generation,
                rank: specification.rank(),
                outcome,
                shrinkage: specification.shrinkage,
                ridge: specification.ridge,
                condition_estimate: condition,
                factorization_failures: failures,
                step_before,
                step_after_restart: dual.as_ref().map(|_| active_step),
            });
        }
        if transition + 1 == config.discarded
            && let Some(value) = &dual
        {
            active_step = value.final_step();
        }
        if let Some(total) = &mut combined {
            total.diagnostics.append(&mut output.diagnostics);
            if transition >= config.discarded {
                total.samples.extend_from_slice(&next);
                total.retained += 1;
            }
            add_work(&mut total.telemetry.total, &transition_work)?;
            if transition < config.discarded {
                add_work(&mut total.telemetry.discarded, &transition_work)?;
            } else {
                add_work(&mut total.telemetry.retained, &transition_work)?;
            }
        } else {
            if transition < config.discarded {
                output.samples.clear();
                output.retained = 0;
                output.telemetry.discarded = transition_work.clone();
                output.telemetry.retained = WorkTotals::default();
            } else {
                output.retained = 1;
                output.telemetry.discarded = WorkTotals::default();
                output.telemetry.retained = transition_work.clone();
            }
            output.telemetry.total = transition_work;
            combined = Some(output);
        }
    }
    let mut chain =
        combined.ok_or_else(|| Error::configuration("run requires at least one transition"))?;
    chain.metadata.algorithm_revision = PROJECTED_ARROWHEAD_REVISION;
    chain.metadata.step_size = active_step;
    chain.metadata.tuning.step_size = active_step;
    chain.metadata.discarded = config.discarded;
    chain.metadata.retained = config.retained;
    chain.telemetry.step_searches = step_searches;
    Ok(ProjectedArrowheadOutput {
        chain,
        metric_updates: updates,
        final_mass: active_mass,
    })
}

struct PooledProjectedChain {
    position: Vec<f64>,
    persistent: PersistentChainContext,
    active_step: f64,
    dual: Option<DualAveraging>,
    accumulator: Option<ProjectedCovariance>,
    output: Option<ChainOutput>,
}

fn append_projected_transition(
    combined: &mut Option<ChainOutput>,
    mut output: ChainOutput,
    transition: usize,
    discarded: usize,
    work: &WorkTotals,
) -> Result<(), Error> {
    let next = output.samples.clone();
    if let Some(total) = combined {
        total.diagnostics.append(&mut output.diagnostics);
        if transition >= discarded {
            total.samples.extend_from_slice(&next);
            total.retained += 1;
        }
        add_work(&mut total.telemetry.total, work)?;
        if transition < discarded {
            add_work(&mut total.telemetry.discarded, work)?;
        } else {
            add_work(&mut total.telemetry.retained, work)?;
        }
    } else {
        if transition < discarded {
            output.samples.clear();
            output.retained = 0;
            output.telemetry.discarded = work.clone();
            output.telemetry.retained = WorkTotals::default();
        } else {
            output.retained = 1;
            output.telemetry.discarded = WorkTotals::default();
            output.telemetry.retained = work.clone();
        }
        output.telemetry.total = work.clone();
        *combined = Some(output);
    }
    Ok(())
}

/// Pooled projected-arrowhead adaptation with a deterministic window barrier.
///
/// Chains own independent RNG/cache/dual-averaging state. At each common
/// slow-window boundary their Welford summaries are merged in chain-index
/// order and exactly one metric generation is installed for all chains.
#[allow(clippy::too_many_arguments)]
pub fn sample_chains_projected_arrowhead<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
) -> Result<PooledProjectedArrowheadOutput, Error> {
    let warmup = config
        .warmup
        .as_ref()
        .ok_or_else(|| Error::configuration("pooled projected adaptation requires warmup"))?;
    reject_paper_adaptation(config, "pooled projected arrowhead")?;
    if !warmup.adapt_mass || initial_positions.is_empty() {
        return Err(Error::configuration(
            "pooled projected adaptation requires chains and mass adaptation",
        ));
    }
    let chains = initial_positions.len();
    if chains > config.limits.max_chains {
        return Err(Error::resource("chain count exceeds its resource limit"));
    }
    let dimension = initial_mass.dimension();
    let global = initial_mass.global_lower.len();
    if global != 6
        || target.dimension() != dimension
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_positions
            .iter()
            .any(|position| position.len() != dimension)
    {
        return Err(Error::configuration(
            "pooled projected dimensions are incompatible",
        ));
    }
    let schedule = warmup_schedule(config.discarded, &warmup.windows)?;
    let selected = global
        .checked_add(specification.rank())
        .ok_or_else(Error::overflow)?;
    let per_chain_workspace = selected
        .checked_mul(selected)
        .and_then(|x| x.checked_mul(size_of::<f64>() * 4))
        .and_then(|x| {
            x.checked_add(
                dimension
                    .checked_mul(specification.rank())?
                    .checked_mul(size_of::<f64>() * 2)?,
            )
        })
        .ok_or_else(Error::overflow)?;
    if per_chain_workspace
        .checked_mul(chains)
        .ok_or_else(Error::overflow)?
        > config.limits.max_working_bytes
    {
        return Err(Error::resource(
            "pooled projected adaptation workspace exceeds its resource limit",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(dimension).unwrap());
    validate(
        target,
        chains,
        initial_positions.iter().map(Vec::as_slice),
        &identity,
        config,
    )?;
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let failed_chain = AtomicUsize::new(usize::MAX);
    let threads = max_threads.get().min(chains);
    let pool = (threads > 1)
        .then(|| {
            rayon::ThreadPoolBuilder::new()
                .num_threads(threads)
                .build()
                .map_err(|_| Error::resource("could not create bounded Rayon pool"))
        })
        .transpose()?;
    let mut states = initial_positions
        .iter()
        .enumerate()
        .map(|(chain, position)| PooledProjectedChain {
            position: position.clone(),
            persistent: PersistentChainContext::new(chain_seed(config.seed, chain)),
            active_step: config.tuning.step_size,
            dual: warmup
                .adapt_step_size
                .then(|| DualAveraging::new(config.tuning.step_size, warmup.target_acceptance)),
            accumulator: None,
            output: None,
        })
        .collect::<Vec<_>>();
    let mut active_mass = initial_mass.clone();
    let mut updates = Vec::with_capacity(schedule.windows.len());
    let mut generation = 0usize;

    for transition in 0..transitions {
        run_control_check(run_control)?;
        let window_index = schedule
            .windows
            .iter()
            .position(|window| transition >= window.start && transition < window.end);
        for state in &mut states {
            if window_index.is_some() && state.accumulator.is_none() {
                state.accumulator = Some(ProjectedCovariance::new(
                    global,
                    specification,
                    active_mass.path(),
                ));
            }
        }
        let mass = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
        let execute = |(chain, state): (usize, &mut PooledProjectedChain)| {
            let control = ExecutionControl {
                public: run_control,
                failed_chain: Some(&failed_chain),
                chain,
            };
            let mut one = config.clone();
            one.discarded = 0;
            one.retained = 1;
            one.warmup = None;
            one.capture_acceptance = true;
            one.tuning.step_size = state.active_step;
            let result = run_chain(
                target,
                dimension,
                &state.position,
                &identity,
                Some(&mass),
                false,
                &one,
                chain_seed(config.seed, chain),
                threads,
                &control,
                None,
                Some(&mut state.persistent),
            )
            .map_err(|error| error.at_chain(chain).at_transition(transition));
            if result.is_err() {
                failed_chain.fetch_min(chain, Ordering::AcqRel);
            }
            result
        };
        let results: Vec<Result<ChainOutput, Error>> = if let Some(pool) = &pool {
            pool.install(|| states.par_iter_mut().enumerate().map(execute).collect())
        } else {
            states.iter_mut().enumerate().map(execute).collect()
        };
        for (chain, result) in results.into_iter().enumerate() {
            let output = result?;
            let state = &mut states[chain];
            let work = output.telemetry.total.clone();
            state.position.copy_from_slice(&output.samples);
            if let Some(accumulator) = &mut state.accumulator {
                accumulator.update(&state.position);
            }
            if let (Some(dual), Some(acceptance)) =
                (&mut state.dual, output.telemetry.acceptance_values[0])
            {
                state.active_step = dual.update(acceptance);
            }
            append_projected_transition(
                &mut state.output,
                output,
                transition,
                config.discarded,
                &work,
            )?;
        }

        if let Some(index) = window_index
            && schedule.windows[index].end == transition + 1
        {
            run_control_check(run_control)?;
            let mut pooled = ProjectedCovariance::new(global, specification, active_mass.path());
            for state in &mut states {
                let summary = state.accumulator.take().expect("window accumulator exists");
                pooled.covariance.merge(&summary.covariance)?;
            }
            let sample_count = pooled.covariance.count;
            let step_before = states[0].active_step;
            let (outcome, candidate, condition, failures) = pooled.candidate(specification);
            run_control_check(run_control)?;
            if let Some(candidate) = candidate {
                active_mass = candidate;
                generation += 1;
                if warmup.adapt_step_size && transition + 1 < config.discarded {
                    for (chain, state) in states.iter_mut().enumerate() {
                        if let Some(search) = &warmup.initial_step_search {
                            let control = ExecutionControl {
                                public: run_control,
                                failed_chain: Some(&failed_chain),
                                chain,
                            };
                            let cached =
                                state.persistent.cached_state.as_ref().ok_or_else(|| {
                                    Error::new(
                                        ErrorKind::Internal,
                                        "pooled barrier lost cached state",
                                    )
                                })?;
                            let direct = DirectOriginalQMass::LowRankArrowhead(active_mass.clone());
                            let momentum = direct
                                .sample_momentum(&mut state.persistent.rng)
                                .map_err(Error::internal)?;
                            let mut search_work = WorkTotals::default();
                            let (step, diagnostics) = search_step_from_evaluated(
                                target,
                                EvaluatedTransitionInput {
                                    theta: cached.theta.clone(),
                                    rho: momentum,
                                    log_prob: cached.log_prob,
                                    grad: cached.grad.clone(),
                                },
                                &direct,
                                KernelTuning {
                                    step_size: state.active_step,
                                    ..config.tuning
                                },
                                warmup.target_acceptance,
                                search,
                                &mut state.persistent.rng,
                                &control,
                                transition,
                                true,
                                &mut search_work,
                            )
                            .map_err(|error| error.at_chain(chain).at_transition(transition))?;
                            state.active_step = step;
                            let output = state.output.as_mut().expect("chain has transitioned");
                            add_work(&mut output.telemetry.total, &search_work)?;
                            add_work(&mut output.telemetry.discarded, &search_work)?;
                            output.telemetry.step_searches.push(StepSearchEvent {
                                reason: StepSearchReason::MetricUpdate {
                                    window_index: index,
                                },
                                search: diagnostics,
                            });
                        }
                        state.dual = Some(DualAveraging::restart(
                            state.active_step,
                            warmup.target_acceptance,
                            warmup.research_restart_reference_multiplier,
                        ));
                    }
                }
            }
            updates.push(ProjectedMetricUpdate {
                window_index: index,
                transition,
                sample_count,
                generation,
                rank: specification.rank(),
                outcome,
                shrinkage: specification.shrinkage,
                ridge: specification.ridge,
                condition_estimate: condition,
                factorization_failures: failures,
                step_before,
                step_after_restart: states.first().map(|state| state.active_step),
            });
        }
        if transition + 1 == config.discarded {
            for state in &mut states {
                if let Some(dual) = &state.dual {
                    state.active_step = dual.final_step();
                }
            }
        }
    }
    let mut outputs = Vec::with_capacity(chains);
    let mut final_steps = Vec::with_capacity(chains);
    for (chain, state) in states.into_iter().enumerate() {
        let mut output = state
            .output
            .ok_or_else(|| Error::configuration("run requires at least one transition"))?;
        output.metadata.algorithm_revision = PROJECTED_ARROWHEAD_REVISION;
        output.metadata.base_seed = config.seed;
        output.metadata.effective_seed = chain_seed(config.seed, chain);
        output.metadata.thread_count = threads;
        output.metadata.step_size = state.active_step;
        output.metadata.tuning.step_size = state.active_step;
        output.metadata.discarded = config.discarded;
        output.metadata.retained = config.retained;
        final_steps.push(state.active_step);
        outputs.push(output);
    }
    Ok(PooledProjectedArrowheadOutput {
        chains: MultiChainOutput {
            chains: outputs,
            base_seed: config.seed,
            algorithm_revision: PROJECTED_ARROWHEAD_REVISION,
        },
        metric_updates: updates,
        final_mass: active_mass,
        final_steps,
    })
}

pub fn preflight_chains_projected_arrowhead<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    initial_mass: &LowRankArrowheadMass,
    specification: &ProjectedArrowheadWarmup,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if initial_positions.is_empty()
        || target.dimension() != initial_mass.dimension()
        || specification.basis.len() != initial_mass.path.dimension()
        || initial_positions
            .iter()
            .any(|position| position.len() != initial_mass.dimension())
    {
        return Err(Error::configuration(
            "pooled projected preflight dimensions are incompatible",
        ));
    }
    let identity = DiagonalMass::identity(NonZeroUsize::new(initial_mass.dimension()).unwrap());
    preflight_chains(target, initial_positions, &identity, config)
}

fn run_control_check(control: &RunControl<'_>) -> Result<(), Error> {
    ExecutionControl {
        public: control,
        failed_chain: None,
        chain: 0,
    }
    .check()
    .map_err(control_error)
}

/// Validate a direct-original-q run without invoking the target callback.
pub fn preflight_direct_original_q<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
) -> Result<PreflightReport, Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        return Err(Error::configuration(
            "direct fixed-metric API does not permit mass adaptation",
        ));
    }
    let identity =
        DiagonalMass::identity(NonZeroUsize::new(mass.dimension()).ok_or_else(Error::overflow)?);
    preflight_chains(target, initial_positions, &identity, config)
}

pub fn preflight_direct_original_q_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<PreflightReport, Error> {
    if budget.maximum() > admission_limit.maximum() {
        return Err(Error::configuration(
            "runtime target-evaluation budget exceeds its admission ceiling",
        ));
    }
    let identity =
        DiagonalMass::identity(NonZeroUsize::new(mass.dimension()).ok_or_else(Error::overflow)?);
    let (dimension, _, total_transitions) = validate_with_admission(
        target,
        initial_positions.len(),
        initial_positions.iter().map(Vec::as_slice),
        &identity,
        config,
        Some(admission_limit.maximum()),
    )?;
    Ok(PreflightReport {
        dimension,
        chains: initial_positions.len(),
        total_transitions,
        worst_case_target_evaluations: config.worst_case_target_evaluations(
            NonZeroUsize::new(initial_positions.len()).ok_or_else(Error::overflow)?,
        )?,
        admission_ceiling: admission_limit.maximum(),
    })
}

pub fn sample_direct_original_q_with_target_budget_and_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
    control: &RunControl<'_>,
) -> Result<ChainOutput, Error> {
    if budget.started() != 0 {
        return Err(Error::configuration(
            "runtime target-evaluation budget must be fresh",
        ));
    }
    preflight_direct_original_q_with_target_budget(
        target,
        &[initial_position.to_vec()],
        mass,
        config,
        admission_limit,
        budget,
    )?;
    let wrapped = budget.wrap(target);
    sample_direct_original_q_with_control(&wrapped, initial_position, mass, config, control)
}

/// Deterministic chain-index ordered direct-original-q execution.
pub fn sample_chains_direct_original_q<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DirectOriginalQMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    let report = preflight_direct_original_q(target, initial_positions, mass, config)?;
    let threads = max_threads.get().min(report.chains());
    let execute = |chain: usize, position: &Vec<f64>| {
        let mut chain_config = config.clone();
        chain_config.seed = config.seed.wrapping_add(chain as u64);
        sample_direct_original_q(target, position, mass, &chain_config)
            .map(|mut output| {
                output.metadata.base_seed = config.seed;
                output.metadata.effective_seed = chain_seed(config.seed, chain);
                output.metadata.thread_count = threads;
                output
            })
            .map_err(|error| error.at_chain(chain))
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| {
            pool.install(|| {
                initial_positions
                    .par_iter()
                    .enumerate()
                    .map(|(chain, position)| execute(chain, position))
                    .collect::<Vec<_>>()
            })
        }))
        .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    Ok(MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: DIRECT_ORIGINAL_Q_REVISION,
    })
}

/// Sample explicitly initialized chains in chain-index order.
///
/// `max_threads` bounds a run-local Rayon pool. A value of one is sequential.
pub fn sample_chains<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    sample_chains_with_control(
        target,
        initial_positions,
        mass,
        config,
        max_threads,
        &RunControl::new(),
    )
}

/// Sample chains under an explicit conservative admission ceiling and an exact
/// shared runtime cap on started target callbacks.
///
/// The budget must be fresh. This entry point alone may admit a conservative
/// bound above [`RESEARCH_MAX_TARGET_EVALUATIONS`]; all unbudgeted entry points
/// retain their existing ceilings.
pub fn sample_chains_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<MultiChainOutput, Error> {
    sample_chains_with_target_budget_and_control(
        target,
        initial_positions,
        mass,
        config,
        max_threads,
        admission_limit,
        budget,
        &RunControl::new(),
    )
}

/// Budgeted diagonal sampling with the same run controls as
/// [`sample_chains_with_control`]. Admission is completed before any target
/// callback and the exact shared callback budget remains authoritative.
#[allow(clippy::too_many_arguments)]
pub fn sample_chains_with_target_budget_and_control<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
    run_control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    if budget.started() != 0 {
        return Err(Error::configuration(
            "runtime target-evaluation budget must be fresh",
        ));
    }
    let report = preflight_chains_with_target_budget(
        target,
        initial_positions,
        mass,
        config,
        admission_limit,
        budget,
    )?;
    if target.cancel_after_admission() {
        return Err(Error::new(
            ErrorKind::Cancelled,
            "execution cancelled after budgeted admission",
        ));
    }
    let wrapped = budget.wrap(target);
    let mut output = sample_chains_validated(
        &wrapped,
        initial_positions,
        mass,
        config,
        max_threads,
        run_control,
        report.dimension(),
    )?;
    for chain in &mut output.chains {
        chain.metadata.effective_max_target_evaluations = admission_limit.maximum();
        chain.metadata.target_evaluation_limit_provenance =
            TargetEvaluationLimitProvenance::ExplicitBudgetedAdmission;
    }
    Ok(output)
}

/// Budgeted dense sampling. This is the dense counterpart of
/// [`sample_chains_with_target_budget`] and uses exactly the report returned by
/// the public dense budgeted preflight.
pub fn sample_chains_dense_with_target_budget<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DenseMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
) -> Result<MultiChainOutput, Error> {
    sample_chains_dense_with_target_budget_and_control(
        target,
        initial_positions,
        mass,
        config,
        max_threads,
        admission_limit,
        budget,
        &RunControl::new(),
    )
}

/// Budgeted dense sampling with the same generic run controls as
/// [`sample_chains_dense_with_control`].
#[allow(clippy::too_many_arguments)]
pub fn sample_chains_dense_with_target_budget_and_control<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DenseMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    admission_limit: TargetEvaluationAdmissionLimit,
    budget: &TargetEvaluationBudget,
    run_control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    if config
        .warmup
        .as_ref()
        .is_some_and(|warmup| warmup.adapt_mass)
    {
        reject_paper_adaptation(config, "dense adaptive")?;
    }
    if budget.started() != 0 {
        return Err(Error::configuration(
            "runtime target-evaluation budget must be fresh",
        ));
    }
    preflight_chains_dense_with_target_budget(
        target,
        initial_positions,
        mass,
        config,
        admission_limit,
        budget,
    )?;
    if target.cancel_after_admission() {
        return Err(Error::new(
            ErrorKind::Cancelled,
            "execution cancelled after dense budgeted admission",
        ));
    }
    let wrapped = budget.wrap(target);
    let threads = max_threads.get().min(initial_positions.len());
    if threads > config.limits.max_chains {
        return Err(Error::resource("thread count exceeds its resource limit"));
    }
    let execute = |chain: usize, position: &Vec<f64>| {
        let mut chain_config = config.clone();
        chain_config.seed = config.seed.wrapping_add(chain as u64);
        sample_dense_with_control(&wrapped, position, mass, &chain_config, run_control)
            .map(|mut chain_output| {
                chain_output.metadata.base_seed = config.seed;
                chain_output.metadata.effective_seed = chain_seed(config.seed, chain);
                chain_output.metadata.thread_count = threads;
                chain_output
            })
            .map_err(|error| error.at_chain(chain))
    };
    let run = || {
        initial_positions
            .par_iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| pool.install(run)))
            .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    let mut output = MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: ALGORITHM_REVISION,
    };
    for chain in &mut output.chains {
        chain.metadata.effective_max_target_evaluations = admission_limit.maximum();
        chain.metadata.target_evaluation_limit_provenance =
            TargetEvaluationLimitProvenance::ExplicitBudgetedAdmission;
    }
    Ok(output)
}

/// Sample explicitly initialized chains with cooperative run control.
pub fn sample_chains_with_control<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    let (dimension, _, _) = validate(
        target,
        initial_positions.len(),
        initial_positions.iter().map(Vec::as_slice),
        mass,
        config,
    )?;
    sample_chains_validated(
        target,
        initial_positions,
        mass,
        config,
        max_threads,
        run_control,
        dimension,
    )
}

fn sample_chains_validated<T: Target>(
    target: &T,
    initial_positions: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
    dimension: usize,
) -> Result<MultiChainOutput, Error> {
    let threads = max_threads.get().min(initial_positions.len());
    if threads > config.limits.max_chains {
        return Err(Error::resource("thread count exceeds its resource limit"));
    }
    let failed_chain = AtomicUsize::new(usize::MAX);
    let shared_initial_step_search = if let Some((warmup, search)) =
        config.warmup.as_ref().and_then(|warmup| {
            warmup
                .initial_step_search
                .as_ref()
                .map(|search| (warmup, search))
        }) {
        let control = ExecutionControl {
            public: run_control,
            failed_chain: Some(&failed_chain),
            chain: 0,
        };
        let inverse = inverse_mass(mass)?;
        Some(
            catch_unwind(AssertUnwindSafe(|| {
                search_initial_step(
                    target,
                    &initial_positions[0],
                    mass,
                    &inverse,
                    config.tuning,
                    warmup.target_acceptance,
                    search,
                    chain_seed(config.seed, 0),
                    &control,
                )
            }))
            .unwrap_or_else(|_| {
                Err(Error::new(
                    ErrorKind::Panic,
                    "initial-step search worker panicked",
                ))
            })
            .map_err(|error| error.at_chain(0))?,
        )
    } else {
        None
    };
    let execute = |chain: usize, position: &Vec<f64>| {
        let control = ExecutionControl {
            public: run_control,
            failed_chain: Some(&failed_chain),
            chain,
        };
        let result = catch_unwind(AssertUnwindSafe(|| {
            run_chain(
                target,
                dimension,
                position,
                mass,
                None,
                false,
                config,
                chain_seed(config.seed, chain),
                threads,
                &control,
                shared_initial_step_search.as_ref(),
                None,
            )
        }))
        .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "Rayon worker panicked")))
        .map_err(|error| error.at_chain(chain));
        if result.is_err() {
            failed_chain.fetch_min(chain, Ordering::AcqRel);
        }
        result
    };
    let run = || {
        initial_positions
            .par_iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    };
    let results = if threads == 1 {
        initial_positions
            .iter()
            .enumerate()
            .map(|(chain, position)| execute(chain, position))
            .collect::<Vec<_>>()
    } else {
        let pool = rayon::ThreadPoolBuilder::new()
            .num_threads(threads)
            .build()
            .map_err(|_| Error::resource("could not create bounded Rayon pool"))?;
        catch_unwind(AssertUnwindSafe(|| pool.install(run)))
            .map_err(|_| Error::new(ErrorKind::Panic, "Rayon pool panicked"))?
    };
    let mut chains = Vec::with_capacity(results.len());
    for result in results {
        chains.push(result?);
    }
    Ok(MultiChainOutput {
        chains,
        base_seed: config.seed,
        algorithm_revision: ALGORITHM_REVISION,
    })
}

/// Sample multiple chains from the same exact initial position. No jitter is added.
pub fn sample_chains_from<T: Target>(
    target: &T,
    initial_position: &[f64],
    chains: NonZeroUsize,
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
) -> Result<MultiChainOutput, Error> {
    sample_chains_from_with_control(
        target,
        initial_position,
        chains,
        mass,
        config,
        max_threads,
        &RunControl::new(),
    )
}

/// Sample equal initial positions with cooperative run control and no jitter.
pub fn sample_chains_from_with_control<T: Target>(
    target: &T,
    initial_position: &[f64],
    chains: NonZeroUsize,
    mass: &DiagonalMass,
    config: &RunConfig,
    max_threads: NonZeroUsize,
    run_control: &RunControl<'_>,
) -> Result<MultiChainOutput, Error> {
    let (dimension, _, _) = validate(
        target,
        chains.get(),
        std::iter::repeat_n(initial_position, chains.get()),
        mass,
        config,
    )?;
    let mut initial_positions = Vec::new();
    initial_positions
        .try_reserve_exact(chains.get())
        .map_err(|_| Error::resource("initial-position matrix allocation failed"))?;
    for _ in 0..chains.get() {
        let mut position = Vec::new();
        position
            .try_reserve_exact(initial_position.len())
            .map_err(|_| Error::resource("initial-position allocation failed"))?;
        position.extend_from_slice(initial_position);
        initial_positions.push(position);
    }
    sample_chains_validated(
        target,
        &initial_positions,
        mass,
        config,
        max_threads,
        run_control,
        dimension,
    )
}

fn chain_seed(base_seed: u64, chain_index: usize) -> u64 {
    splitmix64(base_seed.wrapping_add(chain_index as u64))
}

fn search_event_seed(chain_seed: u64, event_index: usize) -> u64 {
    splitmix64(
        chain_seed
            .wrapping_add(0x7761_726d_7570_0000)
            .wrapping_add(event_index as u64),
    )
}

fn splitmix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9E37_79B9_7F4A_7C15);
    value = (value ^ (value >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    value ^ (value >> 31)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::kernel::{ScriptedTransitionRng, TransitionDraw, transition_w_with_telemetry};
    use std::sync::atomic::{AtomicBool, AtomicUsize};
    use std::thread;

    struct Gaussian(usize);

    impl Target for Gaussian {
        fn dimension(&self) -> usize {
            self.0
        }

        fn log_density_gradient(
            &self,
            position: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            for (output, input) in gradient.iter_mut().zip(position) {
                *output = -*input;
            }
            Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
        }
    }

    fn config(seed: u64) -> RunConfig {
        RunConfig::new(2, NonZeroUsize::new(5).unwrap(), seed)
    }

    #[test]
    fn same_seed_is_identical_and_metadata_is_present() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let first = sample(&target, &[0.2, -0.1], &mass, &config(42)).unwrap();
        let second = sample(&target, &[0.2, -0.1], &mass, &config(42)).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.samples().len(), 10);
        assert_eq!(first.metadata().algorithm_revision(), ALGORITHM_REVISION);
        assert_eq!(first.telemetry().discarded().transitions(), 2);
        assert_eq!(first.telemetry().retained().transitions(), 5);
        assert_eq!(first.telemetry().total().transitions(), 7);
        assert_eq!(
            first.telemetry().total().target_calls_total(),
            first
                .diagnostics()
                .iter()
                .map(TransitionDiagnostics::target_evaluations)
                .sum::<usize>()
        );
    }

    #[test]
    fn production_default_is_bit_identical_to_explicit_biased_progressive_selection() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let default = sample(&target, &[0.2, -0.1], &mass, &config(0x5e1ec7)).unwrap();
        let explicit = sample(
            &target,
            &[0.2, -0.1],
            &mass,
            &config(0x5e1ec7)
                .with_research_outer_orbit_selection(OuterOrbitSelection::BiasedProgressive),
        )
        .unwrap();
        assert_eq!(default, explicit);
    }

    #[test]
    fn original_q_driver_identity_dense_is_bit_identical_to_diagonal_facade() {
        let target = Gaussian(2);
        let config = config(0x00d1_2ec7);
        let initial = [0.2, -0.1];
        let diagonal = sample(
            &target,
            &initial,
            &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
            &config,
        )
        .unwrap();
        let direct = sample_operator_fixed_with_control(
            &target,
            &initial,
            &DenseMass::identity(NonZeroUsize::new(2).unwrap()).unwrap(),
            &config,
            &RunControl::new(),
        )
        .unwrap();
        assert_eq!(direct.samples(), diagonal.samples());
        assert_eq!(direct.diagnostics(), diagonal.diagnostics());
        assert_eq!(direct.telemetry(), diagonal.telemetry());
    }

    #[test]
    fn sequential_and_parallel_chains_are_identical_without_jitter() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let positions = vec![vec![0.1, 0.2]; 4];
        let sequential = sample_chains(
            &target,
            &positions,
            &mass,
            &config(7),
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        let parallel = sample_chains(
            &target,
            &positions,
            &mass,
            &config(7),
            NonZeroUsize::new(2).unwrap(),
        )
        .unwrap();
        for (sequential, parallel) in sequential.chains().iter().zip(parallel.chains()) {
            assert_eq!(sequential.samples(), parallel.samples());
            assert_eq!(sequential.diagnostics(), parallel.diagnostics());
            assert_eq!(sequential.telemetry(), parallel.telemetry());
            assert_eq!(sequential.metadata().thread_count(), 1);
            assert_eq!(parallel.metadata().thread_count(), 2);
        }
        assert_ne!(
            sequential.chains()[0].samples(),
            sequential.chains()[1].samples()
        );
    }

    #[test]
    fn generated_randomness_matches_supplied_transition_seam() {
        struct RecordingRng<'a> {
            rng: &'a mut SmallRng,
            draws: Vec<TransitionDraw>,
        }
        impl Uniform01 for RecordingRng<'_> {
            fn uniform_01(&mut self) -> Result<f64, ValidationError> {
                let value = self.rng.random();
                self.draws.push(TransitionDraw::Uniform(value));
                Ok(value)
            }
        }
        impl TransitionRng for RecordingRng<'_> {
            fn direction(&mut self) -> Result<Direction, ValidationError> {
                let value = if self.rng.random() {
                    Direction::Forward
                } else {
                    Direction::Backward
                };
                self.draws.push(TransitionDraw::Direction(value));
                Ok(value)
            }
        }

        let seed = 81;
        let mass = DiagonalMass::from_diagonal(vec![0.5, 3.0]).unwrap();
        let inverse = inverse_mass(&mass).unwrap();
        let mut rng = SmallRng::seed_from_u64(seed);
        let normals: Vec<f64> = (0..2).map(|_| StandardNormal.sample(&mut rng)).collect();
        let momentum: Vec<f64> = normals
            .iter()
            .zip(mass.diagonal())
            .map(|(normal, mass)| normal * mass.sqrt())
            .collect();
        let mut recording = RecordingRng {
            rng: &mut rng,
            draws: Vec::new(),
        };
        let mut eval = |theta: &[f64]| {
            (
                -0.5 * theta.iter().map(|value| value * value).sum::<f64>(),
                theta.iter().map(|value| -*value).collect(),
            )
        };
        let direct = transition_w_with_telemetry(
            &mut recording,
            TransitionInput {
                theta: vec![0.2, -0.1],
                rho: momentum.clone(),
            },
            &inverse,
            tuning(),
            &mut eval,
        )
        .unwrap();
        let mut scripted = ScriptedTransitionRng::new(recording.draws);
        let supplied = transition_w_with_telemetry(
            &mut scripted,
            TransitionInput {
                theta: vec![0.2, -0.1],
                rho: momentum,
            },
            &inverse,
            tuning(),
            &mut eval,
        )
        .unwrap();
        assert_eq!(direct.result.selected, supplied.result.selected);
        assert_eq!(direct.result.diagnostics, supplied.result.diagnostics);
        assert_eq!(direct.work, supplied.work);
    }

    #[test]
    fn static_validation_precedes_target_and_resource_limits_are_checked() {
        use std::sync::atomic::{AtomicUsize, Ordering};
        struct Counting<'a>(&'a AtomicUsize);
        impl Target for Counting<'_> {
            fn dimension(&self) -> usize {
                2
            }
            fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
                self.0.fetch_add(1, Ordering::SeqCst);
                Ok(0.0)
            }
        }
        let calls = AtomicUsize::new(0);
        let target = Counting(&calls);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        assert!(sample(&target, &[f64::NAN, 0.0], &mass, &config(1)).is_err());
        let limits = ResourceLimits::new(
            NonZeroUsize::new(2).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(16).unwrap(),
            NonZeroUsize::new(16).unwrap(),
        )
        .unwrap();
        assert!(sample(&target, &[0.0, 0.0], &mass, &config(1).with_limits(limits)).is_err());
        assert_eq!(calls.load(Ordering::SeqCst), 0);
    }

    #[test]
    fn malformed_and_nonfinite_targets_are_fatal() {
        struct Bad(bool);
        impl Target for Bad {
            fn dimension(&self) -> usize {
                1
            }
            fn log_density_gradient(
                &self,
                _: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                if self.0 {
                    Err(TargetError::new("model failed"))
                } else {
                    gradient[0] = f64::NAN;
                    Ok(0.0)
                }
            }
        }
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        for target in [Bad(true), Bad(false)] {
            let error = sample(&target, &[0.0], &mass, &config(3)).unwrap_err();
            assert_eq!(error.kind(), ErrorKind::Target);
            assert_eq!(error.transition(), Some(0));
        }
    }

    #[test]
    fn rejects_nonrepresentable_inverse_mass_and_checked_count_overflow() {
        let smallest_subnormal = f64::from_bits(1);
        let target = Gaussian(1);
        assert_eq!(
            DiagonalMass::from_diagonal(vec![smallest_subnormal])
                .unwrap_err()
                .kind(),
            ErrorKind::Configuration
        );
        let overflow = RunConfig {
            discarded: usize::MAX,
            retained: 1,
            seed: 0,
            max_maximum_depth_stops: usize::MAX,
            limits: ResourceLimits::default(),
            tuning: KernelTuning::default(),
            warmup: None,
            research_target_evaluation_limit: None,
            capture_acceptance: false,
            outer_orbit_selection: OuterOrbitSelection::BiasedProgressive,
        };
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        assert_eq!(
            sample(&target, &[0.0], &mass, &overflow)
                .unwrap_err()
                .kind(),
            ErrorKind::Overflow
        );
    }

    #[test]
    fn sample_indices_never_overflow_or_panic() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let output = sample(&target, &[0.0, 0.0], &mass, &config(9)).unwrap();
        assert!(output.sample(output.retained()).is_none());
        assert!(output.sample(usize::MAX).is_none());
        let overflow_index = usize::MAX / output.dimension() + 1;
        assert!(output.sample(overflow_index).is_none());
    }

    #[test]
    fn chain_limit_rejects_before_shared_initial_position_cloning() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let error = sample_chains_from(
            &target,
            &[0.0, 0.0],
            NonZeroUsize::new(ResourceLimits::default().max_chains() + 1).unwrap(),
            &mass,
            &config(1),
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap_err();
        assert_eq!(error.kind(), ErrorKind::ResourceLimit);
        assert_eq!(error.message(), "chain count exceeds its resource limit");
    }

    #[test]
    fn complete_result_memory_bound_has_an_exact_boundary() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let retained = 1;
        let result_bytes = retained * 2 * size_of::<f64>()
            + retained * size_of::<TransitionDiagnostics>()
            + 2 * 3 * size_of::<f64>()
            + size_of::<ChainOutput>()
            + size_of::<MultiChainOutput>()
            + size_of::<RunTelemetry>();
        let base = ResourceLimits::default();
        let limits_at_boundary = ResourceLimits {
            max_result_bytes: result_bytes,
            ..base.clone()
        };
        let run = RunConfig::new(0, NonZeroUsize::new(retained).unwrap(), 3)
            .with_limits(limits_at_boundary);
        assert!(sample(&target, &[0.0, 0.0], &mass, &run).is_ok());

        let limits_below_boundary = ResourceLimits {
            max_result_bytes: result_bytes - 1,
            ..base
        };
        let run = RunConfig::new(0, NonZeroUsize::new(retained).unwrap(), 3)
            .with_limits(limits_below_boundary);
        let error = sample(&target, &[0.0, 0.0], &mass, &run).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::ResourceLimit);
        assert_eq!(error.message(), "result data exceeds its resource limit");
    }

    impl Cancellation for AtomicBool {
        fn is_cancelled(&self) -> bool {
            self.load(Ordering::SeqCst)
        }
    }

    #[test]
    fn cancellation_and_deadline_fail_without_partial_success() {
        let target = Gaussian(1);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let cancelled = AtomicBool::new(true);
        let control = RunControl::new().with_cancellation(&cancelled);
        let error = sample_with_control(&target, &[0.0], &mass, &config(1), &control).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Cancelled);

        let control = RunControl::new().with_deadline(Instant::now());
        let error = sample_with_control(&target, &[0.0], &mass, &config(1), &control).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::DeadlineExceeded);
    }

    #[test]
    fn cancellation_set_inside_target_is_observed_after_callback() {
        struct Cancelling<'a>(&'a AtomicBool);
        impl Target for Cancelling<'_> {
            fn dimension(&self) -> usize {
                1
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                gradient[0] = -position[0];
                self.0.store(true, Ordering::SeqCst);
                Ok(-0.5 * position[0] * position[0])
            }
        }
        let cancelled = AtomicBool::new(false);
        let control = RunControl::new().with_cancellation(&cancelled);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let error =
            sample_with_control(&Cancelling(&cancelled), &[0.0], &mass, &config(2), &control)
                .unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Cancelled);
        assert_eq!(error.transition(), Some(0));
    }

    #[test]
    fn target_panics_at_initial_and_mid_transition_are_contained() {
        struct PanicAt {
            calls: AtomicUsize,
            at: usize,
        }
        impl Target for PanicAt {
            fn dimension(&self) -> usize {
                1
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                let call = self.calls.fetch_add(1, Ordering::SeqCst);
                assert_ne!(call, self.at, "intentional target panic");
                gradient[0] = -position[0];
                Ok(-0.5 * position[0] * position[0])
            }
        }
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        for at in [0, 1] {
            let target = PanicAt {
                calls: AtomicUsize::new(0),
                at,
            };
            let error = sample(&target, &[0.0], &mass, &config(4)).unwrap_err();
            assert_eq!(error.kind(), ErrorKind::Panic);
            assert_eq!(error.transition(), Some(0));
        }
    }

    #[test]
    fn extreme_mass_is_rejected_before_sampling() {
        let error = DiagonalMass::from_diagonal(vec![f64::MAX]).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration);
    }

    #[test]
    fn maximum_depth_health_limit_is_enforced() {
        struct Flat;
        impl Target for Flat {
            fn dimension(&self) -> usize {
                1
            }
            fn log_density_gradient(
                &self,
                _: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                gradient[0] = 0.0;
                Ok(0.0)
            }
        }
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let healthy = sample(
            &Flat,
            &[0.0],
            &mass,
            &RunConfig::new(0, NonZeroUsize::new(3).unwrap(), 8),
        )
        .unwrap();
        assert!(
            healthy
                .diagnostics()
                .iter()
                .all(|item| item.stop() == StopReason::MaximumDepth)
        );
        let guarded =
            RunConfig::new(0, NonZeroUsize::new(3).unwrap(), 8).with_maximum_depth_stop_limit(0);
        let error = sample(&Flat, &[0.0], &mass, &guarded).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Unhealthy);
        assert_eq!(error.transition(), Some(0));
    }

    #[test]
    fn parallel_errors_choose_lowest_chain_after_all_workers_finish() {
        struct SleepingPanics;
        impl Target for SleepingPanics {
            fn dimension(&self) -> usize {
                1
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                _: &mut [f64],
            ) -> Result<f64, TargetError> {
                if position[0] == 0.0 {
                    thread::sleep(Duration::from_millis(40));
                } else {
                    thread::sleep(Duration::from_millis(1));
                }
                panic!("intentional concurrent target panic");
            }
        }
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let started = Instant::now();
        let error = sample_chains(
            &SleepingPanics,
            &[vec![0.0], vec![1.0]],
            &mass,
            &RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 5),
            NonZeroUsize::new(2).unwrap(),
        )
        .unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Panic);
        assert_eq!(error.chain(), Some(0));
        assert!(started.elapsed() >= Duration::from_millis(35));
    }

    #[test]
    fn dimension_is_panic_contained_and_cached_once() {
        struct ChangingDimension(AtomicUsize);
        impl Target for ChangingDimension {
            fn dimension(&self) -> usize {
                if self.0.fetch_add(1, Ordering::SeqCst) == 0 {
                    1
                } else {
                    panic!("dimension queried twice")
                }
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                gradient[0] = -position[0];
                Ok(-0.5 * position[0] * position[0])
            }
        }
        let target = ChangingDimension(AtomicUsize::new(0));
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        assert!(sample(&target, &[0.0], &mass, &config(4)).is_ok());
        assert_eq!(target.0.load(Ordering::SeqCst), 1);

        struct PanickingDimension;
        impl Target for PanickingDimension {
            fn dimension(&self) -> usize {
                panic!("dimension panic")
            }
            fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
                unreachable!()
            }
        }
        let error = sample(&PanickingDimension, &[0.0], &mass, &config(4)).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Panic);
    }

    #[test]
    fn panicking_cancellation_is_structured() {
        struct PanickingCancellation;
        impl Cancellation for PanickingCancellation {
            fn is_cancelled(&self) -> bool {
                panic!("cancellation panic")
            }
        }
        let target = Gaussian(1);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let control = RunControl::new().with_cancellation(&PanickingCancellation);
        let error = sample_with_control(&target, &[0.0], &mass, &config(2), &control).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Panic);
        assert_eq!(error.message(), "cancellation callback panicked");
    }

    #[test]
    fn single_chain_matches_multi_chain_zero_and_metadata_is_complete() {
        let target = Gaussian(2);
        let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
        let run = config(0x1234);
        let single = sample(&target, &[0.1, -0.2], &mass, &run).unwrap();
        let multi = sample_chains(
            &target,
            &[vec![0.1, -0.2], vec![0.1, -0.2]],
            &mass,
            &run,
            NonZeroUsize::new(2).unwrap(),
        )
        .unwrap();
        assert_eq!(single.samples(), multi.chains()[0].samples());
        assert_eq!(single.diagnostics(), multi.chains()[0].diagnostics());
        assert_eq!(single.telemetry(), multi.chains()[0].telemetry());
        assert_eq!(
            single.samples(),
            (0..single.retained())
                .flat_map(|draw| single.sample(draw).unwrap().iter().copied())
                .collect::<Vec<_>>()
        );
        assert_eq!(single.diagnostics().len(), run.discarded() + run.retained());
        let metadata = single.metadata();
        assert_eq!(metadata.base_seed(), run.seed());
        assert_eq!(metadata.effective_seed(), chain_seed(run.seed(), 0));
        assert_eq!(metadata.dimension(), 2);
        assert_eq!(metadata.discarded(), run.discarded());
        assert_eq!(metadata.retained(), run.retained());
        assert_eq!(
            metadata.maximum_depth_stop_limit(),
            run.maximum_depth_stop_limit()
        );
        assert_eq!(metadata.qualified_step_size(), DEFAULT_STEP_SIZE);
        assert_eq!(metadata.min_micro_steps(), DEFAULT_MIN_MICRO_STEPS);
        assert_eq!(
            metadata.max_refinement_levels(),
            DEFAULT_MAX_REFINEMENT_LEVELS
        );
        assert_eq!(metadata.max_error(), DEFAULT_MAX_ERROR);
        assert_eq!(metadata.max_depth(), DEFAULT_MAX_DEPTH);
        assert_eq!(metadata.initial_position(), &[0.1, -0.2]);
        assert_eq!(metadata.thread_count(), 1);
        assert_eq!(metadata.mass_diagonal(), mass.diagonal());
        assert_eq!(metadata.limits(), run.limits());
        assert_eq!(
            multi.chains()[1].metadata().initial_position(),
            &[0.1, -0.2]
        );
        assert_eq!(multi.chains()[1].metadata().thread_count(), 2);
        assert!(metadata.rng_implementation().contains("Cargo.lock"));
        assert_eq!(
            metadata.seed_derivation(),
            "splitmix64(base_seed + chain_index)"
        );
    }

    #[test]
    fn opt_in_warmup_is_deterministic_and_preserves_provenance() {
        let target = Gaussian(2);
        let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
        let run = RunConfig::new(80, NonZeroUsize::new(20).unwrap(), 0xada7)
            .with_warmup(WarmupConfig::default());
        let first = sample(&target, &[0.2, -0.3], &mass, &run).unwrap();
        let second = sample(&target, &[0.2, -0.3], &mass, &run).unwrap();
        assert_eq!(first, second);
        assert_eq!(first.metadata().initial_mass_diagonal(), mass.diagonal());
        assert_eq!(first.metadata().warmup(), run.warmup());
        assert!(
            first.metadata().qualified_step_size().is_finite()
                && first.metadata().qualified_step_size() > 0.0
        );
        assert_ne!(first.metadata().mass_diagonal(), mass.diagonal());
    }

    #[test]
    fn diagonal_warmup_tracks_gaussian_scales() {
        struct ScaledGaussian([f64; 2]);
        impl Target for ScaledGaussian {
            fn dimension(&self) -> usize {
                2
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                let mut log_density = 0.0;
                for ((value, gradient), scale) in position.iter().zip(gradient).zip(self.0) {
                    let variance = scale * scale;
                    *gradient = -*value / variance;
                    log_density -= 0.5 * value * value / variance;
                }
                Ok(log_density)
            }
        }

        let target = ScaledGaussian([0.5, 2.0]);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let run = RunConfig::new(600, NonZeroUsize::new(50).unwrap(), 991)
            .with_warmup(WarmupConfig::default());
        let output = sample(&target, &[0.1, -0.1], &mass, &run).unwrap();
        let adapted = output.metadata().mass_diagonal();
        assert!(adapted[0] > adapted[1]);
        assert!((adapted[0] - 4.0).abs() < 2.5);
        assert!((adapted[1] - 0.25).abs() < 0.25);
    }

    #[test]
    fn warmup_validation_and_fixed_mode_compatibility_are_explicit() {
        assert!(WarmupConfig::new(0.0).is_err());
        assert!(WarmupConfig::new(1.0).is_err());
        let target = Gaussian(1);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let no_discard = RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 1)
            .with_warmup(WarmupConfig::default());
        assert_eq!(
            sample(&target, &[0.0], &mass, &no_discard)
                .unwrap_err()
                .kind(),
            ErrorKind::Configuration
        );

        let legacy = config(44);
        let output = sample(&target, &[0.0], &mass, &legacy).unwrap();
        assert!(output.metadata().warmup().is_none());
        assert_eq!(output.metadata().initial_mass_diagonal(), mass.diagonal());
        assert_eq!(output.metadata().mass_diagonal(), mass.diagonal());
        assert_eq!(
            output.metadata().qualified_step_size(),
            legacy.tuning().step_size()
        );
    }

    #[test]
    fn initial_step_search_brackets_widely_scaled_starts_and_accounts_work() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        for initial in [1.0e-4, 1.0e-2, 1.0, 1.0e2] {
            let tuning = KernelTuning::new(
                initial,
                NonZeroUsize::new(3).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(2).unwrap(),
                1.0,
            )
            .unwrap();
            let warmup = WarmupConfig::default()
                .with_step_size_adaptation(false)
                .with_mass_adaptation(false)
                .with_initial_step_search(InitialStepSearchConfig::default());
            let run = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 72)
                .with_tuning(tuning)
                .with_warmup(warmup);
            let output = sample(&target, &[0.1, -0.2], &mass, &run).unwrap();
            let search = output.telemetry().initial_step_search().unwrap();
            assert_eq!(search.initial_step(), initial);
            assert_eq!(search.probes(), 4);
            assert!(search.steps() < 16);
            assert!(search.target_calls() <= 1_024);
            assert!(search.micro_steps() > 0);
            assert_eq!(output.metadata().initial_step_search(), Some(search));
            assert_eq!(
                output.metadata().qualified_step_size(),
                search.selected_step()
            );
        }
    }

    #[test]
    fn initial_step_search_is_parallel_deterministic_for_anisotropic_gaussian() {
        struct Anisotropic;
        impl Target for Anisotropic {
            fn dimension(&self) -> usize {
                2
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                gradient[0] = -position[0] / 0.01;
                gradient[1] = -position[1] / 100.0;
                Ok(-0.5 * (position[0] * position[0] / 0.01 + position[1] * position[1] / 100.0))
            }
        }
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let warmup = WarmupConfig::default()
            .with_mass_adaptation(false)
            .with_initial_step_search(InitialStepSearchConfig::default());
        let run = RunConfig::new(8, NonZeroUsize::new(2).unwrap(), 911).with_warmup(warmup);
        let positions = vec![vec![0.1, -0.1]; 4];
        let sequential = sample_chains(
            &Anisotropic,
            &positions,
            &mass,
            &run,
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        let parallel = sample_chains(
            &Anisotropic,
            &positions,
            &mass,
            &run,
            NonZeroUsize::new(4).unwrap(),
        )
        .unwrap();
        for (left, right) in sequential.chains().iter().zip(parallel.chains()) {
            assert_eq!(left.samples(), right.samples());
            assert_eq!(left.telemetry(), right.telemetry());
            assert_eq!(
                left.metadata().qualified_step_size(),
                right.metadata().qualified_step_size()
            );
        }
        let selected = sequential.chains()[0]
            .telemetry()
            .initial_step_search()
            .unwrap()
            .selected_step();
        assert!(sequential.chains().iter().all(|chain| {
            chain
                .telemetry()
                .initial_step_search()
                .is_some_and(|search| search.selected_step() == selected && search.steps() < 16)
        }));
    }

    #[test]
    fn initial_step_search_requires_coarsest_acceptance_and_uses_bracket_endpoint() {
        let target = Gaussian(1);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let tuning = KernelTuning::new(
            8.0,
            NonZeroUsize::new(3).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(3).unwrap(),
            1.0,
        )
        .unwrap();
        let warmup = WarmupConfig::default()
            .with_step_size_adaptation(false)
            .with_mass_adaptation(false)
            .with_initial_step_search(InitialStepSearchConfig::default());
        let run = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 0x51ea)
            .with_tuning(tuning)
            .with_warmup(warmup);
        let output = sample(&target, &[0.2], &mass, &run).unwrap();
        let search = output.telemetry().initial_step_search().unwrap();

        assert!(search.steps() < search_config_max_steps(&run));
        assert!(search.selected_step() < search.initial_step());
        assert_eq!(
            output.metadata().qualified_step_size(),
            search.selected_step()
        );
    }

    fn search_config_max_steps(run: &RunConfig) -> usize {
        run.warmup()
            .and_then(WarmupConfig::initial_step_search)
            .unwrap()
            .max_steps()
    }

    #[test]
    fn initial_step_search_configuration_and_resource_limits_fail_cleanly() {
        assert!(
            InitialStepSearchConfig::new(
                NonZeroUsize::new(2).unwrap(),
                NonZeroUsize::new(2).unwrap(),
                NonZeroUsize::new(1).unwrap(),
            )
            .is_err()
        );
        let target = Gaussian(1);
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let limits = ResourceLimits {
            max_target_evaluations: 1,
            ..ResourceLimits::default()
        };
        let run = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 4)
            .with_limits(limits)
            .with_warmup(
                WarmupConfig::default()
                    .with_initial_step_search(InitialStepSearchConfig::default()),
            );
        let error = sample(&target, &[0.0], &mass, &run).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::ResourceLimit);
        assert_eq!(
            error.message(),
            "target-evaluation bound exceeds its resource limit"
        );
    }

    #[test]
    fn expanding_warmup_schedule_table_is_exact() {
        let expected = [
            (1, 0, 1, vec![(0, 1)], true),
            (2, 0, 2, vec![(0, 2)], true),
            (19, 2, 18, vec![(2, 18)], true),
            (20, 3, 18, vec![(3, 18)], true),
            (50, 7, 45, vec![(7, 45)], true),
            (149, 22, 135, vec![(22, 135)], true),
            (150, 75, 100, vec![(75, 100)], false),
            (200, 75, 150, vec![(75, 100), (100, 150)], false),
            (
                1000,
                75,
                950,
                vec![(75, 100), (100, 150), (150, 250), (250, 450), (450, 950)],
                false,
            ),
        ];
        for (n, initial_end, terminal_start, windows, fallback) in expected {
            let schedule = warmup_schedule(n, &WarmupWindowConfig::default()).unwrap();
            assert_eq!(schedule.initial_fast_end(), initial_end);
            assert_eq!(schedule.terminal_fast_start(), terminal_start);
            assert_eq!(schedule.used_short_warmup_fallback(), fallback);
            assert_eq!(
                schedule
                    .windows()
                    .iter()
                    .map(|window| (window.start(), window.end()))
                    .collect::<Vec<_>>(),
                windows
            );
            assert_eq!(
                schedule
                    .windows()
                    .iter()
                    .map(|window| window.len())
                    .sum::<usize>(),
                terminal_start - initial_end
            );
        }
    }

    #[test]
    fn metric_windows_reset_report_updates_and_skip_one_sample_install() {
        let target = Gaussian(2);
        let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
        let short = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 87)
            .with_warmup(WarmupConfig::default());
        let output = sample(&target, &[0.1, -0.2], &mass, &short).unwrap();
        assert_eq!(output.metadata().mass_diagonal(), mass.diagonal());
        assert_eq!(output.telemetry().metric_updates().len(), 1);
        let update = &output.telemetry().metric_updates()[0];
        assert_eq!(update.sample_count(), 1);
        assert_eq!(update.outcome(), MetricUpdateOutcome::InsufficientSamples);

        let windows = WarmupWindowConfig::new(2, NonZeroUsize::new(2).unwrap(), 2).unwrap();
        let run = RunConfig::new(12, NonZeroUsize::new(1).unwrap(), 88).with_warmup(
            WarmupConfig::default()
                .with_windows(windows)
                .with_initial_step_search(InitialStepSearchConfig::default()),
        );
        let output = sample(&target, &[0.1, -0.2], &mass, &run).unwrap();
        assert_eq!(
            output
                .telemetry()
                .metric_updates()
                .iter()
                .map(MetricUpdateTelemetry::sample_count)
                .collect::<Vec<_>>(),
            vec![2, 6]
        );
        assert!(
            output
                .telemetry()
                .metric_updates()
                .iter()
                .all(|update| update.outcome() == MetricUpdateOutcome::Installed)
        );
        assert_eq!(output.telemetry().step_searches().len(), 3);
        assert_eq!(output.telemetry().initial_fast().transitions(), 2);
        assert_eq!(output.telemetry().slow().transitions(), 8);
        assert_eq!(output.telemetry().terminal_fast().transitions(), 2);
    }

    #[test]
    fn windowed_adaptation_is_sequential_parallel_deterministic() {
        let target = Gaussian(2);
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let windows = WarmupWindowConfig::new(2, NonZeroUsize::new(3).unwrap(), 2).unwrap();
        let run = RunConfig::new(20, NonZeroUsize::new(3).unwrap(), 0xa11ce)
            .with_warmup(WarmupConfig::default().with_windows(windows));
        let positions = vec![vec![0.1, -0.2]; 4];
        let sequential = sample_chains(
            &target,
            &positions,
            &mass,
            &run,
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        let parallel = sample_chains(
            &target,
            &positions,
            &mass,
            &run,
            NonZeroUsize::new(4).unwrap(),
        )
        .unwrap();
        for (left, right) in sequential.chains().iter().zip(parallel.chains()) {
            assert_eq!(left.samples(), right.samples());
            assert_eq!(left.telemetry(), right.telemetry());
            assert_eq!(
                left.metadata().mass_diagonal(),
                right.metadata().mass_diagonal()
            );
        }
    }

    #[test]
    fn rotated_gaussian_windowed_metric_is_finite_and_symmetric_in_scale() {
        struct RotatedGaussian;
        impl Target for RotatedGaussian {
            fn dimension(&self) -> usize {
                2
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                // Covariance eigenvalues 0.25 and 4.0, rotated by 45 degrees.
                let p00 = 2.125;
                let p01 = -1.875;
                gradient[0] = -(p00 * position[0] + p01 * position[1]);
                gradient[1] = -(p01 * position[0] + p00 * position[1]);
                Ok(0.5 * (position[0] * gradient[0] + position[1] * gradient[1]))
            }
        }

        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let run = RunConfig::new(600, NonZeroUsize::new(10).unwrap(), 0x707a7ed)
            .with_warmup(WarmupConfig::default());
        let output = sample(&RotatedGaussian, &[0.2, -0.1], &mass, &run).unwrap();
        let adapted = output.metadata().mass_diagonal();
        assert!(
            adapted
                .iter()
                .all(|value| value.is_finite() && *value > 0.0)
        );
        let ratio = adapted[0] / adapted[1];
        assert!((0.25..4.0).contains(&ratio));
        assert!(
            output
                .telemetry()
                .metric_updates()
                .iter()
                .all(|update| update.outcome() == MetricUpdateOutcome::Installed)
        );
    }

    #[test]
    fn block_mass_matches_equivalent_full_dense_operations() {
        let first = vec![2.0, 0.5, 0.5, 1.5];
        let second = vec![3.0];
        let block =
            BlockDiagonalMass::from_blocks(vec![(first.clone(), 2), (second.clone(), 1)]).unwrap();
        let full =
            DenseMass::from_matrix(vec![2.0, 0.5, 0.0, 0.5, 1.5, 0.0, 0.0, 0.0, 3.0], 3).unwrap();
        let momentum = vec![0.7, -1.2, 0.3];
        let block_drift = block.drift(&momentum).unwrap();
        let full_drift = full.drift(&momentum).unwrap();
        for (left, right) in block_drift.iter().zip(full_drift) {
            assert!((left - right).abs() <= 4.0 * f64::EPSILON);
        }
        assert!(
            (block.kinetic_energy(&momentum).unwrap() - full.kinetic_energy(&momentum).unwrap())
                .abs()
                <= 4.0 * f64::EPSILON
        );
        let mut block_rng = rand::rngs::StdRng::seed_from_u64(91);
        let mut full_rng = rand::rngs::StdRng::seed_from_u64(91);
        let block_draw = block.sample_momentum(&mut block_rng).unwrap();
        let full_draw = full.sample_momentum(&mut full_rng).unwrap();
        for (left, right) in block_draw.iter().zip(full_draw) {
            assert!((left - right).abs() <= 4.0 * f64::EPSILON);
        }
    }

    #[test]
    fn block_metric_sampling_matches_full_dense_at_small_dimension() {
        let matrix = vec![2.0, 0.4, 0.0, 0.4, 1.3, 0.0, 0.0, 0.0, 0.7];
        let full = DenseMass::from_matrix(matrix, 3).unwrap();
        let block =
            BlockDiagonalMass::from_blocks(vec![(vec![2.0, 0.4, 0.4, 1.3], 2), (vec![0.7], 1)])
                .unwrap();
        let run = RunConfig::new(2, NonZeroUsize::new(8).unwrap(), 1234)
            .with_warmup(WarmupConfig::default().with_mass_adaptation(false));
        let dense = sample_dense(&Gaussian(3), &[0.2, -0.1, 0.3], &full, &run).unwrap();
        let blocked = sample_block_dense(&Gaussian(3), &[0.2, -0.1, 0.3], &block, &run).unwrap();
        for (left, right) in dense.samples().iter().zip(blocked.samples()) {
            assert!((left - right).abs() <= 32.0 * f64::EPSILON);
        }
        assert_eq!(dense.diagnostics(), blocked.diagnostics());
    }

    #[test]
    fn block_metric_enforces_block_and_adaptation_limits() {
        let too_large = DenseMass::MAX_DIMENSION + 1;
        assert!(
            BlockDiagonalMass::from_blocks(vec![(vec![0.0; too_large * too_large], too_large)])
                .is_err()
        );
        let block = BlockDiagonalMass::from_blocks(vec![(vec![1.0], 1)]).unwrap();
        let run = RunConfig::new(2, NonZeroUsize::new(2).unwrap(), 7)
            .with_warmup(WarmupConfig::default());
        let error = sample_block_dense(&Gaussian(1), &[0.0], &block, &run).unwrap_err();
        assert!(error.to_string().contains("adaptation is unsupported"));
    }

    #[test]
    fn target_budget_is_an_exact_shared_runtime_callback_cap() {
        let target = Gaussian(1);
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(3).unwrap());
        let wrapped = budget.wrap(&target);
        let mut gradient = [0.0];
        for _ in 0..3 {
            wrapped.log_density_gradient(&[0.0], &mut gradient).unwrap();
        }
        let error = wrapped
            .log_density_gradient(&[0.0], &mut gradient)
            .unwrap_err();
        assert_eq!(budget.started(), 3);
        assert!(error.message().contains("budget exhausted"));
    }

    #[test]
    fn pathology_depth_bounds_are_exact_and_distinct_from_runtime_caps() {
        let chains = NonZeroUsize::new(4).unwrap();
        for (depth, expected) in [(8, 100_998_000), (9, 202_374_000), (10, 405_126_000)] {
            let tuning = KernelTuning::new(
                0.005,
                NonZeroUsize::new(depth).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(4).unwrap(),
                10.0,
            )
            .unwrap();
            let config = RunConfig::new(500, NonZeroUsize::new(4000).unwrap(), 1)
                .with_tuning(tuning)
                .with_warmup(WarmupConfig::new(0.9).unwrap());
            assert_eq!(
                config.worst_case_target_evaluations(chains).unwrap(),
                expected
            );
        }
        let tuning = KernelTuning::new(
            0.005,
            NonZeroUsize::new(10).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(4).unwrap(),
            10.0,
        )
        .unwrap();
        let config = RunConfig::new(500, NonZeroUsize::new(4000).unwrap(), 1)
            .with_tuning(tuning)
            .with_warmup(WarmupConfig::new(0.9).unwrap())
            .with_research_target_evaluation_limit(
                ResearchTargetEvaluationLimit::new(NonZeroUsize::new(405_126_000).unwrap())
                    .unwrap(),
            );
        let positions = vec![vec![0.0]; 4];
        let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
        let report = preflight_chains(&Gaussian(1), &positions, &mass, &config).unwrap();
        assert_eq!(report.worst_case_target_evaluations(), 405_126_000);
        assert_eq!(report.admission_ceiling(), 405_126_000);
    }

    #[test]
    fn structured_blocks_match_equivalent_dense_operators() {
        let bidiagonal = StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: vec![2.0, 1.5, 0.8],
            subdiagonal: vec![0.3, -0.2],
        };
        let ar1 = StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.2, 0.7, 2.0],
            rho: 0.5,
        };
        for block in [bidiagonal, ar1] {
            let n = block.dimension();
            let mut matrix = vec![0.0; n * n];
            for column in 0..n {
                let mut basis = vec![0.0; n];
                basis[column] = 1.0;
                let l = block.multiply_lower(&basis);
                for i in 0..n {
                    for j in 0..n {
                        matrix[i * n + j] += l[i] * l[j];
                    }
                }
            }
            let dense = DenseMass::from_matrix(matrix, n).unwrap();
            let structured = StructuredBlockMass::new(vec![block]).unwrap();
            let p = vec![0.4, -0.7, 1.1];
            for (a, b) in structured
                .drift(&p)
                .unwrap()
                .iter()
                .zip(dense.drift(&p).unwrap())
            {
                assert!((a - b).abs() < 1e-12);
            }
            assert!(
                (structured.kinetic_energy(&p).unwrap() - dense.kinetic_energy(&p).unwrap()).abs()
                    < 1e-12
            );
            let mut left = rand::rngs::StdRng::seed_from_u64(77);
            let mut right = rand::rngs::StdRng::seed_from_u64(77);
            let a = structured.sample_momentum(&mut left).unwrap();
            let b = dense.sample_momentum(&mut right).unwrap();
            for (a, b) in a.iter().zip(b) {
                assert!((a - b).abs() < 1e-12);
            }
        }
    }

    #[test]
    fn low_rank_arrowhead_matches_dense_sampling_velocity_energy_and_reversibility() {
        let global = vec![vec![1.4, 0.0], vec![0.2, 0.9]];
        let path = StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: vec![1.1, 0.8, 1.3],
            subdiagonal: vec![0.15, -0.1],
        };
        let u = vec![vec![0.2], vec![-0.3], vec![0.1]];
        let v = vec![vec![0.4], vec![-0.25]];
        let mass =
            LowRankArrowheadMass::new(global.clone(), path.clone(), u.clone(), v.clone()).unwrap();
        let n = mass.dimension();
        let mut lower = vec![0.0; n * n];
        for i in 0..2 {
            for j in 0..=i {
                lower[i * n + j] = global[i][j];
            }
        }
        for column in 0..3 {
            let mut basis = vec![0.0; 3];
            basis[column] = 1.0;
            let p_column = path.multiply_lower(&basis);
            for i in 0..3 {
                lower[(i + 2) * n + column + 2] = p_column[i];
            }
        }
        for column in 0..2 {
            let coupling = u
                .iter()
                .map(|row| row[0] * v[column][0])
                .collect::<Vec<_>>();
            let p_column = path.multiply_lower(&coupling);
            for i in 0..3 {
                lower[(i + 2) * n + column] = p_column[i];
            }
        }
        let mut covariance = vec![0.0; n * n];
        for i in 0..n {
            for j in 0..n {
                covariance[i * n + j] = (0..n).map(|k| lower[i * n + k] * lower[j * n + k]).sum();
            }
        }
        let dense = DenseMass::from_matrix(covariance.clone(), n).unwrap();
        let momentum = vec![0.3, -0.8, 0.5, 1.2, -0.4];
        for (a, b) in mass
            .drift(&momentum)
            .unwrap()
            .iter()
            .zip(dense.drift(&momentum).unwrap())
        {
            assert!((a - b).abs() < 1e-11);
        }
        assert!(
            (mass.kinetic_energy(&momentum).unwrap() - dense.kinetic_energy(&momentum).unwrap())
                .abs()
                < 1e-11
        );
        let mut left = rand::rngs::StdRng::seed_from_u64(814);
        let mut right = rand::rngs::StdRng::seed_from_u64(814);
        for (a, b) in mass
            .sample_momentum(&mut left)
            .unwrap()
            .iter()
            .zip(dense.sample_momentum(&mut right).unwrap())
        {
            assert!((a - b).abs() < 1e-11);
        }
        let mut seeded = rand::rngs::StdRng::seed_from_u64(991);
        let mut empirical = vec![0.0; n * n];
        let draws = 50_000;
        for _ in 0..draws {
            let sample = mass.sample_momentum(&mut seeded).unwrap();
            for i in 0..n {
                for j in 0..n {
                    empirical[i * n + j] += sample[i] * sample[j] / draws as f64;
                }
            }
        }
        assert!(
            empirical
                .iter()
                .zip(&covariance)
                .all(|(observed, expected)| (observed - expected).abs() < 0.04)
        );
        let q0 = vec![0.2, -0.1, 0.4, -0.3, 0.7];
        let p0 = momentum;
        let step = |q: &[f64], p: &[f64], epsilon: f64| {
            let half = p
                .iter()
                .zip(q)
                .map(|(p, q)| p - 0.5 * epsilon * q)
                .collect::<Vec<_>>();
            let velocity = mass.drift(&half).unwrap();
            let q1 = q
                .iter()
                .zip(velocity)
                .map(|(q, v)| q + epsilon * v)
                .collect::<Vec<_>>();
            let p1 = half
                .iter()
                .zip(&q1)
                .map(|(p, q)| p - 0.5 * epsilon * q)
                .collect::<Vec<_>>();
            (q1, p1)
        };
        let (q1, p1) = step(&q0, &p0, 0.03);
        let (q2, p2) = step(&q1, &p1, -0.03);
        assert!(q0.iter().zip(q2).all(|(a, b)| (a - b).abs() < 1e-12));
        assert!(p0.iter().zip(p2).all(|(a, b)| (a - b).abs() < 1e-12));
    }

    #[test]
    fn selected_subspace_arrowhead_matches_exact_dense_factor() {
        let basis = vec![vec![0.6], vec![0.8]];
        let mass = LowRankArrowheadMass::new_with_path_subspace(
            vec![vec![1.2]],
            StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: vec![1.0, 1.0],
                subdiagonal: vec![0.0],
            },
            basis.clone(),
            vec![vec![0.3]],
            basis.clone(),
            vec![vec![1.4]],
        )
        .unwrap();
        // Q = I + V(S-I)V', and the lower-left block is V * 0.3.
        let q = [
            [1.0 + 0.4 * 0.36, 0.4 * 0.48],
            [0.4 * 0.48, 1.0 + 0.4 * 0.64],
        ];
        let lower = [
            1.2,
            0.0,
            0.0,
            0.6 * 0.3,
            q[0][0],
            q[0][1],
            0.8 * 0.3,
            q[1][0],
            q[1][1],
        ];
        let covariance = (0..3)
            .flat_map(|i| {
                (0..3).map(move |j| (0..3).map(|k| lower[i * 3 + k] * lower[j * 3 + k]).sum())
            })
            .collect::<Vec<f64>>();
        let dense = DenseMass::from_matrix(covariance, 3).unwrap();
        let momentum = [0.4, -0.7, 0.2];
        for (actual, expected) in mass
            .drift(&momentum)
            .unwrap()
            .iter()
            .zip(dense.drift(&momentum).unwrap())
        {
            assert!((actual - expected).abs() < 2.0e-14);
        }
        assert!(
            (mass.kinetic_energy(&momentum).unwrap() - dense.kinetic_energy(&momentum).unwrap())
                .abs()
                < 2.0e-14
        );
        let raw_basis = basis.iter().map(|row| row[0]).collect::<Vec<_>>();
        assert!((raw_basis.iter().map(|x| x * x).sum::<f64>() - 1.0).abs() < 1.0e-15);
    }

    #[test]
    fn low_rank_arrowhead_fails_closed_on_spd_rank_and_resource_errors() {
        let path = || StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: vec![1.0, 1.0],
            subdiagonal: vec![0.0],
        };
        assert!(
            LowRankArrowheadMass::new(
                vec![vec![0.0]],
                path(),
                vec![vec![0.1], vec![0.2]],
                vec![vec![0.3]]
            )
            .is_err()
        );
        assert!(
            LowRankArrowheadMass::new(
                vec![vec![1.0]],
                path(),
                vec![vec![0.0; 17], vec![0.0; 17]],
                vec![vec![0.0; 17]]
            )
            .is_err()
        );
        assert!(
            LowRankArrowheadMass::new(
                vec![vec![1.0]],
                path(),
                vec![vec![f64::NAN], vec![0.0]],
                vec![vec![0.0]]
            )
            .is_err()
        );
    }

    #[test]
    fn structured_validation_and_sampling_are_deterministic() {
        assert!(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
                scale: vec![1.0],
                rho: 1.0
            }])
            .is_err()
        );
        let mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.0, 2.0],
            rho: 0.5,
        }])
        .unwrap();
        let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 99)
            .with_warmup(WarmupConfig::new(0.9).unwrap().with_mass_adaptation(false));
        let starts = vec![vec![0.1, -0.2]];
        let a = sample_chains_structured(
            &Gaussian(2),
            &starts,
            &mass,
            &config,
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        let b = sample_chains_structured(
            &Gaussian(2),
            &starts,
            &mass,
            &config,
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        assert_eq!(a.chains()[0].samples(), b.chains()[0].samples());
        assert_eq!(a.chains()[0].diagnostics(), b.chains()[0].diagnostics());
        assert_eq!(a.chains()[0].telemetry(), b.chains()[0].telemetry());
        assert!(a.chains()[0].diagnostics().iter().all(|diagnostic| {
            diagnostic.initial_hamiltonian().is_finite()
                && diagnostic.minimum_hamiltonian().is_finite()
                && diagnostic.maximum_hamiltonian().is_finite()
                && diagnostic.maximum_absolute_energy_error().is_finite()
        }));
    }

    #[test]
    fn structured_bidiagonal_spd_and_resource_limits_fail_closed() {
        assert!(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: vec![1.0, 0.0],
                subdiagonal: vec![0.2],
            },])
            .is_err()
        );
        assert!(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: vec![1.0; BlockDiagonalMass::MAX_TOTAL_DIMENSION + 1],
                subdiagonal: vec![0.0; BlockDiagonalMass::MAX_TOTAL_DIMENSION],
            },])
            .is_err()
        );
        let too_many = (0..=BlockDiagonalMass::MAX_BLOCKS)
            .map(|_| StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: vec![1.0],
                subdiagonal: vec![],
            })
            .collect();
        assert!(StructuredBlockMass::new(too_many).is_err());
    }

    #[test]
    fn structured_preflight_is_exact_and_starts_zero_callbacks() {
        struct CountingGaussian(AtomicUsize);
        impl Target for CountingGaussian {
            fn dimension(&self) -> usize {
                2
            }
            fn log_density_gradient(
                &self,
                position: &[f64],
                gradient: &mut [f64],
            ) -> Result<f64, TargetError> {
                self.0.fetch_add(1, Ordering::Relaxed);
                gradient.copy_from_slice(position);
                Ok(-0.5 * position.iter().map(|x| x * x).sum::<f64>())
            }
        }
        let target = CountingGaussian(AtomicUsize::new(0));
        let mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.0, 2.0],
            rho: 0.5,
        }])
        .unwrap();
        let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 99)
            .with_warmup(WarmupConfig::new(0.9).unwrap().with_mass_adaptation(false));
        let report =
            preflight_chains_structured(&target, &[vec![0.1, -0.2]], &mass, &config).unwrap();
        assert_eq!(report.dimension(), 2);
        assert_eq!(report.chains(), 1);
        assert_eq!(target.0.load(Ordering::Relaxed), 0);
    }

    #[test]
    fn trajectory_acceptance_dual_averaging_is_opt_in_and_default_identical() {
        let base = WarmupConfig::new(0.9)
            .unwrap()
            .with_mass_adaptation(false)
            .with_telemetry_checkpoints((0..8).collect())
            .unwrap();
        let config =
            RunConfig::new(8, NonZeroUsize::new(4).unwrap(), 812).with_warmup(base.clone());
        let explicit =
            RunConfig::new(8, NonZeroUsize::new(4).unwrap(), 812)
                .with_warmup(base.clone().with_dual_averaging_acceptance(
                    DualAveragingAcceptance::CurrentCoarseEndpoint,
                ));
        let trajectory = RunConfig::new(8, NonZeroUsize::new(4).unwrap(), 812).with_warmup(
            base.with_dual_averaging_acceptance(DualAveragingAcceptance::AcceptedTrajectory),
        );
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let a = sample(&Gaussian(2), &[0.1, -0.2], &mass, &config).unwrap();
        let b = sample(&Gaussian(2), &[0.1, -0.2], &mass, &explicit).unwrap();
        let c = sample(&Gaussian(2), &[0.1, -0.2], &mass, &trajectory).unwrap();
        assert_eq!(a, b);
        assert!(c.metadata().qualified_step_size().is_finite());
        assert_eq!(c.samples().len(), a.samples().len());
    }

    #[test]
    fn paper_quantile_and_delta_rule_are_closed_form() {
        assert_eq!(sample_quantile(&mut [], 0.5), None);
        assert_eq!(sample_quantile(&mut [3.0], 0.95), Some(3.0));
        assert_eq!(
            sample_quantile(&mut [5.0, 1.0, 3.0, 2.0, 4.0], 0.5),
            Some(3.0)
        );
        let q = sample_quantile(&mut [5.0, 1.0, 3.0, 2.0, 4.0], 0.95).unwrap();
        assert!((q - 4.8).abs() < 1e-12);

        let paper = PaperAdaptationConfig::new(2.0, 0.95, 0.8)
            .unwrap()
            .with_minimum_orbits(NonZeroUsize::new(5).unwrap());
        let mut window = PaperWindow::new();
        for range in [0.5, 1.0, 3.0, 2.0, 4.0] {
            window.record(range, Some(1.0));
        }
        // delta = 0.5: K = range / 0.5, q_{0.95}(K) = 2 * 3.8 = 7.6, so
        // delta_new = 2 / 7.6.
        let (orbits, inflation, range_quantile, candidate, outcome) = window.candidate(&paper, 0.5);
        assert_eq!(orbits, 5);
        assert!((inflation.unwrap() - 7.6).abs() < 1e-12);
        assert!((range_quantile.unwrap() - 3.8).abs() < 1e-12);
        assert!((candidate.unwrap() - 2.0 / 7.6).abs() < 1e-12);
        assert_eq!(outcome, PaperAdaptationOutcome::Installed);
        assert_eq!(window.unrefined_mean(), Some(1.0));

        // Small inflation is floored at one, so delta never exceeds Delta.
        let mut calm = PaperWindow::new();
        for range in [0.01, 0.02, 0.03, 0.04, 0.05] {
            calm.record(range, None);
        }
        let (_, inflation, _, candidate, outcome) = calm.candidate(&paper, 1.0);
        assert!(inflation.unwrap() < 1.0);
        assert_eq!(candidate, Some(2.0));
        assert_eq!(outcome, PaperAdaptationOutcome::Installed);
        assert_eq!(calm.unrefined_mean(), None);

        // Too few orbits and the disabled rule leave delta untouched.
        let mut sparse = PaperWindow::new();
        sparse.record(1.0, Some(0.5));
        let (orbits, _, _, candidate, outcome) = sparse.candidate(&paper, 1.0);
        assert_eq!((orbits, candidate), (1, None));
        assert_eq!(outcome, PaperAdaptationOutcome::InsufficientOrbits);
        let disabled = paper.with_local_error_adaptation(false);
        let (_, _, _, candidate, outcome) = window.candidate(&disabled, 0.5);
        assert_eq!(candidate, None);
        assert_eq!(outcome, PaperAdaptationOutcome::Disabled);

        // Nonfinite ranges are ignored rather than recorded.
        let mut nonfinite = PaperWindow::new();
        nonfinite.record(f64::INFINITY, None);
        nonfinite.record(f64::NAN, None);
        nonfinite.record(-1.0, None);
        assert_eq!(nonfinite.energy_ranges.len(), 0);
    }

    #[test]
    fn paper_step_statistic_pools_cumulatively_and_resets_once() {
        let mut window = PaperWindow::new();
        // Per-transition: the statistic is the fraction itself; the running
        // mean still accumulates in the background.
        assert_eq!(
            window.step_statistic(PaperStepStatistic::PerTransition, Some(1.0)),
            Some(1.0)
        );
        assert_eq!(
            window.step_statistic(PaperStepStatistic::PerTransition, None),
            None
        );
        assert_eq!(window.cumulative_mean(), Some(1.0));
        // Cumulative: running mean over recorded fractions; `None` inputs
        // neither count nor clear the mean.
        assert_eq!(
            window.step_statistic(PaperStepStatistic::Cumulative, Some(0.0)),
            Some(0.5)
        );
        assert_eq!(
            window.step_statistic(PaperStepStatistic::Cumulative, None),
            Some(0.5)
        );
        let third = window
            .step_statistic(PaperStepStatistic::Cumulative, Some(0.5))
            .unwrap();
        assert!((third - 0.5).abs() < 1e-15);
        // Window resets do not touch the running mean; only the explicit
        // initial-fast reset does.
        window.record(1.0, Some(0.25));
        window.reset();
        assert_eq!(window.cumulative_mean(), Some(0.5));
        window.reset_cumulative();
        assert_eq!(window.cumulative_mean(), None);
        assert_eq!(
            window.step_statistic(PaperStepStatistic::Cumulative, None),
            None
        );
        let config = PaperAdaptationConfig::default();
        assert_eq!(config.step_statistic(), PaperStepStatistic::PerTransition);
        assert_eq!(
            config.restart_policy(),
            PaperRestartPolicy::ContinueThroughLocalErrorInstall
        );
        let config = config
            .with_step_statistic(PaperStepStatistic::Cumulative)
            .with_restart_policy(PaperRestartPolicy::RestartOnLocalErrorInstall);
        assert_eq!(config.step_statistic(), PaperStepStatistic::Cumulative);
        assert_eq!(
            config.restart_policy(),
            PaperRestartPolicy::RestartOnLocalErrorInstall
        );
    }

    #[test]
    fn paper_step_rule_moves_with_the_unrefined_fraction() {
        let mut too_few_refinements = DualAveraging::new(0.1, 0.8);
        let mut step = 0.1;
        for _ in 0..20 {
            step = too_few_refinements.update(1.0);
        }
        assert!(step > 0.1, "step must grow when no leaf needs refinement");
        let mut too_many_refinements = DualAveraging::new(0.1, 0.8);
        for _ in 0..20 {
            step = too_many_refinements.update(0.0);
        }
        assert!(step < 0.1, "step must shrink when every leaf refines");
        // Exactly on target, the Hoffman--Gelman iterate sits at the
        // reference `mu = log(10 * step)`, as in the acceptance-driven rule.
        let mut on_target = DualAveraging::new(0.1, 0.8);
        for _ in 0..20 {
            step = on_target.update(0.8);
        }
        assert!((step - 1.0).abs() < 1e-9);
    }

    #[test]
    fn unrefined_fraction_counts_built_leaves_only() {
        let mut work = TransitionWorkTelemetry::default();
        assert_eq!(unrefined_leaf_fraction(&work), None);
        // Eight leaves attempted, all invalid at the coarsest level: nothing
        // was built, so no statistic (this previously read as 1.0).
        work.histograms.refinement_level_attempts = vec![8];
        work.leaves_attempted = 8;
        work.rejections.invalid_forward_evaluation = 8;
        assert_eq!(unrefined_leaf_fraction(&work), None);
        // Eight built at the coarsest level.
        work.rejections.invalid_forward_evaluation = 0;
        work.leaves_built = 8;
        work.histograms.refinement_level_built = vec![8];
        assert_eq!(unrefined_leaf_fraction(&work), Some(1.0));
        // Six built at level 0, one at level 1, one rejected: the rejected
        // attempt is in neither numerator nor denominator.
        work.histograms.refinement_level_attempts = vec![8, 2, 1];
        work.leaves_built = 7;
        work.histograms.refinement_level_built = vec![6, 1];
        assert_eq!(unrefined_leaf_fraction(&work), Some(6.0 / 7.0));
        // A missing built histogram never yields a fraction above one.
        work.histograms.refinement_level_built = vec![];
        assert_eq!(unrefined_leaf_fraction(&work), Some(0.0));
        work.histograms.refinement_level_built = vec![9];
        assert_eq!(unrefined_leaf_fraction(&work), Some(1.0));
    }

    #[test]
    fn paper_step_is_bounded_relative_to_the_initial_step() {
        assert_eq!(clamp_paper_step(0.5, 0.1), 0.5);
        assert_eq!(
            clamp_paper_step(1.0e9, 0.1),
            0.1 * PAPER_STEP_RELATIVE_BOUND
        );
        assert_eq!(
            clamp_paper_step(1.0e-9, 0.1),
            0.1 / PAPER_STEP_RELATIVE_BOUND
        );
        // Dual averaging alone would run to its absolute ceiling under a
        // permanently unrefined statistic; the paper-mode bound holds it.
        let mut dual = DualAveraging::new(0.1, 0.8);
        let mut step = 0.1;
        for _ in 0..2_000 {
            step = clamp_paper_step(dual.update(1.0), 0.1);
        }
        assert_eq!(step, 0.1 * PAPER_STEP_RELATIVE_BOUND);
        assert!(dual.final_step() > step);
    }

    #[test]
    fn paper_adaptation_configuration_fails_closed() {
        assert!(PaperAdaptationConfig::new(0.0, 0.95, 0.8).is_err());
        assert!(PaperAdaptationConfig::new(2.0, 1.0, 0.8).is_err());
        assert!(PaperAdaptationConfig::new(2.0, 0.95, 0.0).is_err());
        assert!(PaperAdaptationConfig::new(f64::NAN, 0.95, 0.8).is_err());
        let paper = PaperAdaptationConfig::default();
        assert_eq!(
            paper.global_energy_bound(),
            DEFAULT_PAPER_GLOBAL_ENERGY_BOUND
        );
        assert_eq!(
            paper.quantile_probability(),
            DEFAULT_PAPER_QUANTILE_PROBABILITY
        );
        assert_eq!(
            paper.unrefined_fraction_target(),
            DEFAULT_PAPER_UNREFINED_FRACTION_TARGET
        );
        assert!(paper.adapts_local_error());
        assert_eq!(paper.minimum_orbits(), DEFAULT_PAPER_MINIMUM_ORBITS);

        let warmup = WarmupConfig::default().with_paper_adaptation(paper);
        assert_eq!(warmup.paper_adaptation(), Some(&paper));
        assert!(WarmupConfig::default().paper_adaptation().is_none());
        let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
        let single_level = KernelTuning::new(
            0.5,
            NonZeroUsize::new(3).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            1.0,
        )
        .unwrap();
        let config = RunConfig::new(4, NonZeroUsize::new(2).unwrap(), 3)
            .with_tuning(single_level)
            .with_warmup(warmup.clone());
        assert_eq!(
            sample(&Gaussian(2), &[0.0, 0.0], &mass, &config)
                .unwrap_err()
                .kind(),
            ErrorKind::Configuration
        );
        let dense = DenseMass::identity(NonZeroUsize::new(2).unwrap()).unwrap();
        let dense_config = RunConfig::new(4, NonZeroUsize::new(2).unwrap(), 3).with_warmup(warmup);
        assert_eq!(
            sample_dense(&Gaussian(2), &[0.0, 0.0], &dense, &dense_config)
                .unwrap_err()
                .kind(),
            ErrorKind::Configuration
        );
    }
}
