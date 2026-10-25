//! The arms of the scale-free regularisation study (WP41), shared by both
//! binaries. Every arm is the shipped `sampler` default (`Tuning::default()`:
//! `h0 0.5`, depth 10, eight refinement levels, `MomentumSum`, `delta 1`;
//! `Metric::diagonal()`; dual averaging at 0.8 on the coarse-endpoint
//! statistic; the WP24 warmup exhaustion rule; no chain rescue) except for
//! the diagonal-metric regularisation applied at each slow-window boundary:
//!
//! | arm | `DiagonalMetricRegularization` | installed variance (`n` window draws, `m` = median over coordinates of the window variances) |
//! |---|---|---|
//! | `da` | `Stan` (the shipped default, through `Adaptation::default()`) | `(n/(n+5)) var_i + 1e-3 * 5/(n+5)` |
//! | `sfmed` | `ScaleFreeMedian` (primary) | `(n/(n+5)) var_i + (5/(n+5)) * m` |
//! | `sfstan` | `ScaleFreeStanMedian` (secondary) | `(n/(n+5)) var_i + 1e-3 * (5/(n+5)) * m` |
//!
//! Both scale-free arms fall back to the anchor `m = 1` for a window whose
//! median variance is not finite and positive.
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE,
    DEFAULT_WARMUP_EXHAUSTION, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::DiagonalMetricRegularization;
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 3] = ["da", "sfmed", "sfstan"];

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    pub regularization: DiagonalMetricRegularization,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let regularization = match name {
            "da" => DEFAULT_METRIC_REGULARIZATION,
            "sfmed" => DiagonalMetricRegularization::ScaleFreeMedian,
            "sfstan" => DiagonalMetricRegularization::ScaleFreeStanMedian,
            other => {
                return Err(format!("unknown arm {other:?} (expected one of {ARMS:?})").into());
            }
        };
        let name = ARMS
            .iter()
            .copied()
            .find(|a| *a == name)
            .expect("matched above");
        Ok(Self {
            name,
            regularization,
        })
    }

    pub fn is_default(&self) -> bool {
        self.name == "da"
    }

    pub fn tuning(&self) -> Tuning {
        Tuning::default()
    }

    /// `da` is literally `Adaptation::default()`. The scale-free arms are the
    /// same `WarmupConfig` that `Adaptation::DualAveraging { 0.8 }` builds
    /// (`WarmupConfig::new(0.8)`, the default warmup exhaustion rule, no
    /// chain rescue because `DEFAULT_CHAIN_RESCUE` is `None`) with the
    /// regularisation switched.
    pub fn adaptation(&self) -> Result<Adaptation, Box<dyn Error>> {
        assert!(
            DEFAULT_CHAIN_RESCUE.is_none(),
            "the arms assume the shipped default has no chain rescue"
        );
        Ok(if self.is_default() {
            Adaptation::default()
        } else {
            Adaptation::Custom(
                WarmupConfig::new(0.8)?
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                    .with_metric_regularization(self.regularization),
            )
        })
    }

    pub fn json(&self) -> serde_json::Value {
        json!({
            "arm": self.name, "mode": "dual_averaging", "target_accept": 0.8,
            "metric_regularization": format!("{:?}", self.regularization),
            "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
            "u_turn": format!("{DEFAULT_U_TURN_RULE:?}"),
            "chain_rescue": format!("{DEFAULT_CHAIN_RESCUE:?}"),
            "source": if self.is_default() { "Adaptation::default()" } else { "Adaptation::Custom(WarmupConfig::new(0.8).with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION).with_metric_regularization(arm))" },
            "mass_adaptation": true,
        })
    }
}
