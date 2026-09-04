//! The recommended sampling API: one builder, one result type.
//!
//! [`Sampler`] configures a run (warmup, draws, chains, seed, threads,
//! [`Metric`], [`Adaptation`], [`Tuning`], [`Limits`]) and
//! [`Sampler::run`] executes it, returning a [`Posterior`]. Every path is a
//! thin wrapper over one entry point of [`crate::walnutpie`]: the builder
//! chooses the facade and assembles its arguments, and the draws are
//! bit-identical to calling that facade directly with the same
//! configuration. Kernel behaviour, seeding, and telemetry are documented in
//! the [`walnutpie`](crate::walnutpie) module; nothing here changes them.
//!
//! ```rust,ignore
//! use owalnuts::sampler::{Metric, Sampler, Target, TargetError};
//!
//! let posterior = Sampler::new()
//!     .warmup(1_000)
//!     .draws(2_000)
//!     .seed(0x5eed)
//!     .metric(Metric::diagonal())
//!     .run(&target, &starts)?;
//! for draw in posterior.draws() {
//!     // draw: &[f64], one retained position
//! }
//! ```
//!
//! # Which facade runs
//!
//! | [`Metric`] | Adapts mass | `walnutpie` entry point |
//! |---|---|---|
//! | `Identity` | no | `sample_chains_with_control` with `DiagonalMass::identity` |
//! | `Diagonal { adapt, .. }` | `adapt` | `sample_chains_with_control` |
//! | `Dense { adapt, .. }` | `adapt` | `sample_chains_dense_with_control` |
//! | `Structured(mass)` | no | `sample_chains_structured_with_control` |
//! | `StructuredRefresh { .. }` | yes | `sample_chains_structured_refresh` |
//!
//! With [`Limits::max_target_evaluations`] (or
//! [`Limits::admit_worst_case`]) the diagonal and dense paths use their
//! `_with_target_budget_and_control` variants, which admit the run against
//! that exact ceiling and enforce it at runtime; the structured paths wrap the
//! target in the same runtime [`TargetEvaluationBudget`] (there is no
//! budgeted admission variant for them).
//!
//! [`Init`] chooses the starting positions: [`Init::Given`] (the positions
//! passed to [`Sampler::run`]) or [`Init::Uniform`], the CmdStan rule of
//! uniform(-r, r) unconstrained starts redrawn until the log density and
//! gradient are finite ([`Sampler::run_with_init`],
//! [`Sampler::run_from_random_starts`]).
//!
//! [`Adaptation`] selects the warmup rules: acceptance-driven dual averaging
//! (`WarmupConfig::new(target_accept)`, the default), the JMLR Appendix C
//! rules (`WarmupConfig::default().with_paper_adaptation(..)`), or none. The
//! metric decides `WarmupConfig::with_mass_adaptation`. The sampler's own
//! modes apply [`DEFAULT_WARMUP_EXHAUSTION`],
//! [`DEFAULT_METRIC_REGULARIZATION`], and the disabled
//! [`DEFAULT_CHAIN_RESCUE`] to the configuration they build;
//! [`Adaptation::Custom`] is used as given and is the explicit chain-rescue
//! opt-in.
//!
//! [`TargetEvaluationBudget`]: crate::walnutpie::TargetEvaluationBudget

use std::fmt;
use std::num::NonZeroUsize;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::Arc;
use std::time::{Duration, Instant};

use rand::{Rng, SeedableRng, rngs::SmallRng};

#[cfg(feature = "research")]
pub use crate::walnutpie::NonfinitePositionPolicy;
#[cfg(feature = "research")]
pub use crate::walnutpie::ReverseCoarseningOrder;
pub use crate::walnutpie::{
    Cancellation, ChainOutput, Error, ErrorKind, PaperAdaptationConfig, RunMetadata, RunTelemetry,
    StructuredBlockMass, StructuredCovarianceBlock, StructuredMetricRefresh,
    StructuredRefreshConfig, StructuredRefreshUpdate, Target, TargetError, WarmupConfig,
    WindowSummary,
};
use crate::walnutpie::{
    ChainRescueConfig, DEFAULT_DIVERGENCE_THRESHOLD, DenseMass, DiagonalMass,
    DiagonalMetricRegularization, ExhaustionRule, KernelOptions, KernelTuning, MultiChainOutput,
    RunConfig, RunControl, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, UTurnRule,
    sample_chains_dense_with_control, sample_chains_dense_with_target_budget_and_control,
    sample_chains_structured_refresh, sample_chains_structured_with_control,
    sample_chains_with_control, sample_chains_with_target_budget_and_control,
};

/// Momentum covariance `M` and whether warmup adapts it.
///
/// Fixed values are validated when the run starts. `initial` vectors are the
/// diagonal (length `dimension`) or the row-major dense matrix (length
/// `dimension * dimension`); `None` means the identity.
#[non_exhaustive]
pub enum Metric {
    /// Identity mass, never adapted.
    Identity,
    /// Diagonal mass, adapted during warmup when `adapt` is set.
    Diagonal {
        /// Estimate the diagonal from warmup draws (Welford, regularized).
        adapt: bool,
        /// Starting or fixed diagonal; `None` is the identity.
        initial: Option<Vec<f64>>,
    },
    /// Dense mass, adapted during warmup when `adapt` is set.
    Dense {
        /// Estimate the full covariance from warmup draws.
        adapt: bool,
        /// Starting or fixed row-major matrix; `None` is the identity.
        initial: Option<Vec<f64>>,
    },
    /// Fixed structured block mass (bidiagonal Cholesky or scaled AR(1)
    /// blocks), run in Cholesky coordinates.
    Structured(StructuredBlockMass),
    /// Structured block mass rebuilt at every completed slow warmup window by
    /// `refresh`, run directly in original coordinates. Requires warmup and an
    /// adaptation mode other than [`Adaptation::None`]; the paper rules are
    /// not supported on this path.
    StructuredRefresh {
        /// Operator installed before the first transition.
        initial: StructuredBlockMass,
        /// Builds the candidate operator from a window summary.
        refresh: Box<dyn StructuredMetricRefresh>,
        /// Minimum window sample count and dual-averaging restart policy.
        config: StructuredRefreshConfig,
    },
}

