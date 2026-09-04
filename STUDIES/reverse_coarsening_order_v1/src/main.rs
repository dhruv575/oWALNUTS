#![forbid(unsafe_code)]

#[allow(dead_code, clippy::excessive_precision)]
#[rustfmt::skip]
#[path = "../../sspd11_confirmation_v1/primary/src/canonical.rs"]
mod canonical;

use canonical::{CenteredTarget, Data, latent_path_from_innovations, to_innovations};
use owalnuts::sampler::{
    Adaptation, Limits, Metric, Posterior, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts::walnutpie::{
    ComparisonAdaptation, ComparisonObserver, ComparisonTransitionObservation, MetricUpdateOutcome,
    ProposalDirection, ProposalObservation, ProposalObservationControl, ProposalObserver,
    ProposalPhase, ProposalTargetOutcome, Rejection, ReverseCoarseningOrder, StopReason,
    TargetError, TargetErrorKind, WarmupPhase,
};
use owalnuts_bridgestan::{StanTarget, default_preload};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::error::Error;
use std::fs::{self, File, OpenOptions};
use std::io::{BufWriter, Read, Write};
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Mutex, MutexGuard};
use std::time::Instant;

const CHAINS: usize = 4;
const FUNNEL_DIMENSION: usize = 10;
const GAUSSIAN_DIMENSION: usize = 100;
const COMPLETE: &str = "WP37B_CELL_COMPLETE_V1";

#[derive(Clone, Debug, Deserialize)]
struct Manifest {
    schema: String,
    cells: Vec<Cell>,
}

#[derive(Clone, Debug, Deserialize)]
struct Cell {
    ordinal: usize,
    id: String,
    target: String,
    seed: u64,
    arm: String,
    warmup: usize,
    retained: usize,
    timeout_seconds: u64,
    model_library: Option<PathBuf>,
    data_json: Option<PathBuf>,
    reference_names: Vec<String>,
    pair_common_sha256: String,
    arm_config_sha256: String,
}

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        let value =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() && gradient.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

struct Gaussian;

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        GAUSSIAN_DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(position) {
            *g = -*x;
        }
        Ok(-0.5 * position.iter().map(|x| x * x).sum::<f64>())
    }
}

enum StudyTarget {
    Funnel(Funnel),
    Gaussian(Gaussian),
    StateSpace(CenteredTarget),
    BridgeStan(StanTarget),
}

impl Target for StudyTarget {
    fn dimension(&self) -> usize {
        match self {
            Self::Funnel(target) => target.dimension(),
            Self::Gaussian(target) => target.dimension(),
            Self::StateSpace(target) => target.dimension(),
            Self::BridgeStan(target) => target.dimension(),
        }
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        match self {
            Self::Funnel(target) => target.parameter_names(),
            Self::Gaussian(target) => target.parameter_names(),
            Self::StateSpace(target) => target.parameter_names(),
            Self::BridgeStan(target) => target.parameter_names(),
        }
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        match self {
            Self::Funnel(target) => target.log_density_gradient(position, gradient),
            Self::Gaussian(target) => target.log_density_gradient(position, gradient),
            Self::StateSpace(target) => target.log_density_gradient(position, gradient),
            Self::BridgeStan(target) => target.log_density_gradient(position, gradient),
        }
    }
}

#[derive(Clone, Debug, Serialize)]
struct InitialAttempt {
    chain: usize,
    attempt: usize,
    position_bits: Vec<u64>,
    evaluation: String,
    log_density_bits: Option<u64>,
    gradient_bits: Option<Vec<u64>>,
    selected: bool,
    message: Option<String>,
}

struct RecordingTarget {
    inner: StudyTarget,
    record_initialization: AtomicBool,
    initial_attempts: Mutex<Vec<InitialAttempt>>,
}

impl RecordingTarget {
    fn new(inner: StudyTarget) -> Self {
        Self {
            inner,
            record_initialization: AtomicBool::new(false),
            initial_attempts: Mutex::new(Vec::new()),
        }
    }

    fn begin_initialization(&self) {
        self.record_initialization.store(true, Ordering::Release);
    }

    fn finish_initialization(&self) -> Vec<InitialAttempt> {
        self.record_initialization.store(false, Ordering::Release);
        let mut records = lock(&self.initial_attempts);
        let mut chain = 0usize;
        let mut attempt = 0usize;
        for record in records.iter_mut() {
            record.chain = chain;
            record.attempt = attempt;
            if record.evaluation == "finite" {
                record.selected = true;
                chain += 1;
                attempt = 0;
            } else {
                attempt += 1;
            }
        }
        std::mem::take(&mut *records)
    }

    fn constrain_reference(
        &self,
        draw: &[f64],
        reference_names: &[String],
    ) -> Result<Option<Vec<f64>>, Box<dyn Error>> {
        match &self.inner {
            StudyTarget::BridgeStan(target) => {
                let values = target.constrain(draw)?;
                let names = target
                    .constrained_param_names()
                    .iter()
                    .map(|name| bridgestan_name(name))
                    .collect::<Vec<_>>();
                let index = names
                    .iter()
                    .enumerate()
                    .map(|(index, name)| (name.as_str(), index))
                    .collect::<BTreeMap<_, _>>();
                let selected = reference_names
                    .iter()
                    .map(|name| {
                        index
                            .get(name.as_str())
                            .copied()
                            .map(|column| values[column])
                            .ok_or_else(|| format!("missing BridgeStan reference parameter {name}"))
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Ok(Some(selected))
            }
            StudyTarget::StateSpace(_) => Ok(Some(functionals(draw).to_vec())),
            StudyTarget::Funnel(_) | StudyTarget::Gaussian(_) => Ok(None),
        }
    }
}

impl Target for RecordingTarget {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }

    fn parameter_names(&self) -> Option<Vec<String>> {
        self.inner.parameter_names()
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let outcome = self.inner.log_density_gradient(position, gradient);
        if self.record_initialization.load(Ordering::Acquire) {
            let (evaluation, log_density_bits, gradient_bits, message) = match &outcome {
                Ok(value)
                    if value.is_finite() && gradient.iter().all(|value| value.is_finite()) =>
                {
                    (
                        "finite",
                        Some(value.to_bits()),
                        Some(gradient.iter().map(|value| value.to_bits()).collect()),
                        None,
                    )
                }
                Err(error) if error.kind() == TargetErrorKind::Recoverable => (
                    "recoverable_zero_density",
                    None,
                    None,
                    Some(error.message().to_owned()),
                ),
                Ok(_) => ("malformed", None, None, None),
                Err(error) => ("fatal", None, None, Some(error.message().to_owned())),
            };
            lock(&self.initial_attempts).push(InitialAttempt {
                chain: usize::MAX,
                attempt: usize::MAX,
                position_bits: position.iter().map(|value| value.to_bits()).collect(),
                evaluation: evaluation.to_owned(),
                log_density_bits,
                gradient_bits,
                selected: false,
                message,
            });
        }
        outcome
    }
}

fn lock<T>(mutex: &Mutex<T>) -> MutexGuard<'_, T> {
    mutex
        .lock()
        .unwrap_or_else(|poisoned| poisoned.into_inner())
}

fn bridgestan_name(name: &str) -> String {
    let parts = name.split('.').collect::<Vec<_>>();
    if parts.len() == 1 || !parts[1..].iter().all(|part| part.parse::<usize>().is_ok()) {
        name.to_owned()
    } else {
        format!("{}[{}]", parts[0], parts[1..].join(","))
    }
}

fn functionals(y: &[f64]) -> [f64; 8] {
    let q = to_innovations(y, 1.0);
    let path = latent_path_from_innovations(&q);
    let mean = path.iter().sum::<f64>() / path.len() as f64;
    [
        q[0],
        q[1].exp(),
        q[2].exp(),
        q[3].exp(),
        q[4].exp(),
        2.0 + q[5].exp(),
        *path.last().expect("state-space path is nonempty"),
        mean,
    ]
}

#[derive(Clone)]
struct Evaluation {
    phase: ProposalPhase,
    direction: Option<ProposalDirection>,
    level: Option<usize>,
    evaluation_index: usize,
    leaf_attempt: Option<usize>,
    micro_steps: Option<usize>,
    step: Option<f64>,
    reverse_schedule_index: Option<usize>,
    position: Vec<f64>,
    gradient: Vec<f64>,
    mid_step_momentum: Option<Vec<f64>>,
    log_density: Option<f64>,
    outcome: ProposalTargetOutcome,
}

