//! The arms of the refinement-role study, shared by the three binaries.
//!
//! Every arm is the shipped `sampler` default (`Tuning::default()`: `h0 0.5`,
//! depth 10, eight refinement levels, `MomentumSum`; `Metric::diagonal()`
//! with the Stan regularisation; the WP24 warmup exhaustion rule) except for
//! the step-size adaptation rule and the local error bound `delta`
//! (`Tuning::max_error`):
//!
//! | arm | step rule | `delta` |
//! |---|---|---|
//! | `da` | dual averaging at 0.8 on the coarse-endpoint statistic (`Adaptation::default()`) | 1 |
//! | `da06` | dual averaging at 0.6 on the coarse-endpoint statistic | 1 |
//! | `da06-d05` | dual averaging at 0.6 on the coarse-endpoint statistic | 0.5 |
//! | `paper08` | `Adaptation::Paper(PaperAdaptationConfig::default())`: Appendix C, Gamma 0.8, K-quantile `delta` | adapted |
//! | `paper06` | Appendix C with Gamma 0.6 | adapted |
//! | `stanacc` | dual averaging at 0.8 on Stan's mean-trajectory acceptance (`DualAveragingAcceptance::MeanTrajectoryAcceptance`) | 1 |
//! | `da-d2` | dual averaging at 0.8 on the coarse-endpoint statistic (the default rule) | 2 |
//! | `da06-d2` | dual averaging at 0.6 on the coarse-endpoint statistic | 2 |
//!
//! `da-d2` and `da06-d2` are arm (f) of the task, chosen from the
//! instrumentation (see `PREREGISTRATION.md`): at the adapted step the
//! reverse-coarser stop ends 10–54 % of the retained transitions on the
//! four models where oWALNUTS is furthest behind CmdStan, and `delta = 2`
//! halves the fraction of leaves that refine there without moving `h`.
#![allow(dead_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION,
    PaperAdaptationConfig, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::{
    DEFAULT_PAPER_GLOBAL_ENERGY_BOUND, DEFAULT_PAPER_QUANTILE_PROBABILITY, DualAveragingAcceptance,
    KernelOptions,
};
use serde_json::json;
use std::error::Error;

pub const ARMS: [&str; 8] = [
    "da", "da06", "da06-d05", "paper08", "paper06", "stanacc", "da-d2", "da06-d2",
];

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum StepRule {
    /// Dual averaging toward `target` on the given acceptance statistic.
    DualAveraging {
        target: f64,
        statistic: DualAveragingAcceptance,
    },
    /// The Appendix C rules with the unrefined-leaf fraction target `gamma`.
    Paper { gamma: f64 },
}

#[derive(Clone, Copy, Debug)]
pub struct Arm {
    pub name: &'static str,
    pub rule: StepRule,
    /// `Tuning::max_error` (`delta`); for the paper arms the initial value.
    pub max_error: f64,
}