impl Metric {
    /// Adaptive diagonal mass starting from the identity (the default).
    pub fn diagonal() -> Self {
        Self::Diagonal {
            adapt: true,
            initial: None,
        }
    }

    /// Fixed diagonal mass.
    pub fn fixed_diagonal(diagonal: Vec<f64>) -> Self {
        Self::Diagonal {
            adapt: false,
            initial: Some(diagonal),
        }
    }

    /// Adaptive dense mass starting from the identity.
    pub fn dense() -> Self {
        Self::Dense {
            adapt: true,
            initial: None,
        }
    }

    /// Fixed dense mass from a row-major `dimension * dimension` matrix.
    pub fn fixed_dense(matrix: Vec<f64>) -> Self {
        Self::Dense {
            adapt: false,
            initial: Some(matrix),
        }
    }

    /// Boundary-refreshed structured mass with the default refresh config.
    pub fn structured_refresh(
        initial: StructuredBlockMass,
        refresh: impl StructuredMetricRefresh + 'static,
    ) -> Self {
        Self::StructuredRefresh {
            initial,
            refresh: Box::new(refresh),
            config: StructuredRefreshConfig::default(),
        }
    }

    fn adapts_mass(&self) -> bool {
        match self {
            Self::Identity | Self::Structured(_) => false,
            Self::Diagonal { adapt, .. } | Self::Dense { adapt, .. } => *adapt,
            Self::StructuredRefresh { .. } => true,
        }
    }

    /// Only the identity and diagonal metrics use the multi-chain driver that
    /// supports an optional warmup-time chain rescue.
    fn supports_chain_rescue(&self) -> bool {
        matches!(self, Self::Identity | Self::Diagonal { .. })
    }
}

impl Default for Metric {
    fn default() -> Self {
        Self::diagonal()
    }
}

impl fmt::Debug for Metric {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Identity => f.write_str("Identity"),
            Self::Diagonal { adapt, initial } => f
                .debug_struct("Diagonal")
                .field("adapt", adapt)
                .field("initial", initial)
                .finish(),
            Self::Dense { adapt, initial } => f
                .debug_struct("Dense")
                .field("adapt", adapt)
                .field("initial", initial)
                .finish(),
            Self::Structured(mass) => f.debug_tuple("Structured").field(mass).finish(),
            Self::StructuredRefresh {
                initial, config, ..
            } => f
                .debug_struct("StructuredRefresh")
                .field("initial", initial)
                .field("config", config)
                .finish_non_exhaustive(),
        }
    }
}

/// Warmup rules applied during the discarded transitions.
///
/// The default is dual averaging (`WarmupConfig::new(target)`) with the
/// sampler's warmup exhaustion rule ([`DEFAULT_WARMUP_EXHAUSTION`]),
/// diagonal-metric regularisation ([`DEFAULT_METRIC_REGULARIZATION`], Stan's
/// prior since the post-WP31 default change), and no automatic warmup-time
/// chain rescue ([`DEFAULT_CHAIN_RESCUE`], the post-WP36 decision). The
/// Stan-parity warmup (`WarmupConfig::stan_style`) is opt-in through
/// [`Adaptation::Custom`]: in `STUDIES/adaptation_parity_v1` it reached a
/// 2.0x geometric-mean ESS-per-gradient gain over the default on nine
/// posteriordb models but lost 12-16 % on three of them and failed the
/// R-hat gate on two, so it did not meet the preregistered rule for a
/// default.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub enum Adaptation {
    /// No adaptation: warmup transitions run the fixed kernel and are
    /// discarded. Incompatible with metrics that adapt.
    None,
    /// Nesterov dual averaging of the step size toward `target_accept`, plus
    /// windowed mass estimation when the metric adapts (the default,
    /// `target_accept = 0.8`).
    DualAveraging {
        /// Target acceptance statistic, strictly between zero and one.
        target_accept: f64,
    },
    /// The JMLR Appendix C rules: the K-quantile rule for `max_error`
    /// (`delta`) and dual averaging of the step toward an unrefined-leaf
    /// fraction. Supported by the identity, diagonal, and structured (fixed)
    /// metrics.
    Paper(PaperAdaptationConfig),
    /// Any `walnutpie::WarmupConfig`; its mass-adaptation flag is replaced by
    /// what the metric requires. This is also where the opt-in warmup-time
    /// chain rescue lives (`WarmupConfig::with_chain_rescue`,
    /// `STUDIES/chain_rescue_v1` and `chain_rescue_v2`): on the diagonal and identity metrics with
    /// at least two chains it synchronises warmup at slow-window boundaries
    /// and re-seeds or pools outlier chains; retained draws are untouched.
    Custom(WarmupConfig),
}

impl Default for Adaptation {
    fn default() -> Self {
        Self::DualAveraging { target_accept: 0.8 }
    }
}

/// The exhaustion rule the sampler's own adaptation modes
/// ([`Adaptation::DualAveraging`], [`Adaptation::Paper`]) apply to the
/// discarded transitions: Stan's one-sided divergence test, so that a chain
/// started where every leaf exhausts slides out instead of freezing
/// (`STUDIES/freeze_mode_v1`). Retained transitions keep
/// [`Tuning::kernel_options`] (the frozen two-sided exhaustion rule by default), whose
/// funnel tail mass is validated; [`Adaptation::Custom`] configurations are
/// used as given.
pub const DEFAULT_WARMUP_EXHAUSTION: ExhaustionRule = ExhaustionRule::AcceptUnlessDivergent;

