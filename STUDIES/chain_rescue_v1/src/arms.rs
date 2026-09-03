//! The three arms of `STUDIES/chain_rescue_v1`, defined once.
//!
//! `da` is the shipped default (`Adaptation::default()`); `restart` and
//! `pool` are the same dual-averaging warmup (target 0.8, the WP24 warmup
//! exhaustion rule, Stan's regularisation, mass adaptation) with one
//! [`ChainRescueConfig`] attached through `Adaptation::Custom`.

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, WarmupConfig,
};
use owalnuts::walnutpie::{ChainRescueConfig, ChainRescueOutcome, RunTelemetry};
use serde_json::{Value, json};

pub const TARGET_ACCEPT: f64 = 0.8;

pub fn adaptation(arm: &str) -> Result<Adaptation, String> {
    let rescue = match arm {
        "da" => return Ok(Adaptation::default()),
        "restart" => ChainRescueConfig::restart_from_best(),
        "pool" => ChainRescueConfig::pool_at_boundaries(),
        other => return Err(format!("unknown arm {other:?} (expected da|restart|pool)")),
    };
    let warmup = WarmupConfig::new(TARGET_ACCEPT)
        .map_err(|e| e.to_string())?
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
        .with_chain_rescue(rescue);
    Ok(Adaptation::Custom(warmup))
}

pub fn warmup_json(arm: &str) -> Value {
    let rescue = match arm {
        "restart" => Some(ChainRescueConfig::restart_from_best()),
        "pool" => Some(ChainRescueConfig::pool_at_boundaries()),
        _ => None,
    };
    json!({
        "mode": "dual_averaging",
        "target_accept": TARGET_ACCEPT,
        "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
        "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
        "mass_adaptation": true,
        "chain_rescue": rescue.map(|r| json!({
            "mode": format!("{:?}", r.mode()),
            "step_ratio": r.step_ratio(),
            "log_density_iqr_factor": r.log_density_iqr_factor(),
            "minimum_window_transitions": r.minimum_window_transitions(),
        })),
    })
}

/// Every rescue boundary record of one chain as JSON.
pub fn rescues_json(telemetry: &RunTelemetry) -> Vec<Value> {
    telemetry
        .chain_rescues()
        .iter()
        .map(|u| {
            let outcome = match u.outcome() {
                ChainRescueOutcome::Kept => json!({"kind": "kept"}),
                ChainRescueOutcome::Skipped(reason) => {
                    json!({"kind": "skipped", "reason": format!("{reason:?}")})
                }
                ChainRescueOutcome::Restarted {
                    source,
                    criterion,
                    source_position,
                    step_after,
                } => json!({"kind": "restarted", "source": source,
                            "criterion": format!("{criterion:?}"),
                            "source_position": source_position, "step_after": step_after}),
                ChainRescueOutcome::Pooled {
                    step_after,
                    pooled_sample_count,
                } => json!({"kind": "pooled", "step_after": step_after,
                            "pooled_sample_count": pooled_sample_count}),
                _ => json!({"kind": "other"}),
            };
            json!({
                "window_index": u.window_index(),
                "transition": u.transition(),
                "chain": u.chain(),
                "window_transitions": u.window_transitions(),
                "step_before": u.step_before(),
                "median_log_density": u.median_log_density(),
                "log_density_iqr": u.log_density_iqr(),
                "outcome": outcome,
            })
        })
        .collect()
}
