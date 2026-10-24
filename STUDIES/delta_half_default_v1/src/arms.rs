//! The three arms of the delta-half study (WP42), shared by the three binaries.
//!
//! Every arm is the shipped `sampler` default (`Tuning::default()`: `h0 0.5`,
//! depth 10, eight refinement levels, `MomentumSum`; `Adaptation::default()`:
//! dual averaging at 0.8 on the coarse-endpoint statistic; `Metric::diagonal()`
//! with the Stan regularisation; the WP24 warmup exhaustion rule) except for
//! the local error bound `delta` (`Tuning::max_error`):
//!
//! | arm | `delta` |
//! |---|---|
//! | `d1` | 1 (the default; literally `Tuning::default()`) |
//! | `d075` | 0.75 |
//! | `d05` | 0.5 |
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION,
    Tuning, WarmupConfig,
};
use owalnuts::walnutpie::KernelOptions;
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 3] = ["d1", "d075", "d05"];

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    /// `Tuning::max_error` (`delta`).
    pub max_error: f64,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let max_error = match name {
            "d1" => 1.0,
            "d075" => 0.75,
            "d05" => 0.5,
            other => {
                return Err(format!("unknown arm {other:?} (expected one of {ARMS:?})").into());
            }
        };
        let name = ARMS
            .iter()
            .copied()
            .find(|a| *a == name)
            .expect("matched above");
        Ok(Self { name, max_error })
    }

    pub fn is_default(&self) -> bool {
        self.name == "d1"
    }

    /// The sampler's kernel options: the shipped default (`MomentumSum`).
    pub fn kernel_options(&self) -> KernelOptions {
        KernelOptions {
            u_turn: DEFAULT_U_TURN_RULE,
            ..KernelOptions::default()
        }
    }

    /// `Tuning::default()` with the arm's `delta`; literally the default for `d1`.
    pub fn tuning(&self) -> Tuning {
        if self.is_default() {
            Tuning::default()
        } else {
            Tuning::default().max_error(self.max_error)
        }
    }

    /// The shipped adaptation for every arm.
    pub fn adaptation(&self) -> Result<Adaptation, Box<dyn Error>> {
        Ok(Adaptation::default())
    }

    /// The Eight Schools strict track's `WarmupConfig::new(strict_target)` with
    /// mass adaptation and the default regularisation (unchanged across arms).
    pub fn facade_warmup(&self, strict_target: f64) -> Result<WarmupConfig, Box<dyn Error>> {
        Ok(WarmupConfig::new(strict_target)?
            .with_mass_adaptation(true)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION))
    }

    pub fn json(&self) -> serde_json::Value {
        json!({
            "arm": self.name, "mode": "dual_averaging (Adaptation::default())", "target_accept": 0.8,
            "max_error": self.max_error,
            "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
            "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
            "u_turn": format!("{DEFAULT_U_TURN_RULE:?}"),
            "mass_adaptation": true,
        })
    }
}
