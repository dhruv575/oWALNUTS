//! The four arms of the joint default study, shared by the three binaries.
//!
//! | arm | `KernelOptions::u_turn` | diagonal-metric regularisation |
//! |---|---|---|
//! | `da` | `Endpoints` (current default) | `TowardUnit` (current default) |
//! | `rhosum` | `MomentumSum` | `TowardUnit` |
//! | `stanreg` | `Endpoints` | `Stan` |
//! | `joint` | `MomentumSum` | `Stan` |
//!
//! Everything else is the `sampler` default at freeze (`Tuning::default()`:
//! `h0 = 0.5`, depth 10, eight refinement levels, `delta = 1`;
//! `Adaptation::default()` = dual averaging at 0.8 with the WP24 warmup
//! exhaustion rule; adapted diagonal metric; cached initial evaluation).
#![allow(dead_code)]

use owalnuts::sampler::{Adaptation, DEFAULT_WARMUP_EXHAUSTION, WarmupConfig};
use owalnuts::walnutpie::{DiagonalMetricRegularization, KernelOptions, UTurnRule};
use std::error::Error;

pub const ARMS: [&str; 4] = ["da", "rhosum", "stanreg", "joint"];

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    pub u_turn: UTurnRule,
    pub regularization: DiagonalMetricRegularization,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let (u_turn, regularization) = match name {
            "da" => (
                UTurnRule::Endpoints,
                DiagonalMetricRegularization::TowardUnit,
            ),
            "rhosum" => (
                UTurnRule::MomentumSum,
                DiagonalMetricRegularization::TowardUnit,
            ),
            "stanreg" => (UTurnRule::Endpoints, DiagonalMetricRegularization::Stan),
            "joint" => (UTurnRule::MomentumSum, DiagonalMetricRegularization::Stan),
            other => {
                return Err(
                    format!("unknown arm {other:?} (expected da|rhosum|stanreg|joint)").into(),
                );
            }
        };
        let name = ARMS
            .iter()
            .copied()
            .find(|a| *a == name)
            .expect("matched above");
        Ok(Self {
            name,
            u_turn,
            regularization,
        })
    }

    pub fn kernel_options(&self) -> KernelOptions {
        KernelOptions {
            u_turn: self.u_turn,
            ..KernelOptions::default()
        }
    }

    /// The sampler's default dual-averaging warmup (`Adaptation::default()`
    /// builds exactly `WarmupConfig::new(0.8)` with
    /// `DEFAULT_WARMUP_EXHAUSTION`) plus the arm's regularisation. The
    /// `TowardUnit` arms return `Adaptation::default()` itself so that the
    /// baseline is literally the shipped default.
    pub fn adaptation(&self, target_accept: f64) -> Result<Adaptation, Box<dyn Error>> {
        Ok(match self.regularization {
            DiagonalMetricRegularization::TowardUnit if target_accept == 0.8 => {
                Adaptation::default()
            }
            regularization => Adaptation::Custom(
                WarmupConfig::new(target_accept)?
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                    .with_metric_regularization(regularization),
            ),
        })
    }
}
