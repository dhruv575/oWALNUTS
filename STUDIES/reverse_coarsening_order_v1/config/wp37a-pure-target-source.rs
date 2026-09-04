//! WP37A one-shot pure-Rust child harness.
//!
//! The parent runner is the only supported evidence launcher. Each invocation
//! executes one canonical manifest tuple and atomically publishes one raw JSON
//! result. Sampler errors are serialized as observations and exit zero.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE,
    DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric, Posterior, Sampler, Target, TargetError,
    Tuning,
};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, DiagonalMetricRegularization, ExhaustionRule, KernelOptions,
    KernelTuning, MultiChainOutput, RunConfig, TargetEvaluationAdmissionLimit,
    TargetEvaluationBudget, UTurnRule, WarmupConfig, WorkTotals,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    env,
    error::Error,
    fs::{self, OpenOptions},
    io::{Read, Write},
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const RAW_SCHEMA: &str = "owalnuts-delta2-sidechecks-v1-raw";
const COMPLETE: &str = "WP37A_CELL_COMPLETE_V1";
const CHAINS: usize = 4;
const FUNNEL_DIMENSION: usize = 10;
const GAUSSIAN_DIMENSION: usize = 100;
const ES_DIMENSION: usize = 10;
const ES_CALLBACK_CAP: usize = 10_000_000;
const HARNESS_COMMIT: &str = env!("WP37A_HARNESS_COMMIT");
const HARNESS_TREE: &str = env!("WP37A_HARNESS_TREE");
const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const SCHOOL_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SCHOOL_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
enum Arm {
    Fixed1,
    Fixed2,
}

impl Arm {
    fn parse(value: &str) -> Result<Self, Box<dyn Error>> {
        match value {
            "fixed1" => Ok(Self::Fixed1),
            "fixed2" => Ok(Self::Fixed2),
            _ => Err(format!("unknown arm {value:?}").into()),
        }
    }

    const fn name(self) -> &'static str {
        match self {
            Self::Fixed1 => "fixed1",
            Self::Fixed2 => "fixed2",
        }
    }

    const fn max_error(self) -> f64 {
        match self {
            Self::Fixed1 => 1.0,
            Self::Fixed2 => 2.0,
        }
    }
}

#[derive(Debug)]
struct CellArgs {
    ordinal: usize,
    target: String,
    seed: u64,
    repetition: usize,
    arm: Arm,
    sentinel: String,
    provenance: PathBuf,
    output: PathBuf,
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

struct EightSchools {
    calls: AtomicUsize,
}

impl EightSchools {
    fn new() -> Self {
        Self {
            calls: AtomicUsize::new(0),
        }
    }
}

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        ES_DIMENSION
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let call = self.calls.fetch_add(1, Ordering::Relaxed) + 1;
        if call > ES_CALLBACK_CAP {
            return Err(TargetError::new(
                "runtime target-evaluation budget exhausted",
            ));
        }
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0.0, 5.0)
            + (2.0 / (std::f64::consts::PI * 5.0 * (1.0 + (tau / 5.0).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.0);
        gradient[0] = -mu / 25.0;
        gradient[1] = 1.0 - 2.0 * tau * tau / (25.0 + tau * tau);
        for school in 0..8 {
            let theta = mu + tau * z[school];
            let residual = SCHOOL_Y[school] - theta;
            let likelihood_gradient = residual / SCHOOL_SE[school].powi(2);
            value += normal_log_density(SCHOOL_Y[school], theta, SCHOOL_SE[school])
                + normal_log_density(z[school], 0.0, 1.0);
            gradient[0] += likelihood_gradient;
            gradient[1] += likelihood_gradient * tau * z[school];
            gradient[school + 2] = -z[school] + likelihood_gradient * tau;
        }
        if value.is_finite() && gradient.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite Eight Schools evaluation"))
        }
    }
}

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

fn funnel_starts() -> Vec<Vec<f64>> {
    [-3.0, -1.0, 1.0, 3.0]
        .map(|omega| {
            let mut position = vec![0.0; FUNNEL_DIMENSION];
            position[0] = omega;
            position
        })
        .to_vec()
}

fn eight_schools_starts() -> Vec<Vec<f64>> {
    [-2.0, -1.0, 0.0, 1.0]
        .map(|log_tau| {
            let mut position = vec![0.0; ES_DIMENSION];
            position[1] = log_tau;
            position
        })
        .to_vec()
}