impl From<&ProposalObservation> for Evaluation {
    fn from(observation: &ProposalObservation) -> Self {
        Self {
            phase: observation.phase(),
            direction: observation.direction(),
            level: observation.refinement_level(),
            evaluation_index: observation.evaluation_in_attempt(),
            leaf_attempt: observation.leaf_attempt(),
            micro_steps: observation.micro_steps(),
            step: observation.step(),
            reverse_schedule_index: observation.reverse_schedule_index(),
            position: observation.coordinates().to_vec(),
            gradient: observation.gradient().to_vec(),
            mid_step_momentum: observation.mid_step_momentum().map(<[f64]>::to_vec),
            log_density: observation.potential().map(|potential| -potential),
            outcome: observation.outcome(),
        }
    }
}

struct ChainCollector {
    pending: Vec<Evaluation>,
    transitions: BufWriter<File>,
    forward: BufWriter<File>,
    reverse: BufWriter<File>,
    stops: BufWriter<File>,
    transition_count: usize,
    forward_count: usize,
    reverse_count: usize,
    stop_count: usize,
    phase_work: [PhaseAggregate; 2],
}

#[derive(Clone, Debug, Default, Serialize)]
struct PhaseAggregate {
    transitions: u64,
    initial_state_or_cached_transition_calls: u64,
    forward_calls: u64,
    reverse_calls: u64,
    gated_kernel_calls: u64,
    forward_refinement_attempts: u64,
    forward_micro_steps_requested: u64,
    forward_micro_steps_executed: u64,
    reverse_coarsening_attempts: u64,
    attempted_reverse_micro_steps: u64,
    executed_reverse_micro_steps: u64,
    leaves_attempted: u64,
    leaves_built: u64,
    zero_density_evaluations: u64,
    refinement_exhausted_rejections: u64,
    reverse_coarser_accepted_rejections: u64,
    invalid_forward_rejections: u64,
    invalid_reverse_rejections: u64,
    divergences: u64,
    refinement_exhaustions: u64,
    maximum_depth_stops: u64,
    invalid_stops: u64,
    generated_reverse_level_histogram: BTreeMap<usize, u64>,
    visited_reverse_level_histogram: BTreeMap<usize, u64>,
    first_rejecting_reverse_level_histogram: BTreeMap<usize, u64>,
}

struct Collector {
    chains: Vec<Mutex<ChainCollector>>,
    error: Mutex<Option<String>>,
    warmup: usize,
    reverse_order: ReverseCoarseningOrder,
}

impl ProposalObserver for Collector {
    fn observe(&self, observation: &ProposalObservation) {
        lock(&self.chains[observation.chain()])
            .pending
            .push(Evaluation::from(observation));
    }
}

impl ComparisonObserver for Collector {
    fn observe(&self, observation: &ComparisonTransitionObservation) {
        if lock(&self.error).is_some() {
            return;
        }
        let result = self.encode_transition(observation);
        if let Err(error) = result {
            *lock(&self.error) = Some(error);
        }
    }
}

struct Canon<W> {
    inner: W,
}

impl<W: Write> Canon<W> {
    fn new(inner: W) -> Self {
        Self { inner }
    }

    fn byte(&mut self, value: u8) -> std::io::Result<()> {
        self.inner.write_all(&[value])
    }

    fn boolean(&mut self, value: bool) -> std::io::Result<()> {
        self.byte(u8::from(value))
    }

    fn u64(&mut self, value: usize) -> std::io::Result<()> {
        self.inner.write_all(&(value as u64).to_le_bytes())
    }

    fn raw_u64(&mut self, value: u64) -> std::io::Result<()> {
        self.inner.write_all(&value.to_le_bytes())
    }

    fn f64(&mut self, value: f64) -> std::io::Result<()> {
        self.raw_u64(value.to_bits())
    }

    fn string(&mut self, value: &str) -> std::io::Result<()> {
        self.u64(value.len())?;
        self.inner.write_all(value.as_bytes())
    }

    fn vector_f64(&mut self, values: &[f64]) -> std::io::Result<()> {
        self.u64(values.len())?;
        for value in values {
            self.f64(*value)?;
        }
        Ok(())
    }

    fn option_f64(&mut self, value: Option<f64>) -> std::io::Result<()> {
        match value {
            None => self.byte(0),
            Some(value) => {
                self.byte(1)?;
                self.f64(value)
            }
        }
    }

    fn option_u64(&mut self, value: Option<usize>) -> std::io::Result<()> {
        match value {
            None => self.byte(0),
            Some(value) => {
                self.byte(1)?;
                self.u64(value)
            }
        }
    }

    fn option_vector_f64(&mut self, value: Option<&[f64]>) -> std::io::Result<()> {
        match value {
            None => self.byte(0),
            Some(value) => {
                self.byte(1)?;
                self.vector_f64(value)
            }
        }
    }
}

#[derive(Clone)]
struct Endpoint {
    theta: Vec<f64>,
    rho: Vec<f64>,
    log_density: f64,
    gradient: Vec<f64>,
}

fn evaluation_tag(evaluation: &Evaluation) -> Result<u8, String> {
    match evaluation.outcome {
        ProposalTargetOutcome::Finite => Ok(0),
        ProposalTargetOutcome::Recoverable => Ok(1),
        other => Err(format!(
            "fatal or malformed proposal observation: {other:?}"
        )),
    }
}

fn mapped_gradient(evaluation: &Evaluation) -> Result<Vec<f64>, String> {
    match evaluation.outcome {
        ProposalTargetOutcome::Finite => Ok(evaluation.gradient.clone()),
        ProposalTargetOutcome::Recoverable => Ok(vec![0.0; evaluation.position.len()]),
        other => Err(format!("cannot map proposal outcome {other:?}")),
    }
}

fn endpoint(evaluations: &[&Evaluation], micro_steps: usize, step: f64) -> Option<Endpoint> {
    let last = *evaluations.last()?;
    if evaluations.len() != micro_steps
        || last.evaluation_index + 1 != micro_steps
        || evaluation_tag(last).is_err()
    {
        return None;
    }
    let gradient = mapped_gradient(last).ok()?;
    let mid = last.mid_step_momentum.as_ref()?;
    if mid.len() != gradient.len() {
        return None;
    }
    let rho = mid
        .iter()
        .zip(&gradient)
        .map(|(momentum, gradient)| momentum + 0.5 * step * gradient)
        .collect();
    Some(Endpoint {
        theta: last.position.clone(),
        rho,
        log_density: last.log_density.unwrap_or(f64::NEG_INFINITY),
        gradient,
    })
}

fn write_target_evaluation<W: Write>(
    encoder: &mut Canon<W>,
    evaluation: &Evaluation,
) -> Result<(), String> {
    encoder
        .byte(evaluation_tag(evaluation)?)
        .map_err(io_string)?;
    encoder
        .vector_f64(&evaluation.position)
        .map_err(io_string)?;
    match evaluation.outcome {
        ProposalTargetOutcome::Finite => {
            encoder
                .option_f64(evaluation.log_density)
                .map_err(io_string)?;
            encoder.byte(1).map_err(io_string)?;
            encoder
                .vector_f64(&evaluation.gradient)
                .map_err(io_string)?;
        }
        ProposalTargetOutcome::Recoverable => {
            encoder.option_f64(None).map_err(io_string)?;
            encoder.byte(0).map_err(io_string)?;
        }
        _ => unreachable!("evaluation_tag rejected unsupported outcomes"),
    }
    Ok(())
}

fn write_endpoint<W: Write>(encoder: &mut Canon<W>, endpoint: &Endpoint) -> std::io::Result<()> {
    encoder.vector_f64(&endpoint.theta)?;
    encoder.vector_f64(&endpoint.rho)?;
    encoder.f64(endpoint.log_density)?;
    encoder.vector_f64(&endpoint.gradient)
}

fn write_option_endpoint<W: Write>(
    encoder: &mut Canon<W>,
    endpoint: Option<&Endpoint>,
) -> std::io::Result<()> {
    match endpoint {
        None => encoder.byte(0),
        Some(endpoint) => {
            encoder.byte(1)?;
            write_endpoint(encoder, endpoint)
        }
    }
}

fn direction_tag(direction: ProposalDirection) -> u8 {
    match direction {
        ProposalDirection::Forward => 0,
        ProposalDirection::Backward => 1,
    }
}

fn rejection_tag(rejection: Rejection) -> u8 {
    match rejection {
        Rejection::RefinementExhausted => 0,
        Rejection::ReverseCoarserAccepted => 1,
        Rejection::InvalidEvaluation => 2,
    }
}

fn stop_tag(stop: StopReason) -> u8 {
    match stop {
        StopReason::MaximumDepth => 0,
        StopReason::OuterUTurn => 1,
        StopReason::RecursiveUTurn => 2,
        StopReason::RefinementExhausted => 3,
        StopReason::ReverseCoarserAccepted => 4,
        StopReason::InvalidEvaluation => 5,
        _ => unreachable!("unknown stop reason"),
    }
}

