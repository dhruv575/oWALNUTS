//! Internal limited-beta, fixed-tuning, diagonal-mass WALNUTS facade.
//!
//! This is an internal beta, not a generally supported or statistically validated
//! production sampler. It is limited to deterministic, smooth densities in
//! unconstrained `f64` coordinates and performs no adaptation. Student-t and
//! other heavy-tailed targets, constrained transforms, hierarchical targets,
//! and real models have not been validated. Only this facade is public; the
//! numerical implementation remains private.
//!
//! # Frozen kernel
//!
//! Revision [`ALGORITHM_REVISION`] freezes step size `0.6`, minimum micro-step
//! count `1`, at most `2` refinement levels, local error threshold `1.0`, and
//! maximum tree depth `3`. There is no warmup adaptation: `discarded` merely
//! labels initial fixed-kernel transitions whose positions are omitted.
//! Maximum-depth stops are valid completed transitions, but frequent stops
//! indicate a truncated trajectory. Use
//! [`RunConfig::with_maximum_depth_stop_limit`] to turn that health signal into
//! [`ErrorKind::Unhealthy`]; the run fails when the cumulative count becomes
//! strictly greater than the configured limit.
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
//! thread-safe, and free of hidden cross-chain state. Returning [`TargetError`],
//! returning nonfinite data, or panicking fails the whole call. Every public
//! sampling function is all-or-error: no samples, diagnostics, telemetry, or
//! partially completed chains are returned in [`Error`].
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
    Direction, FixedTuning, Rejection, SpanStop, TransitionInput, TransitionRng, TransitionStop,
    TransitionTuning, TransitionWorkTelemetry, Uniform01, transition_w_with_telemetry,
};
use crate::types::ValidationError;

/// Revision of the numerical kernel, seed derivation, random stream layout,
/// frozen tuning, and counter meanings.
///
/// Bitwise replay is promised only for this crate build with the same
/// `Cargo.lock`, target architecture, inputs, and revision. In particular,
/// `rand`'s `SmallRng` and `rand_distr::StandardNormal` are not upstream-stable
/// algorithms across dependency updates.
pub const ALGORITHM_REVISION: &str = "walnutpie-fixed-diagonal-tau0.6-m1-r2-e1-d3-v2";

const STEP_SIZE: f64 = 0.6;
const MAX_REFINEMENT_LEVELS: usize = 2;
const MIN_MICRO_STEPS: usize = 1;
const MAX_ERROR: f64 = 1.0;
const MAX_DEPTH: usize = 3;
const MAX_LEAVES_PER_TRANSITION: usize = (1 << MAX_DEPTH) - 1;
// Initial call plus a deliberately conservative bound for all forward/reverse
// calls made by the frozen two-level leaf.
const MAX_TARGET_CALLS_PER_TRANSITION: usize = 1 + MAX_LEAVES_PER_TRANSITION * 16;

/// Error returned by a user target.
#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct TargetError {
    message: Box<str>,
}

impl TargetError {
    pub fn new(message: impl Into<Box<str>>) -> Self {
        Self {
            message: message.into(),
        }
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

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError>;
}

/// Cooperative cancellation checked at deterministic kernel safe points.
///
/// A target callback that never returns cannot be interrupted safely inside
/// the process. Applications requiring that guarantee must evaluate targets in
/// an isolated worker process and terminate that process on timeout.
pub trait Cancellation: Send + Sync {
    fn is_cancelled(&self) -> bool;
}

/// Optional cooperative cancellation and wall-clock deadline.
#[derive(Clone, Copy, Default)]
pub struct RunControl<'a> {
    cancellation: Option<&'a dyn Cancellation>,
    deadline: Option<Instant>,
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

/// Checked resource ceilings. Values can only be tightened from the defaults.
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
            max_target_evaluations: 113_000_000,
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

/// Fixed-count run configuration. Discarded transitions do not adapt anything.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RunConfig {
    discarded: usize,
    retained: usize,
    seed: u64,
    max_maximum_depth_stops: usize,
    limits: ResourceLimits,
}

