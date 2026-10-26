//! Research-only per-run dense / diagonal auto-selection
//! (`WarmupConfig::with_dense_auto_select`, `STUDIES/metric_autoselect_v1`,
//! WP75): off by default and bit-identical when unflagged, the dense branch
//! on a correlated Gaussian, the diagonal branch on an independent badly
//! scaled one, one decision per run, determinism, and validation.
#![cfg(feature = "research")]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric,
    Posterior, Sampler, WarmupConfig,
};
use owalnuts::walnutpie::{DenseAutoSelectConfig, ErrorKind, Target, TargetError};

/// Gaussian with covariance `S = diag(s) R diag(s)`, `R` equicorrelated at `rho`.
struct Gaussian {
    scales: Vec<f64>,
    rho: f64,
}

impl Gaussian {
    fn precision_times(&self, z: &[f64]) -> Vec<f64> {
        // R^{-1} = (I - c 11^T) / (1 - rho), c = rho / (1 + (d - 1) rho).
        let d = z.len() as f64;
        let c = self.rho / (1.0 + (d - 1.0) * self.rho);
        let sum: f64 = z.iter().sum();
        z.iter().map(|x| (x - c * sum) / (1.0 - self.rho)).collect()
    }
}

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.scales.len()
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let z: Vec<f64> = q.iter().zip(&self.scales).map(|(x, s)| x / s).collect();
        let rz = self.precision_times(&z);
        let value = -0.5 * z.iter().zip(&rz).map(|(a, b)| a * b).sum::<f64>();
        for ((g, r), s) in gradient.iter_mut().zip(&rz).zip(&self.scales) {
            *g = -r / s;
        }
        Ok(value)
    }
}

fn starts(target: &Gaussian, chains: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|c| {
            target
                .scales
                .iter()
                .enumerate()
                .map(|(i, s)| s * (0.4 * c as f64 - 0.6) * if i % 2 == 0 { 1.0 } else { -0.5 })
                .collect()
        })
        .collect()
}

fn warmup(auto: Option<DenseAutoSelectConfig>) -> WarmupConfig {
    let w = WarmupConfig::new(0.8)
        .unwrap()
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION);
    match auto {
        Some(a) => w.with_dense_auto_select(a),
        None => w,
    }
}

fn run(
    target: &Gaussian,
    adaptation: Adaptation,
    threads: usize,
) -> Result<Posterior, owalnuts::sampler::Error> {
    Sampler::new()
        .warmup(600)
        .draws(200)
        .chains(4)
        .seed(75)
        .threads(threads)
        .metric(Metric::dense())
        .adaptation(adaptation)
        .limits(Limits::new().admit_worst_case())
        .run(target, &starts(target, 4))
}

fn off_diagonal_max(matrix: &[f64], d: usize) -> f64 {
    (0..d * d)
        .filter(|k| k / d != k % d)
        .map(|k| matrix[k].abs())
        .fold(0.0, f64::max)
}

#[test]
fn unflagged_is_the_dense_default_and_off_by_default() {
    assert_eq!(WarmupConfig::default().dense_auto_select(), None);
    let target = Gaussian {
        scales: vec![1.0, 2.0, 0.5],
        rho: 0.6,
    };
    let default = run(&target, Adaptation::default(), 4).unwrap();
    let custom = run(&target, Adaptation::Custom(warmup(None)), 4).unwrap();
    for (a, b) in default.chains().iter().zip(custom.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert!(b.telemetry().dense_auto_select().is_none());
    }
}