fn write_dual_averaging<W: Write>(
    encoder: &mut Canon<W>,
    state: &owalnuts::walnutpie::DualAveragingTelemetry,
) -> std::io::Result<()> {
    encoder.f64(state.target())?;
    encoder.f64(state.mu())?;
    encoder.f64(state.log_step())?;
    encoder.f64(state.log_step_bar())?;
    encoder.f64(state.h_bar())?;
    encoder.u64(state.iteration())
}

fn write_option_dual_averaging<W: Write>(
    encoder: &mut Canon<W>,
    state: Option<&owalnuts::walnutpie::DualAveragingTelemetry>,
) -> std::io::Result<()> {
    match state {
        None => encoder.byte(0),
        Some(state) => {
            encoder.byte(1)?;
            write_dual_averaging(encoder, state)
        }
    }
}

fn write_adaptation<W: Write>(
    encoder: &mut Canon<W>,
    adaptation: &ComparisonAdaptation,
) -> Result<(), String> {
    encoder
        .byte(match adaptation.stage {
            WarmupPhase::InitialFast => 0,
            WarmupPhase::SlowWindow => 1,
            WarmupPhase::TerminalFast => 2,
            _ => return Err("unknown warmup phase".to_owned()),
        })
        .map_err(io_string)?;
    encoder
        .option_u64(adaptation.window_index)
        .map_err(io_string)?;
    encoder
        .option_u64(adaptation.window_start)
        .map_err(io_string)?;
    encoder
        .option_u64(adaptation.window_end)
        .map_err(io_string)?;
    encoder
        .option_f64(adaptation.input_acceptance)
        .map_err(io_string)?;
    encoder
        .f64(adaptation.active_step_before)
        .map_err(io_string)?;
    encoder
        .f64(adaptation.active_step_after)
        .map_err(io_string)?;
    write_option_dual_averaging(encoder, adaptation.dual_averaging_before.as_ref())
        .map_err(io_string)?;
    write_option_dual_averaging(encoder, adaptation.dual_averaging_after.as_ref())
        .map_err(io_string)?;
    let metric_tag = match adaptation.metric_update {
        None => 0,
        Some(MetricUpdateOutcome::InsufficientSamples) => 1,
        Some(MetricUpdateOutcome::Installed) => 2,
        Some(other) => return Err(format!("unencodable metric update outcome {other:?}")),
    };
    encoder.byte(metric_tag).map_err(io_string)?;
    encoder
        .option_vector_f64(adaptation.installed_metric.as_deref())
        .map_err(io_string)
}

impl Collector {
    fn encode_transition(
        &self,
        observation: &ComparisonTransitionObservation,
    ) -> Result<(), String> {
        let mut chain = lock(&self.chains[observation.chain]);
        let evaluations = std::mem::take(&mut chain.pending);
        let observed_calls = evaluations.len();
        let expected_calls = observation
            .work
            .target_calls_initial
            .checked_add(observation.work.target_calls_forward)
            .and_then(|value| value.checked_add(observation.work.target_calls_reverse))
            .ok_or_else(|| "transition work count overflow".to_owned())?;
        if observed_calls != expected_calls {
            return Err(format!(
                "transition {} chain {} observed {observed_calls} calls but work reports {expected_calls}",
                observation.transition, observation.chain
            ));
        }
        if observation.leaf_outcomes.len() != observation.work.leaves_attempted {
            return Err(format!(
                "transition {} chain {} has {} leaf outcomes but {} leaves",
                observation.transition,
                observation.chain,
                observation.leaf_outcomes.len(),
                observation.work.leaves_attempted
            ));
        }

        let mut transition_bytes = Vec::new();
        {
            let mut encoder = Canon::new(&mut transition_bytes);
            encoder
                .byte(u8::from(!observation.discarded))
                .map_err(io_string)?;
            let phase_index = if observation.discarded {
                observation.transition
            } else {
                observation
                    .transition
                    .checked_sub(self.warmup)
                    .ok_or_else(|| "retained transition precedes warmup boundary".to_owned())?
            };
            encoder.u64(phase_index).map_err(io_string)?;
            encoder.u64(observation.transition).map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.direction_draws())
                .map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.uniform_draws())
                .map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.orbit_states())
                .map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.initial_index())
                .map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.selected_index())
                .map_err(io_string)?;
            encoder
                .u64(observation.diagnostics.depth())
                .map_err(io_string)?;
            encoder
                .boolean(observation.diagnostics.position_changed())
                .map_err(io_string)?;
            encoder
                .vector_f64(&observation.selected_theta)
                .map_err(io_string)?;
            encoder
                .vector_f64(&observation.selected_rho)
                .map_err(io_string)?;
            encoder
                .f64(observation.selected_log_density)
                .map_err(io_string)?;
            encoder
                .vector_f64(&observation.selected_gradient)
                .map_err(io_string)?;
            encoder
                .u64(observation.leaf_outcomes.len())
                .map_err(io_string)?;

            for leaf in &observation.leaf_outcomes {
                encoder.u64(leaf.leaf_attempt).map_err(io_string)?;
                encoder
                    .byte(direction_tag(leaf.direction))
                    .map_err(io_string)?;
                let mut attempts = BTreeMap::<usize, Vec<&Evaluation>>::new();
                for evaluation in evaluations.iter().filter(|evaluation| {
                    evaluation.phase == ProposalPhase::Forward
                        && evaluation.leaf_attempt == Some(leaf.leaf_attempt)
                }) {
                    if evaluation.direction != Some(leaf.direction) {
                        return Err("forward evaluation direction disagrees with leaf".to_owned());
                    }
                    attempts
                        .entry(
                            evaluation
                                .level
                                .ok_or_else(|| "forward evaluation missing level".to_owned())?,
                        )
                        .or_default()
                        .push(evaluation);
                }
                encoder.u64(attempts.len()).map_err(io_string)?;
                let mut endpoints = BTreeMap::<usize, Endpoint>::new();
                for (level, attempt) in &attempts {
                    let first = attempt
                        .first()
                        .ok_or_else(|| "empty forward attempt".to_owned())?;
                    let micro_steps = first
                        .micro_steps
                        .ok_or_else(|| "forward attempt missing microsteps".to_owned())?;
                    let step = first
                        .step
                        .ok_or_else(|| "forward attempt missing step".to_owned())?;
                    encoder.u64(*level).map_err(io_string)?;
                    encoder.u64(micro_steps).map_err(io_string)?;
                    encoder.f64(step).map_err(io_string)?;
                    encoder.u64(attempt.len()).map_err(io_string)?;
                    for evaluation in attempt {
                        write_target_evaluation(&mut encoder, evaluation)?;
                        write_forward_record(
                            &mut chain.forward,
                            observation.chain,
                            observation.transition,
                            leaf.leaf_attempt,
                            *level,
                            evaluation,
                        )?;
                        chain.forward_count += 1;
                    }
                    let endpoint = endpoint(attempt, micro_steps, step);
                    write_option_endpoint(&mut encoder, endpoint.as_ref()).map_err(io_string)?;
                    if let Some(endpoint) = endpoint {
                        endpoints.insert(*level, endpoint);
                    }
                }
                encoder
                    .option_u64(leaf.accepted_forward_level)
                    .map_err(io_string)?;
                let accepted_endpoint = leaf
                    .accepted_forward_level
                    .and_then(|level| endpoints.get(&level));
                write_option_endpoint(&mut encoder, accepted_endpoint).map_err(io_string)?;
                let schedule = observation
                    .reverse_schedules
                    .iter()
                    .find(|schedule| schedule.leaf_attempt == leaf.leaf_attempt);
                match (leaf.accepted_forward_level, schedule) {
                    (Some(level), Some(schedule)) if schedule.accepted_forward_level == level => {}
                    (None, None) => {}
                    _ => return Err("leaf accepted-level/schedule mismatch".to_owned()),
                }
                if let (Some(level), Some(schedule)) = (leaf.accepted_forward_level, schedule) {
                    let accepted_attempt = attempts
                        .get(&level)
                        .and_then(|attempt| attempt.first())
                        .ok_or_else(|| "accepted forward attempt is missing".to_owned())?;
                    let mut microsteps = accepted_attempt
                        .micro_steps
                        .ok_or_else(|| "accepted attempt missing microsteps".to_owned())?;
                    let mut step = accepted_attempt
                        .step
                        .ok_or_else(|| "accepted attempt missing step".to_owned())?;
                    let mut coarse_level = level;
                    let mut expected = Vec::with_capacity(level);
                    while microsteps / 2 >= 1 {
                        microsteps /= 2;
                        step *= 2.0;
                        coarse_level -= 1;
                        expected.push((coarse_level, microsteps, step.to_bits()));
                    }
                    let actual = schedule
                        .entries
                        .iter()
                        .map(|entry| (entry.coarse_level, entry.micro_steps, entry.step.to_bits()))
                        .collect::<Vec<_>>();
                    if actual != expected {
                        return Err(
                            "generated reverse schedule violates repeated arithmetic".into()
                        );
                    }
                    let mut visits = Vec::new();
                    for evaluation in evaluations.iter().filter(|evaluation| {
                        evaluation.phase == ProposalPhase::Reverse
                            && evaluation.leaf_attempt == Some(leaf.leaf_attempt)
                    }) {
                        let index = evaluation.reverse_schedule_index.ok_or_else(|| {
                            "reverse evaluation missing generated-schedule index".to_owned()
                        })?;
                        if visits.last() != Some(&index) {
                            if visits.contains(&index) {
                                return Err("reverse level was revisited".to_owned());
                            }
                            visits.push(index);
                        }
                    }
                    let traversal = match self.reverse_order {
                        ReverseCoarseningOrder::FinestToCoarsest => {
                            (0..schedule.entries.len()).collect::<Vec<_>>()
                        }
                        ReverseCoarseningOrder::CoarsestToFinest => {
                            (0..schedule.entries.len()).rev().collect::<Vec<_>>()
                        }
                    };
                    if visits.len() > traversal.len() || visits != traversal[..visits.len()] {
                        return Err("reverse visits are not a legal traversal prefix".to_owned());
                    }
                    if leaf.rejection.is_none() && visits.len() != traversal.len() {
                        return Err("accepted leaf skipped a reverse schedule entry".to_owned());
                    }
                    for index in visits {
                        let entry = &schedule.entries[index];
                        let count = evaluations
                            .iter()
                            .filter(|evaluation| {
                                evaluation.phase == ProposalPhase::Reverse
                                    && evaluation.leaf_attempt == Some(leaf.leaf_attempt)
                                    && evaluation.reverse_schedule_index == Some(index)
                            })
                            .count();
                        if count != entry.micro_steps {
                            return Err(
                                "reverse attempt did not execute every microstep".to_owned()
                            );
                        }
                    }
                }
                encoder
                    .u64(schedule.map_or(0, |schedule| schedule.entries.len()))
                    .map_err(io_string)?;
                if let Some(schedule) = schedule {
                    for entry in &schedule.entries {
                        encoder.u64(entry.coarse_level).map_err(io_string)?;
                        encoder.u64(entry.micro_steps).map_err(io_string)?;
                        encoder.f64(entry.step).map_err(io_string)?;
                    }
                }
                encoder
                    .byte(u8::from(leaf.rejection.is_some()))
                    .map_err(io_string)?;
                match leaf.rejection {
                    None => encoder.byte(0).map_err(io_string)?,
                    Some(rejection) => {
                        encoder.byte(1).map_err(io_string)?;
                        encoder.byte(rejection_tag(rejection)).map_err(io_string)?;
                    }
                }
                write_option_endpoint(
                    &mut encoder,
                    if leaf.rejection.is_none() {
                        accepted_endpoint
                    } else {
                        None
                    },
                )
                .map_err(io_string)?;
            }
            match observation.adaptation.as_ref() {
                None => encoder.byte(0).map_err(io_string)?,
                Some(adaptation) => {
                    encoder.byte(1).map_err(io_string)?;
                    write_adaptation(&mut encoder, adaptation)?;
                }
            }
        }

        for evaluation in evaluations
            .iter()
            .filter(|evaluation| evaluation.phase == ProposalPhase::Reverse)
        {
            write_reverse_record(
                &mut chain.reverse,
                observation.chain,
                observation.transition,
                evaluation,
            )?;
            chain.reverse_count += 1;
        }
        write_stop_record(&mut chain.stops, observation)?;
        chain.stop_count += 1;
        chain
            .transitions
            .write_all(&transition_bytes)
            .map_err(io_string)?;
        chain.transition_count += 1;
        update_phase_aggregate(
            &mut chain.phase_work[usize::from(!observation.discarded)],
            observation,
            &evaluations,
        )?;
        Ok(())
    }
}

