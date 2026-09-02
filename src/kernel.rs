//! Feature-gated, fixed-tuning prototype of one walnutpie macro leaf.
//!
//! Algorithm derived from flatironinstitute/walnutpie at commit
//! f5bba36529697c34567a2944be36b68e305c546d. Copyright the walnutpie
//! contributors; used under the MIT License.

#![allow(clippy::large_enum_variant, clippy::too_many_arguments)]

use crate::types::{State, ValidationError};
use rand::RngCore;
use rand_distr::{Distribution, StandardNormal};
use std::cell::{Cell, RefCell};
use std::ops::Deref;
use std::rc::Rc;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(crate) enum EvaluationPhase {
    Initial,
    Forward,
    Reverse,
}

#[derive(Clone, Copy, Debug)]
pub(crate) struct EvaluationContext {
    pub phase: EvaluationPhase,
    pub direction: Option<Direction>,
    pub refinement_level: Option<usize>,
    pub evaluation_in_attempt: usize,
    pub kinetic: f64,
    pub initial_hamiltonian: Option<f64>,
}

thread_local! {
    static EVALUATION_CONTEXT: Cell<Option<EvaluationContext>> = const { Cell::new(None) };
}

pub(crate) fn take_evaluation_context() -> Option<EvaluationContext> {
    EVALUATION_CONTEXT.take()
}

fn set_evaluation_context(context: EvaluationContext) {
    EVALUATION_CONTEXT.set(Some(context));
}

/// Immutable Euclidean metric used by one complete transition.
///
/// Implementations must not change while any state/span built with them is
/// live. The slice implementation below deliberately preserves the original
/// diagonal arithmetic and summation order.
pub(crate) trait MassOperator {
    fn dimension(&self) -> usize;
    fn sample_momentum(&self, rng: &mut dyn RngCore) -> Result<Vec<f64>, ValidationError>;
    fn velocity(&self, momentum: &[f64]) -> Vec<f64>;
    /// Write `velocity(momentum)` into `out` without allocating. The default
    /// forwards to [`MassOperator::velocity`] and copies, so every
    /// implementation produces identical bits either way.
    fn velocity_into(&self, momentum: &[f64], out: &mut [f64]) {
        let velocity = self.velocity(momentum);
        out.copy_from_slice(&velocity);
    }
    fn kinetic_energy(&self, momentum: &[f64]) -> f64;
    fn is_valid(&self) -> bool;
}

impl MassOperator for [f64] {
    fn sample_momentum(&self, rng: &mut dyn RngCore) -> Result<Vec<f64>, ValidationError> {
        let momentum = self
            .iter()
            .map(|inverse| {
                let normal: f64 = StandardNormal.sample(&mut *rng);
                normal / inverse.sqrt()
            })
            .collect::<Vec<_>>();
        if momentum.iter().all(|value| value.is_finite()) {
            Ok(momentum)
        } else {
            Err(ValidationError(
                "momentum refresh is not safely representable".into(),
            ))
        }
    }

    fn dimension(&self) -> usize {
        self.len()
    }

    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        momentum
            .iter()
            .zip(self)
            .map(|(p, inverse_mass)| p * inverse_mass)
            .collect()
    }

    #[inline]
    fn velocity_into(&self, momentum: &[f64], out: &mut [f64]) {
        for ((out, p), inverse_mass) in out.iter_mut().zip(momentum).zip(self) {
            *out = p * inverse_mass;
        }
    }

    #[inline]
    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        0.5 * momentum
            .iter()
            .zip(self)
            .map(|(p, m)| p * p * m)
            .sum::<f64>()
    }

    fn is_valid(&self) -> bool {
        self.iter().all(|value| value.is_finite() && *value > 0.0)
    }
}

impl<const N: usize> MassOperator for [f64; N] {
    fn sample_momentum(&self, rng: &mut dyn RngCore) -> Result<Vec<f64>, ValidationError> {
        self.as_slice().sample_momentum(rng)
    }

    fn dimension(&self) -> usize {
        N
    }

    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.as_slice().velocity(momentum)
    }

    #[inline]
    fn velocity_into(&self, momentum: &[f64], out: &mut [f64]) {
        self.as_slice().velocity_into(momentum, out)
    }

    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        self.as_slice().kinetic_energy(momentum)
    }

    fn is_valid(&self) -> bool {
        self.as_slice().is_valid()
    }
}

impl MassOperator for Vec<f64> {
    fn sample_momentum(&self, rng: &mut dyn RngCore) -> Result<Vec<f64>, ValidationError> {
        self.as_slice().sample_momentum(rng)
    }

    fn dimension(&self) -> usize {
        self.len()
    }

    fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
        self.as_slice().velocity(momentum)
    }

    #[inline]
    fn velocity_into(&self, momentum: &[f64], out: &mut [f64]) {
        self.as_slice().velocity_into(momentum, out)
    }

    fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
        self.as_slice().kinetic_energy(momentum)
    }

    fn is_valid(&self) -> bool {
        self.as_slice().is_valid()
    }
}

#[inline]
fn kinetic_energy<M: MassOperator + ?Sized>(momentum: &[f64], mass: &M) -> f64 {
    mass.kinetic_energy(momentum)
}

/// Fused log-density/gradient evaluation at the kernel boundary.
///
/// `gradient` has exactly the position's length; an implementation writes
/// every component into it and returns the log density together with a flag
/// that is `false` only when it could not produce a gradient of that length
/// (the kernel then treats the call as an invalid evaluation, exactly as it
/// treats a wrong-length gradient vector).
pub trait FusedEval {
    fn evaluate(&mut self, theta: &[f64], gradient: &mut [f64]) -> (f64, bool);
}

impl<F> FusedEval for F
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    #[inline]
    fn evaluate(&mut self, theta: &[f64], gradient: &mut [f64]) -> (f64, bool) {
        let (log_prob, returned) = self(theta);
        if returned.len() == gradient.len() {
            gradient.copy_from_slice(&returned);
            (log_prob, true)
        } else {
            (log_prob, false)
        }
    }
}

/// Adapter for callbacks that write the gradient in place.
pub struct InPlaceEval<F>(pub F);

impl<F> FusedEval for InPlaceEval<F>
where
    F: FnMut(&[f64], &mut [f64]) -> f64,
{
    #[inline]
    fn evaluate(&mut self, theta: &[f64], gradient: &mut [f64]) -> (f64, bool) {
        ((self.0)(theta, gradient), true)
    }
}

/// Per-transition scratch storage reused by every leaf and micro-step.
struct Workspace {
    candidate: State,
    reversed: State,
    velocity: Vec<f64>,
    difference: Vec<f64>,
    scaled_difference: Vec<f64>,
}

// Most recently released workspace and the freed leaf states of this
// thread. Both are pure allocation caches: their contents are always
// overwritten before use, so they cannot influence any numerical result.
thread_local! {
    static WORKSPACE_CACHE: RefCell<Option<Workspace>> = const { RefCell::new(None) };
    static STATE_POOL: RefCell<Vec<State>> = const { RefCell::new(Vec::new()) };
}

/// Upper bound on pooled leaf states per thread.
const STATE_POOL_LIMIT: usize = 4096;

impl Workspace {
    fn new(dimension: usize) -> Self {
        let blank = || State {
            theta: vec![0.0; dimension],
            rho: vec![0.0; dimension],
            log_prob: 0.0,
            grad: vec![0.0; dimension],
        };
        Self {
            candidate: blank(),
            reversed: blank(),
            velocity: vec![0.0; dimension],
            difference: vec![0.0; dimension],
            scaled_difference: vec![0.0; dimension],
        }
    }

    /// Reuse this thread's released workspace when its dimension matches.
    fn acquire(dimension: usize) -> Self {
        WORKSPACE_CACHE
            .with(|cache| cache.borrow_mut().take())
            .filter(|workspace| workspace.velocity.len() == dimension)
            .unwrap_or_else(|| Self::new(dimension))
    }

    fn release(self) {
        WORKSPACE_CACHE.with(|cache| *cache.borrow_mut() = Some(self));
    }
}

#[inline]
fn copy_state(into: &mut State, from: &State) {
    into.theta.copy_from_slice(&from.theta);
    into.rho.copy_from_slice(&from.rho);
    into.grad.copy_from_slice(&from.grad);
    into.log_prob = from.log_prob;
}

/// A copy of `from` in storage taken from this thread's pool when possible.
fn pooled_copy(from: &State) -> State {
    let recycled = STATE_POOL.with(|pool| pool.borrow_mut().pop());
    match recycled {
        Some(mut state) if state.theta.len() == from.theta.len() => {
            copy_state(&mut state, from);
            state
        }
        _ => from.clone(),
    }
}

/// A leaf state whose storage returns to the thread pool when the last
/// span referencing it is dropped.
#[derive(Debug)]
pub(crate) struct PooledState(Option<State>);

impl PooledState {
    fn new(state: State) -> Rc<Self> {
        Rc::new(Self(Some(state)))
    }

    fn into_inner(mut self) -> State {
        self.0
            .take()
            .expect("pooled state is present until dropped")
    }
}

impl Deref for PooledState {
    type Target = State;

    #[inline]
    fn deref(&self) -> &State {
        self.0
            .as_ref()
            .expect("pooled state is present until dropped")
    }
}

impl Drop for PooledState {
    fn drop(&mut self) {
        if let Some(state) = self.0.take() {
            // Ignore a torn-down thread-local: the state is simply freed.
            let _ = STATE_POOL.try_with(|pool| {
                let mut pool = pool.borrow_mut();
                if pool.len() < STATE_POOL_LIMIT {
                    pool.push(state);
                }
            });
        }
    }
}

/// One physical endpoint of a span, including its cached joint log density.
///
/// The state is shared: a fresh leaf span's two endpoints and its selected
/// candidate are the same allocation, and merging spans moves the surviving
/// endpoints without copying.
#[derive(Clone, Debug)]
pub struct Endpoint {
    pub state: Rc<PooledState>,
    pub log_joint: f64,
}

/// The position-valued candidate retained by progressive sampling.
#[derive(Clone, Debug, PartialEq)]
pub struct SelectedState {
    pub theta: Vec<f64>,
    pub grad: Vec<f64>,
    pub log_prob: f64,
}

/// A contiguous trajectory segment in physical time.
#[derive(Clone, Debug)]
pub struct Span {
    pub backward: Endpoint,
    pub forward: Endpoint,
    /// The position-valued candidate retained by progressive sampling; its
    /// `rho` is incidental and never read.
    pub selected: Rc<PooledState>,
    /// Log of the sum of the leaves' unnormalized joint densities.
    pub log_weight: f64,
}

impl Span {
    /// Construct a one-state span.
    pub fn from_state<M: MassOperator + ?Sized>(
        state: State,
        mass: &M,
    ) -> Result<Self, ValidationError> {
        validate_state_and_mass(&state, mass)?;
        let log_joint = joint_log_density(&state, mass);
        Self::from_leaf_state(state, log_joint, mass.dimension())
    }

    /// Build a one-state span from a leaf produced under an already validated
    /// metric, with the joint log density that was evaluated on that exact
    /// state.
    ///
    /// An accepted endpoint's log density and momentum are finite because its
    /// finite Hamiltonian error was tested, and its gradient because the
    /// final fused call was checked; only the position can be nonfinite
    /// (a callback that returns finite values at a nonfinite position), and
    /// that is rejected exactly as [`Span::from_state`] rejects it.
    fn from_leaf_state(
        state: State,
        log_joint: f64,
        mass_dimension: usize,
    ) -> Result<Self, ValidationError> {
        if state.theta.len() != mass_dimension {
            return Err(ValidationError(
                "state and diagonal inverse mass dimensions must match and be nonzero".into(),
            ));
        }
        if state.theta.iter().any(|value| !value.is_finite()) {
            return Err(ValidationError("state must be finite".into()));
        }
        if !log_joint.is_finite() {
            return Err(ValidationError(
                "state joint log density must be finite".into(),
            ));
        }
        let state = PooledState::new(state);
        let endpoint = Endpoint { state, log_joint };
        Ok(Self {
            backward: endpoint.clone(),
            selected: Rc::clone(&endpoint.state),
            forward: endpoint,
            log_weight: log_joint,
        })
    }

    fn from_subspans(
        earlier: Span,
        later: Span,
        selected: Rc<PooledState>,
        log_weight: f64,
    ) -> Self {
        Self {
            backward: earlier.backward,
            forward: later.forward,
            selected,
            log_weight,
        }
    }
}

/// Minimal source of scripted candidate-selection randomness.
pub trait Uniform01 {
    fn uniform_01(&mut self) -> Result<f64, ValidationError>;
}

/// Deterministic uniform source for prototype tests and future oracle traces.
#[derive(Clone, Debug)]
pub struct ScriptedUniform01 {
    values: Vec<f64>,
    consumed: usize,
}

impl ScriptedUniform01 {
    pub fn new(values: Vec<f64>) -> Self {
        Self {
            values,
            consumed: 0,
        }
    }

    pub fn consumed(&self) -> usize {
        self.consumed
    }

    pub fn remaining(&self) -> usize {
        self.values.len().saturating_sub(self.consumed)
    }
}

impl Uniform01 for ScriptedUniform01 {
    fn uniform_01(&mut self) -> Result<f64, ValidationError> {
        let value = *self
            .values
            .get(self.consumed)
            .ok_or_else(|| ValidationError("scripted uniform values exhausted".into()))?;
        if !value.is_finite() || !(0.0..1.0).contains(&value) {
            return Err(ValidationError(
                "uniform value must be finite and in [0, 1)".into(),
            ));
        }
        self.consumed += 1;
        Ok(value)
    }
}

/// Time direction in which to construct the leaf.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Direction {
    Forward,
    Backward,
}

/// Immutable tuning for one macro-leaf decision.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FixedTuning {
    /// Micro-step size at the minimum refinement level.
    pub step_size: f64,
    /// Number of attempted levels, including the minimum level.
    pub max_refinement_levels: usize,
    /// Leapfrog steps in the first attempt. Must be positive.
    pub min_micro_steps: usize,
    /// Inclusive endpoint Hamiltonian-error tolerance (`|H(end) - H(start)|`
    /// per macro step, the upstream `within_tolerance` statistic).
    pub max_error: f64,
    /// Maximum absolute trajectory energy error before a transition is divergent.
    pub divergence_threshold: f64,
}

/// Why a deterministic leaf was rejected.
///
/// `InvalidEvaluation` is a malformed evaluation (NaN or `+inf` log density,
/// nonfinite or wrong-length gradient, or a NaN Hamiltonian); integration stops
/// on that call. A log density of exactly `-inf` with a finite gradient is a
/// zero-density point, not an invalid evaluation: it fails the endpoint
/// tolerance like any over-tolerance micro-step and refines, ending in
/// `RefinementExhausted` only when every level fails, exactly as upstream
/// walnutpie treats a failed evaluation (`logp = -inf`, `grad = 0`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Rejection {
    RefinementExhausted,
    ReverseCoarserAccepted,
    InvalidEvaluation,
}

/// Deterministic result of attempting one macro leaf.
#[derive(Clone, Debug)]
pub struct MacroLeafResult {
    /// The accepted endpoint, or `None` when the leaf was rejected.
    pub end_state: Option<State>,
    /// Accepted micro-step count, or the last attempted count on exhaustion.
    pub micro_steps: usize,
    /// Total target log-density/gradient evaluations.
    pub evaluations: usize,
    /// Evaluations used by forward refinement attempts.
    pub forward_evaluations: usize,
    /// Evaluations used to test reverse coarsenings.
    pub reverse_evaluations: usize,
    /// Value supplied to upstream's step-size adaptation callback.
    pub adaptation_value: f64,
    /// Metropolis acceptance probability at the accepted refined endpoint.
    pub accepted_trajectory_adaptation_value: Option<f64>,
    /// Joint log density of the accepted endpoint, as evaluated by the final
    /// micro-step; NaN when the leaf was rejected.
    pub end_log_joint: f64,
    pub rejection: Option<Rejection>,
    pub selected_refinement_level: Option<usize>,
    pub refinement_attempts: usize,
    pub initial_hamiltonian: f64,
    pub minimum_hamiltonian: f64,
    pub maximum_hamiltonian: f64,
    pub maximum_absolute_energy_error: f64,
}

impl MacroLeafResult {
    pub fn accepted(&self) -> bool {
        self.end_state.is_some()
    }
}

/// Outcome of deterministically extending a span by one macro leaf.
#[derive(Clone, Debug)]
pub enum BuildLeafResult {
    Built {
        span: Span,
        micro_steps: usize,
        evaluations: usize,
        adaptation_value: f64,
        accepted_trajectory_adaptation_value: Option<f64>,
    },
    Stopped {
        rejection: Rejection,
        micro_steps: usize,
        evaluations: usize,
        adaptation_value: f64,
        accepted_trajectory_adaptation_value: Option<f64>,
    },
}

/// Why recursive span construction stopped.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SpanStop {
    Leaf(Rejection),
    UTurn,
}

/// Outcome of recursively constructing `2^depth` new leaves.
#[derive(Clone, Debug)]
pub enum BuildSpanResult {
    Built {
        span: Span,
        leaves: usize,
        evaluations: usize,
    },
    Stopped {
        cause: SpanStop,
        evaluations: usize,
    },
}

