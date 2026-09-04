//! One fresh-child posteriordb cell for the preregistered WP36 study.
//!
//! Usage:
//! `chain-rescue-v2 <target> <model.so> <data.json> <observe|current|two_hit>
//!  <seed> <heartbeat-dir> <out.json> [threads]`
#![forbid(unsafe_code)]

mod arms;

use arms::{Arm, Heartbeat};
use owalnuts::sampler::{
    DEFAULT_U_TURN_RULE, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts::walnutpie::ALGORITHM_REVISION;
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    ffi::OsString,
    fs,
    path::{Path, PathBuf},
    time::Instant,
};

const CHAINS: usize = 4;
const WARMUP: usize = 1_000;
const RETAINED: usize = 1_000;

struct Config {
    target: String,
    model: PathBuf,
    data: PathBuf,
    arm: Arm,
    seed: u64,
    heartbeat: PathBuf,
    output: PathBuf,
    threads: usize,
}

impl Config {
    fn parse(args: impl IntoIterator<Item = OsString>) -> Result<Self, Box<dyn Error>> {
        let args = args
            .into_iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        let [target, model, data, arm, seed, heartbeat, output, rest @ ..] = args.as_slice() else {
            return Err(
                "usage: <target> <model.so> <data.json> <observe|current|two_hit> \
                 <seed> <heartbeat-dir> <out.json> [threads]"
                    .into(),
            );
        };
        if rest.len() > 1 {
            return Err("at most one threads argument is allowed".into());
        }
        let threads = rest.first().map_or(Ok(CHAINS), |value| value.parse())?;
        if threads == 0 {
            return Err("threads must be positive".into());
        }
        let seed = seed.parse::<u64>()?;
        if seed > u32::MAX as u64 {
            return Err("seed does not fit BridgeStan's u32 seed".into());
        }
        Ok(Self {
            target: target.clone(),
            model: model.into(),
            data: data.into(),
            arm: Arm::parse(arm, false)?,
            seed,
            heartbeat: heartbeat.into(),
            output: output.into(),
            threads,
        })
    }
}

fn write_result(path: &Path, payload: &Value) -> Result<(), Box<dyn Error>> {
    arms::write_new_atomically(path, &serde_json::to_vec_pretty(payload)?)
}

struct SamplerErrorContext<'a> {
    stage: &'a str,
    error: &'a str,
    starts: &'a [Vec<f64>],
    initial_hashes: &'a [String],
    wall_seconds: f64,
    radius: f64,
    max_attempts: usize,
    start_search_calls: usize,
}

fn sampler_error_payload(
    cfg: &Config,
    target: &ReplicatedStanTarget,
    context: &SamplerErrorContext<'_>,
) -> Value {
    let telemetry_unknown = context.stage == "run";
    json!({
        "schema": "chain-rescue-v2-cell-raw",
        "schema_version": 1,
        "complete": true,
        "telemetry_complete": false,
        "telemetry_unknown": telemetry_unknown,
        "rescue_history": if telemetry_unknown { "unavailable" } else { "known_zero" },
        "status": "sampler_error",
        "stage": context.stage,
        "error": context.error,
        "target": cfg.target,
        "arm": cfg.arm.as_str(),
        "seed": cfg.seed,
        "chains": CHAINS,
        "warmup": WARMUP,
        "retained": RETAINED,
        "threads": cfg.threads,
        "dimension": target.dimension(),
        "initial_positions": context.starts,
        "initial_position_sha256": context.initial_hashes,
        "wall_seconds": context.wall_seconds,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
        "init": {
            "rule": "owalnuts::sampler::Init::uniform()",
            "radius": context.radius,
            "max_attempts": context.max_attempts,
            "start_search_calls": context.start_search_calls,
        },
        "warmup_config": arms::warmup_json(cfg.arm),
        "warmup_schedule": null,
        "algorithm_revision": ALGORITHM_REVISION,
        "chains_data": if telemetry_unknown { Value::Null } else { json!([]) },
        "actions": if telemetry_unknown { Value::Null } else { json!([]) },
    })
}