fn add_u64(destination: &mut u64, value: usize) -> Result<(), String> {
    *destination = destination
        .checked_add(value as u64)
        .ok_or_else(|| "work counter overflow".to_owned())?;
    Ok(())
}

fn update_phase_aggregate(
    aggregate: &mut PhaseAggregate,
    observation: &ComparisonTransitionObservation,
    evaluations: &[Evaluation],
) -> Result<(), String> {
    add_u64(&mut aggregate.transitions, 1)?;
    add_u64(
        &mut aggregate.initial_state_or_cached_transition_calls,
        observation.work.target_calls_initial,
    )?;
    add_u64(
        &mut aggregate.forward_calls,
        observation.work.target_calls_forward,
    )?;
    add_u64(
        &mut aggregate.reverse_calls,
        observation.work.target_calls_reverse,
    )?;
    let gated = observation
        .work
        .target_calls_initial
        .checked_add(observation.work.target_calls_forward)
        .and_then(|value| value.checked_add(observation.work.target_calls_reverse))
        .ok_or_else(|| "gated kernel call overflow".to_owned())?;
    add_u64(&mut aggregate.gated_kernel_calls, gated)?;
    add_u64(
        &mut aggregate.forward_refinement_attempts,
        observation.work.forward_refinement_attempts,
    )?;
    add_u64(
        &mut aggregate.forward_micro_steps_requested,
        observation.work.forward_micro_steps_requested,
    )?;
    add_u64(
        &mut aggregate.forward_micro_steps_executed,
        observation.work.forward_micro_steps_executed,
    )?;
    add_u64(
        &mut aggregate.reverse_coarsening_attempts,
        observation.work.reverse_coarsening_attempts,
    )?;
    add_u64(
        &mut aggregate.attempted_reverse_micro_steps,
        observation.work.reverse_micro_steps_requested,
    )?;
    add_u64(
        &mut aggregate.executed_reverse_micro_steps,
        observation.work.reverse_micro_steps_executed,
    )?;
    add_u64(
        &mut aggregate.leaves_attempted,
        observation.work.leaves_attempted,
    )?;
    add_u64(&mut aggregate.leaves_built, observation.work.leaves_built)?;
    add_u64(
        &mut aggregate.zero_density_evaluations,
        observation.work.zero_density_evaluations,
    )?;
    add_u64(
        &mut aggregate.refinement_exhausted_rejections,
        observation.work.refinement_exhausted_rejections,
    )?;
    add_u64(
        &mut aggregate.reverse_coarser_accepted_rejections,
        observation.work.reverse_coarser_accepted_rejections,
    )?;
    add_u64(
        &mut aggregate.invalid_forward_rejections,
        observation.work.invalid_forward_rejections,
    )?;
    add_u64(
        &mut aggregate.invalid_reverse_rejections,
        observation.work.invalid_reverse_rejections,
    )?;
    add_u64(
        &mut aggregate.divergences,
        usize::from(observation.diagnostics.divergent()),
    )?;
    add_u64(
        &mut aggregate.refinement_exhaustions,
        usize::from(observation.diagnostics.stop() == StopReason::RefinementExhausted),
    )?;
    add_u64(
        &mut aggregate.maximum_depth_stops,
        usize::from(observation.diagnostics.stop() == StopReason::MaximumDepth),
    )?;
    add_u64(
        &mut aggregate.invalid_stops,
        usize::from(observation.diagnostics.stop() == StopReason::InvalidEvaluation),
    )?;
    for schedule in &observation.reverse_schedules {
        for entry in &schedule.entries {
            *aggregate
                .generated_reverse_level_histogram
                .entry(entry.coarse_level)
                .or_default() += 1;
        }
    }
    let visited = evaluations
        .iter()
        .filter(|evaluation| evaluation.phase == ProposalPhase::Reverse)
        .map(|evaluation| {
            (
                evaluation.leaf_attempt,
                evaluation.reverse_schedule_index,
                evaluation.level,
            )
        })
        .collect::<BTreeSet<_>>();
    for (_, _, level) in visited {
        *aggregate
            .visited_reverse_level_histogram
            .entry(level.ok_or_else(|| "visited reverse level missing index".to_owned())?)
            .or_default() += 1;
    }
    for leaf in &observation.leaf_outcomes {
        if matches!(
            leaf.rejection,
            Some(Rejection::ReverseCoarserAccepted | Rejection::InvalidEvaluation)
        ) && let Some(level) = evaluations
            .iter()
            .rev()
            .find(|evaluation| {
                evaluation.phase == ProposalPhase::Reverse
                    && evaluation.leaf_attempt == Some(leaf.leaf_attempt)
            })
            .and_then(|evaluation| evaluation.level)
        {
            *aggregate
                .first_rejecting_reverse_level_histogram
                .entry(level)
                .or_default() += 1;
        }
    }
    Ok(())
}

