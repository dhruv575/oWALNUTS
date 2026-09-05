//! The four arms of the second reverse-coarser policy study, shared by both
//! binaries.
//!
//! All arms are the shipped `sampler` defaults (`Tuning::default()`: `h0
//! 0.5`, depth 10, eight refinement levels, `delta = 1`, `MomentumSum`;
//! `Metric::diagonal()` with the Stan regularisation and the WP24 warmup
//! exhaustion rule) and differ in `Tuning::reverse_coarser_policy` and in
//! whether the step is adapted:
//!
//! | arm | policy | step |
//! |---|---|---|
//! | `stop` | `StopOrbit` (default) | `Adaptation::default()` (dual averaging 0.8) |
//! | `beyond-adapt` | `ZeroWeightBeyondAdaptSelected` | `Adaptation::default()` |
//! | `stop-fixed` | `StopOrbit` | fixed at the `stop` cell's adapted step (same model, same seed); mass still adapted |
//! | `beyond-fixed` | `ZeroWeightBeyond` | fixed at the same step |
//!
//! `stop` is literally `Tuning::default()` + `Adaptation::default()`. The
//! fixed-step arms use `Adaptation::Custom(WarmupConfig::new(0.8)
//! .with_step_size_adaptation(false))` with the default regularisation and
//! exhaustion rule, so the warmup adapts the mass as the default does and
//! never touches the step. At a fixed step `ZeroWeightBeyond` and
//! `ZeroWeightBeyondAdaptSelected` are bit-identical (the adaptation
//! statistic is unused), so `beyond-fixed` names the original variant.
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, ReverseCoarserPolicy,
    Tuning, WarmupConfig,
};
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 4] = ["stop", "beyond-adapt", "stop-fixed", "beyond-fixed"];

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    pub policy: ReverseCoarserPolicy,
    pub fixed_step: bool,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let (policy, fixed_step) = match name {
            "stop" => (ReverseCoarserPolicy::StopOrbit, false),
            "beyond-adapt" => (ReverseCoarserPolicy::ZeroWeightBeyondAdaptSelected, false),
            "stop-fixed" => (ReverseCoarserPolicy::StopOrbit, true),
            "beyond-fixed" => (ReverseCoarserPolicy::ZeroWeightBeyond, true),
            other => {
                return Err(format!("unknown arm {other:?} (expected one of {ARMS:?})").into());
            }
        };
        let name = ARMS.iter().copied().find(|a| *a == name).expect("matched");
        Ok(Self {
            name,
            policy,
            fixed_step,
        })
    }

    pub fn is_default(&self) -> bool {
        self.name == "stop"
    }

    /// `Tuning::default()` with the arm's policy and, for the fixed-step
    /// arms, the given step.
    pub fn tuning(&self, fixed_step: Option<f64>) -> Result<Tuning, Box<dyn Error>> {
        let mut tuning = Tuning::default();
        if self.policy != ReverseCoarserPolicy::StopOrbit {
            tuning = tuning.reverse_coarser_policy(self.policy);
        }
        match (self.fixed_step, fixed_step) {
            (true, Some(h)) => Ok(tuning.step_size(h)),
            (true, None) => Err(format!("arm {} needs a fixed step", self.name).into()),
            (false, Some(_)) => {
                Err(format!("arm {} does not take a fixed step", self.name).into())
            }
            (false, None) => Ok(tuning),
        }
    }

    pub fn adaptation(&self) -> Result<Adaptation, Box<dyn Error>> {
        Ok(if self.fixed_step {
            Adaptation::Custom(
                WarmupConfig::new(0.8)?
                    .with_step_size_adaptation(false)
                    .with_mass_adaptation(true)
                    .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION),
            )
        } else {
            Adaptation::default()
        })
    }

    pub fn json(&self, fixed_step: Option<f64>) -> serde_json::Value {
        json!({
            "arm": self.name,
            "reverse_coarser_policy": format!("{:?}", self.policy),
            "fixed_step": fixed_step,
            "adaptation": if self.fixed_step {
                "Adaptation::Custom(WarmupConfig::new(0.8).with_step_size_adaptation(false).with_mass_adaptation(true) + default regularisation and exhaustion rule)"
            } else { "owalnuts::sampler::Adaptation::default()" },
            "mass_adaptation": true,
        })
    }
}
