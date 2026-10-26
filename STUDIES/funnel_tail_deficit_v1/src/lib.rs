//! WP66 `funnel_tail_deficit_v1`: the four preregistered arms. Each is the
//! shipped sampler default (`Tuning::default()`, `Adaptation::default()`,
//! `Metric::diagonal()`, `Limits::new().admit_worst_case()`) with at most one
//! builder override.
//!
//! | arm | override | hypothesis |
//! |---|---|---|
//! | `default` | none (the control) | — |
//! | `accept0.9` | `Adaptation::DualAveraging { target_accept: 0.9 }` | H1 step adaptation |
//! | `levels10` | `Tuning::default().max_refinement_levels(10)` | H2 refinement ceiling |
//! | `endpoint` | `Tuning::default().kernel_options(KernelOptions::default())` | H3 U-turn rule |
#![forbid(unsafe_code)]

use owalnuts::sampler::{Adaptation, Tuning};
use owalnuts::walnutpie::KernelOptions;

pub const ARMS: [&str; 4] = ["default", "accept0.9", "levels10", "endpoint"];

pub fn arm(name: &str) -> Result<(Tuning, Adaptation), String> {
    match name {
        "default" => Ok((Tuning::default(), Adaptation::default())),
        "accept0.9" => Ok((
            Tuning::default(),
            Adaptation::DualAveraging { target_accept: 0.9 },
        )),
        "levels10" => Ok((
            Tuning::default().max_refinement_levels(10),
            Adaptation::default(),
        )),
        "endpoint" => Ok((
            Tuning::default().kernel_options(KernelOptions::default()),
            Adaptation::default(),
        )),
        other => Err(format!("unknown arm {other:?} (one of {ARMS:?})")),
    }
}
