//! Feature-gated, fixed-tuning prototype of one walnutpie macro leaf.
//!
//! Algorithm derived from flatironinstitute/walnutpie at commit
//! f5bba36529697c34567a2944be36b68e305c546d. Copyright the walnutpie
//! contributors; used under the MIT License.

#![allow(clippy::large_enum_variant, clippy::too_many_arguments)]

use crate::types::{State, ValidationError};

/// One physical endpoint of a span, including its cached joint log density.
#[derive(Clone, Debug)]
pub struct Endpoint {
    pub state: State,
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
    pub selected: SelectedState,
    /// Log of the sum of the leaves' unnormalized joint densities.
    pub log_weight: f64,
}

impl Span {
    /// Construct a one-state span.
    pub fn from_state(state: State, inverse_mass: &[f64]) -> Result<Self, ValidationError> {
        validate_state_and_mass(&state, inverse_mass)?;
        let log_joint = joint_log_density(&state, inverse_mass);
        if !log_joint.is_finite() {
            return Err(ValidationError(
                "state joint log density must be finite".into(),
            ));
        }
        let selected = SelectedState {
            theta: state.theta.clone(),
            grad: state.grad.clone(),
            log_prob: state.log_prob,
        };
        let endpoint = Endpoint { state, log_joint };
        Ok(Self {
            backward: endpoint.clone(),
            forward: endpoint,
            selected,
            log_weight: log_joint,
        })
    }

    fn from_subspans(earlier: Span, later: Span, selected: SelectedState, log_weight: f64) -> Self {
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
    /// Inclusive endpoint Hamiltonian-error tolerance.
    pub max_error: f64,
}

/// Why a deterministic leaf was rejected.
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
    pub rejection: Option<Rejection>,
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
    },
    Stopped {
        rejection: Rejection,
        micro_steps: usize,
        evaluations: usize,
        adaptation_value: f64,
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
pub fn build_leaf<F>(
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
) -> Result<BuildLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    build_leaf_observed(
        last_span,
        inverse_mass,
        tuning,
        direction,
        eval,
        &mut TransitionWorkTelemetry::default(),
    )
}

fn build_leaf_observed<F>(
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
    work: &mut TransitionWorkTelemetry,
) -> Result<BuildLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    validate_span(last_span, inverse_mass)?;
    let start = match direction {
        Direction::Forward => &last_span.forward.state,
        Direction::Backward => &last_span.backward.state,
    };
    increment(&mut work.leaves_attempted)?;
    let result = macro_leaf_observed(start, inverse_mass, tuning, direction, eval, work)?;
    match (result.end_state, result.rejection) {
        (Some(state), None) => {
            increment(&mut work.leaves_built)?;
            Ok(BuildLeafResult::Built {
                span: Span::from_state(state, inverse_mass)?,
                micro_steps: result.micro_steps,
                evaluations: result.evaluations,
                adaptation_value: result.adaptation_value,
            })
        }
        (None, Some(rejection)) => Ok(BuildLeafResult::Stopped {
            rejection,
            micro_steps: result.micro_steps,
            evaluations: result.evaluations,
            adaptation_value: result.adaptation_value,
        }),
        _ => Err(ValidationError(
            "macro leaf returned an inconsistent outcome".into(),
        )),
    }
}

/// Recursively build `2^depth` leaves, stopping on exhaustion or a U-turn.
pub fn build_span<F, R>(
    rng: &mut R,
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    eval: &mut F,
) -> Result<BuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: Uniform01,
{
    validate_span(last_span, inverse_mass)?;
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
        inverse_mass,
        tuning,
        direction,
        depth,
        leaves,
        eval,
        &mut evaluations,
        &mut leaves_attempted,
        &mut leaves_built,
        &mut work,
    )
}

