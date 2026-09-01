//! Record NUTS and WALNUTS orbits on Neal's 10-D funnel and write
//! `demo/data/funnel-replay.json` for the side-by-side animated replay
//! ("NUTS vs WALNUTS") on the demo page.
//!
//! The target is the paper's funnel (`omega ~ Normal(0, 3)`,
//! `x_i | omega ~ Normal(0, exp(omega))` for nine `x_i`). Three arms run one
//! chain each from the origin with the identity mass, no warmup adaptation,
//! nothing discarded, 20,000 retained transitions and one fixed seed:
//!
//! * `walnuts`: the paper's fixed tuning (`h = 0.36`, `delta = 0.21`, ten
//!   refinement levels, trees up to depth ten), identical to
//!   `examples/funnel_orbit_trace.rs` and arm F of
//!   `STUDIES/paper_funnel_reproduction_v1`.
//! * `nuts_h011`: the same kernel with `max_refinement_levels = 1`, which
//!   disables within-orbit step refinement and leaves standard fixed-step
//!   NUTS at the paper's NUTS step `h = 0.11` (arm N11 of the study: no
//!   energy-error cap, `delta = 1000`).
//! * `nuts_h036`: refinement disabled at the WALNUTS step `h = 0.36` with
//!   `delta = 0.21` (arm N36 of the study, "what refinement buys").
//!
//! The `nuts_*` arms are therefore the paper's control: the same multinomial
//! NUTS tree with the step size frozen.
//!
//! Output layout: `meta` (seed, retained count, number of replayed
//! transitions, exact tail mass, algorithm revision, point columns) and one
//! entry per arm with the first 2,000 retained `(omega, x_1)` draws, the
//! `P(omega < -5)` estimate, the count of divergent transitions (a
//! divergence, refinement exhaustion or invalid evaluation), the deepest
//! `omega` reached and the mean evaluations per transition, all computed over
//! the full 20,000-transition run, and, for a window of `replay_transitions`
//! consecutive transitions starting at `meta.replay_start` (the same window
//! for every arm, chosen as the multiple of 50 that maximizes the number of
//! WALNUTS draws below `omega = -5` inside it), every recorded target
//! evaluation as
//! `[omega, x1, level, direction]` in evaluation order. Coordinates that are
//! not finite are written as `null` so a divergence stays visible. When the
//! full record would exceed the file-size ceiling, level-0 points are thinned
//! by a uniform stride (all refined points are kept) and the transition is
//! flagged `thinned`. Floats carry three decimals. This is a visualization,
//! not evidence: one chain, one fixed seed, per arm.

use std::error::Error;
use std::fs;
use std::num::NonZeroUsize;
use std::ops::Range;
use std::path::PathBuf;
use std::sync::Mutex;

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, ProposalDirection, ProposalObservation,
    ProposalObservationControl, ProposalObserver, RunConfig, RunControl, StopReason, Target,
    TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
    sample_chains_with_target_budget_and_control,
};
use serde_json::{Map, Value, json};

const DIMENSION: usize = 10;
/// Exact `P(omega < -5)` for `omega ~ Normal(0, 3)`.
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const MAX_DEPTH: usize = 10;
const MIN_MICRO_STEPS: usize = 1;
/// All arms of the paper reproduction study run with this divergence threshold.
const DIVERGENCE_THRESHOLD: f64 = 1000.0;
const SEED: u64 = 0x0f0f_2028;
const DISCARDED: usize = 0;
/// Transitions run (and summarized) per arm.
const RETAINED: usize = 20_000;
/// Retained draws written to the JSON, from the start of the chain.
const DRAWS_KEPT: usize = 2_000;
/// Preferred number of replayed transitions per arm.
const PREFERRED_REPLAY: usize = 300;
/// The replay window starts at a multiple of this many transitions.
const WINDOW_STRIDE: usize = 50;
/// Ceiling on the serialized file size, in bytes.
const SIZE_CEILING: usize = 900_000;

struct Arm {
    key: &'static str,
    label: &'static str,
    step_size: f64,
    max_error: f64,
    levels: usize,
}

const ARMS: [Arm; 3] = [
    Arm {
        key: "walnuts",
        label: "WALNUTS (h = 0.36, refines to h/1024)",
        step_size: 0.36,
        max_error: 0.21,
        levels: 10,
    },
    Arm {
        key: "nuts_h011",
        label: "NUTS (h = 0.11, no refinement)",
        step_size: 0.11,
        max_error: 1000.0,
        levels: 1,
    },
    Arm {
        key: "nuts_h036",
        label: "NUTS (h = 0.36, no refinement)",
        step_size: 0.36,
        max_error: 0.21,
        levels: 1,
    },
];

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            // Far below the neck the density is numerically zero; the kernel
            // refines through this region exactly as the upstream reference.
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

