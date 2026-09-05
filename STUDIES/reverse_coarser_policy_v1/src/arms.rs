//! The two arms of the reverse-coarser policy study, shared by both binaries.
//!
//! Both arms are the shipped `sampler` defaults (`Tuning::default()`: `h0
//! 0.5`, depth 10, eight refinement levels, `delta = 1`, `MomentumSum`;
//! `Adaptation::default()`: dual averaging at 0.8 on the coarse-endpoint
//! statistic with the Stan regularisation and the WP24 warmup exhaustion
//! rule; `Metric::diagonal()`) and differ only in
//! `Tuning::reverse_coarser_policy`:
//!
//! | arm | policy | what happens at a refined leaf whose reverse check fails |
//! |---|---|---|
//! | `stop` | `ReverseCoarserPolicy::StopOrbit` (the default) | the doubling is discarded and the orbit ends |
//! | `beyond` | `ReverseCoarserPolicy::ZeroWeightBeyond` | the leaf's endpoint and every leaf beyond it in that direction are kept at zero weight; the orbit runs on to its U-turn or the depth cap |
//!
//! `stop` is literally `Tuning::default()`, so its cells are the shipped
//! sampler (bit-identical to `refinement_role_v1`'s `da` arm at equal seeds).
#![allow(dead_code)]

use owalnuts::sampler::{Adaptation, ReverseCoarserPolicy, Tuning};
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 2] = ["stop", "beyond"];

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    pub policy: ReverseCoarserPolicy,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let policy = match name {
            "stop" => ReverseCoarserPolicy::StopOrbit,
            "beyond" => ReverseCoarserPolicy::ZeroWeightBeyond,
            other => {
                return Err(format!("unknown arm {other:?} (expected one of {ARMS:?})").into());
            }
        };
        let name = ARMS.iter().copied().find(|a| *a == name).expect("matched");
        Ok(Self { name, policy })
    }

    pub fn is_default(&self) -> bool {
        self.policy == ReverseCoarserPolicy::StopOrbit
    }

    /// `Tuning::default()` itself for `stop`; the same with the policy
    /// switched for `beyond`.
    pub fn tuning(&self) -> Tuning {
        if self.is_default() {
            Tuning::default()
        } else {
            Tuning::default().reverse_coarser_policy(self.policy)
        }
    }

    /// The shipped adaptation for both arms.
    pub fn adaptation(&self) -> Adaptation {
        Adaptation::default()
    }

    pub fn json(&self) -> serde_json::Value {
        json!({
            "arm": self.name,
            "reverse_coarser_policy": format!("{:?}", self.policy),
            "tuning": if self.is_default() { "owalnuts::sampler::Tuning::default()" } else { "owalnuts::sampler::Tuning::default().reverse_coarser_policy(ZeroWeightBeyond)" },
            "adaptation": "owalnuts::sampler::Adaptation::default()",
            "mass_adaptation": true,
        })
    }
}
