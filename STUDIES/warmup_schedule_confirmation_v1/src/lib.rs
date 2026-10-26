//! WP77 `warmup_schedule_confirmation_v1`: WP73's `src/lib.rs` verbatim (WP77 runs
//! `default`, `half` and `init25`; `stablestop` is kept but not run). WP73 header follows.
//!
//! WP73 `warmup_spend_v1`: the four preregistered oWALNUTS arms, shared by the
//! posteriordb harness (`src/main.rs`) and the funnel sanity binary
//! (`src/bin/funnel.rs`) so that both run exactly the same settings.
//!
//! Every arm is the shipped sampler default (`Tuning::default()`,
//! `Metric::default()`, `Init::default()`, `Adaptation::default()`) with at most
//! one warmup override. The three candidates are written as
//! `Adaptation::Custom` around [`house_warmup`], which is the configuration
//! `Adaptation::default()` builds (`tests/stable_metric_stop.rs::custom_house_warmup_is_the_default`
//! pins that the two are bit-identical).
//!
//! | arm | override | warmup at the study's 1,000 (funnel 2,000) |
//! |---|---|---|
//! | `default` | none | 75 / 25, 50, 100, 200, 500 / 50 (funnel: ... 400, 1,100 / 50) |
//! | `init25` | `WarmupWindowConfig::new(25, 25, 50)`: initial fast phase 25 instead of 75 | 25 / 25, 50, 100, 200, 550 / 50 |
//! | `half` | half the warmup transitions, same window rule: the last metric window closes at 450 (funnel 850) | 500 (funnel 1,000) |
//! | `stablestop` | `WarmupConfig::with_stable_metric_stop(StableMetricStop::new(3, 0.9, ln 1.5, ln 1.5))` | 1,000, or 500 when the metric and step are stable at the close of window 3 (funnel also 900 at window 4) |
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::{StableMetricStop, WarmupWindowConfig};
use std::num::NonZeroUsize;

pub const ARMS: [&str; 4] = ["default", "init25", "half", "stablestop"];

/// `StableMetricStop` parameters of the `stablestop` arm (frozen in protocol.json).
pub const STOP_FIRST_WINDOW: usize = 3;
pub const STOP_QUANTILE: f64 = 0.9;
pub const STOP_METRIC_FACTOR: f64 = 1.5;
pub const STOP_STEP_FACTOR: f64 = 1.5;

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
    let custom = |warmup: WarmupConfig, length: usize| Arm {
        tuning: Tuning::default(),
        adaptation: Adaptation::Custom(warmup),
        warmup: length,
    };
    match name {
        "default" => Ok(Arm {
            tuning: Tuning::default(),
            adaptation: Adaptation::default(),
            warmup: nominal_warmup,
        }),
        "init25" => {
            let windows = WarmupWindowConfig::new(25, NonZeroUsize::new(25).unwrap(), 50)
                .map_err(|e| e.to_string())?;
            Ok(custom(house_warmup().with_windows(windows), nominal_warmup))
        }
        "half" => Ok(Arm {
            tuning: Tuning::default(),
            adaptation: Adaptation::default(),
            warmup: nominal_warmup / 2,
        }),
        "stablestop" => {
            let rule = StableMetricStop::new(
                STOP_FIRST_WINDOW,
                STOP_QUANTILE,
                STOP_METRIC_FACTOR.ln(),
                STOP_STEP_FACTOR.ln(),
            )
            .map_err(|e| e.to_string())?;
            Ok(custom(house_warmup().with_stable_metric_stop(rule), nominal_warmup))
        }
        other => Err(format!("unknown arm {other:?} (one of {ARMS:?})")),
    }
}