#[test]
fn correlated_gaussian_takes_the_dense_branch() {
    let target = Gaussian {
        scales: vec![1.0, 3.0, 0.2, 1.0, 5.0],
        rho: 0.95,
    };
    let posterior = run(
        &target,
        Adaptation::Custom(warmup(Some(DenseAutoSelectConfig::default()))),
        4,
    )
    .unwrap();
    let decision = posterior.chains()[0]
        .telemetry()
        .dense_auto_select()
        .unwrap()
        .clone();
    assert!(decision.chose_dense(), "{decision:?}");
    assert!(decision.statistic() >= 5.0, "{decision:?}");
    assert_eq!(decision.window_index(), 2);
    assert_eq!(decision.previous_count(), 4 * 50);
    for chain in posterior.chains() {
        assert_eq!(chain.telemetry().dense_auto_select(), Some(&decision));
        let updates = chain.telemetry().metric_updates();
        for update in &updates[..2] {
            let m = update.mass_dense().unwrap();
            assert_eq!(
                off_diagonal_max(m, 5),
                0.0,
                "pre-selection installs are diagonal"
            );
        }
        for update in &updates[2..] {
            let m = update.mass_dense().unwrap();
            assert!(off_diagonal_max(m, 5) > 0.0, "dense branch installs dense");
        }
    }
    let again = run(
        &target,
        Adaptation::Custom(warmup(Some(DenseAutoSelectConfig::default()))),
        4,
    )
    .unwrap();
    for (a, b) in posterior.chains().iter().zip(again.chains()) {
        assert_eq!(a.samples(), b.samples(), "deterministic");
    }
}

#[test]
fn independent_scaled_gaussian_takes_the_diagonal_branch() {
    let target = Gaussian {
        scales: vec![0.01, 1.0, 30.0, 0.3],
        rho: 0.0,
    };
    let posterior = run(
        &target,
        Adaptation::Custom(warmup(Some(DenseAutoSelectConfig::default()))),
        4,
    )
    .unwrap();
    let decision = posterior.chains()[0]
        .telemetry()
        .dense_auto_select()
        .unwrap()
        .clone();
    assert!(!decision.chose_dense(), "{decision:?}");
    assert!(decision.statistic() < 2.0, "{decision:?}");
    for chain in posterior.chains() {
        for update in chain.telemetry().metric_updates() {
            let m = update.mass_dense().unwrap();
            assert_eq!(
                off_diagonal_max(m, 4),
                0.0,
                "diagonal branch installs diagonal"
            );
        }
        // The diagonal estimate recovers the scales.
        let last = chain.telemetry().metric_updates().last().unwrap();
        let m = last.mass_dense().unwrap();
        for (i, s) in target.scales.iter().enumerate() {
            let ratio = m[i * 4 + i] * s * s;
            assert!((0.6..1.6).contains(&ratio), "coordinate {i}: {ratio}");
        }
    }
}

#[test]
fn validation() {
    assert!(DenseAutoSelectConfig::new(0, 5.0).is_err());
    assert!(DenseAutoSelectConfig::new(2, 0.0).is_err());
    assert!(DenseAutoSelectConfig::new(2, f64::NAN).is_err());
    assert_eq!(
        DenseAutoSelectConfig::new(2, 5.0).unwrap(),
        DenseAutoSelectConfig::default()
    );
    let target = Gaussian {
        scales: vec![1.0, 1.0],
        rho: 0.5,
    };
    let auto = || Adaptation::Custom(warmup(Some(DenseAutoSelectConfig::default())));
    let serial = run(&target, auto(), 1).unwrap_err();
    assert_eq!(serial.kind(), ErrorKind::Configuration, "threads < chains");
    let diagonal = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(2)
        .seed(1)
        .adaptation(auto())
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&target, 2))
        .unwrap_err();
    assert_eq!(diagonal.kind(), ErrorKind::Configuration, "diagonal facade");
    let beyond = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(2)
        .threads(2)
        .seed(1)
        .metric(Metric::dense())
        .adaptation(Adaptation::Custom(warmup(Some(
            DenseAutoSelectConfig::new(9, 5.0).unwrap(),
        ))))
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&target, 2))
        .unwrap_err();
    assert_eq!(
        beyond.kind(),
        ErrorKind::Configuration,
        "window beyond schedule"
    );
}