/// The diagonal-metric regularisation the sampler's own adaptation modes
/// ([`Adaptation::DualAveraging`], [`Adaptation::Paper`]) apply when the
/// metric adapts: Stan's prior, `(n / (n + 5)) * var + 1e-3 * (5 / (n + 5))`.
/// **Default change, post hoc after WP31** (`STUDIES/joint_default_v1`; the
/// preregistered rule there was not met on two cells no option passes, and
/// the flip was decided afterwards and validated on fresh seeds in
/// `STUDIES/posteriordb_bench_v5`, WP32). The `v10` facade default,
/// [`DiagonalMetricRegularization::TowardUnit`], floors small posterior
/// variances at 0.01 and collapses the step on `sblrc` / `arma11`
/// (`STUDIES/step_collapse_v1`); it stays the `walnutpie::WarmupConfig`
/// default and is the opt-in here through [`Adaptation::Custom`]. Use it
/// together with [`DEFAULT_U_TURN_RULE`]: under the endpoint U-turn rule
/// Stan's prior alone is unstable on `earnings` (WP31).
pub const DEFAULT_METRIC_REGULARIZATION: DiagonalMetricRegularization =
    DiagonalMetricRegularization::Stan;

/// The no-U-turn rule of [`Tuning::default`]: Stan's generalised criterion
/// on the momentum sum ([`UTurnRule::MomentumSum`]). **Default change, post
/// hoc after WP31** (see [`DEFAULT_METRIC_REGULARIZATION`]); the frozen
/// `v10` endpoint rule ([`UTurnRule::Endpoints`]) remains the
/// `walnutpie::KernelOptions` default and is one [`Tuning::kernel_options`]
/// call away. Kernel fingerprints, `ALGORITHM_REVISION` and `RunConfig` runs
/// are unchanged.
pub const DEFAULT_U_TURN_RULE: UTurnRule = UTurnRule::MomentumSum;

/// The warmup-time chain rescue installed by the sampler's own adaptation
/// modes ([`Adaptation::DualAveraging`], [`Adaptation::Paper`]): none.
///
/// **Post-study default decision after `STUDIES/chain_rescue_v2` (WP36).**
/// WP33 had temporarily made [`ChainRescueConfig::restart_from_best`] the
/// identity/diagonal multi-chain default after strong bad-start efficacy.
/// In WP36, `two_hit` failed its conjunctive gates, which advanced the frozen
/// rule to the `current` fallback check but did not itself select no rescue.
/// `current` then had registered red lines in four origin-overwrite cells
/// (five events) plus unknown HMM/92104 run history, selecting no rescue. The
/// classifier found pathological/frozen ARMA and Lotka-Volterra origins and
/// zero HMM origins, so WP36 does not establish genuine posterior-mode
/// destruction.
///
/// Rescue remains fully supported as an explicit opt-in through
/// [`Adaptation::Custom`] and [`WarmupConfig::with_chain_rescue`], including
/// immediate restart, observe-only, two-hit, and metric pooling. If a restart
/// acts, it copies state from another chain, so the resulting chains no longer
/// represent independent starts and ordinary independent-chain R-hat is not
/// valid for that run. Every boundary decision is available through
/// [`RunTelemetry::chain_rescues`].
///
/// This sampler-default reversal does not change
/// `walnutpie::WarmupConfig::default()`, `RunConfig`, the retained kernel, or
/// its fingerprints, so it does not advance `ALGORITHM_REVISION`.
pub const DEFAULT_CHAIN_RESCUE: Option<ChainRescueConfig> = None;

impl Adaptation {
    fn warmup_config(
        &self,
        adapt_mass: bool,
        supports_chain_rescue: bool,
    ) -> Result<Option<WarmupConfig>, Error> {
        let with_defaults = |warmup: WarmupConfig| {
            let warmup = warmup
                .with_mass_adaptation(adapt_mass)
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION);
            match (supports_chain_rescue, DEFAULT_CHAIN_RESCUE) {
                (true, Some(rescue)) => warmup.with_chain_rescue(rescue),
                _ => warmup,
            }
        };
        Ok(match self {
            Self::None => {
                if adapt_mass {
                    return Err(Error::configuration(
                        "an adapting metric requires an adaptation mode",
                    ));
                }
                None
            }
            Self::DualAveraging { target_accept } => {
                Some(with_defaults(WarmupConfig::new(*target_accept)?))
            }
            Self::Paper(paper) => Some(with_defaults(
                WarmupConfig::default().with_paper_adaptation(*paper),
            )),
            Self::Custom(warmup) => Some(warmup.clone().with_mass_adaptation(adapt_mass)),
        })
    }
}

/// Where the chains start.
///
/// [`Init::Uniform`] is the CmdStan/Stan initialisation rule: every
/// unconstrained coordinate is drawn uniformly from `(-radius, radius)` and a
/// start is redrawn until the target returns a finite log density and a
/// finite gradient, up to `max_attempts` draws per chain (Stan's defaults
/// are `radius = 2`, 100 attempts). The draws consume no kernel randomness:
/// they come from `SmallRng` seeded by `splitmix64(seed ^ INIT_SEED_TAG)`, so
/// the starts, and therefore the run, are deterministic given the sampler
/// seed. The evaluations made while searching count against nothing but the
/// target's own call counter.
///
/// `STUDIES/posteriordb_bench_v1` drew one uniform(-2, 2) start per chain and
/// aborted when it was not evaluable (two `lotka_volterra` seeds); with this
/// rule those runs proceed exactly as CmdStan's do.
#[derive(Clone, Debug, PartialEq)]
#[non_exhaustive]
pub enum Init {
    /// Use these positions, one per chain (the [`Sampler::run`] contract).
    Given(Vec<Vec<f64>>),
    /// Uniform unconstrained starts with retries; see the type docs.
    Uniform {
        /// Half-width of the uniform box; finite and positive.
        radius: f64,
        /// Draws tried per chain before the run errors; nonzero.
        max_attempts: usize,
    },
}

/// Tag mixed into the sampler seed for the start RNG so that start draws are
/// independent of the chain seeds `splitmix64(seed + i)`.
pub const INIT_SEED_TAG: u64 = 0x5eed_1417_0000_0000_u64;

impl Init {
    /// Stan's default: uniform(-2, 2) with up to 100 attempts per chain.
    pub fn uniform() -> Self {
        Self::Uniform {
            radius: 2.0,
            max_attempts: 100,
        }
    }
}

impl Default for Init {
    fn default() -> Self {
        Self::uniform()
    }
}