fn write_forward_record<W: Write>(
    writer: &mut W,
    chain: usize,
    transition: usize,
    leaf: usize,
    level: usize,
    evaluation: &Evaluation,
) -> Result<(), String> {
    let mut encoder = Canon::new(writer);
    encoder.u64(chain).map_err(io_string)?;
    encoder.u64(transition).map_err(io_string)?;
    encoder.u64(leaf).map_err(io_string)?;
    encoder.u64(level).map_err(io_string)?;
    encoder
        .u64(evaluation.evaluation_index)
        .map_err(io_string)?;
    encoder
        .u64(
            evaluation
                .micro_steps
                .ok_or_else(|| "forward record missing microsteps".to_owned())?,
        )
        .map_err(io_string)?;
    encoder
        .f64(
            evaluation
                .step
                .ok_or_else(|| "forward record missing step".to_owned())?,
        )
        .map_err(io_string)?;
    write_target_evaluation(&mut encoder, evaluation)
}

fn write_reverse_record<W: Write>(
    writer: &mut W,
    chain: usize,
    transition: usize,
    evaluation: &Evaluation,
) -> Result<(), String> {
    let mut encoder = Canon::new(writer);
    encoder.u64(chain).map_err(io_string)?;
    encoder.u64(transition).map_err(io_string)?;
    encoder
        .u64(
            evaluation
                .leaf_attempt
                .ok_or_else(|| "reverse record missing leaf".to_owned())?,
        )
        .map_err(io_string)?;
    encoder
        .u64(evaluation.evaluation_index)
        .map_err(io_string)?;
    encoder
        .u64(
            evaluation
                .level
                .ok_or_else(|| "reverse record missing coarse level".to_owned())?,
        )
        .map_err(io_string)?;
    encoder
        .u64(
            evaluation
                .micro_steps
                .ok_or_else(|| "reverse record missing microsteps".to_owned())?,
        )
        .map_err(io_string)?;
    encoder
        .f64(
            evaluation
                .step
                .ok_or_else(|| "reverse record missing step".to_owned())?,
        )
        .map_err(io_string)?;
    let _schedule_index = evaluation
        .reverse_schedule_index
        .ok_or_else(|| "reverse record missing generated-schedule index".to_owned())?;
    write_target_evaluation(&mut encoder, evaluation)
}

fn write_stop_record<W: Write>(
    writer: &mut W,
    observation: &ComparisonTransitionObservation,
) -> Result<(), String> {
    let mut encoder = Canon::new(writer);
    encoder.u64(observation.chain).map_err(io_string)?;
    encoder.u64(observation.transition).map_err(io_string)?;
    encoder
        .byte(stop_tag(observation.diagnostics.stop()))
        .map_err(io_string)?;
    encoder
        .u64(observation.leaf_outcomes.len())
        .map_err(io_string)?;
    for leaf in &observation.leaf_outcomes {
        encoder
            .byte(u8::from(leaf.rejection.is_some()))
            .map_err(io_string)?;
        match leaf.rejection {
            None => encoder.byte(0).map_err(io_string)?,
            Some(rejection) => {
                encoder.byte(1).map_err(io_string)?;
                encoder.byte(rejection_tag(rejection)).map_err(io_string)?;
            }
        }
    }
    encoder.byte(0).map_err(io_string)
}

fn io_string(error: std::io::Error) -> String {
    error.to_string()
}

struct DigestWriter<W> {
    inner: W,
    digest: Sha256,
    bytes: u64,
}

impl<W> DigestWriter<W> {
    fn new(inner: W) -> Self {
        Self {
            inner,
            digest: Sha256::new(),
            bytes: 0,
        }
    }
}

impl<W: Write> Write for DigestWriter<W> {
    fn write(&mut self, buffer: &[u8]) -> std::io::Result<usize> {
        let written = self.inner.write(buffer)?;
        self.digest.update(&buffer[..written]);
        self.bytes = self
            .bytes
            .checked_add(written as u64)
            .expect("canonical byte count overflow");
        Ok(written)
    }

    fn flush(&mut self) -> std::io::Result<()> {
        self.inner.flush()
    }
}

#[derive(Clone, Debug, Serialize)]
struct RecordArtifact {
    file: String,
    canonical_sha256: String,
    canonical_bytes: u64,
    compressed_sha256: String,
    compressed_bytes: u64,
}

fn write_record(
    path: &Path,
    domain: &str,
    version: u16,
    payload: impl FnOnce(&mut dyn Write) -> Result<(), Box<dyn Error>>,
) -> Result<RecordArtifact, Box<dyn Error>> {
    let temporary = temporary_path(path);
    let file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)?;
    let compressed = zstd::stream::write::Encoder::new(file, 9)?;
    let mut digesting = DigestWriter::new(compressed);
    digesting.write_all(domain.as_bytes())?;
    digesting.write_all(&[0])?;
    digesting.write_all(&version.to_le_bytes())?;
    payload(&mut digesting)?;
    digesting.flush()?;
    let canonical_sha256 = hex(&digesting.digest.finalize());
    let canonical_bytes = digesting.bytes;
    let compressed = digesting.inner.finish()?;
    compressed.sync_all()?;
    fs::rename(&temporary, path)?;
    let (compressed_sha256, compressed_bytes) = sha256_file(path)?;
    Ok(RecordArtifact {
        file: path
            .file_name()
            .expect("artifact filename")
            .to_string_lossy()
            .into_owned(),
        canonical_sha256,
        canonical_bytes,
        compressed_sha256,
        compressed_bytes,
    })
}

fn temporary_path(path: &Path) -> PathBuf {
    let mut temporary = path.as_os_str().to_owned();
    temporary.push(".tmp");
    PathBuf::from(temporary)
}

fn sha256_file(path: &Path) -> Result<(String, u64), Box<dyn Error>> {
    let mut file = File::open(path)?;
    let mut digest = Sha256::new();
    let mut bytes = 0u64;
    let mut buffer = vec![0u8; 1024 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
        bytes = bytes
            .checked_add(read as u64)
            .ok_or("file length overflow")?;
    }
    Ok((hex(&digest.finalize()), bytes))
}

fn hex(bytes: &[u8]) -> String {
    const DIGITS: &[u8; 16] = b"0123456789abcdef";
    let mut result = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        result.push(DIGITS[(byte >> 4) as usize] as char);
        result.push(DIGITS[(byte & 0xf) as usize] as char);
    }
    result
}

fn copy_file(writer: &mut dyn Write, path: &Path) -> Result<(), Box<dyn Error>> {
    let mut file = File::open(path)?;
    std::io::copy(&mut file, writer)?;
    Ok(())
}

fn open_raw(path: &Path) -> Result<BufWriter<File>, Box<dyn Error>> {
    Ok(BufWriter::new(
        OpenOptions::new().create_new(true).write(true).open(path)?,
    ))
}

fn write_initial_positions_record(
    path: &Path,
    target: &str,
    seed: u64,
    starts: &[Vec<f64>],
) -> Result<RecordArtifact, Box<dyn Error>> {
    write_record(
        path,
        "owalnuts.reverse_coarsening_order_v1.initial_positions",
        2,
        |writer| {
            let mut encoder = Canon::new(writer);
            encoder.string(target)?;
            encoder.raw_u64(seed)?;
            encoder.u64(starts.len())?;
            encoder.u64(starts.first().map_or(0, Vec::len))?;
            for start in starts {
                if start.len() != starts.first().map_or(0, Vec::len) {
                    return Err("ragged initial-position matrix".into());
                }
                for value in start {
                    encoder.f64(*value)?;
                }
            }
            Ok(())
        },
    )
}

fn write_initializer_attempts_record(
    path: &Path,
    target: &str,
    seed: u64,
    attempts: &[InitialAttempt],
) -> Result<RecordArtifact, Box<dyn Error>> {
    write_record(
        path,
        "owalnuts.reverse_coarsening_order_v1.initializer_attempts",
        2,
        |writer| {
            let mut encoder = Canon::new(writer);
            encoder.string(target)?;
            encoder.raw_u64(seed)?;
            encoder.u64(attempts.len())?;
            for attempt in attempts {
                encoder.u64(attempt.chain)?;
                encoder.u64(attempt.attempt)?;
                encoder.u64(attempt.position_bits.len())?;
                for value in &attempt.position_bits {
                    encoder.raw_u64(*value)?;
                }
                match attempt.evaluation.as_str() {
                    "finite" => {
                        encoder.byte(0)?;
                        encoder.byte(1)?;
                        encoder.raw_u64(
                            attempt
                                .log_density_bits
                                .ok_or("finite initializer attempt missing log density")?,
                        )?;
                        encoder.byte(1)?;
                        let gradient = attempt
                            .gradient_bits
                            .as_ref()
                            .ok_or("finite initializer attempt missing gradient")?;
                        encoder.u64(gradient.len())?;
                        for value in gradient {
                            encoder.raw_u64(*value)?;
                        }
                    }
                    "recoverable_zero_density" => {
                        encoder.byte(1)?;
                        encoder.byte(0)?;
                        encoder.byte(0)?;
                    }
                    other => return Err(format!("fatal initializer outcome {other}").into()),
                }
                encoder.boolean(attempt.selected)?;
            }
            Ok(())
        },
    )
}