fn kernel_options() -> KernelOptions {
    KernelOptions {
        u_turn: UTurnRule::MomentumSum,
        exhaustion: ExhaustionRule::Stop,
    }
}

fn explicit_warmup(target_accept: f64) -> Result<WarmupConfig, Box<dyn Error>> {
    let warmup = WarmupConfig::new(target_accept)?
        .with_mass_adaptation(true)
        .with_warmup_exhaustion_rule(ExhaustionRule::AcceptUnlessDivergent)
        .with_metric_regularization(DiagonalMetricRegularization::Stan);
    if warmup.chain_rescue().is_some() {
        return Err("explicit warmup unexpectedly enables chain rescue".into());
    }
    Ok(warmup)
}

fn explicit_tuning(target: &str, arm: Arm) -> Tuning {
    let (step, depth) = if target == "eight_schools_strict" {
        (0.3, 8)
    } else {
        (0.5, 10)
    };
    Tuning::new()
        .step_size(step)
        .max_depth(depth)
        .min_micro_steps(1)
        .max_refinement_levels(8)
        .max_error(arm.max_error())
        .divergence_threshold(1000.0)
        .kernel_options(kernel_options())
}

fn kernel_tuning(target: &str, arm: Arm) -> Result<KernelTuning, Box<dyn Error>> {
    Ok(explicit_tuning(target, arm).to_kernel()?)
}

fn assert_current_defaults() -> Result<(), Box<dyn Error>> {
    if DEFAULT_CHAIN_RESCUE.is_some() {
        return Err("DEFAULT_CHAIN_RESCUE is not None".into());
    }
    if DEFAULT_METRIC_REGULARIZATION != DiagonalMetricRegularization::Stan {
        return Err("DEFAULT_METRIC_REGULARIZATION is not Stan".into());
    }
    if DEFAULT_WARMUP_EXHAUSTION != ExhaustionRule::AcceptUnlessDivergent {
        return Err("DEFAULT_WARMUP_EXHAUSTION is not AcceptUnlessDivergent".into());
    }
    if DEFAULT_U_TURN_RULE != UTurnRule::MomentumSum {
        return Err("DEFAULT_U_TURN_RULE is not MomentumSum".into());
    }
    let tuning = Tuning::default().to_kernel()?;
    if tuning.step_size() != 0.5
        || tuning.max_depth() != 10
        || tuning.min_micro_steps() != 1
        || tuning.max_refinement_levels() != 8
        || tuning.max_error() != 1.0
        || tuning.divergence_threshold() != 1000.0
        || tuning.options() != kernel_options()
    {
        return Err(format!("current Tuning::default() mismatch: {tuning:?}").into());
    }
    let warmup = explicit_warmup(0.8)?;
    if warmup.target_acceptance() != 0.8
        || !warmup.adapts_step_size()
        || !warmup.adapts_mass()
        || warmup.metric_regularization() != DiagonalMetricRegularization::Stan
        || warmup.warmup_exhaustion_rule() != Some(ExhaustionRule::AcceptUnlessDivergent)
        || warmup.chain_rescue().is_some()
    {
        return Err("explicit current-final warmup mismatch".into());
    }
    Ok(())
}