/// Prototype-only observation of one upstream-compatible span decision.
///
/// This module is itself excluded unless `walnutpie-prototype` is enabled, so
/// tracing cannot affect the default sampler.
#[derive(Clone, Debug, PartialEq)]
pub struct SpanTraceEvent {
    pub event: &'static str,
    pub depth: Option<usize>,
    pub direction: Direction,
    pub flag: bool,
    pub target_evaluations: usize,
    pub uniform_draw: Option<f64>,
    pub update_log_probability: Option<f64>,
    pub forward_dot: Option<f64>,
    /// `None` preserves upstream's short-circuit when the forward dot turns.
    pub backward_dot: Option<f64>,
    pub adaptation_value: Option<f64>,
    pub accepted_trajectory_adaptation_value: Option<f64>,
}

impl SpanTraceEvent {
    fn basic(
        event: &'static str,
        depth: Option<usize>,
        direction: Direction,
        flag: bool,
        target_evaluations: usize,
    ) -> Self {
        Self {
            event,
            depth,
            direction,
            flag,
            target_evaluations,
            uniform_draw: None,
            update_log_probability: None,
            forward_dot: None,
            backward_dot: None,
            adaptation_value: None,
            accepted_trajectory_adaptation_value: None,
        }
    }
}

/// Result plus execution observations for oracle integration tests.
#[derive(Clone, Debug)]
pub struct TracedBuildSpanResult {
    pub result: BuildSpanResult,
    pub events: Vec<SpanTraceEvent>,
}

/// Stable log-space addition used for span weights.
pub fn log_add_exp(left: f64, right: f64) -> Result<f64, ValidationError> {
    if left.is_nan() || right.is_nan() || left == f64::INFINITY || right == f64::INFINITY {
        return Err(ValidationError(
            "span log weights must not be NaN or positive infinity".into(),
        ));
    }
    if left == f64::NEG_INFINITY {
        return Ok(right);
    }
    if right == f64::NEG_INFINITY {
        return Ok(left);
    }
    let maximum = left.max(right);
    let result = maximum + ((left - maximum).exp() + (right - maximum).exp()).ln();
    if !result.is_finite() {
        return Err(ValidationError(
            "combined span log weight overflowed".into(),
        ));
    }
    Ok(result)
}

/// Deterministically build a one-state span from the directional endpoint.
pub fn build_leaf<F, M: MassOperator + ?Sized>(
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
) -> Result<BuildLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    validate_span(last_span, mass)?;
    validate(&last_span.forward.state, mass, tuning)?;
    let mut workspace = Workspace::new(mass.dimension());
    build_leaf_observed(
        last_span,
        mass,
        tuning,
        direction,
        eval,
        &mut TransitionWorkTelemetry::default(),
        &mut workspace,
    )
}

/// Extend an internally built span by one leaf. The span, metric and tuning
/// were validated when the transition (or public entry point) started.
fn build_leaf_observed<E, M: MassOperator + ?Sized>(
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut E,
    work: &mut TransitionWorkTelemetry,
    workspace: &mut Workspace,
) -> Result<BuildLeafResult, ValidationError>
where
    E: FusedEval,
{
    let start: &State = match direction {
        Direction::Forward => &last_span.forward.state,
        Direction::Backward => &last_span.backward.state,
    };
    increment(&mut work.leaves_attempted)?;
    let result = macro_leaf_in_workspace(start, mass, tuning, direction, eval, work, workspace)?;
    let end_log_joint = result.end_log_joint;
    match (result.end_state, result.rejection) {
        (Some(state), None) => {
            increment(&mut work.leaves_built)?;
            if let Some(level) = result.selected_refinement_level {
                if work.histograms.refinement_level_built.len() <= level {
                    work.histograms.refinement_level_built.resize(level + 1, 0);
                }
                increment(&mut work.histograms.refinement_level_built[level])?;
            }
            Ok(BuildLeafResult::Built {
                span: Span::from_leaf_state(state, end_log_joint, mass.dimension())?,
                micro_steps: result.micro_steps,
                evaluations: result.evaluations,
                adaptation_value: result.adaptation_value,
                accepted_trajectory_adaptation_value: result.accepted_trajectory_adaptation_value,
            })
        }
        (None, Some(rejection)) => Ok(BuildLeafResult::Stopped {
            rejection,
            micro_steps: result.micro_steps,
            evaluations: result.evaluations,
            adaptation_value: result.adaptation_value,
            accepted_trajectory_adaptation_value: result.accepted_trajectory_adaptation_value,
        }),
        _ => Err(ValidationError(
            "macro leaf returned an inconsistent outcome".into(),
        )),
    }
}

/// Recursively build `2^depth` leaves, stopping on exhaustion or a U-turn.
pub fn build_span<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    eval: &mut F,
) -> Result<BuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: Uniform01,
{
    validate_span(last_span, mass)?;
    validate(&last_span.forward.state, mass, tuning)?;
    let mut workspace = Workspace::new(mass.dimension());
    let shift = u32::try_from(depth)
        .map_err(|_| ValidationError("span depth overflows leaf count".into()))?;
    let leaves = 1usize
        .checked_shl(shift)
        .ok_or_else(|| ValidationError("span depth overflows leaf count".into()))?;
    let mut evaluations = 0;
    let mut leaves_attempted = 0;
    let mut leaves_built = 0;
    let mut work = TransitionWorkTelemetry::default();
    build_span_counted_inner(
        rng,
        last_span,
        mass,
        tuning,
        direction,
        depth,
        leaves,
        eval,
        &mut evaluations,
        &mut leaves_attempted,
        &mut leaves_built,
        &mut work,
        &mut workspace,
    )
}

/// Build a span while exposing prototype-only branch and RNG observations.
pub fn build_span_traced<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    eval: &mut F,
) -> Result<TracedBuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: Uniform01,
{
    validate_span(last_span, mass)?;
    validate(&last_span.forward.state, mass, tuning)?;
    let mut workspace = Workspace::new(mass.dimension());
    let shift = u32::try_from(depth)
        .map_err(|_| ValidationError("span depth overflows leaf count".into()))?;
    let leaves = 1usize
        .checked_shl(shift)
        .ok_or_else(|| ValidationError("span depth overflows leaf count".into()))?;
    let mut events = Vec::new();
    let mut evaluations = 0;
    let mut work = TransitionWorkTelemetry::default();
    let result = build_span_inner(
        rng,
        last_span,
        mass,
        tuning,
        direction,
        depth,
        leaves,
        eval,
        &mut evaluations,
        &mut |event| events.push(event),
        &mut work,
        &mut workspace,
    )?;
    Ok(TracedBuildSpanResult { result, events })
}

fn build_span_inner<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    leaves: usize,
    eval: &mut E,
    cumulative_evaluations: &mut usize,
    trace: &mut impl FnMut(SpanTraceEvent),
    work: &mut TransitionWorkTelemetry,
    workspace: &mut Workspace,
) -> Result<BuildSpanResult, ValidationError>
where
    E: FusedEval,
    R: Uniform01,
{
    trace(SpanTraceEvent::basic(
        "enter",
        Some(depth),
        direction,
        false,
        *cumulative_evaluations,
    ));
    if depth == 0 {
        return Ok(
            match build_leaf_observed(last_span, mass, tuning, direction, eval, work, workspace)? {
                BuildLeafResult::Built {
                    span,
                    evaluations,
                    adaptation_value,
                    accepted_trajectory_adaptation_value,
                    ..
                } => {
                    *cumulative_evaluations =
                        checked_add_evaluations(*cumulative_evaluations, evaluations)?;
                    let mut event = SpanTraceEvent::basic(
                        "leaf",
                        Some(depth),
                        direction,
                        true,
                        *cumulative_evaluations,
                    );
                    event.adaptation_value = Some(adaptation_value);
                    event.accepted_trajectory_adaptation_value =
                        accepted_trajectory_adaptation_value;
                    trace(event);
                    BuildSpanResult::Built {
                        span,
                        leaves: 1,
                        evaluations,
                    }
                }
                BuildLeafResult::Stopped {
                    rejection,
                    evaluations,
                    adaptation_value,
                    accepted_trajectory_adaptation_value,
                    ..
                } => {
                    *cumulative_evaluations =
                        checked_add_evaluations(*cumulative_evaluations, evaluations)?;
                    let mut event = SpanTraceEvent::basic(
                        "leaf",
                        Some(depth),
                        direction,
                        false,
                        *cumulative_evaluations,
                    );
                    event.adaptation_value = Some(adaptation_value);
                    event.accepted_trajectory_adaptation_value =
                        accepted_trajectory_adaptation_value;
                    trace(event);
                    BuildSpanResult::Stopped {
                        cause: SpanStop::Leaf(rejection),
                        evaluations,
                    }
                }
            },
        );
    }

    let first = build_span_inner(
        rng,
        last_span,
        mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        trace,
        work,
        workspace,
    )?;
    let (first_span, first_evaluations) = match first {
        BuildSpanResult::Built {
            span, evaluations, ..
        } => (span, evaluations),
        BuildSpanResult::Stopped { cause, evaluations } => {
            trace(SpanTraceEvent::basic(
                "first_leaf_exhausted",
                Some(depth),
                direction,
                false,
                *cumulative_evaluations,
            ));
            return Ok(BuildSpanResult::Stopped { cause, evaluations });
        }
    };
    let second = build_span_inner(
        rng,
        &first_span,
        mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        trace,
        work,
        workspace,
    )?;
    let (second_span, second_evaluations) = match second {
        BuildSpanResult::Built {
            span, evaluations, ..
        } => (span, evaluations),
        BuildSpanResult::Stopped { cause, evaluations } => {
            trace(SpanTraceEvent::basic(
                "second_leaf_exhausted",
                Some(depth),
                direction,
                false,
                *cumulative_evaluations,
            ));
            return Ok(BuildSpanResult::Stopped {
                cause,
                evaluations: checked_add_evaluations(first_evaluations, evaluations)?,
            });
        }
    };
    let evaluations = checked_add_evaluations(first_evaluations, second_evaluations)?;
    let (made_u_turn, forward_dot, backward_dot) =
        spans_make_u_turn_observed(&first_span, &second_span, mass, direction, workspace);
    let mut predicate = SpanTraceEvent::basic(
        "uturn_predicate",
        None,
        direction,
        made_u_turn,
        *cumulative_evaluations,
    );
    predicate.forward_dot = Some(forward_dot);
    predicate.backward_dot = backward_dot;
    trace(predicate);
    trace(SpanTraceEvent::basic(
        "uturn",
        Some(depth),
        direction,
        made_u_turn,
        *cumulative_evaluations,
    ));
    if made_u_turn {
        return Ok(BuildSpanResult::Stopped {
            cause: SpanStop::UTurn,
            evaluations,
        });
    }
    let (span, draw, update_log_probability, update) =
        combine_barker_observed(rng, first_span, second_span, direction)?;
    increment(&mut work.barker.attempted)?;
    if update {
        increment(&mut work.barker.selected_new)?;
    } else {
        increment(&mut work.barker.retained_old)?;
    }
    let mut combined =
        SpanTraceEvent::basic("combine", None, direction, update, *cumulative_evaluations);
    combined.uniform_draw = Some(draw);
    combined.update_log_probability = Some(update_log_probability);
    trace(combined);
    trace(SpanTraceEvent::basic(
        "exit",
        Some(depth),
        direction,
        true,
        *cumulative_evaluations,
    ));
    Ok(BuildSpanResult::Built {
        span,
        leaves,
        evaluations,
    })
}

fn build_span_counted_inner<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    last_span: &Span,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    leaves: usize,
    eval: &mut E,
    cumulative_evaluations: &mut usize,
    leaves_attempted: &mut usize,
    leaves_built: &mut usize,
    work: &mut TransitionWorkTelemetry,
    workspace: &mut Workspace,
) -> Result<BuildSpanResult, ValidationError>
where
    E: FusedEval,
    R: Uniform01,
{
    if depth == 0 {
        *leaves_attempted = leaves_attempted
            .checked_add(1)
            .ok_or_else(|| ValidationError("leaf count overflowed usize".into()))?;
        return Ok(
            match build_leaf_observed(last_span, mass, tuning, direction, eval, work, workspace)? {
                BuildLeafResult::Built {
                    span, evaluations, ..
                } => {
                    *cumulative_evaluations =
                        checked_add_evaluations(*cumulative_evaluations, evaluations)?;
                    *leaves_built = leaves_built
                        .checked_add(1)
                        .ok_or_else(|| ValidationError("leaf count overflowed usize".into()))?;
                    BuildSpanResult::Built {
                        span,
                        leaves: 1,
                        evaluations,
                    }
                }
                BuildLeafResult::Stopped {
                    rejection,
                    evaluations,
                    ..
                } => {
                    *cumulative_evaluations =
                        checked_add_evaluations(*cumulative_evaluations, evaluations)?;
                    BuildSpanResult::Stopped {
                        cause: SpanStop::Leaf(rejection),
                        evaluations,
                    }
                }
            },
        );
    }

    let first = build_span_counted_inner(
        rng,
        last_span,
        mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        leaves_attempted,
        leaves_built,
        work,
        workspace,
    )?;
    let (first_span, first_evaluations) = match first {
        BuildSpanResult::Built {
            span, evaluations, ..
        } => (span, evaluations),
        BuildSpanResult::Stopped { cause, evaluations } => {
            return Ok(BuildSpanResult::Stopped { cause, evaluations });
        }
    };
    let second = build_span_counted_inner(
        rng,
        &first_span,
        mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        leaves_attempted,
        leaves_built,
        work,
        workspace,
    )?;
    let (second_span, second_evaluations) = match second {
        BuildSpanResult::Built {
            span, evaluations, ..
        } => (span, evaluations),
        BuildSpanResult::Stopped { cause, evaluations } => {
            return Ok(BuildSpanResult::Stopped {
                cause,
                evaluations: checked_add_evaluations(first_evaluations, evaluations)?,
            });
        }
    };
    let evaluations = checked_add_evaluations(first_evaluations, second_evaluations)?;
    let (made_u_turn, _, _) =
        spans_make_u_turn_observed(&first_span, &second_span, mass, direction, workspace);
    if made_u_turn {
        return Ok(BuildSpanResult::Stopped {
            cause: SpanStop::UTurn,
            evaluations,
        });
    }
    let (span, _, _, update) = combine_barker_observed(rng, first_span, second_span, direction)?;
    increment(&mut work.barker.attempted)?;
    if update {
        increment(&mut work.barker.selected_new)?;
    } else {
        increment(&mut work.barker.retained_old)?;
    }
    Ok(BuildSpanResult::Built {
        span,
        leaves,
        evaluations,
    })
}

#[cfg(test)]
fn combine_barker<R: Uniform01>(
    rng: &mut R,
    old: Span,
    new: Span,
    direction: Direction,
) -> Result<Span, ValidationError> {
    combine_barker_observed(rng, old, new, direction).map(|(span, _, _, _)| span)
}

fn combine_barker_observed<R: Uniform01>(
    rng: &mut R,
    old: Span,
    new: Span,
    direction: Direction,
) -> Result<(Span, f64, f64, bool), ValidationError> {
    let total = log_add_exp(old.log_weight, new.log_weight)?;
    let update_log_probability = new.log_weight - total;
    let draw = rng.uniform_01()?;
    let update = draw.ln() < update_log_probability;
    let selected = if update {
        Rc::clone(&new.selected)
    } else {
        Rc::clone(&old.selected)
    };
    let (earlier, later) = match direction {
        Direction::Forward => (old, new),
        Direction::Backward => (new, old),
    };
    Ok((
        Span::from_subspans(earlier, later, selected, total),
        draw,
        update_log_probability,
        update,
    ))
}

fn spans_make_u_turn_observed<M: MassOperator + ?Sized>(
    first: &Span,
    second: &Span,
    mass: &M,
    direction: Direction,
    workspace: &mut Workspace,
) -> (bool, f64, Option<f64>) {
    let (earlier, later) = match direction {
        Direction::Forward => (first, second),
        Direction::Backward => (second, first),
    };
    let difference = workspace.difference.as_mut_slice();
    for ((difference, later), earlier) in difference
        .iter_mut()
        .zip(&later.forward.state.theta)
        .zip(&earlier.backward.state.theta)
    {
        *difference = later - earlier;
    }
    let scaled_difference = workspace.scaled_difference.as_mut_slice();
    mass.velocity_into(difference, scaled_difference);
    let later_dot = later
        .forward
        .state
        .rho
        .iter()
        .zip(&*scaled_difference)
        .map(|(rho, difference)| rho * difference)
        .sum::<f64>();
    if later_dot < 0.0 {
        return (true, later_dot, None);
    }
    let earlier_dot = earlier
        .backward
        .state
        .rho
        .iter()
        .zip(&*scaled_difference)
        .map(|(rho, difference)| rho * difference)
        .sum::<f64>();
    (earlier_dot < 0.0, later_dot, Some(earlier_dot))
}

#[inline]
fn checked_add_evaluations(left: usize, right: usize) -> Result<usize, ValidationError> {
    left.checked_add(right)
        .ok_or_else(|| ValidationError("evaluation count overflowed usize".into()))
}

#[inline]
fn checked_add_work(left: usize, right: usize) -> Result<usize, ValidationError> {
    left.checked_add(right)
        .ok_or_else(|| ValidationError("work telemetry count overflowed usize".into()))
}

#[inline]
fn increment(value: &mut usize) -> Result<(), ValidationError> {
    *value = checked_add_work(*value, 1)?;
    Ok(())
}

fn record_histogram(
    bins: &mut Vec<WorkHistogramBin>,
    micro_steps: usize,
) -> Result<(), ValidationError> {
    match bins.binary_search_by_key(&micro_steps, |bin| bin.micro_steps) {
        Ok(index) => increment(&mut bins[index].attempts),
        Err(index) => {
            bins.insert(
                index,
                WorkHistogramBin {
                    micro_steps,
                    attempts: 1,
                },
            );
            Ok(())
        }
    }
}

