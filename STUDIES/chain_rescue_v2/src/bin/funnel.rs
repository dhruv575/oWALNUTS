//! One fresh-child Neal 10-D funnel cell for preregistered WP36.
//!
//! Usage: `funnel <observe|current|two_hit> <seed> <heartbeat-dir> <out.json>`
#![forbid(unsafe_code)]

#[path = "../arms.rs"]
mod arms;

use arms::{Arm, Heartbeat};
use owalnuts::sampler::{Limits, Metric, Sampler, Target, TargetError, Tuning};
use owalnuts::walnutpie::ALGORITHM_REVISION;
use serde_json::json;
use std::{
    env,
    error::Error,
    path::{Path, PathBuf},
    time::Instant,
};

const TARGET_NAME: &str = "funnel-10d";
const DIMENSION: usize = 10;
const CHAINS: usize = 4;
const WARMUP: usize = 2_000;
const RETAINED: usize = 20_000;
const EXACT_TAIL_MASS: f64 = 0.047_8;

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
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|value| value * value).sum();
        let tail = (DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (entry, value) in gradient[1..].iter_mut().zip(&position[1..]) {
            *entry = -inverse_variance * value;
        }
        let logp =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if logp.is_finite() && gradient.iter().all(|value| value.is_finite()) {
            Ok(logp)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

struct Config {
    arm: Arm,
    seed: u64,
    heartbeat: PathBuf,
    output: PathBuf,
}

impl Config {
    fn parse(args: &[String]) -> Result<Self, Box<dyn Error>> {
        let [arm, seed, heartbeat, output] = args else {
            return Err(
                "usage: <observe|current|two_hit> <seed> <heartbeat-dir> <out.json>".into(),
            );
        };
        Ok(Self {
            arm: Arm::parse(arm, false)?,
            seed: seed.parse()?,
            heartbeat: heartbeat.into(),
            output: output.into(),
        })
    }
}

fn write_result(path: &Path, payload: &serde_json::Value) -> Result<(), Box<dyn Error>> {
    arms::write_new_atomically(path, &serde_json::to_vec_pretty(payload)?)
}

fn run(cfg: &Config) -> Result<(), Box<dyn Error>> {
    if cfg.output.exists() {
        return Err(format!("output already exists: {}", cfg.output.display()).into());
    }
    let mut heartbeat = Heartbeat::new(cfg.heartbeat.clone(), TARGET_NAME, cfg.seed, cfg.arm)?;
    heartbeat.event("process", "start")?;
    heartbeat.event("load", "before")?;
    let target = Funnel;
    heartbeat.event("load", "after")?;

    heartbeat.event("initialization", "before")?;
    let starts = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut position = vec![0.0; DIMENSION];
            position[0] = omega;
            position
        })
        .collect::<Vec<_>>();
    let initial_hashes = starts
        .iter()
        .map(|start| arms::initial_position_sha256(start))
        .collect::<Vec<_>>();
    heartbeat.event("initialization", "after")?;

    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .threads(CHAINS)
        .seed(cfg.seed)
        .metric(Metric::diagonal())
        .adaptation(arms::adaptation(cfg.arm)?)
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let admission_bound = sampler.worst_case_target_evaluations(CHAINS)?;

    heartbeat.event("sampling", "before")?;
    let begin = Instant::now();
    let result = sampler.run(&target, &starts);
    let wall_seconds = begin.elapsed().as_secs_f64();
    heartbeat.event("sampling", "after")?;
    let posterior = match result {
        Ok(posterior) => posterior,
        Err(error) => {
            let payload = json!({
                "schema": "chain-rescue-v2-funnel-raw",
                "schema_version": 1,
                "complete": true,
                "telemetry_complete": false,
                "telemetry_unknown": true,
                "rescue_history": "unavailable",
                "status": "sampler_error",
                "stage": "run",
                "error": error.to_string(),
                "target": TARGET_NAME,
                "arm": cfg.arm.as_str(),
                "seed": cfg.seed,
                "chains": CHAINS,
                "warmup": WARMUP,
                "retained": RETAINED,
                "threads": CHAINS,
                "dimension": DIMENSION,
                "initial_positions": starts,
                "initial_position_sha256": initial_hashes,
                "wall_seconds": wall_seconds,
                "warmup_config": arms::warmup_json(cfg.arm),
                "tuning": {
                    "step_size": kernel.step_size(),
                    "max_depth": kernel.max_depth(),
                    "min_micro_steps": kernel.min_micro_steps(),
                    "max_refinement_levels": kernel.max_refinement_levels(),
                    "max_error": kernel.max_error(),
                    "divergence_threshold": kernel.divergence_threshold(),
                    "u_turn": format!("{:?}", kernel.options().u_turn),
                    "exhaustion": format!("{:?}", kernel.options().exhaustion),
                },
                "algorithm_revision": ALGORITHM_REVISION,
                "chains_data": null,
                "actions": null,
            });
            heartbeat.event("result", "before")?;
            write_result(&cfg.output, &payload)?;
            heartbeat.event("result", "after")?;
            heartbeat.event("drop", "before")?;
            heartbeat.event("drop", "after")?;
            heartbeat.event("process", "complete")?;
            return Ok(());
        }
    };

    let chains_data = posterior
        .chains()
        .iter()
        .enumerate()
        .map(|(index, chain)| {
            if arms::initial_position_sha256(chain.metadata().initial_position())
                != initial_hashes[index]
            {
                return Err(format!("chain {index} metadata initial position changed"));
            }
            Ok(arms::chain_json(
                TARGET_NAME,
                cfg.seed,
                cfg.arm,
                chain,
                index,
                WARMUP,
                &initial_hashes,
            ))
        })
        .collect::<Result<Vec<_>, String>>()?;
    let actions = chains_data
        .iter()
        .flat_map(|chain| {
            chain["chain_rescues"]
                .as_array()
                .into_iter()
                .flatten()
                .filter(|event| event["outcome"] == "restarted")
                .cloned()
        })
        .collect::<Vec<_>>();
    let target_calls_total = posterior
        .chains()
        .iter()
        .map(|chain| chain.telemetry().target_calls_including_adaptation())
        .sum::<usize>();
    let below = posterior
        .chains()
        .iter()
        .flat_map(|chain| (0..chain.retained()).map(move |draw| chain.sample(draw).unwrap()[0]))
        .filter(|omega| *omega < -5.0)
        .count();
    let total = CHAINS * RETAINED;
    let payload = json!({
        "schema": "chain-rescue-v2-funnel-raw",
        "schema_version": 1,
        "complete": true,
        "telemetry_complete": true,
        "telemetry_unknown": false,
        "rescue_history": "complete",
        "status": "ok",
        "target": TARGET_NAME,
        "arm": cfg.arm.as_str(),
        "seed": cfg.seed,
        "dimension": DIMENSION,
        "chains": CHAINS,
        "warmup": WARMUP,
        "retained": RETAINED,
        "threads": CHAINS,
        "initial_positions": starts,
        "initial_position_sha256": initial_hashes,
        "exact_tail_probability": EXACT_TAIL_MASS,
        "tail_count": below,
        "tail_total": total,
        "tuning": {
            "step_size": kernel.step_size(),
            "max_depth": kernel.max_depth(),
            "min_micro_steps": kernel.min_micro_steps(),
            "max_refinement_levels": kernel.max_refinement_levels(),
            "max_error": kernel.max_error(),
            "divergence_threshold": kernel.divergence_threshold(),
            "u_turn": format!("{:?}", kernel.options().u_turn),
            "exhaustion": format!("{:?}", kernel.options().exhaustion),
            "source": "owalnuts::sampler::Tuning::default()",
        },
        "warmup_config": arms::warmup_json(cfg.arm),
        "constructor_admission_bound": admission_bound,
        "wall_seconds": wall_seconds,
        "target_calls_total": target_calls_total,
        "chains_data": chains_data,
        "actions": actions,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    heartbeat.event("result", "before")?;
    write_result(&cfg.output, &payload)?;
    heartbeat.event("result", "after")?;
    let action_count = payload["actions"].as_array().map_or(0, Vec::len);

    heartbeat.event("drop", "before")?;
    drop(posterior);
    heartbeat.event("drop", "after")?;
    heartbeat.event("process", "complete")?;
    eprintln!(
        "funnel {} seed {}: tail {:.5}, {} calls, {} actions, {:.3}s",
        cfg.arm.as_str(),
        cfg.seed,
        below as f64 / total as f64,
        target_calls_total,
        action_count,
        wall_seconds
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result = Config::parse(&args).and_then(|cfg| run(&cfg));
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