/// Draw `chains` starts by the [`Init::Uniform`] rule.
///
/// Errors with [`ErrorKind::Target`] (fatal target error), or
/// [`ErrorKind::Numerical`] with a message naming the chain, the number of
/// attempts and the last failure when no evaluable start is found.
pub fn uniform_starts<T: Target + ?Sized>(
    target: &T,
    chains: usize,
    seed: u64,
    radius: f64,
    max_attempts: usize,
) -> Result<Vec<Vec<f64>>, Error> {
    if !radius.is_finite() || radius <= 0.0 {
        return Err(Error::configuration(
            "initialisation radius must be finite and positive",
        ));
    }
    if max_attempts == 0 {
        return Err(Error::configuration(
            "initialisation must allow at least one attempt",
        ));
    }
    if chains == 0 {
        return Err(Error::configuration("chain count must be nonzero"));
    }
    let dimension = catch_unwind(AssertUnwindSafe(|| target.dimension()))
        .map_err(|_| Error::new(ErrorKind::Panic, "target dimension callback panicked"))?;
    if dimension == 0 {
        return Err(Error::configuration("target dimension must be nonzero"));
    }
    let mut rng = SmallRng::seed_from_u64(crate::walnutpie::splitmix64(seed ^ INIT_SEED_TAG));
    let mut gradient = vec![0.0; dimension];
    let mut starts = Vec::with_capacity(chains);
    for chain in 0..chains {
        let mut last_failure = String::new();
        let mut found = None;
        for _attempt in 0..max_attempts {
            let candidate: Vec<f64> = (0..dimension)
                .map(|_| rng.random_range(-radius..radius))
                .collect();
            gradient.iter_mut().for_each(|g| *g = f64::NAN);
            let evaluated = catch_unwind(AssertUnwindSafe(|| {
                target.log_density_gradient(&candidate, &mut gradient)
            }))
            .map_err(|_| Error::new(ErrorKind::Panic, "target callback panicked"))?;
            match evaluated {
                Ok(value) if value.is_finite() && gradient.iter().all(|g| g.is_finite()) => {
                    found = Some(candidate);
                    break;
                }
                Ok(value) => {
                    last_failure = if value.is_finite() {
                        String::from("gradient is not finite")
                    } else {
                        format!("log density is {value}")
                    };
                }
                Err(error) if error.kind() == crate::walnutpie::TargetErrorKind::Fatal => {
                    return Err(Error::new(
                        ErrorKind::Target,
                        format!(
                            "fatal target error while drawing the start of chain {chain}: {}",
                            error.message()
                        ),
                    ));
                }
                Err(error) => last_failure = error.message().to_owned(),
            }
        }
        match found {
            Some(start) => starts.push(start),
            None => {
                return Err(Error::new(
                    ErrorKind::Numerical,
                    format!(
                        "no evaluable start for chain {chain} after {max_attempts} uniform(-{radius}, \
                         {radius}) draws (last failure: {last_failure}); the log density and \
                         gradient must be finite at the start, check the model or supply starts"
                    ),
                ));
            }
        }
    }
    Ok(starts)
}

/// Kernel tuning: the macro step, tree depth, refinement, and error
/// threshold. Values are validated when the run starts.
///
/// The default is `h = 0.5`, depth 10, one minimum micro-step, eight
/// refinement levels, `delta = 1.0`, and the momentum-sum no-U-turn rule
/// ([`DEFAULT_U_TURN_RULE`]; the frozen `v10` endpoint rule is
/// `.kernel_options(KernelOptions::default())`). Eight levels (micro-steps down to
/// `h / 256`) are what make the default unbiased on Neal's funnel: at four
/// levels the adapted step cannot enter the neck and the tail mass
/// `P(omega < -5)` comes out at half the exact value, while on the
/// noncentered Eight Schools and a 100-D Gaussian the extra levels never
/// engage (`STUDIES/funnel_defaults_v1`, 1.05x / 1.00x ESS per call). Depth 10 (Stan's default; the 0.1 API
/// used 8) was chosen by the preregistered ablation in
/// `STUDIES/adaptation_parity_v1`: on the posteriordb regressions with
/// correlated coefficients (`diamonds`, `earnings`, `sblrc`) depth 8 capped
/// 55-85 % of transitions and failed every gate, depth 10 passes them. It
/// differs from `walnutpie::KernelTuning::default()`, which preserves the
/// frozen replay tuning of `ALGORITHM_REVISION` (depth 3).
#[derive(Clone, Debug, PartialEq)]
pub struct Tuning {
    step_size: f64,
    max_depth: usize,
    min_micro_steps: usize,
    max_refinement_levels: usize,
    max_error: f64,
    divergence_threshold: f64,
    kernel_options: KernelOptions,
    #[cfg(feature = "research")]
    reverse_coarsening_order: ReverseCoarseningOrder,
    #[cfg(feature = "research")]
    nonfinite_position: NonfinitePositionPolicy,
}

impl Default for Tuning {
    fn default() -> Self {
        Self {
            step_size: 0.5,
            max_depth: 10,
            min_micro_steps: 1,
            max_refinement_levels: 8,
            max_error: 1.0,
            divergence_threshold: DEFAULT_DIVERGENCE_THRESHOLD,
            kernel_options: KernelOptions {
                u_turn: DEFAULT_U_TURN_RULE,
                ..KernelOptions::default()
            },
            #[cfg(feature = "research")]
            reverse_coarsening_order: ReverseCoarseningOrder::FinestToCoarsest,
            #[cfg(feature = "research")]
            nonfinite_position: NonfinitePositionPolicy::Abort,
        }
    }
}

