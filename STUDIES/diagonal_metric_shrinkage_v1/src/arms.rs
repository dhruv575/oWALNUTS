//! The arms of WP81 (`STUDIES/diagonal_metric_shrinkage_v1`), shared by both binaries.
//!
//! | arm | `DiagonalMetricRegularization` | installed variance (`n` window draws) |
//! |---|---|---|
//! | `defaults` | the shipped default (`Stan`), through `Adaptation::default()` | `(n/(n+5)) var_i + 1e-3 * 5/(n+5)` |
//! | `lowanchor` | `StanLowAnchor` (research) | `(n/(n+5)) var_i + min(1e-3, v_min) * 5/(n+5)` |
//! | `coordcap` | `StanCoordinateCap` (research) | `(n/(n+5)) var_i + min(1e-3, var_i) * 5/(n+5)` |
//!
//! The candidate arms are the `WarmupConfig` that `Adaptation::default()` builds
//! (`WarmupConfig::new(0.8)`, the default warmup exhaustion rule, no chain rescue)
//! with only the regularisation switched (as WP41's `src/arms.rs`).
#![allow(dead_code)]

use owalnuts::sampler::{Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_WARMUP_EXHAUSTION, WarmupConfig};
use owalnuts::walnutpie::DiagonalMetricRegularization;
use std::error::Error;

pub fn regularization(arm: &str) -> Result<Option<DiagonalMetricRegularization>, Box<dyn Error>> {
    match arm {
        "defaults" => Ok(None),
        "lowanchor" => Ok(Some(DiagonalMetricRegularization::StanLowAnchor)),
        "coordcap" => Ok(Some(DiagonalMetricRegularization::StanCoordinateCap)),
        other => Err(format!("unknown arm {other:?} (expected defaults, lowanchor or coordcap)").into()),
    }
}

/// `None` for the default arm (the sampler is left untouched).
pub fn adaptation(arm: &str) -> Result<Option<Adaptation>, Box<dyn Error>> {
    assert!(DEFAULT_CHAIN_RESCUE.is_none(), "the arms assume the shipped default has no chain rescue");
    Ok(match regularization(arm)? {
        None => None,
        Some(r) => Some(Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(r),
        )),
    })
}