fn write_stream_record(
    path: &Path,
    domain: &str,
    count: usize,
    parts: &[PathBuf],
) -> Result<RecordArtifact, Box<dyn Error>> {
    write_record(path, domain, 2, |writer| {
        writer.write_all(&(count as u64).to_le_bytes())?;
        for part in parts {
            copy_file(writer, part)?;
        }
        Ok(())
    })
}

fn write_semantic_record(
    path: &Path,
    cell: &Cell,
    posterior: &Posterior,
    transition_parts: &[PathBuf],
    reference_draws: &[Option<Vec<f64>>],
) -> Result<RecordArtifact, Box<dyn Error>> {
    write_record(
        path,
        "owalnuts.reverse_coarsening_order_v1.semantic",
        2,
        |writer| {
            let mut encoder = Canon::new(writer);
            encoder.string(&cell.target)?;
            encoder.raw_u64(cell.seed)?;
            encoder.u64(posterior.chain_count())?;
            for (chain_index, chain) in posterior.chains().iter().enumerate() {
                let metadata = chain.metadata();
                encoder.u64(chain_index)?;
                encoder.raw_u64(metadata.effective_seed())?;
                encoder.u64(chain.diagnostics().len())?;
                copy_file(&mut encoder.inner, &transition_parts[chain_index])?;
                let tuning = metadata.tuning();
                encoder.f64(0.5)?;
                encoder.f64(tuning.step_size())?;
                encoder.u64(tuning.max_depth())?;
                encoder.u64(tuning.min_micro_steps())?;
                encoder.u64(tuning.max_refinement_levels())?;
                encoder.f64(tuning.max_error())?;
                encoder.f64(tuning.divergence_threshold())?;
                encoder.byte(0)?;
                encoder.byte(0)?;
                encoder.byte(0)?;
                encoder.byte(0)?;
                encoder.vector_f64(metadata.mass_diagonal())?;
                encoder.u64(chain.retained())?;
                encoder.u64(chain.dimension())?;
                for value in chain.samples() {
                    encoder.f64(*value)?;
                }
                match &reference_draws[chain_index] {
                    None => encoder.byte(0)?,
                    Some(draws) => {
                        encoder.byte(1)?;
                        encoder.u64(cell.retained)?;
                        let columns = draws.len().checked_div(cell.retained).unwrap_or(0);
                        if draws.len() != cell.retained * columns {
                            return Err("ragged constrained/reference matrix".into());
                        }
                        encoder.u64(columns)?;
                        for value in draws {
                            encoder.f64(*value)?;
                        }
                    }
                }
            }
            Ok(())
        },
    )
}

fn write_diagnostic_draws(
    path: &Path,
    posterior: &Posterior,
    reference_draws: &[Option<Vec<f64>>],
) -> Result<Value, Box<dyn Error>> {
    let temporary = temporary_path(path);
    let mut file = BufWriter::new(
        OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temporary)?,
    );
    file.write_all(b"WP37BDRW")?;
    file.write_all(&(posterior.chain_count() as u64).to_le_bytes())?;
    file.write_all(&(posterior.draws_per_chain() as u64).to_le_bytes())?;
    file.write_all(&(posterior.dimension() as u64).to_le_bytes())?;
    for chain in posterior.chains() {
        for value in chain.samples() {
            file.write_all(&value.to_bits().to_le_bytes())?;
        }
    }
    let reference_columns = reference_draws
        .iter()
        .find_map(|matrix| matrix.as_ref())
        .map_or(0, |matrix| {
            matrix.len() / posterior.draws_per_chain().max(1)
        });
    file.write_all(&(reference_columns as u64).to_le_bytes())?;
    if reference_columns > 0 {
        for matrix in reference_draws {
            let matrix = matrix
                .as_ref()
                .ok_or("reference matrix availability differs by chain")?;
            for value in matrix {
                file.write_all(&value.to_bits().to_le_bytes())?;
            }
        }
    }
    file.flush()?;
    let file = file.into_inner()?;
    file.sync_all()?;
    fs::rename(temporary, path)?;
    let (sha256, bytes) = sha256_file(path)?;
    Ok(json!({
        "file": path.file_name().expect("draw filename").to_string_lossy(),
        "sha256": sha256,
        "bytes": bytes,
        "reference_columns": reference_columns
    }))
}

struct TemporaryParts {
    transitions: Vec<PathBuf>,
    forward: Vec<PathBuf>,
    reverse: Vec<PathBuf>,
    stops: Vec<PathBuf>,
}

fn make_collector(
    artifact_directory: &Path,
    stem: &str,
    warmup: usize,
    reverse_order: ReverseCoarseningOrder,
) -> Result<(Collector, TemporaryParts), Box<dyn Error>> {
    let mut transitions = Vec::with_capacity(CHAINS);
    let mut forward = Vec::with_capacity(CHAINS);
    let mut reverse = Vec::with_capacity(CHAINS);
    let mut stops = Vec::with_capacity(CHAINS);
    let mut chains = Vec::with_capacity(CHAINS);
    for chain in 0..CHAINS {
        let transition_path = artifact_directory.join(format!("{stem}.c{chain}.transitions.tmp"));
        let forward_path = artifact_directory.join(format!("{stem}.c{chain}.forward.tmp"));
        let reverse_path = artifact_directory.join(format!("{stem}.c{chain}.reverse.tmp"));
        let stop_path = artifact_directory.join(format!("{stem}.c{chain}.stops.tmp"));
        chains.push(Mutex::new(ChainCollector {
            pending: Vec::new(),
            transitions: open_raw(&transition_path)?,
            forward: open_raw(&forward_path)?,
            reverse: open_raw(&reverse_path)?,
            stops: open_raw(&stop_path)?,
            transition_count: 0,
            forward_count: 0,
            reverse_count: 0,
            stop_count: 0,
            phase_work: [PhaseAggregate::default(), PhaseAggregate::default()],
        }));
        transitions.push(transition_path);
        forward.push(forward_path);
        reverse.push(reverse_path);
        stops.push(stop_path);
    }
    Ok((
        Collector {
            chains,
            error: Mutex::new(None),
            warmup,
            reverse_order,
        },
        TemporaryParts {
            transitions,
            forward,
            reverse,
            stops,
        },
    ))
}

fn flush_collector(collector: &Collector) -> Result<(), Box<dyn Error>> {
    for chain in &collector.chains {
        let mut chain = lock(chain);
        chain.transitions.flush()?;
        chain.forward.flush()?;
        chain.reverse.flush()?;
        chain.stops.flush()?;
    }
    if let Some(error) = lock(&collector.error).clone() {
        return Err(error.into());
    }
    Ok(())
}

fn remove_parts(parts: &TemporaryParts) -> Result<(), Box<dyn Error>> {
    for path in parts
        .transitions
        .iter()
        .chain(&parts.forward)
        .chain(&parts.reverse)
        .chain(&parts.stops)
    {
        fs::remove_file(path)?;
    }
    Ok(())
}

fn numbers(value: &Value) -> Result<Vec<f64>, Box<dyn Error>> {
    value
        .as_array()
        .ok_or_else(|| "expected numeric array".into())
        .and_then(|values| {
            values
                .iter()
                .map(|value| value.as_f64().ok_or_else(|| "expected f64".into()))
                .collect()
        })
}

type Starts = Vec<Vec<f64>>;
type BuiltTarget = (StudyTarget, Starts);
type OptionalBuiltTarget = (RecordingTarget, Option<Starts>);

fn state_space_target() -> Result<BuiltTarget, Box<dyn Error>> {
    let manifest_root = Path::new(env!("CARGO_MANIFEST_DIR"));
    let root = manifest_root.join("../sspd11_confirmation_v1/primary");
    let fixture: Value = serde_json::from_slice(&fs::read(
        manifest_root.join("config/sspd-target-fixture.json"),
    )?)?;
    let data = Data::try_from_raw(
        &numbers(&fixture["data"]["y"])?,
        &numbers(&fixture["data"]["s"])?,
        &numbers(&fixture["data"]["v"])?,
    )?;
    let starts_document: Value =
        serde_json::from_slice(&fs::read(root.join("starts/sspd-11.json"))?)?;
    let starts = starts_document["starts"]
        .as_array()
        .ok_or("state-space starts must be an array")?
        .iter()
        .map(numbers)
        .collect::<Result<Vec<_>, _>>()?
        .into_iter()
        .map(|start| canonical::from_innovations(&start, 1.0))
        .collect();
    Ok((
        StudyTarget::StateSpace(CenteredTarget {
            data,
            a: 1.0,
            calls: std::sync::atomic::AtomicUsize::new(0),
        }),
        starts,
    ))
}