impl Tuning {
    /// The default tuning; chain the setters to change it.
    pub fn new() -> Self {
        Self::default()
    }
    /// Initial macro step `h` (adapted during warmup unless
    /// [`Adaptation::None`]).
    pub fn step_size(mut self, step_size: f64) -> Self {
        self.step_size = step_size;
        self
    }
    /// Maximum number of tree doublings.
    pub fn max_depth(mut self, max_depth: usize) -> Self {
        self.max_depth = max_depth;
        self
    }
    /// Micro-steps per macro step at the coarsest level.
    pub fn min_micro_steps(mut self, min_micro_steps: usize) -> Self {
        self.min_micro_steps = min_micro_steps;
        self
    }
    /// Number of halving levels a macro step may refine through.
    pub fn max_refinement_levels(mut self, levels: usize) -> Self {
        self.max_refinement_levels = levels;
        self
    }
    /// Local energy-error threshold `delta` for accepting a refinement level.
    pub fn max_error(mut self, max_error: f64) -> Self {
        self.max_error = max_error;
        self
    }
    /// Absolute trajectory energy error reported as a divergence.
    pub fn divergence_threshold(mut self, threshold: f64) -> Self {
        self.divergence_threshold = threshold;
        self
    }
    /// Kernel rule variants (`walnutpie::KernelOptions`): the no-U-turn
    /// predicate and the treatment of refinement exhaustion. The sampler's
    /// default is [`DEFAULT_U_TURN_RULE`] with the frozen two-sided
    /// exhaustion rule for retained transitions; `KernelOptions::default()`
    /// is the frozen `v10` kernel (endpoint rule). See
    /// `STUDIES/kernel_efficiency_v1`, `STUDIES/kernel_gap_v1` and
    /// `STUDIES/joint_default_v1` for the measurements.
    pub fn kernel_options(mut self, options: KernelOptions) -> Self {
        self.kernel_options = options;
        self
    }
    /// Select reverse-coarsening traversal order for a deterministic target
    /// that returns only finite evaluations or recoverable zero-density
    /// points. Research-only; every default remains finest to coarsest.
    #[cfg(feature = "research")]
    pub fn reverse_coarsening_order(mut self, order: ReverseCoarseningOrder) -> Self {
        self.reverse_coarsening_order = order;
        self
    }
    /// Select how a transition treats a nonfinite integrator position.
    /// Research-only; the default remains `Abort`, which ends the run with
    /// `ErrorKind::Numerical`. See `STUDIES/nonfinite_position_policy_v1`.
    #[cfg(feature = "research")]
    pub fn nonfinite_position(mut self, policy: NonfinitePositionPolicy) -> Self {
        self.nonfinite_position = policy;
        self
    }

    /// The validated `walnutpie` tuning this configures.
    pub fn to_kernel(&self) -> Result<KernelTuning, Error> {
        let nonzero = |value: usize, what: &str| {
            NonZeroUsize::new(value)
                .ok_or_else(|| Error::configuration(format!("{what} must be nonzero")))
        };
        let tuning = KernelTuning::new(
            self.step_size,
            nonzero(self.max_depth, "max_depth")?,
            nonzero(self.min_micro_steps, "min_micro_steps")?,
            nonzero(self.max_refinement_levels, "max_refinement_levels")?,
            self.max_error,
        )?
        .with_divergence_threshold(self.divergence_threshold)
        .map(|tuning| tuning.with_options(self.kernel_options))?;
        #[cfg(feature = "research")]
        let tuning = tuning.with_reverse_coarsening_order(self.reverse_coarsening_order);
        #[cfg(feature = "research")]
        let tuning = tuning.with_nonfinite_position(self.nonfinite_position);
        Ok(tuning)
    }
}

/// Work ceilings and cooperative interruption for one run.
///
/// All limits are optional. Cancellation and deadlines are checked between
/// bounded kernel operations and around target callbacks; a callback that
/// never returns cannot be interrupted.
#[derive(Clone)]
pub struct Limits {
    max_target_evaluations: Option<NonZeroUsize>,
    admit_worst_case: bool,
    deadline: Option<Instant>,
    timeout: Option<Duration>,
    cancellation: Option<Arc<dyn Cancellation>>,
    max_depth_stops: Option<usize>,
}

impl Default for Limits {
    /// No limits; the run is admitted with its exact worst-case evaluation
    /// count (see [`Limits::admit_worst_case`]).
    fn default() -> Self {
        Self {
            max_target_evaluations: None,
            admit_worst_case: true,
            deadline: None,
            timeout: None,
            cancellation: None,
            max_depth_stops: None,
        }
    }
}

impl Limits {
    /// No limits.
    pub fn new() -> Self {
        Self::default()
    }
    /// Exact ceiling on started target evaluations across all chains; the
    /// run is also admitted against this number instead of the conservative
    /// default preflight ceiling. Zero is rejected at run time.
    pub fn max_target_evaluations(mut self, evaluations: usize) -> Self {
        self.max_target_evaluations = NonZeroUsize::new(evaluations);
        self
    }
    /// Admit the run with its exact worst-case evaluation count as the
    /// ceiling. This is the default since 0.2.0: the sampler's own defaults
    /// (depth 10, eight refinement levels) exceed the conservative
    /// `walnutpie` admission ceiling for ordinary 4 x 1,000/2,000 runs, and
    /// the worst case is an exact bound the run can never exceed, so it costs
    /// nothing. Ignored when `max_target_evaluations` is set.
    pub fn admit_worst_case(mut self) -> Self {
        self.admit_worst_case = true;
        self
    }
    /// Admit the run against the conservative `walnutpie` preflight ceiling
    /// instead of the exact worst case (the 0.1.x behaviour). Configurations
    /// whose worst case exceeds that ceiling are then rejected with a
    /// resource-limit error before any target call.
    pub fn admit_conservative(mut self) -> Self {
        self.admit_worst_case = false;
        self
    }
    /// Cooperative wall-clock deadline.
    pub fn deadline(mut self, deadline: Instant) -> Self {
        self.deadline = Some(deadline);
        self
    }
    /// Cooperative timeout measured from the start of the run.
    pub fn timeout(mut self, timeout: Duration) -> Self {
        self.timeout = Some(timeout);
        self
    }
    /// Cooperative cancellation flag polled at kernel safe points.
    pub fn cancellation(mut self, cancellation: Arc<dyn Cancellation>) -> Self {
        self.cancellation = Some(cancellation);
        self
    }
    /// Fail the run when more than this many transitions stop at the maximum
    /// tree depth (`ErrorKind::Unhealthy`).
    pub fn max_depth_stops(mut self, stops: usize) -> Self {
        self.max_depth_stops = Some(stops);
        self
    }
}