fn merge_histogram(
    target: &mut Vec<WorkHistogramBin>,
    source: &[WorkHistogramBin],
) -> Result<(), ValidationError> {
    let mut missing = 0usize;
    let mut target_index = 0usize;
    for bin in source {
        while target_index < target.len() && target[target_index].micro_steps < bin.micro_steps {
            target_index += 1;
        }
        if target_index == target.len() || target[target_index].micro_steps != bin.micro_steps {
            missing = checked_add_work(missing, 1)?;
        }
    }
    target.reserve(missing);
    for bin in source {
        match target.binary_search_by_key(&bin.micro_steps, |item| item.micro_steps) {
            Ok(index) => {
                target[index].attempts = checked_add_work(target[index].attempts, bin.attempts)?;
            }
            Err(index) => target.insert(index, *bin),
        }
    }
    Ok(())
}
fn record_stop(
    work: &mut TransitionWorkTelemetry,
    stop: TransitionStop,
) -> Result<(), ValidationError> {
    match stop {
        TransitionStop::MaxDepth => increment(&mut work.stops.max_depth),
        TransitionStop::OuterUTurn => increment(&mut work.stops.outer_uturn),
        TransitionStop::Recursive(SpanStop::UTurn) => increment(&mut work.stops.recursive_uturn),
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted)) => {
            increment(&mut work.stops.recursive_refinement_exhausted)
        }
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::ReverseCoarserAccepted)) => {
            increment(&mut work.stops.recursive_reverse_coarser_accepted)
        }
        TransitionStop::Recursive(SpanStop::Leaf(Rejection::InvalidEvaluation)) => {
            increment(&mut work.stops.recursive_invalid_evaluation)
        }
    }
}

/// One typed random operation used by a fixed-tuning transition.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum TransitionDraw {
    Direction(Direction),
    Uniform(f64),
}

/// Randomness required by a transition: directions remain distinct from uniforms.
pub trait TransitionRng: Uniform01 {
    fn direction(&mut self) -> Result<Direction, ValidationError>;
}

/// A deterministic, order-sensitive transition random source.
#[derive(Clone, Debug)]
pub struct ScriptedTransitionRng {
    draws: Vec<TransitionDraw>,
    consumed: usize,
}

/// An order-sensitive transition random source borrowing an existing tape.
///
/// This is useful for replay runners, which can avoid allocating and copying a
/// transition's scripted draws while retaining the same exhaustion semantics
/// as [`ScriptedTransitionRng`].
#[derive(Clone, Debug)]
pub struct BorrowedTransitionRng<'a> {
    draws: &'a [TransitionDraw],
    consumed: usize,
}
impl<'a> BorrowedTransitionRng<'a> {
    pub fn new(draws: &'a [TransitionDraw]) -> Self {
        Self { draws, consumed: 0 }
    }

    pub fn consumed(&self) -> usize {
        self.consumed
    }

    pub fn remaining(&self) -> usize {
        self.draws.len().saturating_sub(self.consumed)
    }

    fn next(&self) -> Result<TransitionDraw, ValidationError> {
        self.draws
            .get(self.consumed)
            .copied()
            .ok_or_else(|| ValidationError("scripted transition draws exhausted".into()))
    }
}
impl ScriptedTransitionRng {
    pub fn new(draws: Vec<TransitionDraw>) -> Self {
        Self { draws, consumed: 0 }
    }

    pub fn consumed(&self) -> usize {
        self.consumed
    }

    pub fn remaining(&self) -> usize {
        self.draws.len().saturating_sub(self.consumed)
    }

    fn next(&self) -> Result<TransitionDraw, ValidationError> {
        self.draws
            .get(self.consumed)
            .copied()
            .ok_or_else(|| ValidationError("scripted transition draws exhausted".into()))
    }
}
impl Uniform01 for ScriptedTransitionRng {
    fn uniform_01(&mut self) -> Result<f64, ValidationError> {
        let TransitionDraw::Uniform(value) = self.next()? else {
            return Err(ValidationError(
                "expected a scripted uniform draw, found a direction".into(),
            ));
        };
        if !value.is_finite() || !(0.0..1.0).contains(&value) {
            return Err(ValidationError(
                "uniform value must be finite and in [0, 1)".into(),
            ));
        }
        self.consumed += 1;
        Ok(value)
    }
}
impl TransitionRng for ScriptedTransitionRng {
    fn direction(&mut self) -> Result<Direction, ValidationError> {
        let TransitionDraw::Direction(direction) = self.next()? else {
            return Err(ValidationError(
                "expected a scripted direction, found a uniform draw".into(),
            ));
        };
        self.consumed += 1;
        Ok(direction)
    }
}
impl Uniform01 for BorrowedTransitionRng<'_> {
    fn uniform_01(&mut self) -> Result<f64, ValidationError> {
        let TransitionDraw::Uniform(value) = self.next()? else {
            return Err(ValidationError(
                "expected a scripted uniform draw, found a direction".into(),
            ));
        };
        if !value.is_finite() || !(0.0..1.0).contains(&value) {
            return Err(ValidationError(
                "uniform value must be finite and in [0, 1)".into(),
            ));
        }
        self.consumed += 1;
        Ok(value)
    }
}
impl TransitionRng for BorrowedTransitionRng<'_> {
    fn direction(&mut self) -> Result<Direction, ValidationError> {
        let TransitionDraw::Direction(direction) = self.next()? else {
            return Err(ValidationError(
                "expected a scripted direction, found a uniform draw".into(),
            ));
        };
        self.consumed += 1;
        Ok(direction)
    }
}

/// Momentum-supplied entry to a fixed-tuning transition.
#[derive(Clone, Debug, PartialEq)]
pub struct TransitionInput {
    pub theta: Vec<f64>,
    pub rho: Vec<f64>,
}

/// A momentum-supplied transition whose position target value is already
/// evaluated. This is the versioned driver/kernel boundary representation:
/// `log_prob` and `grad` remain valid across metric installations.
#[derive(Clone, Debug, PartialEq)]
pub(crate) struct EvaluatedTransitionInput {
    pub theta: Vec<f64>,
    pub rho: Vec<f64>,
    pub log_prob: f64,
    pub grad: Vec<f64>,
}

/// Immutable tuning for one fixed-tuning transition.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct TransitionTuning {
    pub leaf: FixedTuning,
    pub max_depth: usize,
}

/// Why transition doubling stopped.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum TransitionStop {
    Recursive(SpanStop),
    OuterUTurn,
    MaxDepth,
}

/// Exact logical work performed by a fixed-tuning transition.
#[derive(Clone, Debug, PartialEq)]
pub struct TransitionDiagnostics {
    pub depth: usize,
    pub stop: TransitionStop,
    pub target_evaluations: usize,
    pub direction_draws: usize,
    pub uniform_draws: usize,
    pub recursive_barker_draws: usize,
    pub outer_metropolis_draws: usize,
    pub leaves_attempted: usize,
    pub leaves_built: usize,
    /// Fused calls that returned a zero-density point (`-inf` log density,
    /// finite gradient) and therefore refined instead of stopping.
    pub zero_density_evaluations: usize,
    pub initial_hamiltonian: f64,
    pub minimum_hamiltonian: f64,
    pub maximum_hamiltonian: f64,
    pub maximum_absolute_energy_error: f64,
    pub divergent: bool,
    pub selected_refinement_level: Option<usize>,
    pub refinement_attempts: usize,
    pub reverse_coarser_rejections: usize,
}

/// Exact fused target-callback counts, partitioned by algorithmic purpose.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct FusedCallCounts {
    pub initial: usize,
    pub forward: usize,
    pub reverse: usize,
}

/// Outcomes of one class of candidate-selection draw.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SelectionDrawCounts {
    pub attempted: usize,
    pub selected_new: usize,
    pub retained_old: usize,
}

/// Exact leaf rejection causes.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct RejectionCounts {
    pub refinement_exhausted: usize,
    pub reverse_coarser_accepted: usize,
    pub invalid_forward_evaluation: usize,
    pub invalid_reverse_evaluation: usize,
}

/// Exact transition stop causes.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct StopCounts {
    pub max_depth: usize,
    pub outer_uturn: usize,
    pub recursive_uturn: usize,
    pub recursive_refinement_exhausted: usize,
    pub recursive_reverse_coarser_accepted: usize,
    pub recursive_invalid_evaluation: usize,
}

/// One sparse micro-step histogram bin.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct WorkHistogramBin {
    pub micro_steps: usize,
    pub attempts: usize,
}

/// Attempt histograms. Refinement levels are zero based.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct WorkHistogram {
    pub refinement_level_attempts: Vec<usize>,
    /// Built leaves by the refinement level at which they were accepted.
    pub refinement_level_built: Vec<usize>,
    pub forward_micro_steps: Vec<WorkHistogramBin>,
    pub reverse_micro_steps: Vec<WorkHistogramBin>,
}

/// Additive exact work performed by one transition.
#[derive(Clone, Debug, Default, PartialEq)]
pub struct TransitionWorkTelemetry {
    pub fused_calls: FusedCallCounts,
    pub forward_refinement_attempts: usize,
    pub forward_refinement_accepted: usize,
    pub forward_micro_steps_requested: usize,
    pub forward_micro_steps_executed: usize,
    pub accepted_forward_micro_steps: usize,
    pub reverse_coarsening_attempts: usize,
    pub reverse_coarsening_accepted: usize,
    pub reverse_micro_steps_requested: usize,
    pub reverse_micro_steps_executed: usize,
    pub leaves_attempted: usize,
    pub leaves_built: usize,
    /// Fused calls that returned a zero-density point (`-inf` log density
    /// with a finite gradient). Such calls refine like any over-tolerance
    /// micro-step; they never stop a transition by themselves.
    pub zero_density_evaluations: usize,
    pub rejections: RejectionCounts,
    pub stops: StopCounts,
    pub direction_draws: usize,
    pub barker: SelectionDrawCounts,
    pub metropolis: SelectionDrawCounts,
    pub histograms: WorkHistogram,
    pub initial_hamiltonian: f64,
    pub minimum_hamiltonian: f64,
    pub maximum_hamiltonian: f64,
    pub maximum_absolute_energy_error: f64,
    pub selected_refinement_level: Option<usize>,
}

impl TransitionWorkTelemetry {
    fn for_tuning(tuning: FixedTuning) -> Self {
        // Most transitions use only a handful of levels. Bound eager storage
        // so adversarial-but-valid tuning cannot turn validation into a large
        // up-front allocation; the vectors retain their normal growth path.
        let levels = tuning.max_refinement_levels.min(8);
        Self {
            histograms: WorkHistogram {
                refinement_level_attempts: Vec::with_capacity(levels),
                refinement_level_built: Vec::with_capacity(levels),
                forward_micro_steps: Vec::with_capacity(levels),
                reverse_micro_steps: Vec::with_capacity(levels.saturating_sub(1)),
            },
            ..Self::default()
        }
    }

    pub fn fused_call_total(&self) -> Result<usize, ValidationError> {
        checked_add_work(
            checked_add_work(self.fused_calls.initial, self.fused_calls.forward)?,
            self.fused_calls.reverse,
        )
    }

    pub fn validate_invariants(&self) -> Result<(), ValidationError> {
        if self.fused_calls.forward != self.forward_micro_steps_executed
            || self.fused_calls.reverse != self.reverse_micro_steps_executed
            || self.leaves_attempted
                != checked_add_work(
                    self.leaves_built,
                    checked_add_work(
                        checked_add_work(
                            self.rejections.refinement_exhausted,
                            self.rejections.reverse_coarser_accepted,
                        )?,
                        checked_add_work(
                            self.rejections.invalid_forward_evaluation,
                            self.rejections.invalid_reverse_evaluation,
                        )?,
                    )?,
                )?
            || self.barker.attempted
                != checked_add_work(self.barker.selected_new, self.barker.retained_old)?
            || self.metropolis.attempted
                != checked_add_work(self.metropolis.selected_new, self.metropolis.retained_old)?
        {
            return Err(ValidationError(
                "transition work telemetry invariant failed".into(),
            ));
        }
        self.fused_call_total()?;
        Ok(())
    }

    pub fn checked_add_assign(&mut self, other: &Self) -> Result<(), ValidationError> {
        macro_rules! add {
            ($($field:ident).+) => {
                self.$($field).+ = checked_add_work(self.$($field).+, other.$($field).+)?
            };
        }
        add!(fused_calls.initial);
        add!(fused_calls.forward);
        add!(fused_calls.reverse);
        add!(forward_refinement_attempts);
        add!(forward_refinement_accepted);
        add!(forward_micro_steps_requested);
        add!(forward_micro_steps_executed);
        add!(accepted_forward_micro_steps);
        add!(reverse_coarsening_attempts);
        add!(reverse_coarsening_accepted);
        add!(reverse_micro_steps_requested);
        add!(reverse_micro_steps_executed);
        add!(leaves_attempted);
        add!(leaves_built);
        add!(zero_density_evaluations);
        add!(rejections.refinement_exhausted);
        add!(rejections.reverse_coarser_accepted);
        add!(rejections.invalid_forward_evaluation);
        add!(rejections.invalid_reverse_evaluation);
        add!(stops.max_depth);
        add!(stops.outer_uturn);
        add!(stops.recursive_uturn);
        add!(stops.recursive_refinement_exhausted);
        add!(stops.recursive_reverse_coarser_accepted);
        add!(stops.recursive_invalid_evaluation);
        add!(direction_draws);
        add!(barker.attempted);
        add!(barker.selected_new);
        add!(barker.retained_old);
        add!(metropolis.attempted);
        add!(metropolis.selected_new);
        add!(metropolis.retained_old);

        if self.histograms.refinement_level_attempts.len()
            < other.histograms.refinement_level_attempts.len()
        {
            self.histograms
                .refinement_level_attempts
                .resize(other.histograms.refinement_level_attempts.len(), 0);
        }
        for (target, value) in self
            .histograms
            .refinement_level_attempts
            .iter_mut()
            .zip(&other.histograms.refinement_level_attempts)
        {
            *target = checked_add_work(*target, *value)?;
        }
        if self.histograms.refinement_level_built.len()
            < other.histograms.refinement_level_built.len()
        {
            self.histograms
                .refinement_level_built
                .resize(other.histograms.refinement_level_built.len(), 0);
        }
        for (target, value) in self
            .histograms
            .refinement_level_built
            .iter_mut()
            .zip(&other.histograms.refinement_level_built)
        {
            *target = checked_add_work(*target, *value)?;
        }
        merge_histogram(
            &mut self.histograms.forward_micro_steps,
            &other.histograms.forward_micro_steps,
        )?;
        merge_histogram(
            &mut self.histograms.reverse_micro_steps,
            &other.histograms.reverse_micro_steps,
        )?;
        Ok(())
    }
}

/// Selected position-valued state and diagnostics from one transition.
#[derive(Clone, Debug, PartialEq)]
pub struct TransitionResult {
    pub selected: SelectedState,
    pub diagnostics: TransitionDiagnostics,
}

/// One transition-level execution observation.
#[derive(Clone, Debug, PartialEq)]
pub struct TransitionTraceEvent {
    pub event: &'static str,
    pub depth: Option<usize>,
    pub direction: Option<Direction>,
    pub stop: Option<TransitionStop>,
    pub target_evaluations: usize,
    pub direction_draws: usize,
    pub uniform_draws: usize,
    pub flag: Option<bool>,
    pub uniform_draw: Option<f64>,
    pub update_log_probability: Option<f64>,
    pub forward_dot: Option<f64>,
    pub backward_dot: Option<f64>,
    pub adaptation_value: Option<f64>,
    pub accepted_trajectory_adaptation_value: Option<f64>,
}
impl TransitionTraceEvent {
    fn basic(
        event: &'static str,
        depth: Option<usize>,
        direction: Option<Direction>,
        counts: &TransitionCounts,
    ) -> Self {
        Self {
            event,
            depth,
            direction,
            stop: None,
            target_evaluations: counts.target_evaluations,
            direction_draws: counts.direction_draws,
            uniform_draws: counts.uniform_draws,
            flag: None,
            uniform_draw: None,
            update_log_probability: None,
            forward_dot: None,
            backward_dot: None,
            adaptation_value: None,
            accepted_trajectory_adaptation_value: None,
        }
    }
}

/// A transition result together with branch and RNG observations.
#[derive(Clone, Debug)]
pub struct TracedTransitionResult {
    pub result: TransitionResult,
    pub events: Vec<TransitionTraceEvent>,
}

/// Transition result with exact additive work telemetry.
#[derive(Clone, Debug)]
pub struct TelemetryTransitionResult {
    pub result: TransitionResult,
    pub work: TransitionWorkTelemetry,
}

/// Traced transition result with exact additive work telemetry.
#[derive(Clone, Debug)]
pub struct TracedTelemetryTransitionResult {
    pub result: TransitionResult,
    pub work: TransitionWorkTelemetry,
    pub events: Vec<TransitionTraceEvent>,
}
#[derive(Default)]
struct TransitionCounts {
    target_evaluations: usize,
    direction_draws: usize,
    uniform_draws: usize,
    recursive_barker_draws: usize,
    outer_metropolis_draws: usize,
    leaves_attempted: usize,
    leaves_built: usize,
}
struct CountedTransitionRng<'a, R> {
    inner: &'a mut R,
    direction_draws: &'a mut usize,
    uniform_draws: &'a mut usize,
}
impl<R: TransitionRng> Uniform01 for CountedTransitionRng<'_, R> {
    fn uniform_01(&mut self) -> Result<f64, ValidationError> {
        let value = self.inner.uniform_01()?;
        *self.uniform_draws = self
            .uniform_draws
            .checked_add(1)
            .ok_or_else(|| ValidationError("uniform draw count overflowed usize".into()))?;
        Ok(value)
    }
}
impl<R: TransitionRng> TransitionRng for CountedTransitionRng<'_, R> {
    fn direction(&mut self) -> Result<Direction, ValidationError> {
        let direction = self.inner.direction()?;
        *self.direction_draws = self
            .direction_draws
            .checked_add(1)
            .ok_or_else(|| ValidationError("direction draw count overflowed usize".into()))?;
        Ok(direction)
    }
}

