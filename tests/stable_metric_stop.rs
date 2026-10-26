//! WP73 (`STUDIES/warmup_spend_v1`): the research-only stable-metric warmup
//! stop (`WarmupConfig::with_stable_metric_stop`).
//!
//! * A chain that stops at window `k` must be bit-identical to a run whose
//!   warmup is `windows[k].end + terminal_buffer` transitions long.
//! * A rule that never fires must be bit-identical to the same configuration
//!   without the rule, and that configuration (`Adaptation::Custom` with the
//!   sampler's own warmup defaults) to `Adaptation::default()`.
//! * Facades other than the diagonal adaptive one reject it.

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric,
    Posterior, Sampler, Target, TargetError,
};
use owalnuts::walnutpie::{StableMetricStop, WarmupConfig};

/// Independent Gaussian with very different scales, so the metric matters.
struct Scaled;

const SCALES: [f64; 5] = [0.1, 1.0, 10.0, 3.0, 0.5];

impl Target for Scaled {
    fn dimension(&self) -> usize {
        SCALES.len()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for ((g, x), s) in gradient.iter_mut().zip(position).zip(SCALES) {
            *g = -x / (s * s);
            value -= 0.5 * x * x / (s * s);
        }
        Ok(value)
    }
}

const SEED: u64 = 0x5eed_7300;
const DRAWS: usize = 200;

fn starts() -> Vec<Vec<f64>> {
    (0..4)
        .map(|c| {
            (0..SCALES.len())
                .map(|i| 0.3 * (c as f64 - 1.5) + 0.1 * i as f64)
                .collect()
        })
        .collect()
}

fn house_warmup() -> WarmupConfig {
    WarmupConfig::new(0.8)
        .unwrap()
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
}

fn run(warmup: usize, adaptation: Adaptation) -> Posterior {
    Sampler::new()
        .warmup(warmup)
        .draws(DRAWS)
        .chains(4)
        .seed(SEED)
        .threads(2)
        .limits(Limits::new().admit_worst_case())
        .adaptation(adaptation)
        .run(&Scaled, &starts())
        .unwrap()
}

fn draws(posterior: &Posterior) -> Vec<Vec<u64>> {
    posterior
        .chains()
        .iter()
        .map(|chain| {
            (0..DRAWS)
                .flat_map(|i| {
                    chain
                        .sample(i)
                        .unwrap()
                        .iter()
                        .map(|v| v.to_bits())
                        .collect::<Vec<_>>()
                })
                .collect()
        })
        .collect()
}

#[test]
fn custom_house_warmup_is_the_default() {
    let default = run(1000, Adaptation::default());
    let custom = run(1000, Adaptation::Custom(house_warmup()));
    assert_eq!(draws(&default), draws(&custom));
}

#[test]
fn rule_that_never_fires_is_bit_identical() {
    let never = StableMetricStop::new(3, 0.9, 0.0, 0.0).unwrap();
    let with_rule = run(
        1000,
        Adaptation::Custom(house_warmup().with_stable_metric_stop(never)),
    );
    let without = run(1000, Adaptation::Custom(house_warmup()));
    assert_eq!(draws(&with_rule), draws(&without));
    for chain in with_rule.chains() {
        assert_eq!(chain.metadata().discarded(), 1000);
        let checks = chain.telemetry().stable_metric_checks();
        // Windows 3 (closes at 449) and 4 (closes at 949; stopping there
        // would not shorten the warmup) are checked.
        assert_eq!(checks.len(), 2);
        assert_eq!(checks[0].window_index(), 3);
        assert_eq!(checks[0].transition(), 449);
        assert_eq!(checks[1].window_index(), 4);
        assert_eq!(checks[1].transition(), 949);
        assert!(checks.iter().all(|check| !check.stopped()));
        assert!(checks[0].metric_change() > 0.0);
        assert!(checks[0].step_change().is_some());
    }
}

#[test]
fn stopped_chain_is_the_short_warmup_run() {
    let always = StableMetricStop::new(3, 0.9, 1.0e6, 1.0e6).unwrap();
    let stopped = run(
        1000,
        Adaptation::Custom(house_warmup().with_stable_metric_stop(always)),
    );
    let short = run(500, Adaptation::Custom(house_warmup()));
    assert_eq!(draws(&stopped), draws(&short));
    for (a, b) in stopped.chains().iter().zip(short.chains()) {
        assert_eq!(a.metadata().discarded(), 500);
        assert_eq!(a.diagnostics().len(), 500 + DRAWS);
        assert_eq!(
            a.metadata().tuning().step_size().to_bits(),
            b.metadata().tuning().step_size().to_bits()
        );
        assert_eq!(a.metadata().mass_diagonal(), b.metadata().mass_diagonal());
        assert_eq!(
            a.telemetry().total().target_calls_total(),
            b.telemetry().total().target_calls_total()
        );
        assert_eq!(
            a.telemetry().discarded().target_calls_total(),
            b.telemetry().discarded().target_calls_total()
        );
        let schedule = a.metadata().warmup_schedule().unwrap();
        assert_eq!(schedule.terminal_fast_start(), 450);
        assert_eq!(schedule.windows().len(), 4);
        let checks = a.telemetry().stable_metric_checks();
        assert_eq!(checks.len(), 1);
        assert!(checks[0].stopped());
    }
}

#[test]
fn rule_is_validated_and_rejected_elsewhere() {
    assert!(StableMetricStop::new(0, 0.9, 0.4, 0.2).is_err());
    assert!(StableMetricStop::new(3, 0.0, 0.4, 0.2).is_err());
    assert!(StableMetricStop::new(3, 0.9, f64::NAN, 0.2).is_err());
    let rule = StableMetricStop::new(3, 0.9, 0.4, 0.2).unwrap();
    let dense = Sampler::new()
        .warmup(300)
        .draws(20)
        .chains(2)
        .seed(SEED)
        .metric(Metric::dense())
        .adaptation(Adaptation::Custom(
            house_warmup().with_stable_metric_stop(rule),
        ))
        .run(&Scaled, &starts()[..2]);
    assert!(dense.is_err());
}
