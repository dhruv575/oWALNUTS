//! WP38 one-shot cell: `nonfinite-position-policy-v1 <manifest.json> <ordinal> <record.json>`.
//!
//! Runs one (target, seed, arm) cell of `protocol.json` with the research-only
//! `NonfinitePositionPolicy` opt-in and writes one JSON record. The arm is the
//! only difference between paired cells; everything else is the frozen common
//! configuration. A cell that fails inside the sampler still exits 0 and
//! records the error kind and message; only a harness failure exits nonzero.
#[path = "../../sspd11_confirmation_v1/primary/src/canonical.rs"]
#[allow(dead_code)]
mod canonical;

use canonical::{CenteredTarget, Data, from_innovations};
use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{
    Adaptation, Limits, Metric, NonfinitePositionPolicy, Posterior, Sampler, Target, Tuning,
    uniform_starts,
};
use owalnuts::walnutpie::{TargetError, TargetErrorKind};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::error::Error;
use std::fs;
use std::path::Path;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

const CHAINS: usize = 4;
const FUNNEL_DIMENSION: usize = 10;
const GAUSSIAN_DIMENSION: usize = 100;

#[derive(Deserialize)]
struct Manifest {
    cells: Vec<Cell>,
}

#[derive(Clone, Deserialize)]
struct Cell {
    ordinal: usize,
    id: String,
    target: String,
    seed: u64,
    arm: String,
    warmup: usize,
    retained: usize,
    initial_step: f64,
    monitored_coordinates: Vec<usize>,
}

#[derive(Serialize)]
struct Functional {
    coordinate: usize,
    rhat: f64,
    ess_bulk: f64,
    ess_tail: f64,
    mean: f64,
}

#[derive(Serialize)]
struct Record {
    schema: &'static str,
    ordinal: usize,
    id: String,
    target: String,
    seed: u64,
    arm: String,
    status: String,
    error_kind: Option<String>,
    error_message: Option<String>,
    wall_seconds: f64,
    total_target_calls: Option<usize>,
    recoverable_target_failures: Option<usize>,
    fatal_reclassified: usize,
    nonfinite_position_rejections_discarded: Option<usize>,
    nonfinite_position_rejections_retained: Option<usize>,
    nonfinite_position_rejections_by_phase: Option<[usize; 3]>,
    retained_divergences: Option<usize>,
    draw_hash_sha256: Option<String>,
    functionals: Vec<Functional>,
    funnel_tail_mass: Option<f64>,
    algorithm_revision: Option<String>,
}

/// The frozen state-space target with every fatal-classified result
/// reclassified as recoverable (the diagnostic's `repair` arm).
struct RepairedStateSpace {
    inner: CenteredTarget,
    reclassified: AtomicUsize,
}

impl Target for RepairedStateSpace {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        match self.inner.log_density_gradient(position, gradient) {
            Err(error) if error.kind() != TargetErrorKind::Recoverable => {
                self.reclassified.fetch_add(1, Ordering::Relaxed);
                Err(TargetError::recoverable(error.message().to_owned()))
            }
            other => other,
        }
    }
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
        let value = -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() {
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
    StateSpace(RepairedStateSpace),
    Funnel(Funnel),
    Gaussian(Gaussian),
}

impl Target for StudyTarget {
    fn dimension(&self) -> usize {
        match self {
            Self::StateSpace(t) => t.dimension(),
            Self::Funnel(t) => t.dimension(),
            Self::Gaussian(t) => t.dimension(),
        }
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        match self {
            Self::StateSpace(t) => t.log_density_gradient(position, gradient),
            Self::Funnel(t) => t.log_density_gradient(position, gradient),
            Self::Gaussian(t) => t.log_density_gradient(position, gradient),
        }
    }
}

fn numbers(value: &Value) -> Result<Vec<f64>, Box<dyn Error>> {
    value
        .as_array()
        .ok_or("expected an array")?
        .iter()
        .map(|item| item.as_f64().ok_or_else(|| "expected a number".into()))
        .collect()
}