/// Run one momentum-supplied, fixed-tuning transition.
pub fn transition_w<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    transition_w_untraced_inner(
        rng,
        input,
        mass,
        tuning,
        eval,
        None,
        OuterSelectionPolicy::BiasedProgressive,
    )
    .map(|output| output.result)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub(crate) enum OuterSelectionPolicy {
    BiasedProgressive,
    NormalizedMultinomial,
}

/// Run one transition and return exact additive work telemetry.
pub fn transition_w_with_telemetry<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    transition_w_untraced_inner(
        rng,
        input,
        mass,
        tuning,
        eval,
        None,
        OuterSelectionPolicy::BiasedProgressive,
    )
}

pub(crate) fn transition_w_with_telemetry_and_outer_policy<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    policy: OuterSelectionPolicy,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    transition_w_untraced_inner(rng, input, mass, tuning, eval, None, policy)
}

/// Run a transition from a valid cached target evaluation. The initial state
/// is validated but the callback is not invoked and initial fused-call work is
/// zero.
pub(crate) fn transition_w_from_evaluated_with_telemetry<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: EvaluatedTransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let plain = TransitionInput {
        theta: input.theta,
        rho: input.rho,
    };
    transition_w_untraced_inner(
        rng,
        plain,
        mass,
        tuning,
        eval,
        Some((input.log_prob, input.grad)),
        OuterSelectionPolicy::BiasedProgressive,
    )
}

pub(crate) fn transition_w_from_evaluated_with_telemetry_and_outer_policy<
    E,
    R,
    M: MassOperator + ?Sized,
>(
    rng: &mut R,
    input: EvaluatedTransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    policy: OuterSelectionPolicy,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    transition_w_untraced_inner(
        rng,
        TransitionInput {
            theta: input.theta,
            rho: input.rho,
        },
        mass,
        tuning,
        eval,
        Some((input.log_prob, input.grad)),
        policy,
    )
}

/// Run a transition while exposing transition and recursive-span observations.
pub fn transition_w_traced<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TracedTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(
        rng,
        input,
        mass,
        tuning,
        eval,
        None,
        OuterSelectionPolicy::BiasedProgressive,
        &mut |event| events.push(event),
    )?;
    Ok(TracedTransitionResult {
        result: output.result,
        events,
    })
}

/// Run a traced transition and return exact additive work telemetry.
pub fn transition_w_traced_with_telemetry<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TracedTelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(
        rng,
        input,
        mass,
        tuning,
        eval,
        None,
        OuterSelectionPolicy::BiasedProgressive,
        &mut |event| events.push(event),
    )?;
    Ok(TracedTelemetryTransitionResult {
        result: output.result,
        work: output.work,
        events,
    })
}

pub(crate) fn transition_w_traced_with_telemetry_and_outer_policy<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    policy: OuterSelectionPolicy,
) -> Result<TracedTelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(rng, input, mass, tuning, eval, None, policy, &mut |event| {
        events.push(event)
    })?;
    Ok(TracedTelemetryTransitionResult {
        result: output.result,
        work: output.work,
        events,
    })
}

pub(crate) fn transition_w_from_evaluated_traced_with_telemetry<F, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: EvaluatedTransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TracedTelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let mut events = Vec::new();
    let cached = Some((input.log_prob, input.grad));
    let output = transition_w_inner(
        rng,
        TransitionInput {
            theta: input.theta,
            rho: input.rho,
        },
        mass,
        tuning,
        eval,
        cached,
        OuterSelectionPolicy::BiasedProgressive,
        &mut |event| events.push(event),
    )?;
    Ok(TracedTelemetryTransitionResult {
        result: output.result,
        work: output.work,
        events,
    })
}

pub(crate) fn transition_w_from_evaluated_traced_with_telemetry_and_outer_policy<
    E,
    R,
    M: MassOperator + ?Sized,
>(
    rng: &mut R,
    input: EvaluatedTransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    policy: OuterSelectionPolicy,
) -> Result<TracedTelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(
        rng,
        TransitionInput {
            theta: input.theta,
            rho: input.rho,
        },
        mass,
        tuning,
        eval,
        Some((input.log_prob, input.grad)),
        policy,
        &mut |event| events.push(event),
    )?;
    Ok(TracedTelemetryTransitionResult {
        result: output.result,
        work: output.work,
        events,
    })
}
fn transition_w_untraced_inner<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    cached: Option<(f64, Vec<f64>)>,
    outer_policy: OuterSelectionPolicy,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    validate_transition_input(&input, mass, tuning)?;
    let mut work = TransitionWorkTelemetry::for_tuning(tuning.leaf);
    let mut workspace = Workspace::acquire(mass.dimension());
    let (log_prob, grad, initial_evaluations) = if let Some((log_prob, grad)) = cached {
        (log_prob, grad, 0)
    } else {
        set_evaluation_context(EvaluationContext {
            phase: EvaluationPhase::Initial,
            direction: None,
            refinement_level: None,
            evaluation_in_attempt: 0,
            kinetic: kinetic_energy(&input.rho, mass),
            initial_hamiltonian: None,
        });
        let mut grad = vec![0.0; input.theta.len()];
        let (log_prob, gradient_shaped) = eval.evaluate(&input.theta, &mut grad);
        work.fused_calls.initial = 1;
        if !gradient_shaped {
            return Err(ValidationError(
                "state and diagonal inverse mass dimensions must match and be nonzero".into(),
            ));
        }
        (log_prob, grad, 1)
    };
    let mut counts = TransitionCounts {
        target_evaluations: initial_evaluations,
        ..TransitionCounts::default()
    };
    let state = State {
        theta: input.theta,
        rho: input.rho,
        log_prob,
        grad,
    };
    validate_state_and_mass(&state, mass)?;
    let initial_log_joint = joint_log_density(&state, mass);
    let mut span_accum = Span::from_leaf_state(state, initial_log_joint, mass.dimension())?;

    let mut final_depth = 0;
    let mut final_stop = TransitionStop::MaxDepth;
    for depth in 1..=tuning.max_depth {
        final_depth = depth;
        let direction = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            counted_rng.direction()?
        };
        let shift = u32::try_from(depth - 1)
            .map_err(|_| ValidationError("transition depth overflows leaf count".into()))?;
        let leaves = 1usize
            .checked_shl(shift)
            .ok_or_else(|| ValidationError("transition depth overflows leaf count".into()))?;
        let uniform_before = counts.uniform_draws;
        let built = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            build_span_counted_inner(
                &mut counted_rng,
                &span_accum,
                mass,
                tuning.leaf,
                direction,
                depth - 1,
                leaves,
                eval,
                &mut counts.target_evaluations,
                &mut counts.leaves_attempted,
                &mut counts.leaves_built,
                &mut work,
                &mut workspace,
            )?
        };
        counts.recursive_barker_draws = counts
            .recursive_barker_draws
            .checked_add(counts.uniform_draws - uniform_before)
            .ok_or_else(|| ValidationError("Barker draw count overflowed usize".into()))?;

        let next_span = match built {
            BuildSpanResult::Built { span, .. } => span,
            BuildSpanResult::Stopped { cause, .. } => {
                final_stop = TransitionStop::Recursive(cause);
                break;
            }
        };

        let (outer_uturn, _, _) =
            spans_make_u_turn_observed(&span_accum, &next_span, mass, direction, &mut workspace);
        let combined = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            let (combined, _, _, update) = combine_outer_observed(
                &mut counted_rng,
                span_accum,
                next_span,
                direction,
                outer_policy,
            )?;
            increment(&mut work.metropolis.attempted)?;
            if update {
                increment(&mut work.metropolis.selected_new)?;
            } else {
                increment(&mut work.metropolis.retained_old)?;
            }
            combined
        };
        counts.outer_metropolis_draws = counts
            .outer_metropolis_draws
            .checked_add(1)
            .ok_or_else(|| ValidationError("Metropolis draw count overflowed usize".into()))?;
        span_accum = combined;

        if outer_uturn {
            final_stop = TransitionStop::OuterUTurn;
            break;
        }
    }

    work.direction_draws = counts.direction_draws;
    record_stop(&mut work, final_stop)?;
    work.validate_invariants()?;
    workspace.release();
    Ok(TelemetryTransitionResult {
        result: TransitionResult {
            selected: take_selected(span_accum),
            diagnostics: TransitionDiagnostics {
                depth: final_depth,
                stop: final_stop,
                target_evaluations: counts.target_evaluations,
                direction_draws: counts.direction_draws,
                uniform_draws: counts.uniform_draws,
                recursive_barker_draws: counts.recursive_barker_draws,
                outer_metropolis_draws: counts.outer_metropolis_draws,
                leaves_attempted: counts.leaves_attempted,
                leaves_built: counts.leaves_built,
                zero_density_evaluations: work.zero_density_evaluations,
                initial_hamiltonian: work.initial_hamiltonian,
                minimum_hamiltonian: work.minimum_hamiltonian,
                maximum_hamiltonian: work.maximum_hamiltonian,
                maximum_absolute_energy_error: work.maximum_absolute_energy_error,
                divergent: !work.maximum_absolute_energy_error.is_finite()
                    || work.maximum_absolute_energy_error > tuning.leaf.divergence_threshold,
                selected_refinement_level: work.selected_refinement_level,
                refinement_attempts: work.forward_refinement_attempts,
                reverse_coarser_rejections: work.rejections.reverse_coarser_accepted,
            },
        },
        work,
    })
}
fn transition_w_inner<E, R, M: MassOperator + ?Sized>(
    rng: &mut R,
    input: TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
    eval: &mut E,
    cached: Option<(f64, Vec<f64>)>,
    outer_policy: OuterSelectionPolicy,
    trace: &mut impl FnMut(TransitionTraceEvent),
) -> Result<TelemetryTransitionResult, ValidationError>
where
    E: FusedEval,
    R: TransitionRng,
{
    validate_transition_input(&input, mass, tuning)?;
    let mut work = TransitionWorkTelemetry::for_tuning(tuning.leaf);
    let mut workspace = Workspace::acquire(mass.dimension());
    let (log_prob, grad, initial_evaluations) = if let Some((log_prob, grad)) = cached {
        (log_prob, grad, 0)
    } else {
        set_evaluation_context(EvaluationContext {
            phase: EvaluationPhase::Initial,
            direction: None,
            refinement_level: None,
            evaluation_in_attempt: 0,
            kinetic: kinetic_energy(&input.rho, mass),
            initial_hamiltonian: None,
        });
        let mut grad = vec![0.0; input.theta.len()];
        let (log_prob, gradient_shaped) = eval.evaluate(&input.theta, &mut grad);
        work.fused_calls.initial = 1;
        if !gradient_shaped {
            return Err(ValidationError(
                "state and diagonal inverse mass dimensions must match and be nonzero".into(),
            ));
        }
        (log_prob, grad, 1)
    };
    let mut counts = TransitionCounts {
        target_evaluations: initial_evaluations,
        ..TransitionCounts::default()
    };
    let state = State {
        theta: input.theta,
        rho: input.rho,
        log_prob,
        grad,
    };
    validate_state_and_mass(&state, mass)?;
    let initial_log_joint = joint_log_density(&state, mass);
    let mut span_accum = Span::from_leaf_state(state, initial_log_joint, mass.dimension())?;
    if initial_evaluations != 0 {
        trace(TransitionTraceEvent::basic(
            "initial_evaluation",
            None,
            None,
            &counts,
        ));
    }

    let mut final_depth = 0;
    let mut final_stop = TransitionStop::MaxDepth;
    let mut final_direction = None;
    for depth in 1..=tuning.max_depth {
        final_depth = depth;
        trace(TransitionTraceEvent::basic(
            "doubling_enter",
            Some(depth),
            None,
            &counts,
        ));
        let direction = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            counted_rng.direction()?
        };
        final_direction = Some(direction);
        let mut direction_event =
            TransitionTraceEvent::basic("direction", Some(depth), Some(direction), &counts);
        direction_event.flag = Some(direction == Direction::Forward);
        trace(direction_event);

        let shift = u32::try_from(depth - 1)
            .map_err(|_| ValidationError("transition depth overflows leaf count".into()))?;
        let leaves = 1usize
            .checked_shl(shift)
            .ok_or_else(|| ValidationError("transition depth overflows leaf count".into()))?;
        let uniform_before = counts.uniform_draws;
        let mut recursive_events = Vec::new();
        let built = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            build_span_inner(
                &mut counted_rng,
                &span_accum,
                mass,
                tuning.leaf,
                direction,
                depth - 1,
                leaves,
                eval,
                &mut counts.target_evaluations,
                &mut |event| recursive_events.push(event),
                &mut work,
                &mut workspace,
            )?
        };
        counts.recursive_barker_draws = counts
            .recursive_barker_draws
            .checked_add(counts.uniform_draws - uniform_before)
            .ok_or_else(|| ValidationError("Barker draw count overflowed usize".into()))?;
        let mut recursive_uniforms_seen = 0usize;
        for event in recursive_events {
            if event.event == "leaf" {
                counts.leaves_attempted = counts
                    .leaves_attempted
                    .checked_add(1)
                    .ok_or_else(|| ValidationError("leaf count overflowed usize".into()))?;
                if event.flag {
                    counts.leaves_built = counts
                        .leaves_built
                        .checked_add(1)
                        .ok_or_else(|| ValidationError("leaf count overflowed usize".into()))?;
                }
            }
            let mut transition_event = TransitionTraceEvent::basic(
                event.event,
                event.depth,
                Some(event.direction),
                &counts,
            );
            if event.uniform_draw.is_some() {
                recursive_uniforms_seen = recursive_uniforms_seen
                    .checked_add(1)
                    .ok_or_else(|| ValidationError("uniform draw count overflowed usize".into()))?;
            }
            transition_event.target_evaluations = event.target_evaluations;
            transition_event.uniform_draws = uniform_before
                .checked_add(recursive_uniforms_seen)
                .ok_or_else(|| ValidationError("uniform draw count overflowed usize".into()))?;
            transition_event.flag = Some(event.flag);
            transition_event.uniform_draw = event.uniform_draw;
            transition_event.update_log_probability = event.update_log_probability;
            transition_event.forward_dot = event.forward_dot;
            transition_event.backward_dot = event.backward_dot;
            transition_event.adaptation_value = event.adaptation_value;
            transition_event.accepted_trajectory_adaptation_value =
                event.accepted_trajectory_adaptation_value;
            trace(transition_event);
        }

        let next_span = match built {
            BuildSpanResult::Built { span, .. } => span,
            BuildSpanResult::Stopped { cause, .. } => {
                final_stop = TransitionStop::Recursive(cause);
                let mut event = TransitionTraceEvent::basic(
                    "recursive_stop",
                    Some(depth),
                    Some(direction),
                    &counts,
                );
                event.stop = Some(final_stop);
                event.flag = Some(true);
                trace(event);
                break;
            }
        };

        let (outer_uturn, forward_dot, backward_dot) =
            spans_make_u_turn_observed(&span_accum, &next_span, mass, direction, &mut workspace);
        let mut event = TransitionTraceEvent::basic(
            "outer_uturn_predicate",
            Some(depth),
            Some(direction),
            &counts,
        );
        event.flag = Some(outer_uturn);
        event.forward_dot = Some(forward_dot);
        event.backward_dot = backward_dot;
        trace(event);

        let (combined, draw, update_log_probability, update) = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            combine_outer_observed(
                &mut counted_rng,
                span_accum,
                next_span,
                direction,
                outer_policy,
            )?
        };
        increment(&mut work.metropolis.attempted)?;
        if update {
            increment(&mut work.metropolis.selected_new)?;
        } else {
            increment(&mut work.metropolis.retained_old)?;
        }
        counts.outer_metropolis_draws = counts
            .outer_metropolis_draws
            .checked_add(1)
            .ok_or_else(|| ValidationError("Metropolis draw count overflowed usize".into()))?;
        span_accum = combined;
        let mut event = TransitionTraceEvent::basic(
            "outer_combine_metropolis",
            Some(depth),
            Some(direction),
            &counts,
        );
        event.flag = Some(update);
        event.uniform_draw = Some(draw);
        event.update_log_probability = Some(update_log_probability);
        trace(event);

        if outer_uturn {
            final_stop = TransitionStop::OuterUTurn;
            break;
        }
        let mut event =
            TransitionTraceEvent::basic("doubling_exit", Some(depth), Some(direction), &counts);
        event.flag = Some(false);
        trace(event);
    }

    let diagnostics = TransitionDiagnostics {
        depth: final_depth,
        stop: final_stop,
        target_evaluations: counts.target_evaluations,
        direction_draws: counts.direction_draws,
        uniform_draws: counts.uniform_draws,
        recursive_barker_draws: counts.recursive_barker_draws,
        outer_metropolis_draws: counts.outer_metropolis_draws,
        leaves_attempted: counts.leaves_attempted,
        leaves_built: counts.leaves_built,
        zero_density_evaluations: work.zero_density_evaluations,
        initial_hamiltonian: work.initial_hamiltonian,
        minimum_hamiltonian: work.minimum_hamiltonian,
        maximum_hamiltonian: work.maximum_hamiltonian,
        maximum_absolute_energy_error: work.maximum_absolute_energy_error,
        divergent: !work.maximum_absolute_energy_error.is_finite()
            || work.maximum_absolute_energy_error > tuning.leaf.divergence_threshold,
        selected_refinement_level: work.selected_refinement_level,
        refinement_attempts: work.forward_refinement_attempts,
        reverse_coarser_rejections: work.rejections.reverse_coarser_accepted,
    };
    let mut event = TransitionTraceEvent::basic(
        "transition_stop",
        Some(final_depth),
        final_direction,
        &counts,
    );
    event.stop = Some(final_stop);
    event.flag = Some(final_stop != TransitionStop::MaxDepth);
    trace(event);
    trace(TransitionTraceEvent::basic(
        "selected_output",
        Some(final_depth),
        None,
        &counts,
    ));
    work.direction_draws = counts.direction_draws;
    record_stop(&mut work, final_stop)?;
    work.validate_invariants()?;
    workspace.release();
    Ok(TelemetryTransitionResult {
        result: TransitionResult {
            selected: take_selected(span_accum),
            diagnostics,
        },
        work,
    })
}
fn combine_metropolis_observed<R: Uniform01>(
    rng: &mut R,
    old: Span,
    new: Span,
    direction: Direction,
) -> Result<(Span, f64, f64, bool), ValidationError> {
    let total = log_add_exp(old.log_weight, new.log_weight)?;
    let update_log_probability = new.log_weight - old.log_weight;
    let draw = rng.uniform_01()?;
    let update = draw.ln() < update_log_probability;
    let selected = if update {
        Rc::clone(&new.selected)
    } else {
        Rc::clone(&old.selected)
    };
    let (earlier, later) = match direction {
        Direction::Forward => (old, new),
        Direction::Backward => (new, old),
    };
    Ok((
        Span::from_subspans(earlier, later, selected, total),
        draw,
        update_log_probability,
        update,
    ))
}