/// Build a span while exposing prototype-only branch and RNG observations.
pub fn build_span_traced<F, R>(
    rng: &mut R,
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    eval: &mut F,
) -> Result<TracedBuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: Uniform01,
{
    validate_span(last_span, inverse_mass)?;
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
        inverse_mass,
        tuning,
        direction,
        depth,
        leaves,
        eval,
        &mut evaluations,
        &mut |event| events.push(event),
        &mut work,
    )?;
    Ok(TracedBuildSpanResult { result, events })
}

fn build_span_inner<F, R>(
    rng: &mut R,
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    leaves: usize,
    eval: &mut F,
    cumulative_evaluations: &mut usize,
    trace: &mut impl FnMut(SpanTraceEvent),
    work: &mut TransitionWorkTelemetry,
) -> Result<BuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
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
            match build_leaf_observed(last_span, inverse_mass, tuning, direction, eval, work)? {
                BuildLeafResult::Built {
                    span,
                    evaluations,
                    adaptation_value,
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
        inverse_mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        trace,
        work,
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
        inverse_mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        trace,
        work,
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
        spans_make_u_turn_observed(&first_span, &second_span, inverse_mass, direction);
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

fn build_span_counted_inner<F, R>(
    rng: &mut R,
    last_span: &Span,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    depth: usize,
    leaves: usize,
    eval: &mut F,
    cumulative_evaluations: &mut usize,
    leaves_attempted: &mut usize,
    leaves_built: &mut usize,
    work: &mut TransitionWorkTelemetry,
) -> Result<BuildSpanResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: Uniform01,
{
    if depth == 0 {
        *leaves_attempted = leaves_attempted
            .checked_add(1)
            .ok_or_else(|| ValidationError("leaf count overflowed usize".into()))?;
        return Ok(
            match build_leaf_observed(last_span, inverse_mass, tuning, direction, eval, work)? {
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
        inverse_mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        leaves_attempted,
        leaves_built,
        work,
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
        inverse_mass,
        tuning,
        direction,
        depth - 1,
        leaves / 2,
        eval,
        cumulative_evaluations,
        leaves_attempted,
        leaves_built,
        work,
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
        spans_make_u_turn_observed(&first_span, &second_span, inverse_mass, direction);
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
        new.selected.clone()
    } else {
        old.selected.clone()
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

fn spans_make_u_turn_observed(
    first: &Span,
    second: &Span,
    inverse_mass: &[f64],
    direction: Direction,
) -> (bool, f64, Option<f64>) {
    let (earlier, later) = match direction {
        Direction::Forward => (first, second),
        Direction::Backward => (second, first),
    };
    let scaled_difference = later
        .forward
        .state
        .theta
        .iter()
        .zip(&earlier.backward.state.theta)
        .zip(inverse_mass)
        .map(|((later, earlier), inverse_mass)| inverse_mass * (later - earlier));
    let later_dot = later
        .forward
        .state
        .rho
        .iter()
        .zip(scaled_difference.clone())
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
        .zip(scaled_difference)
        .map(|(rho, difference)| rho * difference)
        .sum::<f64>();
    (earlier_dot < 0.0, later_dot, Some(earlier_dot))
}

fn checked_add_evaluations(left: usize, right: usize) -> Result<usize, ValidationError> {
    left.checked_add(right)
        .ok_or_else(|| ValidationError("evaluation count overflowed usize".into()))
}

fn checked_add_work(left: usize, right: usize) -> Result<usize, ValidationError> {
    left.checked_add(right)
        .ok_or_else(|| ValidationError("work telemetry count overflowed usize".into()))
}

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
#[derive(Clone, Debug, PartialEq, Eq)]
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
    pub forward_micro_steps: Vec<WorkHistogramBin>,
    pub reverse_micro_steps: Vec<WorkHistogramBin>,
}

/// Additive exact work performed by one transition.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
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
    pub rejections: RejectionCounts,
    pub stops: StopCounts,
    pub direction_draws: usize,
    pub barker: SelectionDrawCounts,
    pub metropolis: SelectionDrawCounts,
    pub histograms: WorkHistogram,
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
pub fn transition_w<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    transition_w_untraced_inner(rng, input, inverse_mass, tuning, eval).map(|output| output.result)
}

/// Run one transition and return exact additive work telemetry.
pub fn transition_w_with_telemetry<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    transition_w_untraced_inner(rng, input, inverse_mass, tuning, eval)
}

/// Run a transition while exposing transition and recursive-span observations.
pub fn transition_w_traced<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TracedTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(rng, input, inverse_mass, tuning, eval, &mut |event| {
        events.push(event)
    })?;
    Ok(TracedTransitionResult {
        result: output.result,
        events,
    })
}

/// Run a traced transition and return exact additive work telemetry.
pub fn transition_w_traced_with_telemetry<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TracedTelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    let mut events = Vec::new();
    let output = transition_w_inner(rng, input, inverse_mass, tuning, eval, &mut |event| {
        events.push(event)
    })?;
    Ok(TracedTelemetryTransitionResult {
        result: output.result,
        work: output.work,
        events,
    })
}
fn transition_w_untraced_inner<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
) -> Result<TelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    validate_transition_input(&input, inverse_mass, tuning)?;
    let (log_prob, grad) = eval(&input.theta);
    let mut work = TransitionWorkTelemetry::for_tuning(tuning.leaf);
    work.fused_calls.initial = 1;
    let mut counts = TransitionCounts {
        target_evaluations: 1,
        ..TransitionCounts::default()
    };
    let state = State {
        theta: input.theta,
        rho: input.rho,
        log_prob,
        grad,
    };
    validate_state_and_mass(&state, inverse_mass)?;
    let mut span_accum = Span::from_state(state, inverse_mass)?;

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
                inverse_mass,
                tuning.leaf,
                direction,
                depth - 1,
                leaves,
                eval,
                &mut counts.target_evaluations,
                &mut counts.leaves_attempted,
                &mut counts.leaves_built,
                &mut work,
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
            spans_make_u_turn_observed(&span_accum, &next_span, inverse_mass, direction);
        let combined = {
            let mut counted_rng = CountedTransitionRng {
                inner: rng,
                direction_draws: &mut counts.direction_draws,
                uniform_draws: &mut counts.uniform_draws,
            };
            let (combined, _, _, update) =
                combine_metropolis_observed(&mut counted_rng, span_accum, next_span, direction)?;
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
    Ok(TelemetryTransitionResult {
        result: TransitionResult {
            selected: span_accum.selected,
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
            },
        },
        work,
    })
}
fn transition_w_inner<F, R>(
    rng: &mut R,
    input: TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
    eval: &mut F,
    trace: &mut impl FnMut(TransitionTraceEvent),
) -> Result<TelemetryTransitionResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
    R: TransitionRng,
{
    validate_transition_input(&input, inverse_mass, tuning)?;
    let (log_prob, grad) = eval(&input.theta);
    let mut work = TransitionWorkTelemetry::for_tuning(tuning.leaf);
    work.fused_calls.initial = 1;
    let mut counts = TransitionCounts {
        target_evaluations: 1,
        ..TransitionCounts::default()
    };
    let state = State {
        theta: input.theta,
        rho: input.rho,
        log_prob,
        grad,
    };
    validate_state_and_mass(&state, inverse_mass)?;
    let mut span_accum = Span::from_state(state, inverse_mass)?;
    trace(TransitionTraceEvent::basic(
        "initial_evaluation",
        None,
        None,
        &counts,
    ));

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
                inverse_mass,
                tuning.leaf,
                direction,
                depth - 1,
                leaves,
                eval,
                &mut counts.target_evaluations,
                &mut |event| recursive_events.push(event),
                &mut work,
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
            spans_make_u_turn_observed(&span_accum, &next_span, inverse_mass, direction);
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
            combine_metropolis_observed(&mut counted_rng, span_accum, next_span, direction)?
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
    Ok(TelemetryTransitionResult {
        result: TransitionResult {
            selected: span_accum.selected,
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
        new.selected.clone()
    } else {
        old.selected.clone()
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
fn validate_transition_input(
    input: &TransitionInput,
    inverse_mass: &[f64],
    tuning: TransitionTuning,
) -> Result<(), ValidationError> {
    let dim = input.theta.len();
    if dim == 0 || input.rho.len() != dim || inverse_mass.len() != dim {
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
    if inverse_mass
        .iter()
        .any(|value| !value.is_finite() || *value <= 0.0)
    {
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
    let validation_state = State {
        theta: input.theta.clone(),
        rho: input.rho.clone(),
        log_prob: 0.0,
        grad: vec![0.0; dim],
    };
    validate(&validation_state, inverse_mass, tuning.leaf)
}

/// Build one fixed-tuning macro leaf using a diagonal inverse mass.
///
/// Refinement tests only the macro-step endpoint, not the range of energies
/// visited by its micro steps. A candidate is accepted only if no admissible
/// coarser reverse trajectory also meets the inclusive endpoint tolerance.
pub fn macro_leaf<F>(
    start: &State,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
) -> Result<MacroLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    macro_leaf_observed(
        start,
        inverse_mass,
        tuning,
        direction,
        eval,
        &mut TransitionWorkTelemetry::default(),
    )
}

fn macro_leaf_observed<F>(
    start: &State,
    inverse_mass: &[f64],
    tuning: FixedTuning,
    direction: Direction,
    eval: &mut F,
    work: &mut TransitionWorkTelemetry,
) -> Result<MacroLeafResult, ValidationError>
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    validate(start, inverse_mass, tuning)?;

    let initial_h = joint_log_density(start, inverse_mass);
    let signed_step = match direction {
        Direction::Forward => tuning.step_size,
        Direction::Backward => -tuning.step_size,
    };
    let mut forward_evaluations = 0;
    let mut last_steps = tuning.min_micro_steps;
    let mut last_adaptation_value = 0.0;

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
        let mut candidate = start.clone();
        let (attempted, valid) = integrate(&mut candidate, step, micro_steps, inverse_mass, eval);
        work.forward_micro_steps_executed =
            checked_add_work(work.forward_micro_steps_executed, attempted)?;
        work.fused_calls.forward = checked_add_work(work.fused_calls.forward, attempted)?;
        forward_evaluations = checked_add_evaluations(forward_evaluations, attempted)?;
        if !valid {
            increment(&mut work.rejections.invalid_forward_evaluation)?;
            return Ok(MacroLeafResult {
                end_state: None,
                micro_steps,
                evaluations: forward_evaluations,
                forward_evaluations,
                reverse_evaluations: 0,
                adaptation_value: 0.0,
                rejection: Some(Rejection::InvalidEvaluation),
            });
        }
        if level == 0 {
            last_adaptation_value =
                (-(joint_log_density(&candidate, inverse_mass) - initial_h).abs()).exp();
        }

        if (joint_log_density(&candidate, inverse_mass) - initial_h).abs() <= tuning.max_error {
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
                let mut reversed = candidate.clone();
                for momentum in &mut reversed.rho {
                    *momentum = -*momentum;
                }
                let (attempted, valid) =
                    integrate(&mut reversed, coarse_step, coarse_steps, inverse_mass, eval);
                work.reverse_micro_steps_executed =
                    checked_add_work(work.reverse_micro_steps_executed, attempted)?;
                work.fused_calls.reverse = checked_add_work(work.fused_calls.reverse, attempted)?;
                reverse_evaluations = checked_add_evaluations(reverse_evaluations, attempted)?;
                if !valid {
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
                        rejection: Some(Rejection::InvalidEvaluation),
                    });
                }
                if (joint_log_density(&reversed, inverse_mass)
                    - joint_log_density(&candidate, inverse_mass))
                .abs()
                    <= tuning.max_error
                {
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
                        rejection: Some(Rejection::ReverseCoarserAccepted),
                    });
                }
            }
            return Ok(MacroLeafResult {
                end_state: Some(candidate),
                micro_steps,
                evaluations: checked_add_evaluations(forward_evaluations, reverse_evaluations)?,
                forward_evaluations,
                reverse_evaluations,
                adaptation_value: last_adaptation_value,
                rejection: None,
            });
        }
    }

    increment(&mut work.rejections.refinement_exhausted)?;
    Ok(MacroLeafResult {
        end_state: None,
        micro_steps: last_steps,
        evaluations: forward_evaluations,
        forward_evaluations,
        reverse_evaluations: 0,
        adaptation_value: last_adaptation_value,
        rejection: Some(Rejection::RefinementExhausted),
    })
}

