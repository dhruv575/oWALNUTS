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
//! [`Adaptation`] selects the warmup rules: acceptance-driven dual averaging
//! (`WarmupConfig::new(target_accept)`, the default), the JMLR Appendix C
//! rules (`WarmupConfig::default().with_paper_adaptation(..)`), or none. The
//! metric decides `WarmupConfig::with_mass_adaptation`.
//!
//! [`TargetEvaluationBudget`]: crate::walnutpie::TargetEvaluationBudget

use std::fmt;
use std::num::NonZeroUsize;
use std::panic::{AssertUnwindSafe, catch_unwind};
use std::sync::Arc;
use std::time::{Duration, Instant};

pub use crate::walnutpie::{
    Cancellation, ChainOutput, Error, ErrorKind, PaperAdaptationConfig, RunMetadata, RunTelemetry,
    StructuredBlockMass, StructuredCovarianceBlock, StructuredMetricRefresh,
    StructuredRefreshConfig, StructuredRefreshUpdate, Target, TargetError, WarmupConfig,
    WindowSummary,
};
use crate::walnutpie::{
    DEFAULT_DIVERGENCE_THRESHOLD, DenseMass, DiagonalMass, KernelTuning, MultiChainOutput,
    RunConfig, RunControl, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
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
/// The default stays the `v10` dual averaging (`WarmupConfig::new(target)`).
/// The Stan-parity warmup (`WarmupConfig::stan_style`) is opt-in through
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
    /// what the metric requires.
    Custom(WarmupConfig),
}

impl Default for Adaptation {
    fn default() -> Self {
        Self::DualAveraging { target_accept: 0.8 }
    }
}

impl Adaptation {
    fn warmup_config(&self, adapt_mass: bool) -> Result<Option<WarmupConfig>, Error> {
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
                Some(WarmupConfig::new(*target_accept)?.with_mass_adaptation(adapt_mass))
            }
            Self::Paper(paper) => Some(
                WarmupConfig::default()
                    .with_mass_adaptation(adapt_mass)
                    .with_paper_adaptation(*paper),
            ),
            Self::Custom(warmup) => Some(warmup.clone().with_mass_adaptation(adapt_mass)),
        })
    }
}

/// Kernel tuning: the macro step, tree depth, refinement, and error
/// threshold. Values are validated when the run starts.
///
/// The default is `h = 0.5`, depth 10, one minimum micro-step, four
/// refinement levels, `delta = 1.0`. Depth 10 (Stan's default; the 0.1 API
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
}

impl Default for Tuning {
    fn default() -> Self {
        Self {
            step_size: 0.5,
            max_depth: 10,
            min_micro_steps: 1,
            max_refinement_levels: 4,
            max_error: 1.0,
            divergence_threshold: DEFAULT_DIVERGENCE_THRESHOLD,
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

    /// The validated `walnutpie` tuning this configures.
    pub fn to_kernel(&self) -> Result<KernelTuning, Error> {
        let nonzero = |value: usize, what: &str| {
            NonZeroUsize::new(value)
                .ok_or_else(|| Error::configuration(format!("{what} must be nonzero")))
        };
        KernelTuning::new(
            self.step_size,
            nonzero(self.max_depth, "max_depth")?,
            nonzero(self.min_micro_steps, "min_micro_steps")?,
            nonzero(self.max_refinement_levels, "max_refinement_levels")?,
            self.max_error,
        )?
        .with_divergence_threshold(self.divergence_threshold)
    }
}

/// Work ceilings and cooperative interruption for one run.
///
/// All limits are optional. Cancellation and deadlines are checked between
/// bounded kernel operations and around target callbacks; a callback that
/// never returns cannot be interrupted.
#[derive(Clone, Default)]
pub struct Limits {
    max_target_evaluations: Option<NonZeroUsize>,
    admit_worst_case: bool,
    deadline: Option<Instant>,
    timeout: Option<Duration>,
    cancellation: Option<Arc<dyn Cancellation>>,
    max_depth_stops: Option<usize>,
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
    /// ceiling. Needed when deep refinement and deep trees exceed the
    /// conservative default admission ceiling (for example the paper's
    /// funnel warmup). Ignored when `max_target_evaluations` is set.
    pub fn admit_worst_case(mut self) -> Self {
        self.admit_worst_case = true;
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
        let mut config =
            RunConfig::new(self.warmup, draws, self.seed).with_tuning(self.tuning.to_kernel()?);
        if let Some(warmup) = self.adaptation.warmup_config(self.metric.adapts_mass())? {
            config = config.with_warmup(warmup);
        }
        if let Some(limit) = self.limits.max_depth_stops {
            config = config.with_maximum_depth_stop_limit(limit);
        }
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

    /// Run the configured sampler from `starts` (one position per chain).
    ///
    /// Errors are all-or-nothing: no draws are returned on failure.
    pub fn run<T: Target>(&self, target: &T, starts: &[Vec<f64>]) -> Result<Posterior, Error> {
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

        let mut control = RunControl::new();
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