fn build_target(cell: &Cell) -> Result<OptionalBuiltTarget, Box<dyn Error>> {
    let (target, starts) = match cell.target.as_str() {
        "neal_funnel_10d" => {
            let starts = [-3.0, -1.0, 1.0, 3.0]
                .into_iter()
                .map(|omega| {
                    let mut start = vec![0.0; FUNNEL_DIMENSION];
                    start[0] = omega;
                    start
                })
                .collect();
            (StudyTarget::Funnel(Funnel), Some(starts))
        }
        "gaussian_100d" => (StudyTarget::Gaussian(Gaussian), None),
        "state_space_sspd11_t1000" => {
            let (target, starts) = state_space_target()?;
            (target, Some(starts))
        }
        target if target.starts_with("posteriordb_") => {
            let model = cell
                .model_library
                .as_ref()
                .ok_or("BridgeStan cell missing model library")?;
            let data = fs::read_to_string(
                cell.data_json
                    .as_ref()
                    .ok_or("BridgeStan cell missing data JSON")?,
            )?;
            let target = StanTarget::load(model, &default_preload(), Some(&data), 1)?;
            if target.execution() != owalnuts_bridgestan::Execution::OwnedSerialised {
                return Err("BridgeStan target is not using the owned serialized backend".into());
            }
            if target.dimension()
                != match cell.target.as_str() {
                    "posteriordb_accel_gp" => 66,
                    "posteriordb_gp_pois_regr" => 13,
                    "posteriordb_eight_schools_centered"
                    | "posteriordb_eight_schools_noncentered" => 10,
                    _ => return Err("unknown posteriordb target".into()),
                }
            {
                return Err("BridgeStan target dimension does not match frozen value".into());
            }
            (StudyTarget::BridgeStan(target), None)
        }
        other => return Err(format!("unknown target {other}").into()),
    };
    Ok((RecordingTarget::new(target), starts))
}

fn validate_work(
    posterior: &Posterior,
    phase_work: &[[PhaseAggregate; 2]],
) -> Result<(), Box<dyn Error>> {
    for (chain_index, chain) in posterior.chains().iter().enumerate() {
        for (phase_index, work) in [chain.telemetry().discarded(), chain.telemetry().retained()]
            .into_iter()
            .enumerate()
        {
            let observed = &phase_work[chain_index][phase_index];
            if observed.initial_state_or_cached_transition_calls
                != work.target_calls_initial() as u64
                || observed.forward_calls != work.target_calls_forward() as u64
                || observed.reverse_calls != work.target_calls_reverse() as u64
                || observed.gated_kernel_calls != work.target_calls_total() as u64
            {
                return Err(format!(
                    "chain {chain_index} phase {phase_index} work partition disagrees with WorkTotals"
                )
                .into());
            }
        }
    }
    let observed_total = phase_work
        .iter()
        .flat_map(|phases| phases.iter())
        .try_fold(0u64, |total, phase| {
            total.checked_add(phase.gated_kernel_calls)
        })
        .ok_or("observed work total overflow")?;
    if observed_total != posterior.total_target_calls() as u64 {
        return Err("checked work sum disagrees with Posterior::total_target_calls".into());
    }
    Ok(())
}

fn reference_matrices(
    target: &RecordingTarget,
    cell: &Cell,
    posterior: &Posterior,
) -> Result<Vec<Option<Vec<f64>>>, Box<dyn Error>> {
    posterior
        .chains()
        .iter()
        .map(|chain| {
            let mut matrix: Option<Vec<f64>> = None;
            for draw in chain.samples().chunks_exact(chain.dimension()) {
                match target.constrain_reference(draw, &cell.reference_names)? {
                    None => {
                        if matrix.is_some() {
                            return Err("reference transform changed availability".into());
                        }
                    }
                    Some(values) => {
                        if values.iter().any(|value| !value.is_finite()) {
                            return Err("reference transform produced nonfinite value".into());
                        }
                        matrix.get_or_insert_with(Vec::new).extend(values);
                    }
                }
            }
            Ok(matrix)
        })
        .collect()
}

fn artifact_path(directory: &Path, stem: &str, kind: &str) -> PathBuf {
    directory.join(format!("{stem}.{kind}.bin.zst"))
}

fn run_cell(
    cell: &Cell,
    raw_output: &Path,
    artifact_directory: &Path,
) -> Result<(), Box<dyn Error>> {
    if raw_output.exists() {
        return Err(format!("raw output already exists: {}", raw_output.display()).into());
    }
    if cell.ordinal >= 84 {
        return Err("cell ordinal exceeds frozen manifest".into());
    }
    fs::create_dir_all(artifact_directory)?;
    let stem = format!("{:03}-{}", cell.ordinal, cell.id.replace('/', "-"));
    let (target, given_starts) = build_target(cell)?;
    let starts;
    let initializer_attempts;
    if let Some(given) = given_starts {
        starts = given;
        initializer_attempts = Vec::new();
    } else {
        target.begin_initialization();
        starts = uniform_starts(&target, CHAINS, cell.seed, 2.0, 100)?;
        initializer_attempts = target.finish_initialization();
        if initializer_attempts
            .iter()
            .filter(|attempt| attempt.selected)
            .count()
            != CHAINS
        {
            return Err("uniform initializer transcript does not select four starts".into());
        }
    }
    if starts.len() != CHAINS || starts.iter().any(|start| start.len() != target.dimension()) {
        return Err("initial-position matrix has the wrong dimensions".into());
    }

    let initial_positions = write_initial_positions_record(
        &artifact_path(artifact_directory, &stem, "initial_positions"),
        &cell.target,
        cell.seed,
        &starts,
    )?;
    let initializer_attempts_record = write_initializer_attempts_record(
        &artifact_path(artifact_directory, &stem, "initializer_attempts"),
        &cell.target,
        cell.seed,
        &initializer_attempts,
    )?;

    let order = match cell.arm.as_str() {
        "finest_to_coarsest" => ReverseCoarseningOrder::FinestToCoarsest,
        "coarsest_to_finest" => ReverseCoarseningOrder::CoarsestToFinest,
        other => return Err(format!("unknown reverse order {other}").into()),
    };
    let tuning = Tuning::new()
        .step_size(0.5)
        .max_depth(10)
        .min_micro_steps(1)
        .max_refinement_levels(8)
        .max_error(1.0)
        .divergence_threshold(1000.0)
        .reverse_coarsening_order(order);
    let sampler = Sampler::new()
        .warmup(cell.warmup)
        .draws(cell.retained)
        .chains(CHAINS)
        .seed(cell.seed)
        .threads(CHAINS)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let maximum_observations =
        NonZeroUsize::new(sampler.worst_case_target_evaluations(CHAINS)?.max(1))
            .expect("maximum observations is positive");
    let (collector, parts) = make_collector(artifact_directory, &stem, cell.warmup, order)?;
    let proposal_control =
        ProposalObservationControl::new(&collector, maximum_observations, target.dimension());
    let started = Instant::now();
    let posterior =
        sampler.run_with_comparison_observers(&target, &starts, &proposal_control, &collector)?;
    let wall_seconds = started.elapsed().as_secs_f64();
    flush_collector(&collector)?;

    let mut phase_work = Vec::with_capacity(CHAINS);
    let mut transition_count = 0usize;
    let mut forward_count = 0usize;
    let mut reverse_count = 0usize;
    let mut stop_count = 0usize;
    for chain in &collector.chains {
        let chain = lock(chain);
        if !chain.pending.is_empty() {
            return Err("proposal observations remain after the last transition".into());
        }
        if chain.transition_count != cell.warmup + cell.retained
            || chain.stop_count != cell.warmup + cell.retained
        {
            return Err("transition or stop record count mismatch".into());
        }
        transition_count = transition_count
            .checked_add(chain.transition_count)
            .ok_or("transition count overflow")?;
        forward_count = forward_count
            .checked_add(chain.forward_count)
            .ok_or("forward count overflow")?;
        reverse_count = reverse_count
            .checked_add(chain.reverse_count)
            .ok_or("reverse count overflow")?;
        stop_count = stop_count
            .checked_add(chain.stop_count)
            .ok_or("stop count overflow")?;
        phase_work.push(chain.phase_work.clone());
    }
    validate_work(&posterior, &phase_work)?;
    if forward_count
        != phase_work
            .iter()
            .flat_map(|phases| phases.iter())
            .map(|phase| phase.forward_calls as usize)
            .sum::<usize>()
        || reverse_count
            != phase_work
                .iter()
                .flat_map(|phases| phases.iter())
                .map(|phase| phase.reverse_calls as usize)
                .sum::<usize>()
    {
        return Err("direct call-record counts disagree with work telemetry".into());
    }

    let reference_draws = reference_matrices(&target, cell, &posterior)?;
    let diagnostic_draws = write_diagnostic_draws(
        &artifact_directory.join(format!("{stem}.diagnostic_draws.bin")),
        &posterior,
        &reference_draws,
    )?;
    let semantic = write_semantic_record(
        &artifact_path(artifact_directory, &stem, "semantic"),
        cell,
        &posterior,
        &parts.transitions,
        &reference_draws,
    )?;
    let forward_calls = write_stream_record(
        &artifact_path(artifact_directory, &stem, "forward_calls"),
        "owalnuts.reverse_coarsening_order_v1.forward_calls",
        forward_count,
        &parts.forward,
    )?;
    let reverse_evaluations = write_stream_record(
        &artifact_path(artifact_directory, &stem, "reverse_evaluations"),
        "owalnuts.reverse_coarsening_order_v1.reverse_evaluations",
        reverse_count,
        &parts.reverse,
    )?;
    let stops = write_stream_record(
        &artifact_path(artifact_directory, &stem, "stops"),
        "owalnuts.reverse_coarsening_order_v1.stops",
        stop_count,
        &parts.stops,
    )?;
    remove_parts(&parts)?;

    let initialization_search_calls = initializer_attempts.len() as u64;
    let gated_kernel_calls = posterior.total_target_calls() as u64;
    let all_callback_calls = initialization_search_calls
        .checked_add(gated_kernel_calls)
        .ok_or("all-callback count overflow")?;
    let raw = json!({
        "schema": "owalnuts-reverse-coarsening-order-v1-cell",
        "comparison_schema_version": 3,
        "completion": COMPLETE,
        "status": "ok",
        "ordinal": cell.ordinal,
        "cell_id": cell.id,
        "target": cell.target,
        "seed": cell.seed,
        "arm": cell.arm,
        "reverse_order": cell.arm,
        "warmup": cell.warmup,
        "retained": cell.retained,
        "timeout_seconds": cell.timeout_seconds,
        "chains": CHAINS,
        "threads": CHAINS,
        "dimension": posterior.dimension(),
        "wall_seconds": wall_seconds,
        "algorithm_revision": posterior.algorithm_revision(),
        "records": {
            "pair_common_static_config": {
                "file": format!("config/{}.pair_common.bin", cell.target),
                "sha256": cell.pair_common_sha256,
            },
            "arm_config": {
                "file": format!("config/{}.{}.arm.bin", cell.target, cell.arm),
                "sha256": cell.arm_config_sha256,
            },
            "initial_positions": initial_positions,
            "initializer_attempts": initializer_attempts_record,
            "semantic": semantic,
            "forward_calls": forward_calls,
            "reverse_evaluations": reverse_evaluations,
            "stops": stops,
            "diagnostic_draws": diagnostic_draws,
            "fatal_errors": [],
            "public_errors": []
        },
        "record_counts": {
            "transitions": transition_count,
            "forward_calls": forward_count,
            "reverse_evaluations": reverse_count,
            "stops": stop_count
        },
        "work": {
            "chains": phase_work,
            "initialization_search_calls": initialization_search_calls,
            "gated_kernel_calls": gated_kernel_calls,
            "all_callback_calls": all_callback_calls
        },
        "health": {
            "nonfinite_outcomes": 0,
            "sampler_errors": 0,
            "public_target_errors": 0,
            "fatal_errors": 0
        },
        "final": posterior.chains().iter().map(|chain| json!({
            "step_bits": format!("{:016x}", chain.metadata().tuning().step_size().to_bits()),
            "metric_bits": chain.metadata().mass_diagonal().iter()
                .map(|value| format!("{:016x}", value.to_bits())).collect::<Vec<_>>()
        })).collect::<Vec<_>>()
    });
    let temporary = temporary_path(raw_output);
    let mut file = OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)?;
    serde_json::to_writer_pretty(&mut file, &raw)?;
    file.write_all(b"\n")?;
    file.flush()?;
    file.sync_all()?;
    fs::rename(temporary, raw_output)?;
    println!("{COMPLETE} {}", cell.id);
    Ok(())
}

