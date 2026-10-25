//! The arms of the adaptive-delta study (WP49), shared by the binaries.
//!
//! Every arm is the shipped `sampler` default (`Tuning::default()`: `h0 0.5`,
//! depth 10, eight refinement levels, `MomentumSum`; `Metric::diagonal()`
//! with the Stan regularisation; the WP24 warmup exhaustion rule; dual
//! averaging at 0.8 on the coarse-endpoint statistic) except for `delta`:
//!
//! | arm | `delta` |
//! |---|---|
//! | `da` | 1 (`Adaptation::default()` + `Tuning::default()`, literally the shipped default) |
//! | `d2` | fixed 2 (WP34's `da-d2`, rerun on this study's seeds) |
//! | `r1` | adapted: `clamp(R1_SCALE / q_0.99(|dH_0|), 1, 2)` at every slow-window boundary |
//! | `r2` | adapted: `clamp(q_0.985(|dH_0|), 0.5, 2)` at every slow-window boundary (refined-fraction target 1.5 %) |
//!
//! `r1` and `r2` start at `delta = 1` and use
//! `WarmupConfig::with_adaptive_delta` through `Adaptation::Custom` with the
//! same warmup settings `Adaptation::DualAveraging` installs (the default
//! exhaustion rule and regularisation, no chain rescue); that path is
//! bit-identical to `Adaptation::default()` when the option is off
//! (`tests/adaptive_delta.rs`).
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, AdaptiveDeltaConfig, AdaptiveDeltaRule, DEFAULT_METRIC_REGULARIZATION,
    DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::KernelOptions;
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 4] = ["da", "d2", "r1", "r2"];

/// R1: inverse tail quantile.
pub const R1_PROBABILITY: f64 = 0.99;
pub const R1_SCALE: f64 = 1.8;
pub const R1_BOUNDS: (f64, f64) = (1.0, 2.0);
/// R2: the fixed point of a refined-fraction controller at target 1.5 %.
pub const R2_PROBABILITY: f64 = 0.985;
pub const R2_SCALE: f64 = 1.0;
pub const R2_BOUNDS: (f64, f64) = (0.5, 2.0);

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    /// Fixed `delta`, or the initial `delta` of an adaptive arm.
    pub max_error: f64,
    pub adaptive: Option<AdaptiveDeltaConfig>,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let (max_error, adaptive) = match name {
            "da" => (1.0, None),
            "d2" => (2.0, None),
            "r1" => (
                1.0,
                Some(AdaptiveDeltaConfig::new(
                    AdaptiveDeltaRule::InverseQuantile {
                        probability: R1_PROBABILITY,
                        scale: R1_SCALE,
                    },
                    R1_BOUNDS.0,
                    R1_BOUNDS.1,
                )?),
            ),
            "r2" => (
                1.0,
                Some(AdaptiveDeltaConfig::new(
                    AdaptiveDeltaRule::QuantileScaled {
                        probability: R2_PROBABILITY,
                        scale: R2_SCALE,
                    },
                    R2_BOUNDS.0,
                    R2_BOUNDS.1,
                )?),
            ),
            other => {
                return Err(format!("unknown arm {other:?} (expected one of {ARMS:?})").into());
            }
        };
        let name = ARMS.iter().copied().find(|a| *a == name).expect("matched above");
        Ok(Self {
            name,
            max_error,
            adaptive,
        })
    }

    pub fn is_default(&self) -> bool {
        self.name == "da"
    }

    pub fn kernel_options(&self) -> KernelOptions {
        KernelOptions {
            u_turn: DEFAULT_U_TURN_RULE,
            ..KernelOptions::default()
        }
    }

    /// `Tuning::default()`, with `delta = 2` for `d2`.
    pub fn tuning(&self) -> Tuning {
        if self.max_error == 1.0 {
            Tuning::default()
        } else {
            Tuning::default().max_error(self.max_error)
        }
    }

    pub fn adaptation(&self) -> Result<Adaptation, Box<dyn Error>> {
        Ok(match self.adaptive {
            None => Adaptation::default(),
            Some(config) => Adaptation::Custom(
                WarmupConfig::new(0.8)?
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                    .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                    .with_adaptive_delta(config),
            ),
        })
    }

    /// The Eight Schools strict-track warmup (WP37A amendment A1:
    /// `WarmupConfig::new(0.95)`, mass adaptation, `AcceptUnlessDivergent`
    /// warmup exhaustion, Stan regularisation, no rescue) plus the arm's
    /// adaptive rule.
    pub fn facade_warmup(&self, strict_target: f64) -> Result<WarmupConfig, Box<dyn Error>> {
        let base = WarmupConfig::new(strict_target)?
            .with_mass_adaptation(true)
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION);
        Ok(match self.adaptive {
            None => base,
            Some(config) => base.with_adaptive_delta(config),
        })
    }

    pub fn json(&self) -> serde_json::Value {
        let adaptive = self.adaptive.map(|c| {
            json!({
                "rule": format!("{:?}", c.rule()),
                "min_max_error": c.min_max_error(),
                "max_max_error": c.max_max_error(),
                "minimum_leaves": c.minimum_leaves(),
            })
        });
        json!({
            "arm": self.name, "mode": "dual_averaging", "target_accept": 0.8,
            "dual_averaging_acceptance": "CurrentCoarseEndpoint",
            "initial_or_fixed_max_error": self.max_error,
            "adaptive_delta": adaptive,
            "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
            "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
            "u_turn": format!("{DEFAULT_U_TURN_RULE:?}"),
            "mass_adaptation": true,
        })
    }
}

/// JSON of a chain's adaptive-delta trajectory (one record per slow window).
pub fn delta_trajectory(updates: &[owalnuts::sampler::AdaptiveDeltaUpdate]) -> serde_json::Value {
    json!(
        updates
            .iter()
            .map(|u| json!({
                "transition": u.transition(),
                "window_index": u.window_index(),
                "leaves": u.leaves(),
                "quantile": u.quantile(),
                "candidate": u.candidate(),
                "max_error_before": u.max_error_before(),
                "max_error_after": u.max_error_after(),
                "step": u.step(),
                "fraction_above_before": u.fraction_above_before(),
                "outcome": format!("{:?}", u.outcome()),
            }))
            .collect::<Vec<_>>()
    )
}