fn combine_outer_observed<R: Uniform01>(
    rng: &mut R,
    old: Span,
    new: Span,
    direction: Direction,
    policy: OuterSelectionPolicy,
) -> Result<(Span, f64, f64, bool), ValidationError> {
    match policy {
        OuterSelectionPolicy::BiasedProgressive => {
            combine_metropolis_observed(rng, old, new, direction)
        }
        OuterSelectionPolicy::NormalizedMultinomial => {
            combine_barker_observed(rng, old, new, direction)
        }
    }
}
fn validate_transition_input<M: MassOperator + ?Sized>(
    input: &TransitionInput,
    mass: &M,
    tuning: TransitionTuning,
) -> Result<(), ValidationError> {
    let dim = input.theta.len();
    if dim == 0 || input.rho.len() != dim || mass.dimension() != dim {
        return Err(ValidationError(
            "transition input and diagonal inverse mass dimensions must match and be nonzero"
                .into(),
        ));
    }
    if input
        .theta
        .iter()
        .chain(&input.rho)
        .any(|value| !value.is_finite())
    {
        return Err(ValidationError("transition input must be finite".into()));
    }
    if !mass.is_valid() {
        return Err(ValidationError(
            "inverse mass entries must be finite and positive".into(),
        ));
    }
    if tuning.max_depth == 0 {
        return Err(ValidationError("max_depth must be positive".into()));
    }
    let shift = u32::try_from(tuning.max_depth)
        .map_err(|_| ValidationError("transition depth overflows leaf count".into()))?;
    1usize
        .checked_shl(shift)
        .ok_or_else(|| ValidationError("transition depth overflows leaf count".into()))?;
    validate_tuning(tuning.leaf)
}

/// Move the selected candidate out of the final span, copying only when a
/// surviving endpoint still shares it.
fn take_selected(span: Span) -> SelectedState {
    let Span {
        backward,
        forward,
        selected,
        ..
    } = span;
    drop(backward);
    drop(forward);
    match Rc::try_unwrap(selected) {
        Ok(pooled) => {
            let state = pooled.into_inner();
            SelectedState {
                theta: state.theta,
                grad: state.grad,
                log_prob: state.log_prob,
            }
        }
        Err(shared) => SelectedState {
            theta: shared.theta.clone(),
            grad: shared.grad.clone(),
            log_prob: shared.log_prob,
        },
    }
}

/// Build one fixed-tuning macro leaf using a diagonal inverse mass.
///
/// Refinement tests the endpoint Hamiltonian departure `|H(end) - H(start)|`
/// of each attempted level, exactly as upstream `walnutpie::macro_step`. The
/// statistic is symmetric under time reversal, so the reverse selection from
/// the accepted endpoint reproduces the forward level; a candidate is then
/// accepted only if no admissible coarser reverse trajectory also meets the
/// same inclusive endpoint tolerance. Path-wide Hamiltonian extrema are still
/// recorded for telemetry and divergence classification but never decide
/// acceptance: a path-wide criterion measured from the start state is not
/// reversible and biased the deterministic kernel toward the Neal-funnel
/// neck (revision v9 correction).
pub fn macro_leaf<F, M: MassOperator + ?Sized>(
    start: &State,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
) -> Result<MacroLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    macro_leaf_observed(
        start,
        mass,
        tuning,
        direction,
        eval,
        &mut TransitionWorkTelemetry::default(),
    )
}

pub(crate) fn macro_leaf_observed<F, M: MassOperator + ?Sized>(
    start: &State,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
    work: &mut TransitionWorkTelemetry,
) -> Result<MacroLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    validate(start, mass, tuning)?;
    let mut workspace = Workspace::new(mass.dimension());
    macro_leaf_in_workspace(start, mass, tuning, direction, eval, work, &mut workspace)
}

/// One macro leaf from a validated start under validated metric and tuning,
/// integrating in the transition's scratch states. Only the accepted endpoint
/// is copied out.
fn macro_leaf_in_workspace<E, M: MassOperator + ?Sized>(
    start: &State,
    mass: &M,
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut E,
    work: &mut TransitionWorkTelemetry,
    workspace: &mut Workspace,
) -> Result<MacroLeafResult, ValidationError>
where
    E: FusedEval,
{
    let Workspace {
        candidate,
        reversed,
        velocity,
        ..
    } = workspace;

    let initial_h = -joint_log_density(start, mass);
    observe_initial_energy(work, initial_h);
    let signed_step = match direction {
        Direction::Forward => tuning.step_size,
        Direction::Backward => -tuning.step_size,
    };
    let mut forward_evaluations = 0;
    let mut last_steps = tuning.min_micro_steps;
    let mut last_adaptation_value = 0.0;
    let mut last_integration = None;

    for level in 0..tuning.max_refinement_levels {
        let shift = u32::try_from(level)
            .map_err(|_| ValidationError("micro-step count overflowed usize".into()))?;
        let multiplier = 1usize
            .checked_shl(shift)
            .ok_or_else(|| ValidationError("micro-step count overflowed usize".into()))?;
        let micro_steps = tuning
            .min_micro_steps
            .checked_mul(multiplier)
            .ok_or_else(|| ValidationError("micro-step count overflowed usize".into()))?;
        increment(&mut work.forward_refinement_attempts)?;
        work.forward_micro_steps_requested =
            checked_add_work(work.forward_micro_steps_requested, micro_steps)?;
        if work.histograms.refinement_level_attempts.len() <= level {
            work.histograms
                .refinement_level_attempts
                .resize(level + 1, 0);
        }
        increment(&mut work.histograms.refinement_level_attempts[level])?;
        record_histogram(&mut work.histograms.forward_micro_steps, micro_steps)?;
        last_steps = micro_steps;
        let step = signed_step / multiplier as f64;
        copy_state(candidate, start);
        let integration = integrate(
            candidate,
            step,
            micro_steps,
            mass,
            initial_h,
            EvaluationPhase::Forward,
            direction,
            level,
            eval,
            velocity,
        );
        last_integration = Some(integration);
        let attempted = integration.attempted;
        let valid = integration.valid;
        let forward_log_joint = integration.endpoint_log_joint;
        work.zero_density_evaluations =
            checked_add_work(work.zero_density_evaluations, integration.zero_density)?;
        work.forward_micro_steps_executed =
            checked_add_work(work.forward_micro_steps_executed, attempted)?;
        work.fused_calls.forward = checked_add_work(work.fused_calls.forward, attempted)?;
        forward_evaluations = checked_add_evaluations(forward_evaluations, attempted)?;
        if !valid {
            observe_energy_range(work, integration.minimum, integration.maximum, initial_h);
            increment(&mut work.rejections.invalid_forward_evaluation)?;
            return Ok(MacroLeafResult {
                end_state: None,
                micro_steps,
                evaluations: forward_evaluations,
                forward_evaluations,
                reverse_evaluations: 0,
                adaptation_value: 0.0,
                accepted_trajectory_adaptation_value: None,
                end_log_joint: f64::NAN,
                rejection: Some(Rejection::InvalidEvaluation),
                selected_refinement_level: None,
                refinement_attempts: level + 1,
                initial_hamiltonian: initial_h,
                minimum_hamiltonian: work.minimum_hamiltonian,
                maximum_hamiltonian: work.maximum_hamiltonian,
                maximum_absolute_energy_error: work.maximum_absolute_energy_error,
            });
        }
        if level == 0 {
            last_adaptation_value = (-integration.endpoint_error).exp();
        }

        if integration.endpoint_error <= tuning.max_error {
            increment(&mut work.forward_refinement_accepted)?;
            work.accepted_forward_micro_steps =
                checked_add_work(work.accepted_forward_micro_steps, micro_steps)?;
            let mut reverse_evaluations = 0;
            let mut coarse_steps = micro_steps;
            let mut coarse_step = step;
            while coarse_steps / 2 >= tuning.min_micro_steps {
                coarse_steps /= 2;
                coarse_step *= 2.0;
                increment(&mut work.reverse_coarsening_attempts)?;
                work.reverse_micro_steps_requested =
                    checked_add_work(work.reverse_micro_steps_requested, coarse_steps)?;
                record_histogram(&mut work.histograms.reverse_micro_steps, coarse_steps)?;
                copy_state(reversed, candidate);
                for momentum in &mut reversed.rho {
                    *momentum = -*momentum;
                }
                let reverse_initial_h = -forward_log_joint;
                let integration = integrate(
                    reversed,
                    coarse_step,
                    coarse_steps,
                    mass,
                    reverse_initial_h,
                    EvaluationPhase::Reverse,
                    match direction {
                        Direction::Forward => Direction::Backward,
                        Direction::Backward => Direction::Forward,
                    },
                    level,
                    eval,
                    velocity,
                );
                let attempted = integration.attempted;
                let valid = integration.valid;
                work.zero_density_evaluations =
                    checked_add_work(work.zero_density_evaluations, integration.zero_density)?;
                work.reverse_micro_steps_executed =
                    checked_add_work(work.reverse_micro_steps_executed, attempted)?;
                work.fused_calls.reverse = checked_add_work(work.fused_calls.reverse, attempted)?;
                reverse_evaluations = checked_add_evaluations(reverse_evaluations, attempted)?;
                if !valid {
                    observe_energy_range(
                        work,
                        integration.minimum,
                        integration.maximum,
                        reverse_initial_h,
                    );
                    increment(&mut work.rejections.invalid_reverse_evaluation)?;
                    return Ok(MacroLeafResult {
                        end_state: None,
                        micro_steps,
                        evaluations: checked_add_evaluations(
                            forward_evaluations,
                            reverse_evaluations,
                        )?,
                        forward_evaluations,
                        reverse_evaluations,
                        adaptation_value: last_adaptation_value,
                        accepted_trajectory_adaptation_value: None,
                        end_log_joint: f64::NAN,
                        rejection: Some(Rejection::InvalidEvaluation),
                        selected_refinement_level: None,
                        refinement_attempts: level + 1,
                        initial_hamiltonian: initial_h,
                        minimum_hamiltonian: work.minimum_hamiltonian,
                        maximum_hamiltonian: work.maximum_hamiltonian,
                        maximum_absolute_energy_error: work.maximum_absolute_energy_error,
                    });
                }
                if integration.endpoint_error <= tuning.max_error {
                    increment(&mut work.reverse_coarsening_accepted)?;
                    increment(&mut work.rejections.reverse_coarser_accepted)?;
                    return Ok(MacroLeafResult {
                        end_state: None,
                        micro_steps,
                        evaluations: checked_add_evaluations(
                            forward_evaluations,
                            reverse_evaluations,
                        )?,
                        forward_evaluations,
                        reverse_evaluations,
                        adaptation_value: last_adaptation_value,
                        accepted_trajectory_adaptation_value: None,
                        end_log_joint: f64::NAN,
                        rejection: Some(Rejection::ReverseCoarserAccepted),
                        selected_refinement_level: None,
                        refinement_attempts: level + 1,
                        initial_hamiltonian: initial_h,
                        minimum_hamiltonian: work.minimum_hamiltonian,
                        maximum_hamiltonian: work.maximum_hamiltonian,
                        maximum_absolute_energy_error: work.maximum_absolute_energy_error,
                    });
                }
            }
            work.selected_refinement_level = Some(
                work.selected_refinement_level
                    .map_or(level, |selected| selected.max(level)),
            );
            observe_energy_range(work, integration.minimum, integration.maximum, initial_h);
            let accepted_trajectory_adaptation_value =
                (initial_h + forward_log_joint).min(0.0).exp();
            return Ok(MacroLeafResult {
                end_state: Some(pooled_copy(candidate)),
                micro_steps,
                evaluations: checked_add_evaluations(forward_evaluations, reverse_evaluations)?,
                forward_evaluations,
                reverse_evaluations,
                adaptation_value: last_adaptation_value,
                accepted_trajectory_adaptation_value: Some(accepted_trajectory_adaptation_value),
                end_log_joint: forward_log_joint,
                rejection: None,
                selected_refinement_level: Some(level),
                refinement_attempts: level + 1,
                initial_hamiltonian: initial_h,
                minimum_hamiltonian: work.minimum_hamiltonian,
                maximum_hamiltonian: work.maximum_hamiltonian,
                maximum_absolute_energy_error: work.maximum_absolute_energy_error,
            });
        }
    }

    increment(&mut work.rejections.refinement_exhausted)?;
    if let Some(integration) = last_integration {
        observe_energy_range(work, integration.minimum, integration.maximum, initial_h);
    }
    Ok(MacroLeafResult {
        end_state: None,
        micro_steps: last_steps,
        evaluations: forward_evaluations,
        forward_evaluations,
        reverse_evaluations: 0,
        adaptation_value: last_adaptation_value,
        accepted_trajectory_adaptation_value: None,
        end_log_joint: f64::NAN,
        rejection: Some(Rejection::RefinementExhausted),
        selected_refinement_level: None,
        refinement_attempts: tuning.max_refinement_levels,
        initial_hamiltonian: initial_h,
        minimum_hamiltonian: work.minimum_hamiltonian,
        maximum_hamiltonian: work.maximum_hamiltonian,
        maximum_absolute_energy_error: work.maximum_absolute_energy_error,
    })
}

fn validate<M: MassOperator + ?Sized>(
    start: &State,
    mass: &M,
    tuning: FixedTuning,
) -> Result<(), ValidationError> {
    validate_state_and_mass(start, mass)?;
    validate_tuning(tuning)
}

fn validate_tuning(tuning: FixedTuning) -> Result<(), ValidationError> {
    if !tuning.step_size.is_finite() || tuning.step_size <= 0.0 {
        return Err(ValidationError(
            "step_size must be finite and positive".into(),
        ));
    }
    if tuning.max_refinement_levels == 0 || tuning.min_micro_steps == 0 {
        return Err(ValidationError(
            "refinement levels and min_micro_steps must be positive".into(),
        ));
    }
    let last_level = tuning.max_refinement_levels - 1;
    let shift = u32::try_from(last_level)
        .map_err(|_| ValidationError("micro-step count overflowed usize".into()))?;
    let multiplier = 1usize
        .checked_shl(shift)
        .ok_or_else(|| ValidationError("micro-step count overflowed usize".into()))?;
    tuning
        .min_micro_steps
        .checked_mul(multiplier)
        .ok_or_else(|| ValidationError("micro-step count overflowed usize".into()))?;
    if !tuning.max_error.is_finite() || tuning.max_error <= 0.0 {
        return Err(ValidationError(
            "max_error must be finite and positive".into(),
        ));
    }
    if !tuning.divergence_threshold.is_finite() || tuning.divergence_threshold <= 0.0 {
        return Err(ValidationError(
            "divergence threshold must be finite and positive".into(),
        ));
    }
    Ok(())
}

fn validate_state_and_mass<M: MassOperator + ?Sized>(
    state: &State,
    mass: &M,
) -> Result<(), ValidationError> {
    validate_state_shape_and_finiteness(state, mass.dimension())?;
    if !mass.is_valid() {
        return Err(ValidationError(
            "inverse mass entries must be finite and positive".into(),
        ));
    }
    Ok(())
}

fn validate_state_shape_and_finiteness(
    state: &State,
    mass_dimension: usize,
) -> Result<(), ValidationError> {
    let dim = state.theta.len();
    if dim == 0 || state.rho.len() != dim || state.grad.len() != dim || mass_dimension != dim {
        return Err(ValidationError(
            "state and diagonal inverse mass dimensions must match and be nonzero".into(),
        ));
    }
    if !state.log_prob.is_finite()
        || state
            .theta
            .iter()
            .chain(&state.rho)
            .chain(&state.grad)
            .any(|value| !value.is_finite())
    {
        return Err(ValidationError("state must be finite".into()));
    }
    Ok(())
}