fn main() -> Result<(), Box<dyn Error>> {
    let arguments = std::env::args().collect::<Vec<_>>();
    if arguments.len() == 4 && arguments[1] == "--compare" {
        let mut left = zstd::stream::read::Decoder::new(File::open(&arguments[2])?)?;
        let mut right = zstd::stream::read::Decoder::new(File::open(&arguments[3])?)?;
        let mut left_buffer = vec![0u8; 1024 * 1024];
        let mut right_buffer = vec![0u8; 1024 * 1024];
        loop {
            let left_read = left.read(&mut left_buffer)?;
            let right_read = right.read(&mut right_buffer)?;
            if left_read != right_read || left_buffer[..left_read] != right_buffer[..right_read] {
                return Err("canonical records differ".into());
            }
            if left_read == 0 {
                return Ok(());
            }
        }
    }
    if arguments.len() == 4 && arguments[1] == "--decompress" {
        let mut input = zstd::stream::read::Decoder::new(File::open(&arguments[2])?)?;
        let temporary = temporary_path(Path::new(&arguments[3]));
        let mut output = OpenOptions::new()
            .create_new(true)
            .write(true)
            .open(&temporary)?;
        std::io::copy(&mut input, &mut output)?;
        output.flush()?;
        output.sync_all()?;
        fs::rename(temporary, &arguments[3])?;
        return Ok(());
    }
    if arguments.len() != 5 {
        return Err(
            "usage: reverse-coarsening-order-v1 <manifest.json> <ordinal> <raw.json> <artifact-dir>"
                .into(),
        );
    }
    let manifest: Manifest = serde_json::from_slice(&fs::read(&arguments[1])?)?;
    if manifest.schema != "owalnuts-reverse-coarsening-order-v1-manifest" {
        return Err("manifest schema mismatch".into());
    }
    let ordinal = arguments[2].parse::<usize>()?;
    let cell = manifest
        .cells
        .get(ordinal)
        .ok_or("manifest ordinal is out of range")?;
    if cell.ordinal != ordinal {
        return Err("manifest ordinal field mismatch".into());
    }
    run_cell(cell, Path::new(&arguments[3]), Path::new(&arguments[4]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rust_encoder_matches_independent_conformance_fixture() {
        let fixture: Value =
            serde_json::from_str(include_str!("../conformance.json")).expect("conformance JSON");
        let mut bytes = Vec::new();
        bytes.extend_from_slice(b"owalnuts.reverse_coarsening_order_v1.conformance\0");
        bytes.extend_from_slice(&2u16.to_le_bytes());
        {
            let mut encoder = Canon::new(&mut bytes);
            encoder.raw_u64(0).unwrap();
            encoder.raw_u64(u64::MAX).unwrap();
            encoder.f64(-0.0).unwrap();
            encoder.f64(f64::from_bits(0x3ff0_0000_0000_0001)).unwrap();
            encoder.boolean(false).unwrap();
            encoder.boolean(true).unwrap();
            encoder.byte(0).unwrap();
            encoder.byte(1).unwrap();
            encoder.raw_u64(7).unwrap();
            encoder.string("").unwrap();
            encoder.string("WP37B/λ").unwrap();
            encoder.raw_u64(0).unwrap();
            encoder.raw_u64(3).unwrap();
            for value in [1u64, 2, 3] {
                encoder.raw_u64(value).unwrap();
            }
            let enum_widths = [
                2u64, 2, 2, 3, 6, 2, 6, 4, 1, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1, 1, 2, 2, 3, 3,
            ];
            encoder.u64(enum_widths.len()).unwrap();
            for width in enum_widths {
                encoder.raw_u64(width).unwrap();
                for tag in 0..width {
                    encoder.byte(tag as u8).unwrap();
                }
            }
            let valid_rows = [
                (0u8, true, true, 2u64, None, true),
                (1, false, false, 0, Some(0u8), false),
                (1, true, true, 2, Some(1), false),
                (1, false, false, 0, Some(2), false),
                (1, true, true, 2, Some(2), false),
            ];
            encoder.u64(valid_rows.len()).unwrap();
            for (outcome, level, endpoint, schedule, rejection, built) in valid_rows {
                encoder.byte(outcome).unwrap();
                encoder.boolean(level).unwrap();
                encoder.boolean(endpoint).unwrap();
                encoder.raw_u64(schedule).unwrap();
                match rejection {
                    None => encoder.byte(0).unwrap(),
                    Some(rejection) => {
                        encoder.byte(1).unwrap();
                        encoder.byte(rejection).unwrap();
                    }
                }
                encoder.boolean(built).unwrap();
            }
            encoder.raw_u64(6).unwrap();
            for error_kind in 0..6u8 {
                encoder.byte(error_kind).unwrap();
                encoder.byte(error_kind.min(4)).unwrap();
                encoder.string(&format!("fatal-{error_kind}")).unwrap();
            }
        }
        assert_eq!(
            hex(&bytes),
            fixture["canonical_hex"].as_str().expect("canonical hex")
        );
        assert_eq!(
            hex(&Sha256::digest(&bytes)),
            fixture["sha256"].as_str().expect("conformance hash")
        );
    }
}
