//! WP82 `centered_eight_schools_refinement_v1`: the four preregistered oWALNUTS
//! arms, shared by the posteriordb harness (`src/main.rs`) and the funnel
//! binary (`src/bin/funnel.rs`) so that both run exactly the same settings.
//! The structure is WP73's / WP77's `src/lib.rs`; the arms are new.
//!
//! Every arm is the shipped sampler default (`Tuning::default()`,
//! `Metric::default()`, `Init::default()`, `Adaptation::default()`) with one
//! override. The adaptation candidates are `Adaptation::Custom` around
//! [`house_warmup`], the configuration `Adaptation::default()` builds
//! (`tests/stable_metric_stop.rs::custom_house_warmup_is_the_default` pins
//! that the two are bit-identical).
//!
//! | arm | override |
//! |---|---|
//! | `default` | none |
//! | `costda` | dual averaging on `DualAveragingAcceptance::CostWeightedCoarseEndpoint` (WP82 research flag): each leaf's coarse value weighted by its target evaluations |
//! | `stanacc` | dual averaging on `DualAveragingAcceptance::MeanTrajectoryAcceptance` (Stan's `accept_stat__`, existing opt-in) |
//! | `levels2` | `Tuning::max_refinement_levels(2)`: at most one halving; a leaf over `delta` at both levels is rejected (refinement exhaustion ends the orbit), warmup under the sampler's warmup exhaustion rule |
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::DualAveragingAcceptance;

pub const ARMS: [&str; 4] = ["default", "costda", "stanacc", "levels2"];

/// Refinement levels of the `levels2` arm (default 8).
pub const CAPPED_LEVELS: usize = 2;

/// What `Adaptation::default()` installs: `WarmupConfig::new(0.8)` with the
/// sampler's warmup exhaustion rule and metric regularisation (no chain rescue).
pub fn house_warmup() -> WarmupConfig {
    WarmupConfig::new(0.8)
        .expect("0.8 is a valid target")
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
}

/// One arm: kernel tuning, adaptation and the warmup length for a nominal warmup.
pub struct Arm {
    pub tuning: Tuning,
    pub adaptation: Adaptation,
    pub warmup: usize,
}

pub fn arm(name: &str, nominal_warmup: usize) -> Result<Arm, String> {
    let custom = |statistic: DualAveragingAcceptance| Arm {
        tuning: Tuning::default(),
        adaptation: Adaptation::Custom(house_warmup().with_dual_averaging_acceptance(statistic)),
        warmup: nominal_warmup,
    };
    match name {
        "default" => Ok(Arm {
            tuning: Tuning::default(),
            adaptation: Adaptation::default(),
            warmup: nominal_warmup,
        }),
        "costda" => Ok(custom(DualAveragingAcceptance::CostWeightedCoarseEndpoint)),
        "stanacc" => Ok(custom(DualAveragingAcceptance::MeanTrajectoryAcceptance)),
        "levels2" => Ok(Arm {
            tuning: Tuning::default().max_refinement_levels(CAPPED_LEVELS),
            adaptation: Adaptation::default(),
            warmup: nominal_warmup,
        }),
        other => Err(format!("unknown arm {other:?} (one of {ARMS:?})")),
    }
}
