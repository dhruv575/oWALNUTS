//! Trace WALNUTS' within-orbit step refinement on Neal's 10-D funnel and
//! write `demo/data/funnel-orbit.json` for the web visualization.
//!
//! The target is the paper's funnel (`omega ~ Normal(0, 3)`,
//! `x_i | omega ~ Normal(0, exp(omega))` for nine `x_i`), sampled with the
//! paper's fixed tuning (`h = 0.36`, `delta = 0.21`, ten refinement levels,
//! trees up to depth ten, identity mass, no warmup adaptation), exactly as arm
//! F of `STUDIES/paper_funnel_reproduction_v1`. One chain starts at the origin.
//!
//! A [`ProposalObserver`] records every fused target evaluation: the
//! transition it belongs to, the integration direction, the refinement level
//! (leapfrog steps at level `l` are `h / 2^l` long), the energy error and the
//! `(omega, x_1)` coordinate prefix. The JSON bundles the retained draws, a
//! compact per-transition summary (depth, target evaluations, deepest
//! refinement level, most negative `omega` visited) and four featured
//! transitions with their evaluation sequences, chosen to show steps
//! shrinking as an orbit descends into the neck and coarsening as it climbs
//! back out.
//!
//! Deep refinement with deep trees exceeds the conservative admission ceiling,
//! so the run is admitted through `sample_chains_with_target_budget_and_control`
//! with the exact worst-case target-evaluation count as its limit. This is a
//! visualization, not evidence: one chain, one fixed seed.

use std::collections::BTreeMap;
use std::error::Error;
use std::fs;
use std::num::NonZeroUsize;
use std::ops::Range;
use std::path::PathBuf;
use std::sync::Mutex;

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, ProposalDirection, ProposalObservation,
    ProposalObservationControl, ProposalObserver, ProposalTargetOutcome, RunConfig, RunControl,
    StopReason, Target, TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget,
    sample_chains_with_target_budget_and_control,
};
use serde_json::{Value, json};

const DIMENSION: usize = 10;
/// Exact `P(omega < -5)` for `omega ~ Normal(0, 3)`.
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const STEP_SIZE: f64 = 0.36;
const MAX_ERROR: f64 = 0.21;
const MAX_DEPTH: usize = 10;
const MIN_MICRO_STEPS: usize = 1;
const REFINEMENT_LEVELS: usize = 10;
/// Arm F of the paper reproduction study runs with this divergence threshold.
const DIVERGENCE_THRESHOLD: f64 = 1000.0;
const SEED: u64 = 0x0f0f_2027;
const DISCARDED: usize = 200;
const RETAINED: usize = 2_000;
/// Maximum evaluation points kept per featured transition.
const FEATURED_POINT_CAP: usize = 1_500;
/// Batch length for the batch-means standard error of the tail mass.
const TAIL_BATCH: usize = 100;

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

/// One recorded fused target evaluation, kept compact because a run produces
/// millions of them.
#[derive(Clone, Copy, Debug)]
struct Event {
    transition: usize,
    discarded: bool,
    direction: i8,
    level: usize,
    omega: f64,
    x1: f64,
    delta_h: Option<f64>,
    outcome: ProposalTargetOutcome,
}

#[derive(Default)]
struct Recorder(Mutex<Vec<Event>>);

impl ProposalObserver for Recorder {
    fn observe(&self, observation: &ProposalObservation) {
        let coordinates = observation.coordinates();
        let event = Event {
            transition: observation.transition(),
            discarded: observation.is_discarded(),
            direction: match observation.direction() {
                Some(ProposalDirection::Forward) => 1,
                Some(ProposalDirection::Backward) => -1,
                None => 0,
            },
            level: observation.refinement_level().unwrap_or(0),
            omega: coordinates.first().copied().unwrap_or(f64::NAN),
            x1: coordinates.get(1).copied().unwrap_or(f64::NAN),
            delta_h: observation.delta_h().filter(|x| x.is_finite()),
            outcome: observation.outcome(),
        };
        self.0.lock().expect("recorder poisoned").push(event);
    }
}