fn effective_config(target: &str, arm: Arm) -> Result<Value, Box<dyn Error>> {
    assert_current_defaults()?;
    let (dimension, warmup, retained, threads, h0, depth, target_accept, timeout) = match target {
        "funnel" => (10, 2_000, 20_000, 4, 0.5, 10, 0.8, 3_600),
        "eight_schools_strict" => (10, 1_000, 1_000, 1, 0.3, 8, 0.95, 900),
        "gaussian100" => (100, 1_000, 1_000, 4, 0.5, 10, 0.8, 600),
        _ => return Err(format!("unknown target {target:?}").into()),
    };
    let starts_or_init = match target {
        "funnel" => json!({"kind": "fixed", "positions": funnel_starts()}),
        "eight_schools_strict" => {
            json!({"kind": "fixed", "positions": eight_schools_starts()})
        }
        "gaussian100" => json!({
            "kind": "Init::uniform",
            "distribution": "uniform(-2,2)",
            "radius": 2.0,
            "max_attempts": 100,
            "seeded": true
        }),
        _ => unreachable!(),
    };
    Ok(json!({
        "schema": "owalnuts-delta2-sidechecks-v1-effective-config",
        "target": target,
        "arm": arm.name(),
        "dimension": dimension,
        "chains": CHAINS,
        "threads": threads,
        "warmup": warmup,
        "retained": retained,
        "timeout_seconds": timeout,
        "starts_or_initializer": starts_or_init,
        "sampler_boundary": if target == "eight_schools_strict" {
            "walnutpie::sample_chains_with_target_budget"
        } else {
            "owalnuts::sampler::Sampler"
        },
        "cache_initial_evaluation": target != "eight_schools_strict",
        "callback_cap": if target == "eight_schools_strict" {
            Some(ES_CALLBACK_CAP)
        } else {
            None
        },
        "admission": if target == "eight_schools_strict" {
            "exact worst-case TargetEvaluationAdmissionLimit"
        } else {
            "Limits::admit_worst_case()"
        },
        "metric": {
            "kind": "adapted diagonal",
            "initial": "identity",
            "regularization": "Stan"
        },
        "adaptation": {
            "kind": "dual_averaging",
            "target_acceptance": target_accept,
            "step_size_adaptation": true,
            "mass_adaptation": true,
            "warmup_exhaustion": "AcceptUnlessDivergent",
            "chain_rescue": null,
            "inherits_default_chain_rescue": false
        },
        "kernel": {
            "initial_step_size": h0,
            "max_tree_depth": depth,
            "min_micro_steps": 1,
            "max_refinement_levels": 8,
            "max_error": arm.max_error(),
            "divergence_threshold": 1000.0,
            "u_turn_rule": "MomentumSum",
            "retained_exhaustion_rule": "Stop"
        },
        "current_final_default_assertions": {
            "Tuning::default.step_size": 0.5,
            "Tuning::default.max_tree_depth": 10,
            "Tuning::default.min_micro_steps": 1,
            "Tuning::default.max_refinement_levels": 8,
            "Tuning::default.max_error": 1.0,
            "Tuning::default.divergence_threshold": 1000.0,
            "DEFAULT_U_TURN_RULE": "MomentumSum",
            "DEFAULT_METRIC_REGULARIZATION": "Stan",
            "DEFAULT_WARMUP_EXHAUSTION": "AcceptUnlessDivergent",
            "DEFAULT_CHAIN_RESCUE": null
        },
        "only_arm_difference": "kernel.max_error"
    }))
}

fn sha256_bytes(bytes: &[u8]) -> String {
    format!("{:x}", Sha256::digest(bytes))
}

fn sha256_file(path: &Path) -> Result<String, Box<dyn Error>> {
    let mut file = fs::File::open(path)?;
    let mut digest = Sha256::new();
    let mut buffer = [0_u8; 1024 * 1024];
    loop {
        let read = file.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        digest.update(&buffer[..read]);
    }
    Ok(format!("{:x}", digest.finalize()))
}

fn config_hash(config: &Value) -> Result<String, Box<dyn Error>> {
    Ok(sha256_bytes(&serde_json::to_vec(config)?))
}