impl RunConfig {
    pub fn new(discarded: usize, retained: NonZeroUsize, seed: u64) -> Self {
        Self {
            discarded,
            retained: retained.get(),
            seed,
            max_maximum_depth_stops: usize::MAX,
            limits: ResourceLimits::default(),
        }
    }

    pub fn with_limits(mut self, limits: ResourceLimits) -> Self {
        self.limits = limits;
        self
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
}

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

#[derive(Clone, Debug, Eq, PartialEq)]
#[non_exhaustive]
pub struct TransitionDiagnostics {
    depth: usize,
    stop: StopReason,
    target_evaluations: usize,
    direction_draws: usize,
    uniform_draws: usize,
    leaves_attempted: usize,
    leaves_built: usize,
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

    fn add_transition(
        &mut self,
        dimension: usize,
        work: &TransitionWorkTelemetry,
        uniform_draws: usize,
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
        Ok(())
    }
}

#[derive(Clone, Debug, Default, Eq, PartialEq)]
#[non_exhaustive]
pub struct RunTelemetry {
    discarded: WorkTotals,
    retained: WorkTotals,
    total: WorkTotals,
}

impl RunTelemetry {
    pub fn discarded(&self) -> &WorkTotals {
        &self.discarded
    }
    pub fn retained(&self) -> &WorkTotals {
        &self.retained
    }
    pub fn total(&self) -> &WorkTotals {
        &self.total
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
    max_depth: usize,
    initial_position: Vec<f64>,
    thread_count: usize,
    mass_diagonal: Vec<f64>,
    limits: ResourceLimits,
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
    pub fn limits(&self) -> &ResourceLimits {
        &self.limits
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

fn tuning() -> TransitionTuning {
    TransitionTuning {
        leaf: FixedTuning {
            step_size: STEP_SIZE,
            max_refinement_levels: MAX_REFINEMENT_LEVELS,
            min_micro_steps: MIN_MICRO_STEPS,
            max_error: MAX_ERROR,
        },
        max_depth: MAX_DEPTH,
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
    let evaluations = total_transitions
        .checked_mul(MAX_TARGET_CALLS_PER_TRANSITION)
        .ok_or_else(Error::overflow)?;
    if evaluations > config.limits.max_target_evaluations {
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
        .and_then(|value| value.checked_mul(size_of::<f64>() * 2))
        .ok_or_else(Error::overflow)?;
    let result_bytes = sample_bytes
        .checked_add(diagnostics_bytes)
        .and_then(|value| value.checked_add(metadata_vector_bytes))
        .and_then(|value| value.checked_add(chain_count.checked_mul(size_of::<ChainOutput>())?))
        .and_then(|value| value.checked_add(size_of::<MultiChainOutput>()))
        .and_then(|value| value.checked_add(chain_count.checked_mul(size_of::<RunTelemetry>())?))
        .ok_or_else(Error::overflow)?;
    if result_bytes > config.limits.max_result_bytes {
        return Err(Error::resource("result data exceeds its resource limit"));
    }
    // The validated kernel uses dimension-sized vectors and bounded depth-three
    // span/state storage. 128 f64 slots per coordinate plus 16 KiB per chain
    // intentionally overbounds current copied inputs and transient workspaces.
    let working_bytes = dimension
        .checked_mul(size_of::<f64>())
        .and_then(|value| value.checked_mul(128))
        .and_then(|value| value.checked_add(16 * 1024))
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

#[allow(clippy::too_many_arguments)]
fn run_chain<T: Target>(
    target: &T,
    dimension: usize,
    initial_position: &[f64],
    mass: &DiagonalMass,
    config: &RunConfig,
    seed: u64,
    thread_count: usize,
    control: &ExecutionControl<'_>,
) -> Result<ChainOutput, Error> {
    let transitions = config
        .discarded
        .checked_add(config.retained)
        .ok_or_else(Error::overflow)?;
    let inverse_mass = inverse_mass(mass)?;
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

    let mut rng = SmallRng::seed_from_u64(seed);
    let mut position = initial_position.to_vec();
    let mut telemetry = RunTelemetry::default();
    for transition_index in 0..transitions {
        control
            .check()
            .map_err(control_error)
            .map_err(|error| error.at_transition(transition_index))?;
        let mut momentum = Vec::new();
        momentum
            .try_reserve_exact(dimension)
            .map_err(|_| Error::resource("momentum allocation failed"))?;
        for (mass_value, inverse_mass_value) in mass.diagonal().iter().zip(&inverse_mass) {
            let normal: f64 = StandardNormal.sample(&mut rng);
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

        let mut target_failure = None;
        let mut numerical_failure = false;
        let mut control_failure = None;
        let mut target_panic = false;
        let mut eval = |theta: &[f64]| {
            let mut gradient = vec![f64::NAN; dimension];
            if let Err(stop) = control.check() {
                control_failure = Some(stop);
                return (f64::NAN, gradient);
            }
            if theta.len() != dimension || theta.iter().any(|value| !value.is_finite()) {
                numerical_failure = true;
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
                    return (f64::NAN, gradient);
                }
            };
            match evaluated {
                Ok(log_density)
                    if log_density.is_finite()
                        && gradient.iter().all(|value| value.is_finite()) =>
                {
                    (log_density, gradient)
                }
                Ok(_) => {
                    target_failure = Some(TargetError::new("target returned a nonfinite value"));
                    (f64::NAN, gradient)
                }
                Err(error) => {
                    target_failure = Some(error);
                    (f64::NAN, gradient)
                }
            }
        };
        let mut rng_stop = None;
        let result = {
            let mut kernel_rng = KernelRng {
                rng: &mut rng,
                control,
                stopped: &mut rng_stop,
            };
            transition_w_with_telemetry(
                &mut kernel_rng,
                TransitionInput {
                    theta: position,
                    rho: momentum,
                },
                &inverse_mass,
                tuning(),
                &mut eval,
            )
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
        let result = result
            .map_err(Error::internal)
            .map_err(|error| error.at_transition(transition_index))?;
        position = result.result.selected.theta;
        let internal = result.result.diagnostics;
        let public = TransitionDiagnostics {
            depth: internal.depth,
            stop: map_stop(internal.stop),
            target_evaluations: internal.target_evaluations,
            direction_draws: internal.direction_draws,
            uniform_draws: internal.uniform_draws,
            leaves_attempted: internal.leaves_attempted,
            leaves_built: internal.leaves_built,
        };
        let partition = if transition_index < config.discarded {
            &mut telemetry.discarded
        } else {
            samples.extend_from_slice(&position);
            &mut telemetry.retained
        };
        partition.add_transition(dimension, &result.work, internal.uniform_draws)?;
        telemetry
            .total
            .add_transition(dimension, &result.work, internal.uniform_draws)?;
        if telemetry.total.maximum_depth_stops > config.max_maximum_depth_stops {
            return Err(Error::new(
                ErrorKind::Unhealthy,
                "maximum-depth stop limit was exceeded",
            )
            .at_transition(transition_index));
        }
        diagnostics.push(public);
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
            step_size: STEP_SIZE,
            min_micro_steps: MIN_MICRO_STEPS,
            max_refinement_levels: MAX_REFINEMENT_LEVELS,
            max_error: MAX_ERROR,
            max_depth: MAX_DEPTH,
            initial_position: initial_position.to_vec(),
            thread_count,
            mass_diagonal: mass.diagonal.clone(),
            limits: config.limits.clone(),
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
            config,
            chain_seed(config.seed, 0),
            1,
            &control,
        )
    }))
    .unwrap_or_else(|_| Err(Error::new(ErrorKind::Panic, "sampling worker panicked")))
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
                config,
                chain_seed(config.seed, chain),
                threads,
                &control,
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
            + 2 * 2 * size_of::<f64>()
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
        assert_eq!(metadata.qualified_step_size(), STEP_SIZE);
        assert_eq!(metadata.min_micro_steps(), MIN_MICRO_STEPS);
        assert_eq!(metadata.max_refinement_levels(), MAX_REFINEMENT_LEVELS);
        assert_eq!(metadata.max_error(), MAX_ERROR);
        assert_eq!(metadata.max_depth(), MAX_DEPTH);
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
}