fn validate(
    start: &State,
    inverse_mass: &[f64],
    tuning: FixedTuning,
) -> Result<(), ValidationError> {
    validate_state_and_mass(start, inverse_mass)?;
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
    Ok(())
}

fn validate_state_and_mass(state: &State, inverse_mass: &[f64]) -> Result<(), ValidationError> {
    let dim = state.theta.len();
    if dim == 0 || state.rho.len() != dim || state.grad.len() != dim || inverse_mass.len() != dim {
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
    if inverse_mass
        .iter()
        .any(|value| !value.is_finite() || *value <= 0.0)
    {
        return Err(ValidationError(
            "inverse mass entries must be finite and positive".into(),
        ));
    }
    Ok(())
}

fn validate_span(span: &Span, inverse_mass: &[f64]) -> Result<(), ValidationError> {
    validate_state_and_mass(&span.backward.state, inverse_mass)?;
    validate_state_and_mass(&span.forward.state, inverse_mass)?;
    let dim = inverse_mass.len();
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

fn integrate<F>(
    state: &mut State,
    step: f64,
    count: usize,
    inverse_mass: &[f64],
    eval: &mut F,
) -> (usize, bool)
where
    F: FnMut(&[f64]) -> (f64, Vec<f64>),
{
    let half_step = 0.5 * step;
    for evaluation in 0..count {
        for (momentum, gradient) in state.rho.iter_mut().zip(&state.grad) {
            *momentum += half_step * gradient;
        }
        for ((position, momentum), inv_mass) in
            state.theta.iter_mut().zip(&state.rho).zip(inverse_mass)
        {
            *position += step * inv_mass * momentum;
        }
        let (log_prob, gradient) = eval(&state.theta);
        if gradient.len() != state.theta.len()
            || !log_prob.is_finite()
            || gradient.iter().any(|value| !value.is_finite())
        {
            state.log_prob = f64::NEG_INFINITY;
            state.grad.fill(0.0);
            return (evaluation + 1, false);
        } else {
            state.log_prob = log_prob;
            state.grad.copy_from_slice(&gradient);
        }
        for (momentum, gradient) in state.rho.iter_mut().zip(&state.grad) {
            *momentum += half_step * gradient;
        }
    }
    (count, true)
}

fn joint_log_density(state: &State, inverse_mass: &[f64]) -> f64 {
    state.log_prob
        - 0.5
            * state
                .rho
                .iter()
                .zip(inverse_mass)
                .map(|(momentum, inv_mass)| momentum * momentum * inv_mass)
                .sum::<f64>()
}

#[cfg(test)]
mod tests {
    use super::*;

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
    fn endpoint_tolerance_does_not_test_intermediate_range() {
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
        assert_eq!(combined.selected, old.selected);
        assert_eq!(boundary.consumed(), 1);

        new.log_weight = 1.0;
        let mut certain = ScriptedUniform01::new(vec![0.999]);
        let (combined, _, log_probability, updated) =
            combine_metropolis_observed(&mut certain, old, new.clone(), Direction::Forward)
                .unwrap();
        assert_eq!(log_probability, 1.0);
        assert!(updated);
        assert_eq!(combined.selected, new.selected);
        assert_eq!(certain.consumed(), 1);
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