fn build_target(cell: &Cell) -> Result<(StudyTarget, Vec<Vec<f64>>), Box<dyn Error>> {
    let manifest_root = Path::new(env!("CARGO_MANIFEST_DIR"));
    match cell.target.as_str() {
        "sspd_repaired" => {
            let fixture: Value = serde_json::from_slice(&fs::read(
                manifest_root.join("../reverse_coarsening_order_v1/config/sspd-target-fixture.json"),
            )?)?;
            let data = Data::try_from_raw(
                &numbers(&fixture["data"]["y"])?,
                &numbers(&fixture["data"]["s"])?,
                &numbers(&fixture["data"]["v"])?,
            )?;
            let starts: Value = serde_json::from_slice(&fs::read(
                manifest_root.join("../sspd11_confirmation_v1/primary/starts/sspd-11.json"),
            )?)?;
            let starts = starts["starts"]
                .as_array()
                .ok_or("starts must be an array")?
                .iter()
                .map(numbers)
                .collect::<Result<Vec<_>, _>>()?
                .into_iter()
                .map(|start| from_innovations(&start, 1.0))
                .collect();
            Ok((
                StudyTarget::StateSpace(RepairedStateSpace {
                    inner: CenteredTarget {
                        data,
                        a: 1.0,
                        calls: AtomicUsize::new(0),
                    },
                    reclassified: AtomicUsize::new(0),
                }),
                starts,
            ))
        }
        "neal_funnel_10d" => {
            let starts = [-3.0, -1.0, 1.0, 3.0]
                .into_iter()
                .map(|omega| {
                    let mut start = vec![0.0; FUNNEL_DIMENSION];
                    start[0] = omega;
                    start
                })
                .collect();
            Ok((StudyTarget::Funnel(Funnel), starts))
        }
        "gaussian_100d" => {
            let starts = uniform_starts(&Gaussian, CHAINS, cell.seed, 2.0, 100)?;
            Ok((StudyTarget::Gaussian(Gaussian), starts))
        }
        other => Err(format!("unknown target {other}").into()),
    }
}

fn policy(arm: &str) -> Result<NonfinitePositionPolicy, Box<dyn Error>> {
    match arm {
        "abort" => Ok(NonfinitePositionPolicy::Abort),
        "reject" => Ok(NonfinitePositionPolicy::RejectLeaf),
        other => Err(format!("unknown arm {other}").into()),
    }
}

fn draw_hash(posterior: &Posterior) -> String {
    let mut hasher = Sha256::new();
    for chain in 0..posterior.chain_count() {
        for value in posterior.chain_draws(chain).unwrap_or(&[]) {
            hasher.update(value.to_bits().to_le_bytes());
        }
    }
    format!("{:x}", hasher.finalize())
}

fn functionals(posterior: &Posterior, coordinates: &[usize]) -> Vec<Functional> {
    let dimension = posterior.dimension();
    coordinates
        .iter()
        .map(|&coordinate| {
            let series: Vec<Vec<f64>> = (0..posterior.chain_count())
                .map(|chain| {
                    posterior
                        .chain_draws(chain)
                        .unwrap_or(&[])
                        .chunks(dimension)
                        .map(|draw| draw[coordinate])
                        .collect()
                })
                .collect();
            let views: Vec<&[f64]> = series.iter().map(Vec::as_slice).collect();
            let count: usize = views.iter().map(|s| s.len()).sum();
            let mean = views.iter().flat_map(|s| s.iter()).sum::<f64>() / count as f64;
            Functional {
                coordinate,
                rhat: rhat(&views),
                ess_bulk: ess_bulk(&views),
                ess_tail: ess_tail(&views),
                mean,
            }
        })
        .collect()
}