impl Arm {
    pub fn parse(name: &str) -> Result<Self, Box<dyn Error>> {
        let coarse = DualAveragingAcceptance::CurrentCoarseEndpoint;
        let stan = DualAveragingAcceptance::MeanTrajectoryAcceptance;
        let (rule, max_error) = match name {
            "da" => (
                StepRule::DualAveraging {
                    target: 0.8,
                    statistic: coarse,
                },
                1.0,
            ),
            "da06" => (
                StepRule::DualAveraging {
                    target: 0.6,
                    statistic: coarse,
                },
                1.0,
            ),
            "da06-d05" => (
                StepRule::DualAveraging {
                    target: 0.6,
                    statistic: coarse,
                },
                0.5,
            ),
            "paper08" => (StepRule::Paper { gamma: 0.8 }, 1.0),
            "paper06" => (StepRule::Paper { gamma: 0.6 }, 1.0),
            "stanacc" => (
                StepRule::DualAveraging {
                    target: 0.8,
                    statistic: stan,
                },
                1.0,
            ),
            "da-d2" => (
                StepRule::DualAveraging {
                    target: 0.8,
                    statistic: coarse,
                },
                2.0,
            ),
            "da06-d2" => (
                StepRule::DualAveraging {
                    target: 0.6,
                    statistic: coarse,
                },
                2.0,
            ),
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
            rule,
            max_error,
        })
    }

    pub fn is_default(&self) -> bool {
        self.name == "da"
    }

    /// The sampler's kernel options: the shipped default (`MomentumSum`).
    pub fn kernel_options(&self) -> KernelOptions {
        KernelOptions {
            u_turn: DEFAULT_U_TURN_RULE,
            ..KernelOptions::default()
        }
    }

    /// `Tuning::default()` with the arm's `delta`; bit-identical to the
    /// default for the `da` arm.
    pub fn tuning(&self) -> Tuning {
        if self.is_default() {
            Tuning::default()
        } else {
            Tuning::default().max_error(self.max_error)
        }
    }

    /// `PaperAdaptationConfig::new(Delta, p, Gamma)` with the default
    /// `Delta = 2` and `p = 0.95`; for `Gamma = 0.8` this is field-for-field
    /// `PaperAdaptationConfig::default()` (`new` fills the rest from the
    /// default), i.e. the v4 robust rule.
    pub fn paper_config(&self) -> Result<Option<PaperAdaptationConfig>, Box<dyn Error>> {
        Ok(match self.rule {
            StepRule::Paper { gamma } => Some(PaperAdaptationConfig::new(
                DEFAULT_PAPER_GLOBAL_ENERGY_BOUND,
                DEFAULT_PAPER_QUANTILE_PROBABILITY,
                gamma,
            )?),
            StepRule::DualAveraging { .. } => None,
        })
    }

    /// The `sampler` adaptation of the arm. `da` returns
    /// `Adaptation::default()` itself so that the baseline is literally the
    /// shipped default; the coarse-statistic arms use
    /// `Adaptation::DualAveraging` (which applies the default warmup
    /// exhaustion rule and regularisation), the Stan-statistic arms the same
    /// `WarmupConfig` with the statistic switched, through `Adaptation::Custom`.
    pub fn adaptation(&self) -> Result<Adaptation, Box<dyn Error>> {
        Ok(match self.rule {
            StepRule::DualAveraging { target, statistic } if self.is_default() => {
                debug_assert_eq!(target, 0.8);
                debug_assert_eq!(statistic, DualAveragingAcceptance::CurrentCoarseEndpoint);
                Adaptation::default()
            }
            StepRule::DualAveraging {
                target,
                statistic: DualAveragingAcceptance::CurrentCoarseEndpoint,
            } => Adaptation::DualAveraging {
                target_accept: target,
            },
            StepRule::DualAveraging { target, statistic } => Adaptation::Custom(
                WarmupConfig::new(target)?
                    .with_dual_averaging_acceptance(statistic)
                    .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                    .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
            ),
            StepRule::Paper { .. } => Adaptation::Paper(self.paper_config()?.expect("paper arm")),
        })
    }

    /// The arm's warmup rule for the `walnutpie` facade (the Eight Schools
    /// strict track): the strict track's `WarmupConfig::new(strict_target)`
    /// with mass adaptation and the default regularisation, with the arm's
    /// rule substituted where the arm changes it — a dual-averaging target
    /// other than 0.8 replaces `strict_target`, the Stan statistic is
    /// switched on at `strict_target`, the paper arms replace dual
    /// averaging by the Appendix C rules.
    pub fn facade_warmup(&self, strict_target: f64) -> Result<WarmupConfig, Box<dyn Error>> {
        let base = |target: f64| -> Result<WarmupConfig, Box<dyn Error>> {
            Ok(WarmupConfig::new(target)?
                .with_mass_adaptation(true)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION))
        };
        Ok(match self.rule {
            StepRule::DualAveraging { target, statistic } => {
                let target = if target == 0.8 { strict_target } else { target };
                base(target)?.with_dual_averaging_acceptance(statistic)
            }
            StepRule::Paper { .. } => {
                base(strict_target)?.with_paper_adaptation(self.paper_config()?.expect("paper arm"))
            }
        })
    }

    pub fn json(&self) -> serde_json::Value {
        match self.rule {
            StepRule::DualAveraging { target, statistic } => json!({
                "arm": self.name, "mode": "dual_averaging", "target_accept": target,
                "dual_averaging_acceptance": format!("{statistic:?}"),
                "max_error": self.max_error,
                "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
                "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
                "u_turn": format!("{DEFAULT_U_TURN_RULE:?}"),
                "mass_adaptation": true,
            }),
            StepRule::Paper { gamma } => json!({
                "arm": self.name, "mode": "appendix_c", "unrefined_fraction_target": gamma,
                "global_energy_bound": DEFAULT_PAPER_GLOBAL_ENERGY_BOUND,
                "quantile_probability": DEFAULT_PAPER_QUANTILE_PROBABILITY,
                "initial_max_error": self.max_error,
                "warmup_exhaustion_rule": format!("{DEFAULT_WARMUP_EXHAUSTION:?}"),
                "metric_regularization": format!("{DEFAULT_METRIC_REGULARIZATION:?}"),
                "u_turn": format!("{DEFAULT_U_TURN_RULE:?}"),
                "mass_adaptation": true,
            }),
        }
    }
}