/// Per-retained-transition summary derived from diagnostics and events.
#[derive(Clone, Debug)]
struct Summary {
    /// Global transition index (discarded transitions come first).
    index: usize,
    start: [f64; 2],
    accepted: [f64; 2],
    depth: usize,
    evals: usize,
    stop: StopReason,
    max_level: usize,
    min_omega_visited: f64,
    /// Range of positions in the event vector belonging to this transition.
    events: Range<usize>,
}

fn round4(value: f64) -> f64 {
    (value * 1e4).round() / 1e4
}

fn number(value: f64) -> Value {
    if value.is_finite() {
        json!(round4(value))
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

fn outcome_name(outcome: ProposalTargetOutcome) -> &'static str {
    match outcome {
        ProposalTargetOutcome::Finite => "finite",
        ProposalTargetOutcome::Recoverable => "recoverable",
        ProposalTargetOutcome::Fatal => "fatal",
        ProposalTargetOutcome::Nonfinite => "nonfinite",
        ProposalTargetOutcome::Panicked => "panicked",
        ProposalTargetOutcome::KernelNonfinite => "kernel_nonfinite",
    }
}

/// Keep every event when the transition is short; otherwise keep every
/// refined (level >= 1) event plus a uniform stride of the coarse ones, and
/// thin uniformly once more if that still exceeds the cap.
fn thin(events: &[Event]) -> Vec<(usize, Event)> {
    let indexed: Vec<(usize, Event)> = events.iter().copied().enumerate().collect();
    if indexed.len() <= FEATURED_POINT_CAP {
        return indexed;
    }
    let coarse = indexed.iter().filter(|(_, e)| e.level == 0).count();
    let refined = indexed.len() - coarse;
    let coarse_budget = FEATURED_POINT_CAP
        .saturating_sub(refined)
        .max(FEATURED_POINT_CAP / 4);
    let stride = coarse.div_ceil(coarse_budget).max(1);
    let mut kept: Vec<(usize, Event)> = indexed
        .iter()
        .filter(|(k, e)| e.level >= 1 || k % stride == 0)
        .copied()
        .collect();
    if kept.len() > FEATURED_POINT_CAP {
        let stride = kept.len().div_ceil(FEATURED_POINT_CAP);
        kept = kept
            .into_iter()
            .enumerate()
            .filter(|(position, _)| position % stride == 0)
            .map(|(_, item)| item)
            .collect();
    }
    kept
}

fn featured_json(summary: &Summary, events: &[Event]) -> Value {
    let points: Vec<Value> = thin(events)
        .into_iter()
        .map(|(k, e)| {
            json!([
                number(e.omega),
                number(e.x1),
                e.level,
                e.direction,
                e.delta_h.map_or(Value::Null, number),
                k,
            ])
        })
        .collect();
    json!({
        "i": summary.index,
        "start": [number(summary.start[0]), number(summary.start[1])],
        "accepted": [number(summary.accepted[0]), number(summary.accepted[1])],
        "depth": summary.depth,
        "evals": summary.evals,
        "stop": stop_name(summary.stop),
        "max_level": summary.max_level,
        "min_omega_visited": number(summary.min_omega_visited),
        "total_points": events.len(),
        "points": points,
    })
}

fn main() -> Result<(), Box<dyn Error>> {
    let nz = |value: usize| NonZeroUsize::new(value).expect("nonzero");

    let tuning = KernelTuning::new(
        STEP_SIZE,
        nz(MAX_DEPTH),
        nz(MIN_MICRO_STEPS),
        nz(REFINEMENT_LEVELS),
        MAX_ERROR,
    )?
    .with_divergence_threshold(DIVERGENCE_THRESHOLD)?;
    let config = RunConfig::new(DISCARDED, nz(RETAINED), SEED).with_tuning(tuning);
    let starts = vec![vec![0.0; DIMENSION]];
    let chains = nz(1);
    let mass = DiagonalMass::identity(nz(DIMENSION));

    let worst_case = config.worst_case_target_evaluations(chains)?;
    let budget = TargetEvaluationBudget::new(nz(worst_case));
    let recorder = Recorder::default();
    // Every fused evaluation is one observation, so the exact worst case is
    // also an exact observation ceiling; request the (omega, x_1) prefix.
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
    println!(
        "recorded {} observations over {} transitions ({} target calls)",
        events.len(),
        chain.diagnostics().len(),
        chain.telemetry().total().target_calls_total(),
    );

    // Group events by transition. Observations are ordered within the chain,
    // so each transition occupies one contiguous range.
    let transitions = DISCARDED + RETAINED;
    let mut ranges: Vec<Range<usize>> = vec![0..0; transitions];
    {
        let mut position = 0;
        while position < events.len() {
            let transition = events[position].transition;
            let start = position;
            while position < events.len() && events[position].transition == transition {
                position += 1;
            }
            if transition < transitions {
                ranges[transition] = start..position;
            }
        }
    }
    debug_assert!(
        events
            .iter()
            .all(|e| e.discarded == (e.transition < DISCARDED))
    );

    let draw = |index: usize| -> [f64; 2] {
        let sample = chain.sample(index).expect("retained draw");
        [sample[0], sample[1]]
    };
    let mut summaries: Vec<Summary> = Vec::with_capacity(RETAINED);
    for retained_index in 0..RETAINED {
        let index = DISCARDED + retained_index;
        let diagnostics = &chain.diagnostics()[index];
        let range = ranges[index].clone();
        let slice = &events[range.clone()];
        let start = if retained_index == 0 {
            // The first retained transition starts at the last discarded
            // state, which is not a retained draw; use its initial evaluation.
            slice
                .first()
                .map_or([f64::NAN, f64::NAN], |e| [e.omega, e.x1])
        } else {
            draw(retained_index - 1)
        };
        summaries.push(Summary {
            index,
            start,
            accepted: draw(retained_index),
            depth: diagnostics.depth(),
            evals: diagnostics.target_evaluations(),
            stop: diagnostics.stop(),
            max_level: slice.iter().map(|e| e.level).max().unwrap_or(0),
            min_omega_visited: slice
                .iter()
                .map(|e| e.omega)
                .filter(|x| x.is_finite())
                .fold(f64::INFINITY, f64::min),
            events: range,
        });
    }

    // Featured transitions. Each is chosen among retained transitions with a
    // known start (retained index >= 1) and distinct from earlier picks.
    let candidates = || summaries.iter().skip(1);
    let mut featured: Vec<&Summary> = Vec::new();
    let unused = |featured: &[&Summary], s: &Summary| featured.iter().all(|f| f.index != s.index);

    // (a) Deepest neck excursion that refined through at least two levels.
    if let Some(a) = candidates()
        .filter(|s| s.max_level >= 2)
        .min_by(|x, y| x.min_omega_visited.total_cmp(&y.min_omega_visited))
    {
        featured.push(a);
    }
    // (b) Another deep-neck excursion from a clearly different start.
    if let Some(b) = candidates()
        .filter(|s| s.max_level >= 1 && unused(&featured, s))
        .filter(|s| {
            featured
                .iter()
                .all(|f| (f.start[0] - s.start[0]).abs() > 1.0)
        })
        .min_by(|x, y| x.min_omega_visited.total_cmp(&y.min_omega_visited))
    {
        featured.push(b);
    }
    // (c) A typical mouth transition: level 0 only, start and end near
    // omega = 0, with median evaluation count among such transitions.
    {
        let mut typical: Vec<&Summary> = candidates()
            .filter(|s| s.max_level == 0 && unused(&featured, s))
            .filter(|s| s.start[0].abs() < 1.0 && s.accepted[0].abs() < 1.5)
            .collect();
        typical.sort_by_key(|s| s.evals);
        if let Some(c) = typical.get(typical.len() / 2) {
            featured.push(c);
        }
    }
    // (d) Starts in the neck and climbs out: largest rise from a start below
    // omega = -4.
    if let Some(d) = candidates()
        .filter(|s| s.start[0] < -4.0 && unused(&featured, s))
        .max_by(|x, y| (x.accepted[0] - x.start[0]).total_cmp(&(y.accepted[0] - y.start[0])))
    {
        featured.push(d);
    }

    // Summary statistics.
    let below = (0..RETAINED).filter(|&i| draw(i)[0] < -5.0).count();
    let tail_estimate = below as f64 / RETAINED as f64;
    // Batch means over blocks of retained draws give an autocorrelation-aware
    // standard error; neck sojourns make a single short chain very sticky.
    let batch_means: Vec<f64> = (0..RETAINED / TAIL_BATCH)
        .map(|batch| {
            let hits = (batch * TAIL_BATCH..(batch + 1) * TAIL_BATCH)
                .filter(|&i| draw(i)[0] < -5.0)
                .count();
            hits as f64 / TAIL_BATCH as f64
        })
        .collect();
    let batches = batch_means.len() as f64;
    let tail_standard_error = (batch_means
        .iter()
        .map(|mean| (mean - tail_estimate).powi(2))
        .sum::<f64>()
        / (batches - 1.0)
        / batches)
        .sqrt();
    let refined = summaries.iter().filter(|s| s.max_level >= 1).count();
    let refined_fraction = refined as f64 / RETAINED as f64;
    let mut level_histogram = vec![0usize; REFINEMENT_LEVELS + 1];
    for s in &summaries {
        level_histogram[s.max_level.min(REFINEMENT_LEVELS)] += 1;
    }
    let mut outcomes: BTreeMap<&str, usize> = BTreeMap::new();
    for e in &events[ranges[DISCARDED].start..] {
        *outcomes.entry(outcome_name(e.outcome)).or_insert(0) += 1;
    }

    let draws: Vec<Value> = (0..RETAINED)
        .map(|i| {
            let d = draw(i);
            json!([number(d[0]), number(d[1])])
        })
        .collect();
    let transitions_json: Vec<Value> = summaries
        .iter()
        .map(|s| {
            json!({
                "i": s.index,
                "omega": number(s.accepted[0]),
                "depth": s.depth,
                "evals": s.evals,
                "max_level": s.max_level,
                "min_omega_visited": number(s.min_omega_visited),
            })
        })
        .collect();
    let featured_json: Vec<Value> = featured
        .iter()
        .map(|s| featured_json(s, &events[s.events.clone()]))
        .collect();
    let document = json!({
        "meta": {
            "tuning": {
                "h": STEP_SIZE,
                "delta": MAX_ERROR,
                "levels": REFINEMENT_LEVELS,
                "depth": MAX_DEPTH,
                "min_micro_steps": MIN_MICRO_STEPS,
                "divergence_threshold": DIVERGENCE_THRESHOLD,
            },
            "seed": SEED,
            "discarded": DISCARDED,
            "retained": RETAINED,
            "dimension": DIMENSION,
            "start_omega": 0.0,
            // Transition indices `i` count from the first discarded transition,
            // so retained draw `j` is produced by transition `i = discarded + j`.
            "first_retained_transition": DISCARDED,
            "algorithm_revision": ALGORITHM_REVISION,
            "tail_mass": {
                "threshold": -5.0,
                "estimate": number(tail_estimate),
                "batch_means_standard_error": number(tail_standard_error),
                "exact": number(EXACT_TAIL_MASS),
            },
            "refined_fraction": number(refined_fraction),
            "max_level_histogram": level_histogram,
            "retained_outcomes": outcomes,
            "point_columns": ["omega", "x1", "level", "direction", "delta_h", "k"],
        },
        "draws": draws,
        "transitions": transitions_json,
        "featured": featured_json,
    });

    let path = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("demo")
        .join("data")
        .join("funnel-orbit.json");
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    let text = serde_json::to_string(&document)?;
    fs::write(&path, &text)?;

    println!(
        "P(omega < -5): estimate {tail_estimate:.4} vs exact {EXACT_TAIL_MASS:.4} \
         (batch-means s.e. {tail_standard_error:.4}, z = {:+.2}, {RETAINED} draws; \
         revision {ALGORITHM_REVISION})",
        (tail_estimate - EXACT_TAIL_MASS) / tail_standard_error,
    );
    println!(
        "transitions that refined (max level >= 1): {refined}/{RETAINED} = {refined_fraction:.3}; \
         max-level histogram {level_histogram:?}"
    );
    for (label, s) in ["a", "b", "c", "d"].iter().zip(&featured) {
        println!(
            "featured ({label}): transition {} start omega {:+.3} -> accepted {:+.3}, depth {}, \
             evals {}, max level {}, min omega visited {:+.3}, stop {}, points {}",
            s.index,
            s.start[0],
            s.accepted[0],
            s.depth,
            s.evals,
            s.max_level,
            s.min_omega_visited,
            stop_name(s.stop),
            s.events.len(),
        );
    }
    println!("wrote {} ({} bytes)", path.display(), text.len());
    Ok(())
}