fn funnel_tail_mass(posterior: &Posterior) -> f64 {
    let dimension = posterior.dimension();
    let mut below = 0usize;
    let mut total = 0usize;
    for chain in 0..posterior.chain_count() {
        for draw in posterior.chain_draws(chain).unwrap_or(&[]).chunks(dimension) {
            total += 1;
            if draw[0] < -5.0 {
                below += 1;
            }
        }
    }
    below as f64 / total as f64
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = std::env::args().collect();
    if args.len() != 4 {
        return Err("usage: <manifest.json> <ordinal> <record.json>".into());
    }
    let manifest: Manifest = serde_json::from_slice(&fs::read(&args[1])?)?;
    let ordinal: usize = args[2].parse()?;
    let output = Path::new(&args[3]);
    if output.exists() {
        return Err(format!("record already exists: {}", output.display()).into());
    }
    let cell = manifest
        .cells
        .get(ordinal)
        .filter(|cell| cell.ordinal == ordinal)
        .ok_or("ordinal not in manifest")?
        .clone();
    let (target, starts) = build_target(&cell)?;
    let tuning = Tuning::new()
        .step_size(cell.initial_step)
        .max_depth(10)
        .min_micro_steps(1)
        .max_refinement_levels(8)
        .max_error(1.0)
        .divergence_threshold(1000.0)
        .nonfinite_position(policy(&cell.arm)?);
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
    let started = Instant::now();
    let result = sampler.run(&target, &starts);
    let wall_seconds = started.elapsed().as_secs_f64();
    let fatal_reclassified = match &target {
        StudyTarget::StateSpace(t) => t.reclassified.load(Ordering::Relaxed),
        _ => 0,
    };
    let mut record = Record {
        schema: "owalnuts-nonfinite-position-policy-v1-record",
        ordinal,
        id: cell.id.clone(),
        target: cell.target.clone(),
        seed: cell.seed,
        arm: cell.arm.clone(),
        status: String::new(),
        error_kind: None,
        error_message: None,
        wall_seconds,
        total_target_calls: None,
        recoverable_target_failures: None,
        fatal_reclassified,
        nonfinite_position_rejections_discarded: None,
        nonfinite_position_rejections_retained: None,
        nonfinite_position_rejections_by_phase: None,
        retained_divergences: None,
        draw_hash_sha256: None,
        functionals: Vec::new(),
        funnel_tail_mass: None,
        algorithm_revision: None,
    };
    match result {
        Ok(posterior) => {
            record.status = "complete".into();
            record.total_target_calls = Some(posterior.total_target_calls());
            let mut recoverable = 0usize;
            let mut discarded = 0usize;
            let mut retained = 0usize;
            let mut by_phase = [0usize; 3];
            let mut divergences = 0usize;
            for telemetry in posterior.telemetry() {
                recoverable += telemetry.total().recoverable_target_failures();
                discarded += telemetry.discarded().nonfinite_position_rejections();
                retained += telemetry.retained().nonfinite_position_rejections();
                by_phase[0] += telemetry.initial_fast().nonfinite_position_rejections();
                by_phase[1] += telemetry.slow().nonfinite_position_rejections();
                by_phase[2] += telemetry.terminal_fast().nonfinite_position_rejections();
                divergences += telemetry.retained().divergences();
            }
            record.recoverable_target_failures = Some(recoverable);
            record.nonfinite_position_rejections_discarded = Some(discarded);
            record.nonfinite_position_rejections_retained = Some(retained);
            record.nonfinite_position_rejections_by_phase = Some(by_phase);
            record.retained_divergences = Some(divergences);
            record.draw_hash_sha256 = Some(draw_hash(&posterior));
            record.functionals = functionals(&posterior, &cell.monitored_coordinates);
            if cell.target == "neal_funnel_10d" {
                record.funnel_tail_mass = Some(funnel_tail_mass(&posterior));
            }
            record.algorithm_revision = Some(posterior.algorithm_revision().to_owned());
        }
        Err(error) => {
            record.status = "sampler_error".into();
            record.error_kind = Some(format!("{:?}", error.kind()));
            record.error_message = Some(error.to_string());
        }
    }
    let temporary = output.with_extension("json.tmp-write");
    fs::write(&temporary, serde_json::to_vec_pretty(&record)?)?;
    fs::rename(&temporary, output)?;
    Ok(())
}