fn hash_f64(domain: &[u8], shape: &[usize], values: impl Iterator<Item = f64>) -> String {
    let mut digest = Sha256::new();
    digest.update(domain);
    digest.update((shape.len() as u64).to_le_bytes());
    for extent in shape {
        digest.update((*extent as u64).to_le_bytes());
    }
    for value in values {
        digest.update(value.to_bits().to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

fn hash_debug(domain: &[u8], value: &impl std::fmt::Debug) -> String {
    let mut digest = Sha256::new();
    digest.update(domain);
    digest.update(format!("{value:?}").as_bytes());
    format!("{:x}", digest.finalize())
}

fn initial_position_hash(position: &[f64]) -> String {
    hash_f64(
        b"delta2_sidechecks_v1.initial_position.v1",
        &[position.len()],
        position.iter().copied(),
    )
}

fn work_json(work: &WorkTotals) -> Value {
    json!({
        "transitions": work.transitions(),
        "momentum_refreshes": work.momentum_refreshes(),
        "standard_normal_components": work.standard_normal_components(),
        "target_calls_initial": work.target_calls_initial(),
        "target_calls_forward": work.target_calls_forward(),
        "target_calls_reverse": work.target_calls_reverse(),
        "target_calls_total": work.target_calls_total(),
        "forward_refinement_attempts": work.forward_refinement_attempts(),
        "forward_micro_steps_executed": work.forward_micro_steps_executed(),
        "reverse_coarsening_attempts": work.reverse_coarsening_attempts(),
        "reverse_micro_steps_executed": work.reverse_micro_steps_executed(),
        "leaves_attempted": work.leaves_attempted(),
        "leaves_built": work.leaves_built(),
        "direction_draws": work.direction_draws(),
        "uniform_draws": work.uniform_draws(),
        "maximum_depth_stops": work.maximum_depth_stops(),
        "recoverable_target_failures": work.recoverable_target_failures(),
        "zero_density_evaluations": work.zero_density_evaluations(),
        "divergences": work.divergences(),
        "invalid_evaluation_stops": work.invalid_evaluation_stops(),
        "refinement_exhaustion_stops": work.refinement_exhaustion_stops(),
        "reverse_coarser_stops": work.reverse_coarser_stops(),
        "reverse_coarser_rejections": work.reverse_coarser_rejections(),
        "accepted_forward_micro_steps": work.accepted_forward_micro_steps(),
        "refinement_level_built": work.refinement_level_built()
    })
}

fn output_hashes(
    chains: &[owalnuts::walnutpie::ChainOutput],
    retained: usize,
    dimension: usize,
    warmup: usize,
) -> Value {
    let draws = hash_f64(
        b"delta2_sidechecks_v1.retained_draws.v1",
        &[chains.len(), retained, dimension],
        chains
            .iter()
            .flat_map(|chain| chain.samples().iter().copied()),
    );
    let diagnostics = chains
        .iter()
        .map(|chain| {
            hash_debug(
                b"delta2_sidechecks_v1.retained_diagnostics.v1",
                &&chain.diagnostics()[warmup..],
            )
        })
        .collect::<Vec<_>>();
    let tuning = chains
        .iter()
        .map(|chain| {
            hash_debug(
                b"delta2_sidechecks_v1.final_tuning.v1",
                chain.metadata().tuning(),
            )
        })
        .collect::<Vec<_>>();
    let metric = chains
        .iter()
        .map(|chain| {
            hash_f64(
                b"delta2_sidechecks_v1.final_metric.v1",
                &[chain.metadata().mass_diagonal().len()],
                chain.metadata().mass_diagonal().iter().copied(),
            )
        })
        .collect::<Vec<_>>();
    json!({
        "retained_draw_bytes_sha256": draws,
        "retained_diagnostics_sha256_by_chain": diagnostics,
        "final_tuning_sha256_by_chain": tuning,
        "final_metric_sha256_by_chain": metric
    })
}

fn chain_json(chain: &owalnuts::walnutpie::ChainOutput, chain_index: usize) -> Value {
    let retained = chain.telemetry().retained();
    let discarded = chain.telemetry().discarded();
    json!({
        "chain": chain_index,
        "initial_position": chain.metadata().initial_position(),
        "initial_position_sha256": initial_position_hash(chain.metadata().initial_position()),
        "samples": (0..chain.retained())
            .map(|draw| chain.sample(draw).expect("retained draw"))
            .collect::<Vec<_>>(),
        "final_step_size": chain.metadata().tuning().step_size(),
        "final_max_error": chain.metadata().tuning().max_error(),
        "final_mass_diagonal": chain.metadata().mass_diagonal(),
        "work": {
            "warmup": work_json(discarded),
            "retained": work_json(retained),
            "total": work_json(chain.telemetry().total()),
            "adaptation_target_calls": chain.telemetry().adaptation_target_calls(),
            "target_calls_including_adaptation": chain.telemetry().target_calls_including_adaptation()
        },
        "chain_rescue_events": chain.telemetry().chain_rescues().len()
    })
}

fn scientific_payload(
    output: &MultiChainOutput,
    warmup: usize,
    retained: usize,
    dimension: usize,
) -> Result<Value, Box<dyn Error>> {
    if output.chains().len() != CHAINS {
        return Err("sampler returned wrong chain count".into());
    }
    for chain in output.chains() {
        if chain.retained() != retained || chain.dimension() != dimension {
            return Err("sampler returned wrong retained shape".into());
        }
        if !chain.samples().iter().all(|x| x.is_finite()) {
            return Err(
                "sampler returned nonfinite draw; raw schema requires representable f64".into(),
            );
        }
        if !chain.telemetry().chain_rescues().is_empty() {
            return Err("no-rescue study observed a chain rescue event".into());
        }
    }
    let hashes = output_hashes(output.chains(), retained, dimension, warmup);
    let chains = output
        .chains()
        .iter()
        .enumerate()
        .map(|(index, chain)| chain_json(chain, index))
        .collect::<Vec<_>>();
    let warmup_calls = output
        .chains()
        .iter()
        .map(|chain| chain.telemetry().discarded().target_calls_total())
        .sum::<usize>();
    let retained_calls = output
        .chains()
        .iter()
        .map(|chain| chain.telemetry().retained().target_calls_total())
        .sum::<usize>();
    let adaptation_calls = output
        .chains()
        .iter()
        .map(|chain| chain.telemetry().adaptation_target_calls())
        .sum::<usize>();
    let total_callbacks = output
        .chains()
        .iter()
        .map(|chain| chain.telemetry().target_calls_including_adaptation())
        .sum::<usize>();
    Ok(json!({
        "chains_data": chains,
        "initial_position_sha256_by_chain": output.chains().iter()
            .map(|chain| initial_position_hash(chain.metadata().initial_position()))
            .collect::<Vec<_>>(),
        "retained_draw_bytes_sha256": hashes["retained_draw_bytes_sha256"],
        "retained_diagnostics_sha256_by_chain": hashes["retained_diagnostics_sha256_by_chain"],
        "final_tuning_sha256_by_chain": hashes["final_tuning_sha256_by_chain"],
        "final_metric_sha256_by_chain": hashes["final_metric_sha256_by_chain"],
        "phase_target_callbacks": {
            "warmup_kernel": warmup_calls,
            "retained_kernel": retained_calls,
            "adaptation": adaptation_calls,
            "total_started": total_callbacks
        }
    }))
}

fn sampler_error(error: &owalnuts::walnutpie::Error, stage: &str, known: Value) -> Value {
    json!({
        "variant": "sampler_error",
        "error_stage": stage,
        "error_class": format!("{:?}", error.kind()),
        "error_message": error.message(),
        "known_counters": known
    })
}

fn run_sampler_facade(
    target_name: &str,
    arm: Arm,
    seed: u64,
) -> Result<(Value, f64), Box<dyn Error>> {
    let (warmup, retained, dimension, threads, target_accept) = match target_name {
        "funnel" => (2_000, 20_000, FUNNEL_DIMENSION, 4, 0.8),
        "gaussian100" => (1_000, 1_000, GAUSSIAN_DIMENSION, 4, 0.8),
        _ => return Err("invalid Sampler-facade target".into()),
    };
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(retained)
        .chains(CHAINS)
        .seed(seed)
        .threads(threads)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::Custom(explicit_warmup(target_accept)?))
        .tuning(explicit_tuning(target_name, arm))
        .limits(Limits::new().admit_worst_case())
        .cache_initial_evaluation(true);
    let begin = Instant::now();
    let result: Result<Posterior, _> = match target_name {
        "funnel" => sampler.run(&Funnel, &funnel_starts()),
        "gaussian100" => sampler.run_with_init(&Gaussian, &Init::uniform()),
        _ => unreachable!(),
    };
    let wall = begin.elapsed().as_secs_f64();
    let payload = match result {
        Ok(posterior) => {
            if posterior.algorithm_revision() != ALGORITHM_REVISION {
                return Err("unexpected algorithm revision".into());
            }
            let mut payload = scientific_payload(posterior.inner(), warmup, retained, dimension)?;
            payload["variant"] = json!("samples_complete");
            payload
        }
        Err(error) => sampler_error(&error, "sampling", json!({})),
    };
    Ok((payload, wall))
}

fn run_eight_schools(arm: Arm, seed: u64) -> Result<(Value, f64), Box<dyn Error>> {
    let tuning = kernel_tuning("eight_schools_strict", arm)?;
    let config = RunConfig::new(1_000, NonZeroUsize::new(1_000).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(explicit_warmup(0.95)?);
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(CHAINS).unwrap())?;
    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    let diagonal = DiagonalMass::identity(NonZeroUsize::new(ES_DIMENSION).unwrap());
    {
        let preflight_target = EightSchools::new();
        let preflight_budget =
            TargetEvaluationBudget::new(NonZeroUsize::new(ES_CALLBACK_CAP).unwrap());
        preflight_chains_with_target_budget(
            &preflight_target,
            &eight_schools_starts(),
            &diagonal,
            &config,
            admission,
            &preflight_budget,
        )?;
        if preflight_target.calls.load(Ordering::Relaxed) != 0 || preflight_budget.started() != 0 {
            return Err("Eight Schools preflight entered target".into());
        }
    }
    let target = EightSchools::new();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(ES_CALLBACK_CAP).unwrap());
    let begin = Instant::now();
    let result = sample_chains_with_target_budget(
        &target,
        &eight_schools_starts(),
        &diagonal,
        &config,
        NonZeroUsize::new(1).unwrap(),
        admission,
        &budget,
    );
    let wall = begin.elapsed().as_secs_f64();
    let target_calls = target.calls.load(Ordering::Relaxed);
    if target_calls != budget.started() {
        return Err("Eight Schools callback counters disagree".into());
    }
    let payload = match result {
        Ok(output) => {
            let mut payload = scientific_payload(&output, 1_000, 1_000, ES_DIMENSION)?;
            if payload["phase_target_callbacks"]["total_started"] != json!(target_calls) {
                return Err("Eight Schools telemetry and callback counter disagree".into());
            }
            payload["variant"] = json!("samples_complete");
            payload["callback_cap"] = json!(ES_CALLBACK_CAP);
            payload["constructor_admission_bound"] = json!(exact);
            payload["target_atomic_calls"] = json!(target_calls);
            payload
        }
        Err(error) => sampler_error(
            &error,
            "sampling",
            json!({
                "target_atomic_calls": target_calls,
                "budget_started": budget.started(),
                "callback_cap": ES_CALLBACK_CAP,
                "constructor_admission_bound": exact
            }),
        ),
    };
    Ok((payload, wall))
}

fn current_binary_record() -> Result<Value, Box<dyn Error>> {
    let path = env::current_exe()?;
    Ok(json!({
        "bytes": fs::metadata(&path)?.len(),
        "sha256": sha256_file(&path)?
    }))
}

fn load_provenance(path: &Path) -> Result<Value, Box<dyn Error>> {
    let value: Value = serde_json::from_slice(&fs::read(path)?)?;
    if value["schema"] != "owalnuts-delta2-sidechecks-v1-provenance" {
        return Err("wrong provenance schema".into());
    }
    if value["harness_source"]["commit"] != HARNESS_COMMIT
        || value["harness_source"]["tree"] != HARNESS_TREE
    {
        return Err("embedded harness source does not match provenance".into());
    }
    let current_binary = current_binary_record()?;
    if value["binary"]["bytes"] != current_binary["bytes"]
        || value["binary"]["sha256"] != current_binary["sha256"]
    {
        return Err("running binary does not match provenance".into());
    }
    if value["algorithm_revision"] != ALGORITHM_REVISION {
        return Err("provenance algorithm revision mismatch".into());
    }
    Ok(value)
}

fn manifest_tuple(args: &CellArgs) -> Value {
    json!({
        "ordinal": args.ordinal,
        "target": args.target,
        "seed": args.seed,
        "zero_based_repetition": args.repetition,
        "arm": args.arm.name(),
        "sentinel": args.sentinel
    })
}

fn authenticate_cell(
    args: &CellArgs,
    provenance: &Value,
) -> Result<(Value, String), Box<dyn Error>> {
    let tuple = manifest_tuple(args);
    let entries = provenance["manifest"]["entries"]
        .as_array()
        .ok_or("provenance manifest entries are missing")?;
    let matches = entries.iter().filter(|entry| **entry == tuple).count();
    if matches != 1 {
        return Err(format!("tuple has {matches} canonical manifest matches").into());
    }
    let config = effective_config(&args.target, args.arm)?;
    let hash = config_hash(&config)?;
    let key = format!("{}/{}", args.target, args.arm.name());
    let registered = &provenance["effective_configs"][&key];
    if registered["sha256"] != hash || registered["config"] != config {
        return Err("runtime effective config does not match provenance".into());
    }
    Ok((config, hash))
}

fn run_cell(args: &CellArgs) -> Result<Value, Box<dyn Error>> {
    let provenance = load_provenance(&args.provenance)?;
    let (config, effective_config_sha256) = authenticate_cell(args, &provenance)?;
    let (scientific, wall_seconds) = match args.target.as_str() {
        "funnel" | "gaussian100" => run_sampler_facade(&args.target, args.arm, args.seed)?,
        "eight_schools_strict" => run_eight_schools(args.arm, args.seed)?,
        _ => return Err("unknown target".into()),
    };
    let mut raw = json!({
        "schema": RAW_SCHEMA,
        "schema_version": 1,
        "completion_sentinel": COMPLETE,
        "manifest": manifest_tuple(args),
        "target": args.target,
        "seed": args.seed,
        "arm": args.arm.name(),
        "zero_based_repetition": args.repetition,
        "repetition_sentinel": args.sentinel,
        "dimension": config["dimension"],
        "chains": config["chains"],
        "threads": config["threads"],
        "warmup": config["warmup"],
        "retained": config["retained"],
        "timeout_seconds": config["timeout_seconds"],
        "effective_config": config,
        "effective_config_sha256": effective_config_sha256,
        "algorithm_revision": ALGORITHM_REVISION,
        "harness_source_commit": HARNESS_COMMIT,
        "harness_source_tree": HARNESS_TREE,
        "binary": current_binary_record()?,
        "provenance_record_sha256": sha256_file(&args.provenance)?,
        "provenance_bindings": {
            "baseline": provenance["baseline"],
            "normalized_source_files": provenance["normalized_source_files"],
            "harness_source": provenance["harness_source"],
            "binary": provenance["binary"],
            "cargo_lock": provenance["cargo_lock"],
            "manifest_sha256": provenance["manifest"]["sha256"]
        },
        "wall_seconds": wall_seconds
    });
    let scientific_object = scientific
        .as_object()
        .ok_or("scientific payload is not an object")?;
    for (key, value) in scientific_object {
        raw[key] = value.clone();
    }
    Ok(raw)
}

fn write_new_atomically(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err(format!("refusing to replace existing result: {}", path.display()).into());
    }
    let parent = path.parent().ok_or("output path has no parent")?;
    fs::create_dir_all(parent)?;
    let filename = path
        .file_name()
        .ok_or("output path has no filename")?
        .to_string_lossy();
    let temporary = parent.join(format!(".{filename}.tmp-{}", std::process::id()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    file.write_all(bytes)?;
    if !bytes.ends_with(b"\n") {
        file.write_all(b"\n")?;
    }
    file.sync_all()?;
    drop(file);
    fs::rename(&temporary, path)?;
    Ok(())
}

fn configs_document() -> Result<Value, Box<dyn Error>> {
    let mut configs = serde_json::Map::new();
    for target in ["funnel", "eight_schools_strict", "gaussian100"] {
        for arm in [Arm::Fixed1, Arm::Fixed2] {
            let config = effective_config(target, arm)?;
            configs.insert(
                format!("{target}/{}", arm.name()),
                json!({"config": config, "sha256": config_hash(&config)?}),
            );
        }
    }
    Ok(json!({
        "schema": "owalnuts-delta2-sidechecks-v1-configs",
        "algorithm_revision": ALGORITHM_REVISION,
        "harness_source_commit": HARNESS_COMMIT,
        "harness_source_tree": HARNESS_TREE,
        "binary": current_binary_record()?,
        "effective_configs": configs
    }))
}

fn fingerprint_document() -> Result<Value, Box<dyn Error>> {
    assert_current_defaults()?;
    let cases: Vec<(&str, Box<dyn Target>, Vec<f64>)> = vec![
        (
            "funnel",
            Box::new(Funnel),
            vec![0.25, -0.5, 0.75, -1.0, 1.25, -1.5, 1.75, -2.0, 2.25, -2.5],
        ),
        (
            "eight_schools_strict",
            Box::new(EightSchools::new()),
            vec![0.25, -0.5, 0.75, -1.0, 1.25, -1.5, 1.75, -2.0, 2.25, -2.5],
        ),
        (
            "gaussian100",
            Box::new(Gaussian),
            (0..100).map(|i| (i as f64 - 49.5) / 25.0).collect(),
        ),
    ];
    let mut target_fingerprints = serde_json::Map::new();
    for (name, target, position) in cases {
        let mut gradient = vec![0.0; target.dimension()];
        let log_density = target.log_density_gradient(&position, &mut gradient)?;
        target_fingerprints.insert(
            name.into(),
            json!({
                "dimension": target.dimension(),
                "position_sha256": hash_f64(b"delta2_sidechecks_v1.fingerprint.position.v1", &[position.len()], position.into_iter()),
                "log_density_bits": format!("0x{:016x}", log_density.to_bits()),
                "gradient_sha256": hash_f64(b"delta2_sidechecks_v1.fingerprint.gradient.v1", &[gradient.len()], gradient.into_iter())
            }),
        );
    }
    Ok(json!({
        "schema": "owalnuts-delta2-sidechecks-v1-fingerprint",
        "evidence": false,
        "algorithm_revision": ALGORITHM_REVISION,
        "harness_source_commit": HARNESS_COMMIT,
        "harness_source_tree": HARNESS_TREE,
        "targets": target_fingerprints,
        "configs": configs_document()?["effective_configs"]
    }))
}

fn parse_cell_args(args: &[String]) -> Result<CellArgs, Box<dyn Error>> {
    let [
        ordinal,
        target,
        seed,
        repetition,
        arm,
        sentinel,
        provenance,
        output,
    ] = args
    else {
        return Err("usage: cell <ordinal> <target> <seed> <repetition> <arm> <sentinel> <provenance.json> <out.json>".into());
    };
    Ok(CellArgs {
        ordinal: ordinal.parse()?,
        target: target.clone(),
        seed: seed.parse()?,
        repetition: repetition.parse()?,
        arm: Arm::parse(arm)?,
        sentinel: sentinel.clone(),
        provenance: provenance.into(),
        output: output.into(),
    })
}

fn real_main() -> Result<(), Box<dyn Error>> {
    let args = env::args().skip(1).collect::<Vec<_>>();
    match args.as_slice() {
        [command] if command == "configs" => {
            println!("{}", serde_json::to_string_pretty(&configs_document()?)?);
        }
        [command, output] if command == "fingerprint" => {
            let document = fingerprint_document()?;
            write_new_atomically(Path::new(output), &serde_json::to_vec_pretty(&document)?)?;
        }
        [command, rest @ ..] if command == "cell" => {
            let cell = parse_cell_args(rest)?;
            let payload = run_cell(&cell)?;
            write_new_atomically(&cell.output, &serde_json::to_vec_pretty(&payload)?)?;
            eprintln!(
                "{:02} {} {} rep{} {}: {} {:.3}s",
                cell.ordinal,
                cell.target,
                cell.seed,
                cell.repetition,
                cell.arm.name(),
                payload["variant"].as_str().unwrap_or("unknown"),
                payload["wall_seconds"].as_f64().unwrap_or(f64::NAN)
            );
        }
        _ => {
            return Err("usage: configs | fingerprint <out.json> | cell <ordinal> <target> <seed> <repetition> <arm> <sentinel> <provenance.json> <out.json>".into());
        }
    }
    Ok(())
}

fn main() {
    if let Err(error) = real_main() {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn frozen_defaults_are_current() {
        assert_current_defaults().unwrap();
    }

    #[test]
    fn arms_differ_only_in_max_error() {
        for target in ["funnel", "eight_schools_strict", "gaussian100"] {
            let mut fixed1 = effective_config(target, Arm::Fixed1).unwrap();
            let mut fixed2 = effective_config(target, Arm::Fixed2).unwrap();
            fixed1["arm"] = Value::Null;
            fixed2["arm"] = Value::Null;
            fixed1["kernel"]["max_error"] = Value::Null;
            fixed2["kernel"]["max_error"] = Value::Null;
            assert_eq!(fixed1, fixed2);
        }
    }

    #[test]
    fn exact_targets_have_finite_reference_evaluations() {
        for (target, position) in [
            (&Funnel as &dyn Target, vec![0.0; 10]),
            (&Gaussian as &dyn Target, vec![0.0; 100]),
        ] {
            let mut gradient = vec![0.0; target.dimension()];
            let value = target
                .log_density_gradient(&position, &mut gradient)
                .unwrap();
            assert!(value.is_finite());
            assert!(gradient.iter().all(|x| x.is_finite()));
        }
        let target = EightSchools::new();
        let mut gradient = vec![0.0; 10];
        assert!(
            target
                .log_density_gradient(&vec![0.0; 10], &mut gradient)
                .unwrap()
                .is_finite()
        );
    }
}
