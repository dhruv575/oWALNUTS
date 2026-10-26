//! Research-only gradient-informed diagonal metric estimator
//! (`WarmupConfig::with_diagonal_metric_estimator`, `STUDIES/gradient_metric_v1`,
//! WP71): off by default and bit-identical when unflagged, recovery of the
//! variances of a badly scaled Gaussian, determinism, and validation.
#![cfg(feature = "research")]

use std::num::NonZeroUsize;

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler,
    WarmupConfig,
};
use owalnuts::walnutpie::{
    ChainRescueConfig, DiagonalMass, DiagonalMetricEstimator, DiagonalMetricRegularization,
    ErrorKind, KernelTuning, MetricUpdateOutcome, RunConfig, Target, TargetError, sample_chains,
};

/// Independent Gaussian with standard deviations `SCALES`.
struct Scaled;

const SCALES: [f64; 4] = [0.01, 0.3, 1.0, 50.0];

impl Target for Scaled {
    fn dimension(&self) -> usize {
        SCALES.len()
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for ((g, x), s) in gradient.iter_mut().zip(q).zip(SCALES) {
            *g = -x / (s * s);
            value -= 0.5 * (x / s) * (x / s);
        }
        Ok(value)
    }
}

fn config(estimator: Option<DiagonalMetricEstimator>) -> RunConfig {
    let warmup = WarmupConfig::new(0.8)
        .unwrap()
        .with_metric_regularization(DiagonalMetricRegularization::Stan);
    let warmup = match estimator {
        Some(estimator) => warmup.with_diagonal_metric_estimator(estimator),
        None => warmup,
    };
    RunConfig::new(1000, NonZeroUsize::new(400).unwrap(), 0x71)
        .with_tuning(
            KernelTuning::new(
                0.5,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(4).unwrap(),
                1.0,
            )
            .unwrap(),
        )
        .with_warmup(warmup)
}

fn starts(chains: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|chain| {
            SCALES
                .iter()
                .enumerate()
                .map(|(i, s)| s * (0.3 * chain as f64 - 0.4) * if i % 2 == 0 { 1.0 } else { -1.0 })
                .collect()
        })
        .collect()
}

#[test]
fn default_is_draw_variance_and_explicit_draw_variance_is_bit_identical() {
    assert_eq!(
        WarmupConfig::default().diagonal_metric_estimator(),
        DiagonalMetricEstimator::DrawVariance
    );
    assert_eq!(
        DiagonalMetricEstimator::default(),
        DiagonalMetricEstimator::DrawVariance
    );
    let mass = DiagonalMass::identity(NonZeroUsize::new(SCALES.len()).unwrap());
    let starts = starts(4);
    for threads in [1, 4] {
        let threads = NonZeroUsize::new(threads).unwrap();
        let plain = sample_chains(&Scaled, &starts, &mass, &config(None), threads).unwrap();
        let explicit = sample_chains(
            &Scaled,
            &starts,
            &mass,
            &config(Some(DiagonalMetricEstimator::DrawVariance)),
            threads,
        )
        .unwrap();
        assert_eq!(plain, explicit, "unflagged run is bit-identical");
    }

    let sampler = |adaptation: Adaptation| {
        Sampler::new()
            .warmup(400)
            .draws(100)
            .chains(4)
            .seed(11)
            .threads(4)
            .adaptation(adaptation)
            .limits(Limits::new().admit_worst_case())
    };
    let custom = Adaptation::Custom(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
            .with_diagonal_metric_estimator(DiagonalMetricEstimator::DrawVariance),
    );
    let starts4 = starts.clone();
    let defaults = sampler(Adaptation::default())
        .run(&Scaled, &starts4)
        .unwrap();
    let flagged_off = sampler(custom).run(&Scaled, &starts4).unwrap();
    for (a, b) in defaults.chains().iter().zip(flagged_off.chains()) {
        assert_eq!(a.samples(), b.samples(), "facade: unflagged is the default");
    }
}

#[test]
fn gradient_informed_recovers_scaled_gaussian_variances() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(SCALES.len()).unwrap());
    let starts = starts(4);
    let threads = NonZeroUsize::new(4).unwrap();
    let plain = sample_chains(&Scaled, &starts, &mass, &config(None), threads).unwrap();
    for estimator in [
        DiagonalMetricEstimator::GradientInformed,
        DiagonalMetricEstimator::GradientInformedOverlap,
    ] {
        let run =
            sample_chains(&Scaled, &starts, &mass, &config(Some(estimator)), threads).unwrap();
        assert_ne!(run, plain, "{estimator:?} changes the run");
        for chain in run.chains() {
            let updates = chain.telemetry().metric_updates();
            assert!(!updates.is_empty());
            assert!(
                updates
                    .iter()
                    .all(|u| u.outcome() == MetricUpdateOutcome::Installed)
            );
            let last = updates.last().unwrap().mass_diagonal().unwrap();
            for (m, s) in last.iter().zip(SCALES) {
                // Installed mass is the inverse variance; the exact
                // population value of sqrt(var x / var g) is s^2.
                let ratio = m * s * s;
                assert!(
                    (0.7..1.4).contains(&ratio),
                    "{estimator:?}: mass {m} vs 1/s^2 = {} (ratio {ratio})",
                    1.0 / (s * s)
                );
            }
        }
        let again =
            sample_chains(&Scaled, &starts, &mass, &config(Some(estimator)), threads).unwrap();
        assert_eq!(run, again, "deterministic");
        let sequential = sample_chains(
            &Scaled,
            &starts,
            &mass,
            &config(Some(estimator)),
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        assert_eq!(
            run.chains()[0].samples(),
            sequential.chains()[0].samples(),
            "thread count does not change draws"
        );
    }
    let primary = sample_chains(
        &Scaled,
        &starts,
        &mass,
        &config(Some(DiagonalMetricEstimator::GradientInformed)),
        threads,
    )
    .unwrap();
    let overlap = sample_chains(
        &Scaled,
        &starts,
        &mass,
        &config(Some(DiagonalMetricEstimator::GradientInformedOverlap)),
        threads,
    )
    .unwrap();
    assert_ne!(primary, overlap, "the overlap variant is a different rule");
}

#[test]
fn validation_combination_and_facades() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(SCALES.len()).unwrap());
    let rescued = config(None).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_chain_rescue(ChainRescueConfig::restart_from_best())
            .with_diagonal_metric_estimator(DiagonalMetricEstimator::GradientInformed),
    );
    let error = sample_chains(
        &Scaled,
        &starts(4),
        &mass,
        &rescued,
        NonZeroUsize::new(4).unwrap(),
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);

    let dense = Sampler::new()
        .warmup(200)
        .draws(50)
        .chains(2)
        .seed(3)
        .adaptation(Adaptation::Custom(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_diagonal_metric_estimator(DiagonalMetricEstimator::GradientInformed),
        ))
        .metric(Metric::dense())
        .limits(Limits::new().admit_worst_case())
        .run(&Scaled, &starts(2))
        .unwrap_err();
    assert_eq!(dense.kind(), ErrorKind::Configuration);
}