/// One recorded fused target evaluation.
#[derive(Clone, Copy, Debug)]
struct Event {
    transition: usize,
    direction: i8,
    level: usize,
    omega: f64,
    x1: f64,
}

#[derive(Default)]
struct Recorder(Mutex<Vec<Event>>);

impl ProposalObserver for Recorder {
    fn observe(&self, observation: &ProposalObservation) {
        let coordinates = observation.coordinates();
        let event = Event {
            transition: observation.transition(),
            direction: match observation.direction() {
                Some(ProposalDirection::Forward) => 1,
                Some(ProposalDirection::Backward) => -1,
                None => 0,
            },
            level: observation.refinement_level().unwrap_or(0),
            omega: coordinates.first().copied().unwrap_or(f64::NAN),
            x1: coordinates.get(1).copied().unwrap_or(f64::NAN),
        };
        self.0.lock().expect("recorder poisoned").push(event);
    }
}

/// Per-transition summary derived from diagnostics and events.
#[derive(Clone, Debug)]
struct Summary {
    index: usize,
    start: [f64; 2],
    accepted: [f64; 2],
    depth: usize,
    evals: usize,
    stop: StopReason,
    divergent: bool,
    max_level: usize,
    events: Range<usize>,
}

/// Divergence-like counts over all retained transitions.
#[derive(Clone, Copy, Debug, Default)]
struct DivergenceKinds {
    divergences: usize,
    refinement_exhausted: usize,
    invalid_evaluation: usize,
    any: usize,
}

struct ArmResult {
    draws: Vec<[f64; 2]>,
    summaries: Vec<Summary>,
    events: Vec<Event>,
    kinds: DivergenceKinds,
    mean_evals: f64,
}

impl ArmResult {
    fn count_below_minus5(&self) -> usize {
        self.draws.iter().filter(|d| d[0] < -5.0).count()
    }

    fn deepest_omega(&self) -> f64 {
        self.draws
            .iter()
            .map(|d| d[0])
            .fold(f64::INFINITY, f64::min)
    }
}

fn round3(value: f64) -> f64 {
    (value * 1e3).round() / 1e3
}

fn number(value: f64) -> Value {
    if value.is_finite() {
        json!(round3(value))
    } else {
        Value::Null
    }
}

fn stop_name(stop: StopReason) -> &'static str {
    match stop {
        StopReason::MaximumDepth => "maximum_depth",
        StopReason::OuterUTurn => "outer_uturn",
        StopReason::RecursiveUTurn => "recursive_uturn",
        StopReason::RefinementExhausted => "refinement_exhausted",
        StopReason::ReverseCoarserAccepted => "reverse_coarser_accepted",
        StopReason::InvalidEvaluation => "invalid_evaluation",
        _ => "other",
    }
}