impl fmt::Debug for Limits {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("Limits")
            .field("max_target_evaluations", &self.max_target_evaluations)
            .field("admit_worst_case", &self.admit_worst_case)
            .field("deadline", &self.deadline)
            .field("timeout", &self.timeout)
            .field("cancellation", &self.cancellation.as_ref().map(|_| ".."))
            .field("max_depth_stops", &self.max_depth_stops)
            .finish()
    }
}

/// Chains used by [`Sampler::run_with_init`] with [`Init::Uniform`] when
/// [`Sampler::chains`] was not set.
pub const DEFAULT_RANDOM_START_CHAINS: usize = 4;

/// Builder for one sampling run.
///
/// Defaults: 1,000 warmup transitions, 1,000 retained draws per chain, one
/// chain per start, seed 0, one thread per chain, adaptive diagonal metric,
/// dual averaging toward acceptance 0.8, [`Tuning::default`], no limits.
#[derive(Debug)]
pub struct Sampler {
    warmup: usize,
    draws: usize,
    chains: Option<usize>,
    seed: u64,
    threads: Option<usize>,
    metric: Metric,
    adaptation: Adaptation,
    tuning: Tuning,
    limits: Limits,
    cache_initial_evaluation: bool,
}

impl Default for Sampler {
    fn default() -> Self {
        Self {
            warmup: 1_000,
            draws: 1_000,
            chains: None,
            seed: 0,
            threads: None,
            metric: Metric::default(),
            adaptation: Adaptation::default(),
            tuning: Tuning::default(),
            limits: Limits::default(),
            cache_initial_evaluation: true,
        }
    }
}

impl Sampler {
    /// A sampler with the documented defaults.
    pub fn new() -> Self {
        Self::default()
    }
    /// Discarded (warmup) transitions per chain.
    pub fn warmup(mut self, transitions: usize) -> Self {
        self.warmup = transitions;
        self
    }
    /// Retained draws per chain; must be nonzero.
    pub fn draws(mut self, draws: usize) -> Self {
        self.draws = draws;
        self
    }
    /// Number of chains. With one start it is replicated (no jitter);
    /// otherwise it must equal the number of starts.
    pub fn chains(mut self, chains: usize) -> Self {
        self.chains = Some(chains);
        self
    }
    /// Base seed; chain `i` uses `splitmix64(seed + i)`.
    pub fn seed(mut self, seed: u64) -> Self {
        self.seed = seed;
        self
    }
    /// Upper bound on worker threads (a run-local pool). Output is
    /// independent of the thread count.
    pub fn threads(mut self, threads: usize) -> Self {
        self.threads = Some(threads);
        self
    }
    /// Momentum covariance and whether warmup adapts it.
    pub fn metric(mut self, metric: Metric) -> Self {
        self.metric = metric;
        self
    }
    /// Warmup rules.
    pub fn adaptation(mut self, adaptation: Adaptation) -> Self {
        self.adaptation = adaptation;
        self
    }
    /// Kernel tuning.
    pub fn tuning(mut self, tuning: Tuning) -> Self {
        self.tuning = tuning;
        self
    }
    /// Work ceilings and cooperative interruption.
    pub fn limits(mut self, limits: Limits) -> Self {
        self.limits = limits;
        self
    }
    /// Reuse each transition's selected log density and gradient as the
    /// next transition's initial evaluation (one target call per transition
    /// saved; draws bit-identical). On by default in `Sampler` since 0.2.0;
    /// `walnutpie::RunConfig` keeps it off to preserve the frozen
    /// target-call fingerprints. See `STUDIES/kernel_efficiency_v1`.
    pub fn cache_initial_evaluation(mut self, enabled: bool) -> Self {
        self.cache_initial_evaluation = enabled;
        self
    }

    /// Exact worst-case target-evaluation count of this configuration for
    /// `chains` chains; the number [`Limits::admit_worst_case`] admits with.
    pub fn worst_case_target_evaluations(&self, chains: usize) -> Result<usize, Error> {
        let chains = NonZeroUsize::new(chains)
            .ok_or_else(|| Error::configuration("chain count must be nonzero"))?;
        self.run_config()?.worst_case_target_evaluations(chains)
    }

    fn run_config(&self) -> Result<RunConfig, Error> {
        let draws = NonZeroUsize::new(self.draws)
            .ok_or_else(|| Error::configuration("draws must be nonzero"))?;
        let mut config = RunConfig::new(self.warmup, draws, self.seed)
            .with_tuning(self.tuning.to_kernel()?)
            .with_cached_initial_evaluation(self.cache_initial_evaluation);
        if let Some(warmup) = self.adaptation.warmup_config(
            self.metric.adapts_mass(),
            self.metric.supports_chain_rescue(),
        )? {
            config = config.with_warmup(warmup);
        }
        if let Some(limit) = self.limits.max_depth_stops {
            config = config.with_maximum_depth_stop_limit(limit);
        }
        Ok(config)
    }