fn validate_span<M: MassOperator + ?Sized>(span: &Span, mass: &M) -> Result<(), ValidationError> {
    validate_state_and_mass(&span.backward.state, mass)?;
    validate_state_and_mass(&span.forward.state, mass)?;
    let dim = mass.dimension();
    if span.selected.theta.len() != dim
        || span.selected.grad.len() != dim
        || !span.selected.log_prob.is_finite()
        || span
            .selected
            .theta
            .iter()
            .chain(&span.selected.grad)
            .any(|value| !value.is_finite())
        || !span.backward.log_joint.is_finite()
        || !span.forward.log_joint.is_finite()
        || !span.log_weight.is_finite()
    {
        return Err(ValidationError(
            "span dimensions and cached values must be finite and consistent".into(),
        ));
    }
    Ok(())
}

#[derive(Clone, Copy, Debug)]
struct IntegrationObservation {
    attempted: usize,
    valid: bool,
    minimum: f64,
    maximum: f64,
    /// Largest departure of any visited micro-step from the initial
    /// Hamiltonian. Telemetry and divergence classification only.
    maximum_absolute_error: f64,
    /// Departure of the final micro-step from the initial Hamiltonian. This
    /// is the upstream `within_tolerance` acceptance statistic; it is
    /// symmetric under time reversal, which the path-wide maximum is not.
    /// It is `+inf` when the final micro-step landed in the zero-density
    /// region.
    endpoint_error: f64,
    /// Fused calls in this attempt that returned a zero-density point
    /// (log density exactly `-inf` with a finite gradient).
    zero_density: usize,
    /// Joint log density of the state after the final micro-step, exactly
    /// the negated `energy` tested there. NaN when the attempt is invalid.
    endpoint_log_joint: f64,
}

fn integrate<E, M: MassOperator + ?Sized>(
    state: &mut State,
    step: f64,
    count: usize,
    mass: &M,
    initial_hamiltonian: f64,
    phase: EvaluationPhase,
    direction: Direction,
    refinement_level: usize,
    eval: &mut E,
    velocity: &mut [f64],
) -> IntegrationObservation
where
    E: FusedEval,
{
    let half_step = 0.5 * step;
    let mut minimum = initial_hamiltonian;
    let mut maximum = initial_hamiltonian;
    let mut maximum_absolute_error = 0.0_f64;
    let mut endpoint_error = 0.0_f64;
    let mut endpoint_log_joint = f64::NAN;
    let mut zero_density = 0usize;
    for evaluation in 0..count {
        for (momentum, gradient) in state.rho.iter_mut().zip(&state.grad) {
            *momentum += half_step * gradient;
        }
        mass.velocity_into(&state.rho, velocity);
        for (position, velocity) in state.theta.iter_mut().zip(&*velocity) {
            *position += step * velocity;
        }
        set_evaluation_context(EvaluationContext {
            phase,
            direction: Some(direction),
            refinement_level: Some(refinement_level),
            evaluation_in_attempt: evaluation,
            kinetic: kinetic_energy(&state.rho, mass),
            initial_hamiltonian: Some(initial_hamiltonian),
        });
        let (log_prob, gradient_shaped) = eval.evaluate(&state.theta, &mut state.grad);
        let gradient_finite = gradient_shaped && state.grad.iter().all(|value| value.is_finite());
        if log_prob == f64::NEG_INFINITY && gradient_finite {
            // Zero-density point (upstream maps a failed evaluation to
            // `logp = -inf`, `grad = 0`). Integration continues with the
            // supplied gradient; the endpoint statistic becomes `+inf` only if
            // this is the final micro-step, exactly as upstream
            // `macro_step`/`within_tolerance`, which overwrite the log density
            // at every micro-step and test the final one.
            zero_density += 1;
            state.log_prob = f64::NEG_INFINITY;
        } else if !log_prob.is_finite() || !gradient_finite {
            state.log_prob = f64::NEG_INFINITY;
            state.grad.fill(0.0);
            return IntegrationObservation {
                attempted: evaluation + 1,
                valid: false,
                minimum: f64::NEG_INFINITY,
                maximum: f64::INFINITY,
                maximum_absolute_error: f64::INFINITY,
                endpoint_error: f64::INFINITY,
                zero_density,
                endpoint_log_joint: f64::NAN,
            };
        } else {
            state.log_prob = log_prob;
        }
        for (momentum, gradient) in state.rho.iter_mut().zip(&state.grad) {
            *momentum += half_step * gradient;
        }
        let log_joint = joint_log_density(state, mass);
        let energy = -log_joint;
        if energy.is_nan() {
            return IntegrationObservation {
                attempted: evaluation + 1,
                valid: false,
                minimum: f64::NEG_INFINITY,
                maximum: f64::INFINITY,
                maximum_absolute_error: f64::INFINITY,
                endpoint_error: f64::INFINITY,
                zero_density,
                endpoint_log_joint: f64::NAN,
            };
        }
        if energy.is_finite() {
            // Zero-density points have infinite energy; they are excluded from
            // the Hamiltonian extrema and the divergence statistic because
            // they are a target-support boundary, not a numerical blow-up.
            minimum = minimum.min(energy);
            maximum = maximum.max(energy);
            maximum_absolute_error =
                maximum_absolute_error.max((energy - initial_hamiltonian).abs());
        }
        endpoint_error = (energy - initial_hamiltonian).abs();
        endpoint_log_joint = log_joint;
    }
    IntegrationObservation {
        attempted: count,
        valid: true,
        minimum,
        maximum,
        maximum_absolute_error,
        endpoint_error,
        zero_density,
        endpoint_log_joint,
    }
}

fn observe_initial_energy(work: &mut TransitionWorkTelemetry, energy: f64) {
    if work.fused_calls.initial <= 1 && work.forward_refinement_attempts == 0 {
        work.initial_hamiltonian = energy;
        work.minimum_hamiltonian = energy;
        work.maximum_hamiltonian = energy;
    }
}

fn observe_energy_range(
    work: &mut TransitionWorkTelemetry,
    minimum: f64,
    maximum: f64,
    reference: f64,
) {
    work.minimum_hamiltonian = work.minimum_hamiltonian.min(minimum);
    work.maximum_hamiltonian = work.maximum_hamiltonian.max(maximum);
    let error = (minimum - reference).abs().max((maximum - reference).abs());
    work.maximum_absolute_energy_error = work.maximum_absolute_energy_error.max(error);
}

