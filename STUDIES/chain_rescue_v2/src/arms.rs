//! Shared, explicit WP36 arm configuration and durable-record helpers.
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, WarmupConfig,
};
use owalnuts::walnutpie::{
    ChainOutput, ChainRescueConfig, ChainRescueOutcome, RunTelemetry, WorkTotals,
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{
    error::Error,
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{SystemTime, UNIX_EPOCH},
};

pub const TARGET_ACCEPT: f64 = 0.8;
pub const INITIAL_POSITION_DOMAIN: &[u8] = b"chain_rescue_v2.initial_position.v1";
pub const INSTALLED_POSITION_DOMAIN: &[u8] = b"chain_rescue_v2.installed_position.v1";

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Arm {
    Observe,
    Current,
    TwoHit,
    Disabled,
}

impl Arm {
    pub fn parse(value: &str, allow_disabled: bool) -> Result<Self, Box<dyn Error>> {
        match value {
            "observe" => Ok(Self::Observe),
            "current" => Ok(Self::Current),
            "two_hit" => Ok(Self::TwoHit),
            "disabled" if allow_disabled => Ok(Self::Disabled),
            _ => Err(format!(
                "unknown arm {value:?} (expected observe|current|two_hit{})",
                if allow_disabled { "|disabled" } else { "" }
            )
            .into()),
        }
    }

    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Observe => "observe",
            Self::Current => "current",
            Self::TwoHit => "two_hit",
            Self::Disabled => "disabled",
        }
    }

    pub const fn rescue(self) -> Option<ChainRescueConfig> {
        match self {
            Self::Observe => Some(ChainRescueConfig::observe_only()),
            Self::Current => Some(ChainRescueConfig::restart_from_best()),
            Self::TwoHit => Some(ChainRescueConfig::two_hit()),
            Self::Disabled => None,
        }
    }
}

/// Build every arm from an explicit custom warmup. This deliberately never
/// passes through `Adaptation::default()` or `DEFAULT_CHAIN_RESCUE`.
pub fn adaptation(arm: Arm) -> Result<Adaptation, Box<dyn Error>> {
    let mut warmup = WarmupConfig::new(TARGET_ACCEPT)?
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION);
    if let Some(rescue) = arm.rescue() {
        warmup = warmup.with_chain_rescue(rescue);
    }
    Ok(Adaptation::Custom(warmup))
}

pub fn warmup_json(arm: Arm) -> Value {
    let rescue = arm.rescue();
    json!({
        "mode": "dual_averaging",
        "target_accept": TARGET_ACCEPT,
        "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
        "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
        "mass_adaptation": true,
        "explicit_arm": true,
        "inherits_default_chain_rescue": false,
        "chain_rescue": rescue.map(|r| json!({
            "mode": format!("{:?}", r.mode()),
            "policy": format!("{:?}", r.policy()),
            "step_ratio": r.step_ratio(),
            "log_density_iqr_factor": r.log_density_iqr_factor(),
            "minimum_window_transitions": r.minimum_window_transitions(),
            "source_tie_rule": "larger step, then larger median log density, then higher chain index"
        })),
    })
}