fn run_arm(arm: &Arm) -> Result<ArmResult, Box<dyn Error>> {
    let nz = |value: usize| NonZeroUsize::new(value).expect("nonzero");

    let tuning = KernelTuning::new(
        arm.step_size,
        nz(MAX_DEPTH),
        nz(MIN_MICRO_STEPS),
        nz(arm.levels),
        arm.max_error,
    )?
    .with_divergence_threshold(DIVERGENCE_THRESHOLD)?;
    let config = RunConfig::new(DISCARDED, nz(RETAINED), SEED).with_tuning(tuning);
    let starts = vec![vec![0.0; DIMENSION]];
    let chains = nz(1);
    let mass = DiagonalMass::identity(nz(DIMENSION));

    // Deep refinement with deep trees exceeds the conservative admission
    // ceiling, so admit through the exact worst-case evaluation count.
    let worst_case = config.worst_case_target_evaluations(chains)?;
    let budget = TargetEvaluationBudget::new(nz(worst_case));
    let recorder = Recorder::default();
    let observations = ProposalObservationControl::new(&recorder, nz(worst_case), 2);
    let control = RunControl::new().with_proposal_observations(&observations);
    let output = sample_chains_with_target_budget_and_control(
        &Funnel,
        &starts,
        &mass,
        &config,
        chains,
        TargetEvaluationAdmissionLimit::new(nz(worst_case)),
        &budget,
        &control,
    )?;
    let chain = &output.chains()[0];
    let events = recorder.0.into_inner().expect("recorder poisoned");

    // Observations are ordered within the chain, so each transition occupies
    // one contiguous range of the event vector.
    let mut ranges: Vec<Range<usize>> = vec![0..0; RETAINED];
    let mut position = 0;
    while position < events.len() {
        let transition = events[position].transition;
        let start = position;
        while position < events.len() && events[position].transition == transition {
            position += 1;
        }
        if transition < RETAINED {
            ranges[transition] = start..position;
        }
    }

    let draws: Vec<[f64; 2]> = (0..RETAINED)
        .map(|index| {
            let sample = chain.sample(index).expect("retained draw");
            [sample[0], sample[1]]
        })
        .collect();
    let mut kinds = DivergenceKinds::default();
    let mut summaries: Vec<Summary> = Vec::with_capacity(RETAINED);
    for index in 0..RETAINED {
        let diagnostics = &chain.diagnostics()[index];
        let range = ranges[index].clone();
        let slice = &events[range.clone()];
        // Nothing is discarded, so transition 0 starts at the origin and
        // transition `i` starts at retained draw `i - 1`.
        let start = if index == 0 {
            [0.0, 0.0]
        } else {
            draws[index - 1]
        };
        let stop = diagnostics.stop();
        let exhausted = stop == StopReason::RefinementExhausted;
        let invalid = stop == StopReason::InvalidEvaluation;
        let divergent = diagnostics.divergent() || exhausted || invalid;
        kinds.divergences += usize::from(diagnostics.divergent());
        kinds.refinement_exhausted += usize::from(exhausted);
        kinds.invalid_evaluation += usize::from(invalid);
        kinds.any += usize::from(divergent);
        summaries.push(Summary {
            index,
            start,
            accepted: draws[index],
            depth: diagnostics.depth(),
            evals: diagnostics.target_evaluations(),
            stop,
            divergent,
            max_level: slice.iter().map(|e| e.level).max().unwrap_or(0),
            events: range,
        });
    }
    let mean_evals = summaries.iter().map(|s| s.evals).sum::<usize>() as f64 / RETAINED as f64;
    Ok(ArmResult {
        draws,
        summaries,
        events,
        kinds,
        mean_evals,
    })
}

/// Keep every refined (level >= 1) event and every `stride`-th level-0 event.
fn thin(events: &[Event], stride: usize) -> Vec<Event> {
    events
        .iter()
        .enumerate()
        .filter(|(k, e)| e.level >= 1 || k % stride == 0)
        .map(|(_, e)| *e)
        .collect()
}

fn transition_json(summary: &Summary, events: &[Event], stride: usize) -> Value {
    let kept = thin(events, stride);
    let thinned = kept.len() < events.len();
    let points: Vec<Value> = kept
        .iter()
        .map(|e| json!([number(e.omega), number(e.x1), e.level, e.direction]))
        .collect();
    json!({
        "i": summary.index,
        "start": [number(summary.start[0]), number(summary.start[1])],
        "accepted": [number(summary.accepted[0]), number(summary.accepted[1])],
        "depth": summary.depth,
        "evals": summary.evals,
        "max_level": summary.max_level,
        "stop": stop_name(summary.stop),
        "divergent": summary.divergent,
        "thinned": thinned,
        "points": points,
    })
}

fn arm_json(arm: &Arm, result: &ArmResult, window: Range<usize>, stride: usize) -> Value {
    let draws: Vec<Value> = result
        .draws
        .iter()
        .take(DRAWS_KEPT)
        .map(|d| json!([number(d[0]), number(d[1])]))
        .collect();
    let below = result.count_below_minus5();
    let window_below = result.draws[window.clone()]
        .iter()
        .filter(|d| d[0] < -5.0)
        .count();
    let window_divergent = result.summaries[window.clone()]
        .iter()
        .filter(|s| s.divergent)
        .count();
    let transitions: Vec<Value> = result.summaries[window]
        .iter()
        .map(|s| transition_json(s, &result.events[s.events.clone()], stride))
        .collect();
    json!({
        "label": arm.label,
        "h": arm.step_size,
        "delta": arm.max_error,
        "levels": arm.levels,
        "draws": draws,
        "tail_mass": {
            "estimate": number(below as f64 / RETAINED as f64),
            "count_below_minus5": below,
        },
        "deepest_omega": number(result.deepest_omega()),
        "divergent_transitions": result.kinds.any,
        "divergence_kinds": {
            "divergence": result.kinds.divergences,
            "refinement_exhausted": result.kinds.refinement_exhausted,
            "invalid_evaluation": result.kinds.invalid_evaluation,
        },
        "mean_evals_per_transition": number(result.mean_evals),
        "window_below_minus5": window_below,
        "window_divergent": window_divergent,
        "transitions": transitions,
    })
}