    /// The structured paths have no budgeted admission variant: they are
    /// admitted against the `RunConfig` ceiling, which is the conservative
    /// `walnutpie` default unless the crate's `research` feature raises it.
    /// With that feature, when the exact worst case exceeds the conservative
    /// ceiling and a budget is set (an explicit
    /// [`Limits::max_target_evaluations`] or the worst case itself under
    /// [`Limits::admit_worst_case`]), that budget, capped at the research
    /// maximum, becomes the admission ceiling, so the sampler defaults
    /// (depth 10, eight refinement levels) are admitted on a structured
    /// metric as they are on the diagonal and dense paths. Runs the
    /// conservative ceiling already admits are configured exactly as before,
    /// and without the feature the facade's conservative admission applies
    /// unchanged.
    fn admit_structured(
        &self,
        config: RunConfig,
        budget: Option<NonZeroUsize>,
        chains: NonZeroUsize,
    ) -> Result<RunConfig, Error> {
        #[cfg(feature = "research")]
        {
            use crate::walnutpie::{
                CONSERVATIVE_MAX_TARGET_EVALUATIONS, RESEARCH_MAX_TARGET_EVALUATIONS,
                ResearchTargetEvaluationLimit,
            };
            if let (Metric::Structured(_) | Metric::StructuredRefresh { .. }, Some(budget)) =
                (&self.metric, budget)
            {
                let worst = config.worst_case_target_evaluations(chains)?;
                let ceiling = budget.get().min(RESEARCH_MAX_TARGET_EVALUATIONS);
                if worst > CONSERVATIVE_MAX_TARGET_EVALUATIONS && worst <= ceiling {
                    let limit = ResearchTargetEvaluationLimit::new(
                        NonZeroUsize::new(ceiling).expect("ceiling above the conservative limit"),
                    )?;
                    return Ok(config.with_research_target_evaluation_limit(limit));
                }
            }
        }
        #[cfg(not(feature = "research"))]
        let _ = (budget, chains);
        Ok(config)
    }

    fn starts(&self, starts: &[Vec<f64>]) -> Result<Vec<Vec<f64>>, Error> {
        match self.chains {
            None => Ok(starts.to_vec()),
            Some(chains) if chains == starts.len() => Ok(starts.to_vec()),
            Some(chains) if starts.len() == 1 && chains > 0 => Ok(vec![starts[0].clone(); chains]),
            Some(_) => Err(Error::configuration(
                "chain count must equal the number of starts, or exactly one start must be given",
            )),
        }
    }

    /// Run from starts chosen by `init`.
    ///
    /// [`Init::Given`] is [`Sampler::run`]. [`Init::Uniform`] draws one start
    /// per chain by [`uniform_starts`] with this sampler's seed; the chain
    /// count is [`Sampler::chains`] or, if unset, four.
    pub fn run_with_init<T: Target>(&self, target: &T, init: &Init) -> Result<Posterior, Error> {
        match init {
            Init::Given(starts) => self.run(target, starts),
            Init::Uniform {
                radius,
                max_attempts,
            } => {
                let chains = self.chains.unwrap_or(DEFAULT_RANDOM_START_CHAINS);
                let starts = uniform_starts(target, chains, self.seed, *radius, *max_attempts)?;
                self.run(target, &starts)
            }
        }
    }

    /// Run from Stan-style random starts ([`Init::uniform`]): uniform(-2, 2)
    /// unconstrained coordinates, redrawn up to 100 times per chain until the
    /// log density and gradient are finite. Deterministic given the seed.
    pub fn run_from_random_starts<T: Target>(&self, target: &T) -> Result<Posterior, Error> {
        self.run_with_init(target, &Init::uniform())
    }

    /// Run the configured sampler from `starts` (one position per chain).
    ///
    /// Errors are all-or-nothing: no draws are returned on failure.
    pub fn run<T: Target>(&self, target: &T, starts: &[Vec<f64>]) -> Result<Posterior, Error> {
        self.run_with_control_value(target, starts, RunControl::new())
    }

    /// Run through the high-level boundary while emitting complete research
    /// comparison and per-target-call records.
    #[cfg(feature = "research")]
    pub fn run_with_comparison_observers<T: Target>(
        &self,
        target: &T,
        starts: &[Vec<f64>],
        proposals: &crate::walnutpie::ProposalObservationControl<'_>,
        comparisons: &dyn crate::walnutpie::ComparisonObserver,
    ) -> Result<Posterior, Error> {
        self.run_with_control_value(
            target,
            starts,
            RunControl::new()
                .with_proposal_observations(proposals)
                .with_comparison_observer(comparisons),
        )
    }

    fn run_with_control_value<'a, T: Target>(
        &self,
        target: &T,
        starts: &[Vec<f64>],
        base_control: RunControl<'a>,
    ) -> Result<Posterior, Error> {
        let config = self.run_config()?;
        let starts = self.starts(starts)?;
        let chains = NonZeroUsize::new(starts.len())
            .ok_or_else(|| Error::configuration("at least one start is required"))?;
        let threads = NonZeroUsize::new(self.threads.unwrap_or(chains.get()))
            .ok_or_else(|| Error::configuration("thread count must be nonzero"))?;
        let dimension = catch_unwind(AssertUnwindSafe(|| target.dimension()))
            .map_err(|_| Error::new(ErrorKind::Panic, "target dimension callback panicked"))?;
        let dimension = NonZeroUsize::new(dimension)
            .ok_or_else(|| Error::configuration("target dimension must be nonzero"))?;

        let mut control = base_control;
        if let Some(cancellation) = &self.limits.cancellation {
            control = control.with_cancellation(&**cancellation);
        }
        if let Some(deadline) = self.limits.deadline {
            control = control.with_deadline(deadline);
        }
        if let Some(timeout) = self.limits.timeout {
            control = control.with_timeout(timeout)?;
        }

        let budget_size = match (
            self.limits.max_target_evaluations,
            self.limits.admit_worst_case,
        ) {
            (Some(evaluations), _) => Some(evaluations),
            (None, true) => Some(
                NonZeroUsize::new(config.worst_case_target_evaluations(chains)?)
                    .ok_or_else(|| Error::configuration("worst case is zero"))?,
            ),
            (None, false) => None,
        };
        let budget = budget_size.map(TargetEvaluationBudget::new);
        let config = self.admit_structured(config, budget_size, chains)?;

        let output = match &self.metric {
            Metric::Identity => {
                let mass = DiagonalMass::identity(dimension);
                run_diagonal(target, &starts, &mass, &config, threads, &control, budget)?
            }
            Metric::Diagonal { initial, .. } => {
                let mass = match initial {
                    Some(diagonal) => DiagonalMass::from_diagonal(diagonal.clone())?,
                    None => DiagonalMass::identity(dimension),
                };
                run_diagonal(target, &starts, &mass, &config, threads, &control, budget)?
            }
            Metric::Dense { initial, .. } => {
                let mass = match initial {
                    Some(matrix) => DenseMass::from_matrix(matrix.clone(), dimension.get())?,
                    None => DenseMass::identity(dimension)?,
                };
                match &budget {
                    Some(budget) => sample_chains_dense_with_target_budget_and_control(
                        target,
                        &starts,
                        &mass,
                        &config,
                        threads,
                        TargetEvaluationAdmissionLimit::new(budget_size.expect("budgeted")),
                        budget,
                        &control,
                    )?,
                    None => sample_chains_dense_with_control(
                        target, &starts, &mass, &config, threads, &control,
                    )?,
                }
            }
            Metric::Structured(mass) => match &budget {
                Some(budget) => sample_chains_structured_with_control(
                    &budget.wrap(target),
                    &starts,
                    mass,
                    &config,
                    threads,
                    &control,
                )?,
                None => sample_chains_structured_with_control(
                    target, &starts, mass, &config, threads, &control,
                )?,
            },
            Metric::StructuredRefresh {
                initial,
                refresh,
                config: refresh_config,
            } => {
                let refreshed = match &budget {
                    Some(budget) => sample_chains_structured_refresh(
                        &budget.wrap(target),
                        &starts,
                        initial,
                        &**refresh,
                        refresh_config,
                        &config,
                        threads,
                        &control,
                    )?,
                    None => sample_chains_structured_refresh(
                        target,
                        &starts,
                        initial,
                        &**refresh,
                        refresh_config,
                        &config,
                        threads,
                        &control,
                    )?,
                };
                let (output, metric_updates, final_masses) = refreshed.into_parts();
                return Ok(Posterior {
                    output,
                    metric_updates,
                    final_masses,
                });
            }
        };
        Ok(Posterior {
            output,
            metric_updates: Vec::new(),
            final_masses: Vec::new(),
        })
    }
}