fn hash_with_shape(domain: &[u8], rows: usize, columns: usize, values: &[f64]) -> String {
    let mut digest = Sha256::new();
    digest.update(domain);
    digest.update((rows as u64).to_le_bytes());
    digest.update((columns as u64).to_le_bytes());
    for value in values {
        digest.update(value.to_bits().to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

/// The exact initial-position encoding frozen in `protocol.json`.
pub fn initial_position_sha256(position: &[f64]) -> String {
    let mut digest = Sha256::new();
    digest.update(INITIAL_POSITION_DOMAIN);
    digest.update((position.len() as u64).to_le_bytes());
    for value in position {
        digest.update(value.to_bits().to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

pub fn installed_position_sha256(position: &[f64]) -> String {
    let mut digest = Sha256::new();
    digest.update(INSTALLED_POSITION_DOMAIN);
    digest.update((position.len() as u64).to_le_bytes());
    for value in position {
        digest.update(value.to_bits().to_le_bytes());
    }
    format!("{:x}", digest.finalize())
}

pub fn retained_unconstrained_sha256(chain: &ChainOutput) -> String {
    hash_with_shape(
        b"chain_rescue_v2.retained_unconstrained.v1",
        chain.retained(),
        chain.dimension(),
        chain.samples(),
    )
}

pub fn final_metric_sha256(chain: &ChainOutput) -> String {
    hash_with_shape(
        b"chain_rescue_v2.final_metric_diagonal.v1",
        1,
        chain.metadata().mass_diagonal().len(),
        chain.metadata().mass_diagonal(),
    )
}

fn hash_debug(domain: &[u8], value: &impl std::fmt::Debug) -> String {
    let mut digest = Sha256::new();
    digest.update(domain);
    digest.update(format!("{value:?}").as_bytes());
    format!("{:x}", digest.finalize())
}

pub fn final_tuning_sha256(chain: &ChainOutput) -> String {
    hash_debug(
        b"chain_rescue_v2.final_tuning_debug.v1",
        chain.metadata().tuning(),
    )
}

pub fn retained_diagnostics_sha256(chain: &ChainOutput, warmup: usize) -> String {
    hash_debug(
        b"chain_rescue_v2.retained_diagnostics_debug.v1",
        &&chain.diagnostics()[warmup..],
    )
}

pub fn non_rescue_telemetry_sha256(telemetry: &RunTelemetry) -> String {
    let value = (
        telemetry.discarded(),
        telemetry.retained(),
        telemetry.total(),
        telemetry.initial_step_search(),
        telemetry.initial_fast(),
        telemetry.slow(),
        telemetry.terminal_fast(),
        telemetry.step_searches(),
        telemetry.metric_updates(),
        telemetry.warmup_checkpoints(),
        telemetry.paper_adaptation_updates(),
    );
    hash_debug(b"chain_rescue_v2.non_rescue_telemetry_debug.v1", &value)
}

pub fn work_json(work: &WorkTotals) -> Value {
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
        "refinement_level_built": work.refinement_level_built(),
    })
}

pub fn rescues_json(
    target: &str,
    seed: u64,
    arm: Arm,
    telemetry: &RunTelemetry,
    initial_hashes: &[String],
) -> Vec<Value> {
    telemetry
        .chain_rescues()
        .iter()
        .map(|update| {
            let mut actual_source = None;
            let mut source_position = None;
            let mut installed_step = None;
            let (outcome, criterion) = match update.outcome() {
                ChainRescueOutcome::Kept => ("kept", None),
                ChainRescueOutcome::Skipped(_) => ("skipped", None),
                ChainRescueOutcome::ObservedHit { criterion } => {
                    ("observed_hit", Some(format!("{criterion:?}")))
                }
                ChainRescueOutcome::PendingFirstHit { criterion } => {
                    ("pending_first_hit", Some(format!("{criterion:?}")))
                }
                ChainRescueOutcome::Restarted {
                    source,
                    criterion,
                    source_position: index,
                    step_after,
                } => {
                    actual_source = Some(*source);
                    source_position = Some(*index);
                    installed_step = Some(*step_after);
                    ("restarted", Some(format!("{criterion:?}")))
                }
                ChainRescueOutcome::Pooled { .. } => ("invalid_pooled_outcome", None),
                _ => ("unknown", None),
            };
            let installed = update.installed_unconstrained_position();
            json!({
                "target": target,
                "seed": seed,
                "arm": arm.as_str(),
                "chain": update.chain(),
                "window_index": update.window_index(),
                "transition": update.transition(),
                "window_transitions": update.window_transitions(),
                "eligible": update.eligible(),
                "skip_reason": update.skip_reason().map(|x| format!("{x:?}")),
                "current_step": update.current_step(),
                "median_step": update.median_step(),
                "step_threshold": update.step_threshold(),
                "step_hit": update.step_hit(),
                "median_log_density": update.median_log_density(),
                "log_density_iqr": update.log_density_iqr(),
                "density_reference": update.density_reference(),
                "density_spread": update.density_spread(),
                "density_gap": update.density_gap(),
                "density_threshold": update.density_threshold(),
                "density_hit": update.density_hit(),
                "observed_canonical_criterion": update.observed_canonical_criterion().map(|x| format!("{x:?}")),
                "prior_criterion": update.prior_criterion().map(|x| format!("{x:?}")),
                "prior_streak": update.prior_streak(),
                "resulting_criterion": update.resulting_criterion().map(|x| format!("{x:?}")),
                "resulting_streak": update.resulting_streak(),
                "proposed_source_chain": update.proposed_source_chain(),
                "outcome": outcome,
                "outcome_criterion": criterion,
                "pre_action_unconstrained_position": update.pre_action_unconstrained_position(),
                "initial_position_sha256": initial_hashes[update.chain()],
                "actual_source_chain": actual_source,
                "source_window_position_index": source_position,
                "installed_step": installed_step,
                "installed_position_sha256": installed.map(installed_position_sha256),
            })
        })
        .collect()
}

pub fn chain_json(
    target: &str,
    seed: u64,
    arm: Arm,
    chain: &ChainOutput,
    chain_index: usize,
    warmup: usize,
    initial_hashes: &[String],
) -> Value {
    let retained = chain.telemetry().retained();
    let discarded = chain.telemetry().discarded();
    json!({
        "chain": chain_index,
        "initial_position": chain.metadata().initial_position(),
        "initial_position_sha256": initial_hashes[chain_index],
        "samples": (0..chain.retained()).map(|i| chain.sample(i).expect("retained draw")).collect::<Vec<_>>(),
        "retained_unconstrained_sha256": retained_unconstrained_sha256(chain),
        "retained_diagnostics_sha256": retained_diagnostics_sha256(chain, warmup),
        "non_rescue_telemetry_sha256": non_rescue_telemetry_sha256(chain.telemetry()),
        "final_metric_sha256": final_metric_sha256(chain),
        "final_tuning_sha256": final_tuning_sha256(chain),
        "final_step_size": chain.metadata().tuning().step_size(),
        "final_max_error": chain.metadata().tuning().max_error(),
        "mass_diagonal": chain.metadata().mass_diagonal(),
        "work": {
            "discarded": work_json(discarded),
            "retained": work_json(retained),
            "total": work_json(chain.telemetry().total()),
            "adaptation_target_calls": chain.telemetry().adaptation_target_calls(),
            "target_calls_including_adaptation": chain.telemetry().target_calls_including_adaptation(),
        },
        "retained_diagnostics": {
            "divergences": retained.divergences(),
            "maximum_depth_stops": retained.maximum_depth_stops(),
            "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
            "recoverable_target_failures": retained.recoverable_target_failures(),
            "zero_density_evaluations": retained.zero_density_evaluations(),
            "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
            "reverse_coarser_stops": retained.reverse_coarser_stops(),
            "reverse_coarser_rejections": retained.reverse_coarser_rejections(),
            "target_calls_total": retained.target_calls_total(),
        },
        "chain_rescues": rescues_json(target, seed, arm, chain.telemetry(), initial_hashes),
    })
}

pub fn write_new_atomically(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err(format!("refusing to replace existing file: {}", path.display()).into());
    }
    let parent = path
        .parent()
        .ok_or_else(|| format!("path has no parent: {}", path.display()))?;
    fs::create_dir_all(parent)?;
    let name = path
        .file_name()
        .ok_or_else(|| format!("path has no file name: {}", path.display()))?
        .to_string_lossy();
    let temporary = parent.join(format!(".{name}.tmp-{}", std::process::id()));
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
    fs::rename(temporary, path)?;
    Ok(())
}

pub struct Heartbeat {
    directory: PathBuf,
    sequence: usize,
    target: String,
    seed: u64,
    arm: Arm,
}

impl Heartbeat {
    pub fn new(
        directory: PathBuf,
        target: &str,
        seed: u64,
        arm: Arm,
    ) -> Result<Self, Box<dyn Error>> {
        fs::create_dir_all(&directory)?;
        Ok(Self {
            directory,
            sequence: 0,
            target: target.to_owned(),
            seed,
            arm,
        })
    }

    pub fn event(&mut self, stage: &str, boundary: &str) -> Result<(), Box<dyn Error>> {
        let sequence = self.sequence;
        let path = self
            .directory
            .join(format!("{sequence:04}-{stage}-{boundary}.json"));
        let payload = json!({
            "schema": "chain-rescue-v2-heartbeat",
            "sequence": sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "target": self.target,
            "seed": self.seed,
            "arm": self.arm.as_str(),
            "stage": stage,
            "boundary": boundary,
        });
        write_new_atomically(&path, &serde_json::to_vec_pretty(&payload)?)?;
        self.sequence += 1;
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn arms_are_explicit_and_frozen() {
        for arm in [Arm::Observe, Arm::Current, Arm::TwoHit] {
            let rescue = arm.rescue().expect("study arm has rescue config");
            assert_eq!(rescue.step_ratio(), 0.1);
            assert_eq!(rescue.log_density_iqr_factor(), 3.0);
            assert_eq!(rescue.minimum_window_transitions(), 10);
        }
        assert!(Arm::Disabled.rescue().is_none());
    }

    #[test]
    fn initial_hash_uses_frozen_little_endian_encoding() {
        let position = [-0.0, 1.5, f64::from_bits(0x7ff8_0000_0000_0042)];
        let mut independent = Sha256::new();
        independent.update(b"chain_rescue_v2.initial_position.v1");
        independent.update(3_u64.to_le_bytes());
        independent.update((-0.0_f64).to_bits().to_le_bytes());
        independent.update(1.5_f64.to_bits().to_le_bytes());
        independent.update(0x7ff8_0000_0000_0042_u64.to_le_bytes());
        assert_eq!(
            initial_position_sha256(&position),
            format!("{:x}", independent.finalize())
        );
    }
}