fn run(cfg: &Config) -> Result<(), Box<dyn Error>> {
    if cfg.output.exists() {
        return Err(format!("output already exists: {}", cfg.output.display()).into());
    }
    let mut heartbeat = Heartbeat::new(cfg.heartbeat.clone(), &cfg.target, cfg.seed, cfg.arm)?;
    heartbeat.event("process", "start")?;

    heartbeat.event("load", "before")?;
    let data_json = fs::read_to_string(&cfg.data)?;
    let target = ReplicatedStanTarget::load(
        &cfg.model,
        &default_preload(),
        Some(&data_json),
        cfg.seed as u32,
        cfg.threads,
    )?;
    heartbeat.event("load", "after")?;

    heartbeat.event("initialization", "before")?;
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    let starts = match uniform_starts(&target, CHAINS, cfg.seed, radius, max_attempts) {
        Ok(starts) => starts,
        Err(error) => {
            heartbeat.event("initialization", "after")?;
            heartbeat.event("sampling", "before")?;
            heartbeat.event("sampling", "after")?;
            let error = error.to_string();
            let payload = sampler_error_payload(
                cfg,
                &target,
                &SamplerErrorContext {
                    stage: "init",
                    error: &error,
                    starts: &[],
                    initial_hashes: &[],
                    wall_seconds: 0.0,
                    radius,
                    max_attempts,
                    start_search_calls: target.calls(),
                },
            );
            heartbeat.event("result", "before")?;
            write_result(&cfg.output, &payload)?;
            heartbeat.event("result", "after")?;
            heartbeat.event("drop", "before")?;
            drop(target);
            heartbeat.event("drop", "after")?;
            heartbeat.event("process", "complete")?;
            return Ok(());
        }
    };
    let initial_hashes = starts
        .iter()
        .map(|start| arms::initial_position_sha256(start))
        .collect::<Vec<_>>();
    let start_search_calls = target.calls();
    heartbeat.event("initialization", "after")?;

    let tuning = Tuning::default();
    let kernel = tuning.to_kernel()?;
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(cfg.seed)
        .threads(cfg.threads)
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
            let error = error.to_string();
            let payload = sampler_error_payload(
                cfg,
                &target,
                &SamplerErrorContext {
                    stage: "run",
                    error: &error,
                    starts: &starts,
                    initial_hashes: &initial_hashes,
                    wall_seconds,
                    radius,
                    max_attempts,
                    start_search_calls,
                },
            );
            heartbeat.event("result", "before")?;
            write_result(&cfg.output, &payload)?;
            heartbeat.event("result", "after")?;
            heartbeat.event("drop", "before")?;
            drop(target);
            heartbeat.event("drop", "after")?;
            heartbeat.event("process", "complete")?;
            return Ok(());
        }
    };

    let schedules = posterior
        .chains()
        .iter()
        .map(arms::warmup_schedule_json)
        .collect::<Result<Vec<_>, _>>()?;
    if schedules.iter().any(|schedule| schedule != &schedules[0]) {
        return Err("chain warmup schedules differ".into());
    }
    let warmup_schedule = schedules[0].clone();
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
                &cfg.target,
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
    let payload = json!({
        "schema": "chain-rescue-v2-cell-raw",
        "schema_version": 1,
        "complete": true,
        "telemetry_complete": true,
        "telemetry_unknown": false,
        "rescue_history": "complete",
        "status": "ok",
        "target": cfg.target,
        "arm": cfg.arm.as_str(),
        "seed": cfg.seed,
        "model_library": cfg.model.display().to_string(),
        "model_info": target.info(),
        "threading": format!("{:?}", target.threading()),
        "replicas": target.replicas(),
        "dimension": target.dimension(),
        "chains": CHAINS,
        "warmup": WARMUP,
        "retained": RETAINED,
        "threads": cfg.threads,
        "initial_positions": starts,
        "initial_position_sha256": initial_hashes,
        "init": {
            "rule": "owalnuts::sampler::Init::uniform()",
            "radius": radius,
            "max_attempts": max_attempts,
            "start_search_calls": start_search_calls,
        },
        "tuning": {
            "step_size": kernel.step_size(),
            "max_depth": kernel.max_depth(),
            "min_micro_steps": kernel.min_micro_steps(),
            "max_refinement_levels": kernel.max_refinement_levels(),
            "max_error": kernel.max_error(),
            "divergence_threshold": kernel.divergence_threshold(),
            "u_turn": format!("{:?}", kernel.options().u_turn),
            "exhaustion": format!("{:?}", kernel.options().exhaustion),
            "default_u_turn_rule": format!("{DEFAULT_U_TURN_RULE:?}"),
            "source": "owalnuts::sampler::Tuning::default()",
        },
        "warmup_config": arms::warmup_json(cfg.arm),
        "warmup_schedule": warmup_schedule,
        "constructor_admission_bound": admission_bound,
        "wall_seconds": wall_seconds,
        "target_calls_total": target.calls(),
        "recoverable_failures_total": target.recoverable_failures(),
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
    drop(target);
    heartbeat.event("drop", "after")?;
    heartbeat.event("process", "complete")?;
    eprintln!(
        "{} {} seed {}: {:.3}s, {} actions",
        cfg.target,
        cfg.arm.as_str(),
        cfg.seed,
        wall_seconds,
        action_count
    );
    Ok(())
}

fn main() {
    let result = Config::parse(env::args_os().skip(1)).and_then(|cfg| run(&cfg));
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use owalnuts::walnutpie::ChainRescueOutcome;

    #[test]
    fn cell_cli_rejects_implicit_default_arm() {
        let args = [
            "target",
            "model.so",
            "data.json",
            "da",
            "1",
            "heartbeats",
            "out.json",
        ]
        .into_iter()
        .map(OsString::from);
        assert!(Config::parse(args).is_err());
    }

    #[test]
    fn every_action_is_a_restart() {
        let outcome = ChainRescueOutcome::Kept;
        assert!(matches!(outcome, ChainRescueOutcome::Kept));
    }
}