fn document(results: &[ArmResult], window: Range<usize>, stride: usize) -> Value {
    let mut arms = Map::new();
    for (arm, result) in ARMS.iter().zip(results) {
        arms.insert(
            arm.key.to_string(),
            arm_json(arm, result, window.clone(), stride),
        );
    }
    json!({
        "meta": {
            "seed": SEED,
            "retained": DRAWS_KEPT,
            "full_run_retained": RETAINED,
            "replay_start": window.start,
            "replay_transitions": window.len(),
            "level0_stride": stride,
            "exact_tail_mass": number(EXACT_TAIL_MASS),
            "algorithm_revision": ALGORITHM_REVISION,
            "point_columns": ["omega", "x1", "level", "direction"],
        },
        "arms": Value::Object(arms),
    })
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut results = Vec::with_capacity(ARMS.len());
    for arm in &ARMS {
        let result = run_arm(arm)?;
        let below = result.count_below_minus5();
        println!(
            "{}: tail mass {:.4} (exact {EXACT_TAIL_MASS:.4}), {below} of {RETAINED} draws \
             below -5; deepest omega {:+.3}; divergent transitions {} (divergence {}, \
             refinement exhausted {}, invalid evaluation {}); mean evals/transition {:.1}; \
             observations {}",
            arm.key,
            below as f64 / RETAINED as f64,
            result.deepest_omega(),
            result.kinds.any,
            result.kinds.divergences,
            result.kinds.refinement_exhausted,
            result.kinds.invalid_evaluation,
            result.mean_evals,
            result.events.len(),
        );
        results.push(result);
    }

    // Replay window: the same slice for every arm, starting at the multiple
    // of 50 that maximizes the number of WALNUTS draws below omega = -5
    // inside it (earliest start on ties), so the replay shows the neck.
    let walnuts = ARMS
        .iter()
        .position(|arm| arm.key == "walnuts")
        .expect("walnuts arm");
    let neck_hits = |start: usize| {
        results[walnuts].draws[start..start + PREFERRED_REPLAY]
            .iter()
            .filter(|d| d[0] < -5.0)
            .count()
    };
    let replay_start = (0..=RETAINED - PREFERRED_REPLAY)
        .step_by(WINDOW_STRIDE)
        .fold(0, |best, start| {
            if neck_hits(start) > neck_hits(best) {
                start
            } else {
                best
            }
        });

    // Prefer the full 300-transition window; thin level-0 points by stride
    // 2 then 3 before shortening the window (its start is kept).
    let mut candidates: Vec<(usize, usize)> =
        (1..=3).map(|stride| (PREFERRED_REPLAY, stride)).collect();
    candidates.extend(
        [250, 200, 150, 100, 75, 50, 30, 20, 10]
            .into_iter()
            .map(|replay| (replay, 3)),
    );
    let mut chosen = None;
    for (replay, stride) in candidates {
        let window = replay_start..replay_start + replay;
        let text = serde_json::to_string(&document(&results, window, stride))?;
        if text.len() <= SIZE_CEILING {
            chosen = Some((replay, stride, text));
            break;
        }
    }
    let (replay, stride, text) = chosen.ok_or("no replay length fits the size ceiling")?;
    for (arm, result) in ARMS.iter().zip(&results) {
        let window = replay_start..replay_start + replay;
        println!(
            "{} window [{replay_start}, {}): {} draws below -5, {} divergent transitions",
            arm.key,
            window.end,
            result.draws[window.clone()]
                .iter()
                .filter(|d| d[0] < -5.0)
                .count(),
            result.summaries[window.clone()]
                .iter()
                .filter(|s| s.divergent)
                .count(),
        );
    }

    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("demo")
        .join("data")
        .join("funnel-replay.json");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(&path, &text)?;
    println!(
        "replayed {replay} transitions per arm from transition {replay_start} (level-0 stride \
         {stride}); wrote {} ({} bytes; revision {ALGORITHM_REVISION})",
        path.display(),
        text.len()
    );
    Ok(())
}