#[inline]
fn joint_log_density<M: MassOperator + ?Sized>(state: &State, mass: &M) -> f64 {
    state.log_prob - mass.kinetic_energy(&state.rho)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::cell::Cell;

    fn same_selected(left: &State, right: &State) -> bool {
        left.theta == right.theta && left.grad == right.grad && left.log_prob == right.log_prob
    }

    struct CoupledMass {
        generation: u64,
        calls: Cell<usize>,
    }

    impl MassOperator for CoupledMass {
        fn sample_momentum(&self, _: &mut dyn RngCore) -> Result<Vec<f64>, ValidationError> {
            unreachable!("test operator uses supplied momentum")
        }

        fn dimension(&self) -> usize {
            2
        }

        fn velocity(&self, momentum: &[f64]) -> Vec<f64> {
            self.calls.set(self.calls.get() + 1);
            vec![
                1.5 * momentum[0] + 0.25 * momentum[1],
                0.25 * momentum[0] + 0.75 * momentum[1],
            ]
        }

        fn kinetic_energy(&self, momentum: &[f64]) -> f64 {
            let velocity = self.velocity(momentum);
            0.5 * momentum
                .iter()
                .zip(velocity)
                .map(|(p, v)| p * v)
                .sum::<f64>()
        }

        fn is_valid(&self) -> bool {
            true
        }
    }

    #[test]
    fn original_q_mass_operator_leapfrog_is_reversible_and_generation_is_fixed() {
        let mass = CoupledMass {
            generation: 7,
            calls: Cell::new(0),
        };
        let initial = State {
            theta: vec![0.2, -0.4],
            rho: vec![0.7, -0.3],
            log_prob: -0.1,
            grad: vec![-0.2, 0.4],
        };
        let mut state = initial.clone();
        let mut velocity = vec![0.0; 2];
        let initial_h = -joint_log_density(&state, &mass);
        let mut eval = |q: &[f64]| {
            (
                -0.5 * q.iter().map(|x| x * x).sum::<f64>(),
                q.iter().map(|x| -*x).collect(),
            )
        };
        let forward = integrate(
            &mut state,
            0.03,
            5,
            &mass,
            initial_h,
            EvaluationPhase::Forward,
            Direction::Forward,
            0,
            &mut eval,
            &mut velocity,
        );
        assert!(forward.valid);
        let reverse_h = -joint_log_density(&state, &mass);
        let reverse = integrate(
            &mut state,
            -0.03,
            5,
            &mass,
            reverse_h,
            EvaluationPhase::Reverse,
            Direction::Backward,
            0,
            &mut eval,
            &mut velocity,
        );
        assert!(reverse.valid);
        for (actual, expected) in state.theta.iter().zip(&initial.theta) {
            assert!((actual - expected).abs() < 2.0e-15);
        }
        for (actual, expected) in state.rho.iter().zip(&initial.rho) {
            assert!((actual - expected).abs() < 2.0e-15);
        }
        assert_eq!(mass.generation, 7);
        assert!(mass.calls.get() > 0);
    }

    #[test]
    fn metric_boundary_install_does_not_remap_q_or_cached_target_state() {
        let selected = SelectedState {
            theta: vec![0.2, -0.4],
            grad: vec![-0.2, 0.4],
            log_prob: -0.1,
        };
        let before = selected.clone();
        let old_mass = CoupledMass {
            generation: 3,
            calls: Cell::new(0),
        };
        let new_mass = CoupledMass {
            generation: 4,
            calls: Cell::new(0),
        };
        assert_ne!(old_mass.generation, new_mass.generation);
        assert_eq!(selected, before);
        assert_eq!(old_mass.calls.get(), 0);
        assert_eq!(new_mass.calls.get(), 0);
    }

    #[test]
    fn complete_transition_uses_one_coupled_metric_generation_with_exact_rng_and_work() {
        let mass = CoupledMass {
            generation: 11,
            calls: Cell::new(0),
        };
        let mut rng = ScriptedTransitionRng::new(vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.25),
        ]);
        let output = transition_w_with_telemetry(
            &mut rng,
            TransitionInput {
                theta: vec![0.2, -0.4],
                rho: vec![0.7, -0.3],
            },
            &mass,
            TransitionTuning {
                leaf: FixedTuning {
                    step_size: 0.03,
                    max_refinement_levels: 1,
                    min_micro_steps: 1,
                    max_error: 1.0,
                    divergence_threshold: 1000.0,
                },
                max_depth: 1,
            },
            &mut gaussian,
        )
        .unwrap();
        assert_eq!(mass.generation, 11);
        assert_eq!(rng.consumed(), 2);
        assert_eq!(output.result.diagnostics.direction_draws, 1);
        assert_eq!(output.result.diagnostics.uniform_draws, 1);
        assert_eq!(output.result.diagnostics.target_evaluations, 2);
        assert_eq!(output.work.forward_micro_steps_executed, 1);
        assert!(mass.calls.get() > 0);
    }

    fn gaussian(theta: &[f64]) -> (f64, Vec<f64>) {
        (
            -0.5 * theta.iter().map(|value| value * value).sum::<f64>(),
            theta.iter().map(|value| -*value).collect(),
        )
    }

    fn state(theta: f64, rho: f64) -> State {
        State {
            theta: vec![theta],
            rho: vec![rho],
            log_prob: -0.5 * theta * theta,
            grad: vec![-theta],
        }
    }

    fn tuning(step_size: f64, levels: usize, min_steps: usize, error: f64) -> FixedTuning {
        FixedTuning {
            step_size,
            max_refinement_levels: levels,
            min_micro_steps: min_steps,
            max_error: error,
            divergence_threshold: 1000.0,
        }
    }

    #[test]
    fn minimum_level_accepts_forward_and_backward_with_exact_counts() {
        for direction in [Direction::Forward, Direction::Backward] {
            let result = macro_leaf(
                &state(0.7, 0.4),
                &[1.0],
                tuning(0.1, 3, 2, 1.0),
                direction,
                &mut gaussian,
            )
            .unwrap();
            assert!(result.accepted());
            assert_eq!(result.micro_steps, 2);
            assert_eq!(result.forward_evaluations, 2);
            assert_eq!(result.reverse_evaluations, 0);
            assert_eq!(result.evaluations, 2);
        }
    }

    #[test]
    fn reports_refinement_exhaustion_and_exact_counts() {
        let result = macro_leaf(
            &state(1.0, 0.0),
            &[1.0],
            tuning(3.0, 3, 1, 1e-14),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::RefinementExhausted));
        assert_eq!(result.micro_steps, 4);
        assert_eq!(result.evaluations, 1 + 2 + 4);
    }

    #[test]
    fn inclusive_endpoint_boundary_is_accepted() {
        let start = state(0.8, 0.3);
        let trial = macro_leaf(
            &start,
            &[1.0],
            tuning(0.7, 1, 1, f64::MAX),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        let endpoint = trial.end_state.unwrap();
        let boundary =
            (joint_log_density(&endpoint, &[1.0]) - joint_log_density(&start, &[1.0])).abs();
        let result = macro_leaf(
            &start,
            &[1.0],
            tuning(0.7, 1, 1, boundary),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        assert!(result.accepted());
    }

    #[test]
    fn interior_energy_spike_is_accepted_when_endpoint_returns_close() {
        // Upstream `within_tolerance` semantics: acceptance is decided by the
        // endpoint Hamiltonian departure only. The interior excursion is still
        // reported through the path-wide telemetry fields.
        let result = macro_leaf(
            &state(1.0, 0.0),
            &[1.0],
            tuning(1.41, 1, 2, 1e-4),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        assert!(result.accepted());
        assert_eq!(result.micro_steps, 2);
        assert_eq!(result.evaluations, 2);
        assert!(result.maximum_absolute_energy_error > 1e-4);
        let end = result.end_state.unwrap();
        let endpoint_error =
            (joint_log_density(&end, &[1.0]) - joint_log_density(&state(1.0, 0.0), &[1.0])).abs();
        assert!(endpoint_error <= 1e-4);
    }

    #[test]
    fn reverse_coarser_acceptance_rejects_leaf() {
        let result = macro_leaf(
            &state(1.0, 0.0),
            &[1.0],
            tuning(3.48, 2, 1, 0.8178),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::ReverseCoarserAccepted));
        assert_eq!(result.forward_evaluations, 1 + 2);
        assert_eq!(result.reverse_evaluations, 1);
        assert_eq!(result.evaluations, 4);
    }

    #[test]
    fn invalid_reverse_replay_stops_on_the_failed_call_with_exact_work() {
        let mut calls = 0;
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(1.0, 0.0),
            &[1.0],
            tuning(3.48, 2, 1, 0.8178),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 4 {
                    (f64::NAN, vec![f64::NAN; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
            &mut work,
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::InvalidEvaluation));
        assert_eq!(result.forward_evaluations, 3);
        assert_eq!(result.reverse_evaluations, 1);
        assert_eq!(result.evaluations, 4);
        assert_eq!(calls, 4);
        assert_eq!(work.fused_calls.forward, 3);
        assert_eq!(work.fused_calls.reverse, 1);
        assert_eq!(work.reverse_micro_steps_executed, 1);
        assert_eq!(work.rejections.invalid_reverse_evaluation, 1);
        assert_eq!(work.rejections.reverse_coarser_accepted, 0);
    }

    #[test]
    fn invalid_reverse_replay_consumes_only_its_direction_draw() {
        let mut rng =
            ScriptedTransitionRng::new(vec![TransitionDraw::Direction(Direction::Forward)]);
        let mut calls = 0;
        let output = transition_w_with_telemetry(
            &mut rng,
            TransitionInput {
                theta: vec![1.0],
                rho: vec![0.0],
            },
            &[1.0],
            transition_tuning(3.48, 1, 2, 1, 0.8178),
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 5 {
                    (f64::NAN, vec![f64::NAN; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
        )
        .unwrap();
        assert_eq!(
            output.result.diagnostics.stop,
            TransitionStop::Recursive(SpanStop::Leaf(Rejection::InvalidEvaluation))
        );
        assert_eq!(output.result.diagnostics.target_evaluations, 5);
        assert_eq!(output.result.diagnostics.direction_draws, 1);
        assert_eq!(output.result.diagnostics.uniform_draws, 0);
        assert_eq!(rng.consumed(), 1);
        assert_eq!(output.work.fused_calls.initial, 1);
        assert_eq!(output.work.fused_calls.forward, 3);
        assert_eq!(output.work.fused_calls.reverse, 1);
    }

    #[test]
    fn rejects_invalid_diagonal_mass() {
        assert!(
            macro_leaf(
                &state(0.0, 1.0),
                &[0.0],
                tuning(0.1, 1, 1, 0.1),
                Direction::Forward,
                &mut gaussian,
            )
            .is_err()
        );
    }

    #[test]
    fn accepts_non_power_of_two_minimum_steps() {
        let result = macro_leaf(
            &state(0.7, 0.4),
            &[1.0],
            tuning(0.1, 2, 3, 1.0),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap();
        assert!(result.accepted());
        assert_eq!(result.micro_steps, 3);
        assert_eq!(result.evaluations, 3);
    }

    #[test]
    fn rejects_micro_step_count_overflow() {
        assert!(
            macro_leaf(
                &state(0.0, 1.0),
                &[1.0],
                tuning(0.1, 2, usize::MAX, 0.1),
                Direction::Forward,
                &mut gaussian,
            )
            .is_err()
        );
    }

    #[test]
    fn invalid_intermediate_evaluation_rejects_immediately() {
        let mut calls = 0;
        let result = macro_leaf(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.1, 3, 2, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 1 {
                    (f64::NAN, vec![f64::NAN; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::InvalidEvaluation));
        assert_eq!(result.evaluations, 1);
        assert_eq!(calls, 1);
    }

    /// Zero-density endpoint at the coarsest level refines to the next level
    /// and is accepted there; the level-0 adaptation statistic is `exp(-inf)`.
    /// The coarse step overshoots into the wall in both directions (calls 1
    /// and 4), so the reverse coarsening check is not within tolerance and
    /// the finer leaf is reversible.
    #[test]
    fn zero_density_endpoint_refines_instead_of_stopping() {
        let mut calls = 0;
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.2, 3, 1, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 1 || calls == 4 {
                    (f64::NEG_INFINITY, vec![0.0; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
            &mut work,
        )
        .unwrap();
        assert!(result.accepted(), "{:?}", result.rejection);
        assert_eq!(result.selected_refinement_level, Some(1));
        assert_eq!(result.micro_steps, 2);
        assert_eq!(result.adaptation_value, 0.0);
        // Level 0 (1 call) + level 1 (2 calls) + reverse coarser check (1 call).
        assert_eq!(result.forward_evaluations, 3);
        assert_eq!(result.reverse_evaluations, 1);
        assert_eq!(work.zero_density_evaluations, 2);
        assert_eq!(work.rejections.invalid_forward_evaluation, 0);
        assert_eq!(work.rejections.invalid_reverse_evaluation, 0);
        assert!(result.maximum_absolute_energy_error.is_finite());
        assert!(result.maximum_hamiltonian.is_finite());
    }

    /// The same leaf with a valid coarse reverse step is rejected as
    /// non-reversible (the coarser level would have been selected in
    /// reverse), exactly as any finite over-tolerance forward level.
    #[test]
    fn zero_density_forward_with_valid_coarse_reverse_is_not_reversible() {
        let mut calls = 0;
        let result = macro_leaf(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.2, 3, 1, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 1 {
                    (f64::NEG_INFINITY, vec![0.0; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::ReverseCoarserAccepted));
        assert_eq!(result.forward_evaluations, 3);
        assert_eq!(result.reverse_evaluations, 1);
    }

    /// Every level ending in the zero-density region is refinement
    /// exhaustion, never an invalid-evaluation stop.
    #[test]
    fn zero_density_at_every_level_is_refinement_exhaustion() {
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.2, 3, 1, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| {
                if theta[0] > 0.04 {
                    (f64::NEG_INFINITY, vec![0.0; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
            &mut work,
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::RefinementExhausted));
        assert_eq!(result.refinement_attempts, 3);
        assert_eq!(result.forward_evaluations, 1 + 2 + 4);
        assert_eq!(result.reverse_evaluations, 0);
        assert_eq!(work.rejections.refinement_exhausted, 1);
        assert_eq!(work.rejections.invalid_forward_evaluation, 0);
        assert_eq!(work.zero_density_evaluations, 1 + 2 + 4);
    }

    /// Upstream `macro_step` overwrites the log density at every micro-step
    /// and tests only the last one: an interior zero-density point followed
    /// by a finite endpoint does not by itself reject the attempt.
    #[test]
    fn interior_zero_density_with_finite_endpoint_follows_upstream_rule() {
        let mut calls = 0;
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.2, 1, 4, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 2 {
                    (f64::NEG_INFINITY, vec![0.0; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
            &mut work,
        )
        .unwrap();
        assert!(result.accepted(), "{:?}", result.rejection);
        assert_eq!(result.forward_evaluations, 4);
        assert_eq!(work.zero_density_evaluations, 1);
        assert!(result.maximum_absolute_energy_error.is_finite());
    }

    /// A zero-density endpoint during the reverse coarsening check is never
    /// "within tolerance", so the coarser level is not selected in reverse
    /// and the finer forward leaf stays accepted.
    #[test]
    fn zero_density_reverse_coarser_check_keeps_forward_leaf() {
        let mut calls = 0;
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(1.0, 0.0),
            &[1.0],
            tuning(3.48, 2, 1, 0.8178),
            Direction::Forward,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 4 {
                    (f64::NEG_INFINITY, vec![0.0; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
            &mut work,
        )
        .unwrap();
        assert!(result.accepted(), "{:?}", result.rejection);
        assert_eq!(result.forward_evaluations, 3);
        assert_eq!(result.reverse_evaluations, 1);
        assert_eq!(work.zero_density_evaluations, 1);
        assert_eq!(work.rejections.invalid_reverse_evaluation, 0);
        assert_eq!(work.rejections.reverse_coarser_accepted, 0);
    }

    /// A `-inf` log density with a nonfinite gradient is malformed, not a
    /// zero-density point.
    #[test]
    fn negative_infinity_with_nonfinite_gradient_is_invalid() {
        let result = macro_leaf(
            &state(0.0, 1.0),
            &[1.0],
            tuning(0.1, 3, 2, 1.0),
            Direction::Forward,
            &mut |theta: &[f64]| (f64::NEG_INFINITY, vec![f64::NAN; theta.len()]),
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::InvalidEvaluation));
        assert_eq!(result.evaluations, 1);
    }

    #[test]
    fn one_state_span_initializes_endpoints_candidate_and_weight() {
        let initial = state(0.7, 0.4);
        let span = Span::from_state(initial.clone(), &[1.0]).unwrap();
        let expected_joint = joint_log_density(&initial, &[1.0]);

        assert_eq!(span.backward.state.theta, initial.theta);
        assert_eq!(span.forward.state.rho, initial.rho);
        assert_eq!(span.selected.theta, vec![0.7]);
        assert_eq!(span.selected.grad, vec![-0.7]);
        assert_eq!(span.backward.log_joint, expected_joint);
        assert_eq!(span.forward.log_joint, expected_joint);
        assert_eq!(span.log_weight, expected_joint);
    }

    #[test]
    fn log_add_exp_is_stable_and_validates_weights() {
        assert_eq!(log_add_exp(f64::NEG_INFINITY, -3.0).unwrap(), -3.0);
        assert_eq!(
            log_add_exp(f64::NEG_INFINITY, f64::NEG_INFINITY).unwrap(),
            f64::NEG_INFINITY
        );
        let combined = log_add_exp(1000.0, 1000.0).unwrap();
        assert_eq!(combined, 1000.0 + 2.0_f64.ln());
        assert!(log_add_exp(f64::NAN, 0.0).is_err());
        assert!(log_add_exp(f64::INFINITY, 0.0).is_err());
        assert_eq!(log_add_exp(f64::MAX, f64::MAX).unwrap(), f64::MAX);
    }

    #[test]
    fn barker_selection_uses_a_strict_boundary() {
        let mut old = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut new = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        old.log_weight = 0.0;
        new.log_weight = 0.0;

        let mut at_boundary = ScriptedUniform01::new(vec![0.5]);
        let combined = combine_barker(
            &mut at_boundary,
            old.clone(),
            new.clone(),
            Direction::Forward,
        )
        .unwrap();
        assert_eq!(combined.selected.theta, old.selected.theta);

        let immediately_below = f64::from_bits(0.5_f64.to_bits() - 1);
        let mut below_boundary = ScriptedUniform01::new(vec![immediately_below]);
        let combined =
            combine_barker(&mut below_boundary, old, new.clone(), Direction::Forward).unwrap();
        assert_eq!(combined.selected.theta, new.selected.theta);
        assert_eq!(below_boundary.consumed(), 1);
    }

    #[test]
    fn randomized_barker_flux_satisfies_discrete_balance() {
        let mut light = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut heavy = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        light.log_weight = 0.0;
        heavy.log_weight = 2.0_f64.ln();
        let trials = 12_000;
        let mut light_to_heavy = 0;
        let mut heavy_to_light = 0;
        for index in 0..trials {
            let draw = (index as f64 + 0.5) / trials as f64;
            let mut forward_rng = ScriptedUniform01::new(vec![draw]);
            let forward = combine_barker(
                &mut forward_rng,
                light.clone(),
                heavy.clone(),
                Direction::Forward,
            )
            .unwrap();
            light_to_heavy += usize::from(forward.selected.theta == heavy.selected.theta);

            let mut reverse_rng = ScriptedUniform01::new(vec![draw]);
            let reverse = combine_barker(
                &mut reverse_rng,
                heavy.clone(),
                light.clone(),
                Direction::Forward,
            )
            .unwrap();
            heavy_to_light += usize::from(reverse.selected.theta == light.selected.theta);
        }
        assert_eq!(light_to_heavy, 2 * heavy_to_light);
    }

    #[test]
    fn gaussian_macro_leaf_is_reversible_under_momentum_flip() {
        let initial = state(0.37, -0.81);
        let forward = macro_leaf(
            &initial,
            &[1.0],
            tuning(0.2, 1, 4, 10.0),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap()
        .end_state
        .unwrap();
        let mut reversed_start = forward;
        reversed_start.rho[0] = -reversed_start.rho[0];
        let returned = macro_leaf(
            &reversed_start,
            &[1.0],
            tuning(0.2, 1, 4, 10.0),
            Direction::Forward,
            &mut gaussian,
        )
        .unwrap()
        .end_state
        .unwrap();
        assert!((returned.theta[0] - initial.theta[0]).abs() < 1e-12);
        assert!((returned.rho[0] + initial.rho[0]).abs() < 1e-12);
        assert!((returned.log_prob - initial.log_prob).abs() < 1e-12);
        assert!((returned.grad[0] - initial.grad[0]).abs() < 1e-12);
    }

    #[test]
    fn scripted_uniform_validates_values_and_exhaustion() {
        let mut rng = ScriptedUniform01::new(vec![0.0, 0.5]);
        assert_eq!(rng.uniform_01().unwrap(), 0.0);
        assert_eq!(rng.uniform_01().unwrap(), 0.5);
        assert_eq!(rng.consumed(), 2);
        assert_eq!(rng.remaining(), 0);
        assert!(rng.uniform_01().is_err());

        for invalid in [-0.1, 1.0, f64::NAN] {
            let mut rng = ScriptedUniform01::new(vec![invalid]);
            assert!(rng.uniform_01().is_err());
            assert_eq!(rng.consumed(), 0);
        }
    }

    #[test]
    fn build_leaf_uses_the_directional_physical_endpoint() {
        let initial = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut rng = ScriptedUniform01::new(vec![0.5]);
        let built = build_span(
            &mut rng,
            &initial,
            &[1.0],
            tuning(0.1, 1, 1, 1.0),
            Direction::Backward,
            1,
            &mut gaussian,
        )
        .unwrap();
        let BuildSpanResult::Built {
            span,
            leaves,
            evaluations,
        } = built
        else {
            panic!("backward span should build");
        };

        assert_eq!(leaves, 2);
        assert_eq!(evaluations, 2);
        assert!(span.backward.state.theta[0] < span.forward.state.theta[0]);
        assert!(span.forward.state.theta[0] < initial.backward.state.theta[0]);
        assert_eq!(rng.consumed(), 1);
    }

    #[test]
    fn first_leaf_exhaustion_propagates_without_rng() {
        let initial = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        let mut rng = ScriptedUniform01::new(vec![]);
        let result = build_span(
            &mut rng,
            &initial,
            &[1.0],
            tuning(3.0, 3, 1, 1e-14),
            Direction::Forward,
            2,
            &mut gaussian,
        )
        .unwrap();

        assert!(matches!(
            result,
            BuildSpanResult::Stopped {
                cause: SpanStop::Leaf(Rejection::RefinementExhausted),
                evaluations: 7
            }
        ));
        assert_eq!(rng.consumed(), 0);
    }

    #[test]
    fn second_leaf_exhaustion_keeps_evaluation_count_and_consumes_no_rng() {
        let initial = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut calls = 0;
        let mut rng = ScriptedUniform01::new(vec![]);
        let result = build_span(
            &mut rng,
            &initial,
            &[1.0],
            tuning(0.1, 1, 1, 1.0),
            Direction::Forward,
            1,
            &mut |theta: &[f64]| {
                calls += 1;
                if calls == 2 {
                    (f64::NAN, vec![f64::NAN; theta.len()])
                } else {
                    gaussian(theta)
                }
            },
        )
        .unwrap();

        assert!(matches!(
            result,
            BuildSpanResult::Stopped {
                cause: SpanStop::Leaf(Rejection::InvalidEvaluation),
                evaluations: 2
            }
        ));
        assert_eq!(calls, 2);
        assert_eq!(rng.consumed(), 0);
    }

    #[test]
    fn parent_uturn_preserves_completed_child_rng_consumption() {
        let initial = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        let mut rng = ScriptedUniform01::new(vec![0.25, 0.75]);
        let result = build_span(
            &mut rng,
            &initial,
            &[1.0],
            tuning(1.0, 1, 1, 1.0),
            Direction::Forward,
            2,
            &mut gaussian,
        )
        .unwrap();

        assert!(matches!(
            result,
            BuildSpanResult::Stopped {
                cause: SpanStop::UTurn,
                evaluations: 4
            }
        ));
        assert_eq!(rng.consumed(), 2);
    }

    #[test]
    fn span_validation_rejects_bad_cache_and_depth_overflow() {
        let mut span = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        span.log_weight = f64::NAN;
        let mut rng = ScriptedUniform01::new(vec![]);
        assert!(
            build_span(
                &mut rng,
                &span,
                &[1.0],
                tuning(0.1, 1, 1, 1.0),
                Direction::Forward,
                0,
                &mut gaussian,
            )
            .is_err()
        );

        let span = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        assert!(
            build_span(
                &mut rng,
                &span,
                &[1.0],
                tuning(0.1, 1, 1, 1.0),
                Direction::Forward,
                usize::BITS as usize,
                &mut gaussian,
            )
            .is_err()
        );
    }
    fn transition_tuning(
        step_size: f64,
        max_depth: usize,
        levels: usize,
        min_steps: usize,
        max_error: f64,
    ) -> TransitionTuning {
        TransitionTuning {
            leaf: tuning(step_size, levels, min_steps, max_error),
            max_depth,
        }
    }
    #[test]
    fn scripted_transition_rng_is_typed_order_sensitive_and_validated() {
        let mut rng = ScriptedTransitionRng::new(vec![
            TransitionDraw::Direction(Direction::Backward),
            TransitionDraw::Uniform(0.25),
        ]);
        assert_eq!(rng.direction().unwrap(), Direction::Backward);
        assert_eq!(rng.uniform_01().unwrap(), 0.25);
        assert_eq!(rng.consumed(), 2);
        assert_eq!(rng.remaining(), 0);
        assert!(rng.direction().is_err());

        let mut wrong = ScriptedTransitionRng::new(vec![TransitionDraw::Uniform(0.5)]);
        assert!(wrong.direction().is_err());
        assert_eq!(wrong.consumed(), 0);
        let mut wrong =
            ScriptedTransitionRng::new(vec![TransitionDraw::Direction(Direction::Forward)]);
        assert!(wrong.uniform_01().is_err());
        assert_eq!(wrong.consumed(), 0);
        for value in [-0.1, 1.0, f64::NAN] {
            let mut invalid = ScriptedTransitionRng::new(vec![TransitionDraw::Uniform(value)]);
            assert!(invalid.uniform_01().is_err());
            assert_eq!(invalid.consumed(), 0);
        }
    }
    #[test]
    fn transition_evaluates_initial_position_once_and_reports_exact_work() {
        let mut calls = 0;
        let mut rng = ScriptedTransitionRng::new(vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.0),
        ]);
        let result = transition_w(
            &mut rng,
            TransitionInput {
                theta: vec![0.7],
                rho: vec![0.4],
            },
            &[1.0],
            transition_tuning(0.1, 1, 1, 2, 1.0),
            &mut |theta| {
                calls += 1;
                gaussian(theta)
            },
        )
        .unwrap();

        assert_eq!(calls, 3);
        assert_eq!(result.diagnostics.target_evaluations, 3);
        assert_eq!(result.diagnostics.depth, 1);
        assert_eq!(result.diagnostics.stop, TransitionStop::MaxDepth);
        assert_eq!(result.diagnostics.direction_draws, 1);
        assert_eq!(result.diagnostics.uniform_draws, 1);
        assert_eq!(result.diagnostics.recursive_barker_draws, 0);
        assert_eq!(result.diagnostics.outer_metropolis_draws, 1);
        assert_eq!(result.diagnostics.leaves_attempted, 1);
        assert_eq!(result.diagnostics.leaves_built, 1);
        assert_eq!(rng.consumed(), 2);
        assert_ne!(result.selected.theta, vec![0.7]);
        assert_eq!(result.selected.grad, vec![-result.selected.theta[0]]);
        assert_eq!(
            result.selected.log_prob,
            -0.5 * result.selected.theta[0] * result.selected.theta[0]
        );
    }
    #[test]
    fn cached_transition_is_numerically_identical_without_initial_target_work() {
        let draws = vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.0),
        ];
        let tuning = transition_tuning(0.1, 1, 1, 2, 1.0);
        let mut ordinary_rng = ScriptedTransitionRng::new(draws.clone());
        let mut cached_rng = ScriptedTransitionRng::new(draws);
        let mut ordinary_calls = 0;
        let ordinary = transition_w_with_telemetry(
            &mut ordinary_rng,
            TransitionInput {
                theta: vec![0.7],
                rho: vec![0.4],
            },
            &[1.0],
            tuning,
            &mut |theta| {
                ordinary_calls += 1;
                gaussian(theta)
            },
        )
        .unwrap();
        let mut cached_calls = 0;
        let cached = transition_w_from_evaluated_with_telemetry(
            &mut cached_rng,
            EvaluatedTransitionInput {
                theta: vec![0.7],
                rho: vec![0.4],
                log_prob: -0.5 * 0.7 * 0.7,
                grad: vec![-0.7],
            },
            &[1.0],
            tuning,
            &mut |theta| {
                cached_calls += 1;
                gaussian(theta)
            },
        )
        .unwrap();

        assert_eq!(ordinary.result.selected, cached.result.selected);
        assert_eq!(ordinary_rng.consumed(), cached_rng.consumed());
        assert_eq!(ordinary_calls, cached_calls + 1);
        assert_eq!(ordinary.work.fused_calls.initial, 1);
        assert_eq!(cached.work.fused_calls.initial, 0);
        assert_eq!(
            ordinary.result.diagnostics.target_evaluations,
            cached.result.diagnostics.target_evaluations + 1
        );
    }
    #[test]
    fn traced_and_untraced_transition_results_diagnostics_and_work_are_identical() {
        let draws = vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.2),
            TransitionDraw::Direction(Direction::Backward),
            TransitionDraw::Uniform(0.3),
            TransitionDraw::Uniform(0.4),
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.5),
            TransitionDraw::Uniform(0.6),
            TransitionDraw::Uniform(0.7),
            TransitionDraw::Uniform(0.8),
        ];
        let input = TransitionInput {
            theta: vec![0.2, -0.3],
            rho: vec![0.7, 0.1],
        };
        let tuning = transition_tuning(0.05, 3, 1, 1, 1.0);
        let mut untraced_rng = ScriptedTransitionRng::new(draws.clone());
        let mut traced_rng = ScriptedTransitionRng::new(draws);
        let mut untraced_evaluations = 0;
        let mut traced_evaluations = 0;

        let untraced = transition_w(
            &mut untraced_rng,
            TransitionInput {
                theta: input.theta.clone(),
                rho: input.rho.clone(),
            },
            &[1.0, 1.5],
            tuning,
            &mut |theta| {
                untraced_evaluations += 1;
                gaussian(theta)
            },
        )
        .unwrap();
        let traced =
            transition_w_traced(&mut traced_rng, input, &[1.0, 1.5], tuning, &mut |theta| {
                traced_evaluations += 1;
                gaussian(theta)
            })
            .unwrap();

        assert_eq!(untraced.selected, traced.result.selected);
        assert_eq!(untraced.diagnostics, traced.result.diagnostics);
        assert_eq!(untraced_evaluations, traced_evaluations);
        assert_eq!(untraced_rng.consumed(), traced_rng.consumed());
        assert_eq!(untraced_rng.remaining(), traced_rng.remaining());
    }
    #[test]
    #[ignore = "wall-clock benchmark"]
    fn benchmark_untraced_against_traced_fixed_gaussian_tape() {
        use std::hint::black_box;
        use std::time::Instant;

        let draws = vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.2),
            TransitionDraw::Direction(Direction::Backward),
            TransitionDraw::Uniform(0.3),
            TransitionDraw::Uniform(0.4),
        ];
        let iterations = 10_000;
        let tuning = transition_tuning(0.05, 2, 1, 1, 1.0);
        let started = Instant::now();
        for _ in 0..iterations {
            let mut rng = ScriptedTransitionRng::new(draws.clone());
            black_box(
                transition_w(
                    &mut rng,
                    TransitionInput {
                        theta: vec![0.2],
                        rho: vec![0.7],
                    },
                    &[1.0],
                    tuning,
                    &mut gaussian,
                )
                .unwrap(),
            );
        }
        let untraced = started.elapsed();

        let started = Instant::now();
        let mut events = 0;
        for _ in 0..iterations {
            let mut rng = ScriptedTransitionRng::new(draws.clone());
            let traced = transition_w_traced(
                &mut rng,
                TransitionInput {
                    theta: vec![0.2],
                    rho: vec![0.7],
                },
                &[1.0],
                tuning,
                &mut gaussian,
            )
            .unwrap();
            events += traced.events.len();
            black_box(traced);
        }
        let traced = started.elapsed();

        eprintln!(
            "fixed Gaussian tape: untraced={untraced:?}, traced={traced:?}, \
             trace events materialized={events}"
        );
        assert!(events > 0);
    }
    #[test]
    fn transition_direction_changes_the_selected_physical_endpoint() {
        let run = |direction| {
            let mut rng = ScriptedTransitionRng::new(vec![
                TransitionDraw::Direction(direction),
                TransitionDraw::Uniform(0.0),
            ]);
            transition_w(
                &mut rng,
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![1.0],
                },
                &[1.0],
                transition_tuning(0.1, 1, 1, 1, 1.0),
                &mut gaussian,
            )
            .unwrap()
        };
        assert!(run(Direction::Forward).selected.theta[0] > 0.0);
        assert!(run(Direction::Backward).selected.theta[0] < 0.0);
    }
    #[test]
    fn recursive_failure_stops_before_outer_uturn_or_metropolis() {
        let mut rng =
            ScriptedTransitionRng::new(vec![TransitionDraw::Direction(Direction::Forward)]);
        let traced = transition_w_traced(
            &mut rng,
            TransitionInput {
                theta: vec![1.0],
                rho: vec![0.0],
            },
            &[1.0],
            transition_tuning(3.0, 2, 3, 1, 1e-14),
            &mut gaussian,
        )
        .unwrap();

        assert_eq!(
            traced.result.diagnostics.stop,
            TransitionStop::Recursive(SpanStop::Leaf(Rejection::RefinementExhausted))
        );
        assert_eq!(traced.result.diagnostics.target_evaluations, 8);
        assert_eq!(traced.result.diagnostics.uniform_draws, 0);
        assert_eq!(traced.result.diagnostics.outer_metropolis_draws, 0);
        assert_eq!(rng.consumed(), 1);
        let names: Vec<_> = traced.events.iter().map(|event| event.event).collect();
        assert!(names.contains(&"recursive_stop"));
        assert!(!names.contains(&"outer_uturn_predicate"));
        assert!(!names.contains(&"outer_combine_metropolis"));
    }
    #[test]
    fn outer_uturn_combines_with_metropolis_before_stopping() {
        let mut rng = ScriptedTransitionRng::new(vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.0),
        ]);
        let traced = transition_w_traced(
            &mut rng,
            TransitionInput {
                theta: vec![0.0],
                rho: vec![1.0],
            },
            &[1.0],
            transition_tuning(1.5, 1, 1, 1, 1.0),
            &mut gaussian,
        )
        .unwrap();

        assert_eq!(traced.result.diagnostics.stop, TransitionStop::OuterUTurn);
        assert_eq!(traced.result.diagnostics.outer_metropolis_draws, 1);
        assert_eq!(traced.result.diagnostics.uniform_draws, 1);
        assert_eq!(rng.consumed(), 2);
        assert_eq!(traced.result.selected.theta, vec![1.5]);
        let outer_uturn = traced
            .events
            .iter()
            .position(|event| event.event == "outer_uturn_predicate")
            .unwrap();
        let metropolis = traced
            .events
            .iter()
            .position(|event| event.event == "outer_combine_metropolis")
            .unwrap();
        let stop = traced
            .events
            .iter()
            .position(|event| event.event == "transition_stop")
            .unwrap();
        assert!(outer_uturn < metropolis && metropolis < stop);
    }
    #[test]
    fn metropolis_uses_old_weight_strict_boundary_and_always_draws() {
        let mut old = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut new = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        old.log_weight = 0.0;
        new.log_weight = 0.5_f64.ln();
        let mut boundary = ScriptedUniform01::new(vec![0.5]);
        let (combined, _, log_probability, updated) = combine_metropolis_observed(
            &mut boundary,
            old.clone(),
            new.clone(),
            Direction::Forward,
        )
        .unwrap();
        assert_eq!(log_probability, 0.5_f64.ln());
        assert!(!updated);
        assert!(same_selected(&combined.selected, &old.selected));
        assert_eq!(boundary.consumed(), 1);

        new.log_weight = 1.0;
        let mut certain = ScriptedUniform01::new(vec![0.999]);
        let (combined, _, log_probability, updated) =
            combine_metropolis_observed(&mut certain, old, new.clone(), Direction::Forward)
                .unwrap();
        assert_eq!(log_probability, 1.0);
        assert!(updated);
        assert!(same_selected(&combined.selected, &new.selected));
        assert_eq!(certain.consumed(), 1);
    }

    #[test]
    fn outer_selection_probabilities_match_closed_form_and_empirical_grid() {
        let mut old = Span::from_state(state(0.0, 1.0), &[1.0]).unwrap();
        let mut new = Span::from_state(state(1.0, 0.0), &[1.0]).unwrap();
        old.log_weight = 0.0;
        new.log_weight = 2.0_f64.ln();
        let n = 10_000usize;

        for (policy, expected) in [
            (OuterSelectionPolicy::BiasedProgressive, 1.0),
            (OuterSelectionPolicy::NormalizedMultinomial, 2.0 / 3.0),
        ] {
            let mut selected = 0usize;
            for index in 0..n {
                let draw = (index as f64 + 0.5) / n as f64;
                let mut rng = ScriptedUniform01::new(vec![draw]);
                let (combined, observed, log_probability, update) = combine_outer_observed(
                    &mut rng,
                    old.clone(),
                    new.clone(),
                    Direction::Forward,
                    policy,
                )
                .unwrap();
                assert_eq!(observed, draw);
                assert_eq!(rng.consumed(), 1);
                assert!((combined.log_weight - 3.0_f64.ln()).abs() < 2.0e-15);
                assert_eq!(update, same_selected(&combined.selected, &new.selected));
                if update {
                    selected += 1;
                }
                let probability = log_probability.exp().min(1.0);
                assert!((probability - expected).abs() < 2.0e-15);
            }
            assert!((selected as f64 / n as f64 - expected).abs() <= 1.0 / n as f64);
        }

        let mut extreme = new;
        extreme.log_weight = -1_000.0;
        let mut rng = ScriptedUniform01::new(vec![0.5]);
        let (combined, _, log_probability, _) = combine_outer_observed(
            &mut rng,
            old,
            extreme,
            Direction::Backward,
            OuterSelectionPolicy::NormalizedMultinomial,
        )
        .unwrap();
        assert!(combined.log_weight.is_finite());
        assert!(log_probability.is_finite());
    }
    #[test]
    fn transition_validates_before_evaluation_or_rng_and_rejects_bad_evaluation() {
        let invalid_inputs = [
            (
                TransitionInput {
                    theta: vec![],
                    rho: vec![],
                },
                vec![],
                transition_tuning(0.1, 1, 1, 1, 1.0),
            ),
            (
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![0.0, 1.0],
                },
                vec![1.0],
                transition_tuning(0.1, 1, 1, 1, 1.0),
            ),
            (
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![1.0],
                },
                vec![0.0],
                transition_tuning(0.1, 1, 1, 1, 1.0),
            ),
            (
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![1.0],
                },
                vec![1.0],
                transition_tuning(0.1, 0, 1, 1, 1.0),
            ),
            (
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![1.0],
                },
                vec![1.0],
                transition_tuning(0.1, usize::BITS as usize, 1, 1, 1.0),
            ),
        ];
        for (input, inverse_mass, tuning) in invalid_inputs {
            let mut calls = 0;
            let mut rng = ScriptedTransitionRng::new(vec![]);
            assert!(
                transition_w(&mut rng, input, &inverse_mass, tuning, &mut |theta| {
                    calls += 1;
                    gaussian(theta)
                },)
                .is_err()
            );
            assert_eq!(calls, 0);
            assert_eq!(rng.consumed(), 0);
        }

        let mut rng = ScriptedTransitionRng::new(vec![]);
        assert!(
            transition_w(
                &mut rng,
                TransitionInput {
                    theta: vec![0.0],
                    rho: vec![1.0],
                },
                &[1.0],
                transition_tuning(0.1, 1, 1, 1, 1.0),
                &mut |_| (f64::NAN, vec![f64::NAN]),
            )
            .is_err()
        );
        assert_eq!(rng.consumed(), 0);
    }
    #[test]
    fn transition_depth_two_accounts_for_recursive_barker_draws() {
        let mut rng = ScriptedTransitionRng::new(vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.0),
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.25),
            TransitionDraw::Uniform(0.0),
        ]);
        let result = transition_w(
            &mut rng,
            TransitionInput {
                theta: vec![0.7, -0.2],
                rho: vec![0.4, 0.6],
            },
            &[0.5, 3.0],
            transition_tuning(0.01, 2, 2, 3, 1.0),
            &mut |theta| {
                (
                    -0.5 * (theta[0] * theta[0] + 2.0 * theta[1] * theta[1]),
                    vec![-theta[0], -2.0 * theta[1]],
                )
            },
        )
        .unwrap();
        assert_eq!(result.diagnostics.stop, TransitionStop::MaxDepth);
        assert_eq!(result.diagnostics.depth, 2);
        assert_eq!(result.diagnostics.direction_draws, 2);
        assert_eq!(result.diagnostics.uniform_draws, 3);
        assert_eq!(result.diagnostics.recursive_barker_draws, 1);
        assert_eq!(result.diagnostics.outer_metropolis_draws, 2);
        assert_eq!(result.diagnostics.leaves_attempted, 3);
        assert_eq!(result.diagnostics.leaves_built, 3);
        assert_eq!(result.diagnostics.target_evaluations, 10);
        assert_eq!(rng.consumed(), 5);
    }
    #[test]
    fn telemetry_partitions_refinement_reverse_and_rejection_work_exactly() {
        let mut work = TransitionWorkTelemetry::default();
        let result = macro_leaf_observed(
            &state(1.0, 0.0),
            &[1.0],
            tuning(3.48, 2, 1, 0.8178),
            Direction::Forward,
            &mut gaussian,
            &mut work,
        )
        .unwrap();
        assert_eq!(result.rejection, Some(Rejection::ReverseCoarserAccepted));
        assert_eq!(work.forward_refinement_attempts, 2);
        assert_eq!(work.forward_refinement_accepted, 1);
        assert_eq!(work.fused_calls.forward, 3);
        assert_eq!(work.fused_calls.reverse, 1);
        assert_eq!(work.reverse_coarsening_attempts, 1);
        assert_eq!(work.reverse_coarsening_accepted, 1);
        assert_eq!(work.histograms.refinement_level_attempts, vec![1, 1]);
        assert_eq!(
            work.histograms.forward_micro_steps,
            vec![
                WorkHistogramBin {
                    micro_steps: 1,
                    attempts: 1
                },
                WorkHistogramBin {
                    micro_steps: 2,
                    attempts: 1
                }
            ]
        );
        assert_eq!(
            work.histograms.reverse_micro_steps,
            vec![WorkHistogramBin {
                micro_steps: 1,
                attempts: 1
            }]
        );
        assert_eq!(work.rejections.reverse_coarser_accepted, 1);
    }
    #[test]
    fn telemetry_transition_api_preserves_legacy_and_traced_rng_behavior() {
        let draws = vec![
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.0),
            TransitionDraw::Direction(Direction::Forward),
            TransitionDraw::Uniform(0.25),
            TransitionDraw::Uniform(0.0),
        ];
        let input = TransitionInput {
            theta: vec![0.7, -0.2],
            rho: vec![0.4, 0.6],
        };
        let tuning = transition_tuning(0.01, 2, 2, 3, 1.0);
        let mut legacy_rng = ScriptedTransitionRng::new(draws.clone());
        let mut telemetry_rng = ScriptedTransitionRng::new(draws.clone());
        let mut traced_rng = ScriptedTransitionRng::new(draws);
        let legacy = transition_w(
            &mut legacy_rng,
            input.clone(),
            &[0.5, 3.0],
            tuning,
            &mut gaussian,
        )
        .unwrap();
        let telemetry = transition_w_with_telemetry(
            &mut telemetry_rng,
            input.clone(),
            &[0.5, 3.0],
            tuning,
            &mut gaussian,
        )
        .unwrap();
        let traced = transition_w_traced_with_telemetry(
            &mut traced_rng,
            input,
            &[0.5, 3.0],
            tuning,
            &mut gaussian,
        )
        .unwrap();

        assert_eq!(legacy.selected, telemetry.result.selected);
        assert_eq!(legacy.diagnostics, telemetry.result.diagnostics);
        assert_eq!(telemetry.result.selected, traced.result.selected);
        assert_eq!(telemetry.result.diagnostics, traced.result.diagnostics);
        assert_eq!(telemetry.work, traced.work);
        assert_eq!(legacy_rng.consumed(), telemetry_rng.consumed());
        assert_eq!(telemetry_rng.consumed(), traced_rng.consumed());
        assert_eq!(legacy_rng.remaining(), telemetry_rng.remaining());
        assert_eq!(telemetry_rng.remaining(), traced_rng.remaining());
        telemetry.work.validate_invariants().unwrap();
        assert_eq!(
            telemetry.work.fused_call_total().unwrap(),
            telemetry.result.diagnostics.target_evaluations
        );
        assert_eq!(
            telemetry.work.barker.attempted,
            telemetry.result.diagnostics.recursive_barker_draws
        );
        assert_eq!(
            telemetry.work.metropolis.attempted,
            telemetry.result.diagnostics.outer_metropolis_draws
        );
    }
}