#[allow(clippy::too_many_arguments)]
fn run_diagonal<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    mass: &DiagonalMass,
    config: &RunConfig,
    threads: NonZeroUsize,
    control: &RunControl<'_>,
    budget: Option<TargetEvaluationBudget>,
) -> Result<MultiChainOutput, Error> {
    match budget {
        Some(budget) => sample_chains_with_target_budget_and_control(
            target,
            starts,
            mass,
            config,
            threads,
            TargetEvaluationAdmissionLimit::new(
                NonZeroUsize::new(budget.maximum()).expect("nonzero budget"),
            ),
            &budget,
            control,
        ),
        None => sample_chains_with_control(target, starts, mass, config, threads, control),
    }
}

/// Retained draws, diagnostics, telemetry, and metadata of every chain.
///
/// Chains are in chain-index order. Draws are the retained positions after
/// warmup; a chain's flat storage is draw-major `[draw][parameter]`.
#[derive(Clone, Debug, PartialEq)]
pub struct Posterior {
    output: MultiChainOutput,
    metric_updates: Vec<Vec<StructuredRefreshUpdate>>,
    final_masses: Vec<StructuredBlockMass>,
}

impl Posterior {
    /// Per-chain output, in chain-index order.
    pub fn chains(&self) -> &[ChainOutput] {
        self.output.chains()
    }
    /// Number of chains.
    pub fn chain_count(&self) -> usize {
        self.output.chains().len()
    }
    /// Parameter dimension.
    pub fn dimension(&self) -> usize {
        self.output
            .chains()
            .first()
            .map_or(0, ChainOutput::dimension)
    }
    /// Retained draws per chain.
    pub fn draws_per_chain(&self) -> usize {
        self.output
            .chains()
            .first()
            .map_or(0, ChainOutput::retained)
    }
    /// Every retained draw, chain by chain, as a position slice.
    pub fn draws(&self) -> impl Iterator<Item = &[f64]> + '_ {
        self.output.chains().iter().flat_map(|chain| {
            let dimension = chain.dimension().max(1);
            chain.samples().chunks_exact(dimension)
        })
    }
    /// Flat draw-major storage of one chain: `[draw][parameter]`.
    pub fn chain_draws(&self, chain: usize) -> Option<&[f64]> {
        self.output.chains().get(chain).map(ChainOutput::samples)
    }
    /// One retained draw of one chain.
    pub fn draw(&self, chain: usize, draw: usize) -> Option<&[f64]> {
        self.output.chains().get(chain)?.sample(draw)
    }
    /// Marginal of one parameter over every retained draw of every chain.
    pub fn parameter(&self, index: usize) -> impl Iterator<Item = f64> + '_ {
        self.draws().map(move |draw| draw[index])
    }
    /// Per-chain telemetry (work partitions, adaptation records).
    pub fn telemetry(&self) -> impl Iterator<Item = &RunTelemetry> + '_ {
        self.output.chains().iter().map(ChainOutput::telemetry)
    }
    /// Per-chain metadata (final tuning, mass, seeds, revision).
    pub fn metadata(&self) -> impl Iterator<Item = &RunMetadata> + '_ {
        self.output.chains().iter().map(ChainOutput::metadata)
    }
    /// Fused log-density/gradient calls over every chain and phase.
    pub fn total_target_calls(&self) -> usize {
        self.telemetry()
            .map(|telemetry| telemetry.total().target_calls_total())
            .sum()
    }
    /// The base seed of the run.
    pub fn seed(&self) -> u64 {
        self.output.base_seed()
    }
    /// Execution identity of the path that produced the draws.
    pub fn algorithm_revision(&self) -> &str {
        self.output.algorithm_revision()
    }
    /// Boundary refresh records per chain ([`Metric::StructuredRefresh`]
    /// only; empty otherwise).
    pub fn metric_updates(&self) -> &[Vec<StructuredRefreshUpdate>] {
        &self.metric_updates
    }
    /// Final installed operator per chain ([`Metric::StructuredRefresh`]
    /// only; empty otherwise).
    pub fn final_masses(&self) -> &[StructuredBlockMass] {
        &self.final_masses
    }
    /// The underlying `walnutpie` output.
    pub fn inner(&self) -> &MultiChainOutput {
        &self.output
    }
    /// The underlying `walnutpie` output.
    pub fn into_inner(self) -> MultiChainOutput {
        self.output
    }
}
