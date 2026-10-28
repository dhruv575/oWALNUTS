//! Research-only Hessian-fit dense / diagonal auto-selection
//! (`DenseAutoSelectConfig::hessian_fit`, `STUDIES/metric_autoselect_v2`,
//! WP79): the diagonal branch is the default diagonal run itself (draws,
//! diagnostics, target calls), a correlated Gaussian takes the dense branch,
//! an independent badly scaled Gaussian and a funnel take the diagonal
//! branch, one decision per run, determinism, and validation.
#![cfg(feature = "research")]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric,
    Posterior, Sampler, WarmupConfig,
};
use owalnuts::walnutpie::{
    DenseAutoSelectConfig, ErrorKind, Target, TargetError, TrappedChainRestartConfig,
};
use std::sync::atomic::{AtomicUsize, Ordering};

/// Gaussian with covariance `S = diag(s) R diag(s)`, `R` equicorrelated at
/// `rho`; counts its evaluations.
struct Gaussian {
    scales: Vec<f64>,
    rho: f64,
    calls: AtomicUsize,
}

impl Gaussian {
    fn new(scales: Vec<f64>, rho: f64) -> Self {
        Self {
            scales,
            rho,
            calls: AtomicUsize::new(0),
        }
    }

    fn precision_times(&self, z: &[f64]) -> Vec<f64> {
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
        self.calls.fetch_add(1, Ordering::Relaxed);
        let z: Vec<f64> = q.iter().zip(&self.scales).map(|(x, s)| x / s).collect();
        let rz = self.precision_times(&z);
        let value = -0.5 * z.iter().zip(&rz).map(|(a, b)| a * b).sum::<f64>();
        for ((g, r), s) in gradient.iter_mut().zip(&rz).zip(&self.scales) {
            *g = -r / s;
        }
        Ok(value)
    }
}

/// Neal's funnel in 4 dimensions (`omega ~ N(0, 9)`, `x_i ~ N(0, e^omega)`).
struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        4
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let omega = q[0];
        let inverse = (-omega).exp();
        let squares: f64 = q[1..].iter().map(|x| x * x).sum();
        gradient[0] = -omega / 9.0 - 1.5 + 0.5 * inverse * squares;
        for (g, x) in gradient[1..].iter_mut().zip(&q[1..]) {
            *g = -inverse * x;
        }
        let value = -omega * omega / 18.0 - 1.5 * omega - 0.5 * inverse * squares;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

fn starts(scales: &[f64], chains: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|c| {
            scales
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

fn hessian() -> DenseAutoSelectConfig {
    DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.5).unwrap()
}

fn sampler(adaptation: Option<Adaptation>, threads: usize) -> Sampler {
    let s = Sampler::new()
        .warmup(600)
        .draws(200)
        .chains(4)
        .seed(79)
        .threads(threads)
        .limits(Limits::new().admit_worst_case());
    match adaptation {
        Some(a) => s.adaptation(a),
        None => s,
    }
}

fn run<T: Target>(
    target: &T,
    scales: &[f64],
    adaptation: Option<Adaptation>,
    threads: usize,
) -> Result<Posterior, owalnuts::sampler::Error> {
    sampler(adaptation, threads).run(target, &starts(scales, 4))
}

fn off_diagonal_max(matrix: &[f64], d: usize) -> f64 {
    (0..d * d)
        .filter(|k| k / d != k % d)
        .map(|k| matrix[k].abs())
        .fold(0.0, f64::max)
}

fn assert_same_run(a: &Posterior, b: &Posterior) {
    assert_eq!(a.chain_count(), b.chain_count());
    for (x, y) in a.chains().iter().zip(b.chains()) {
        assert_eq!(x.samples(), y.samples(), "draws");
        assert_eq!(x.diagnostics(), y.diagnostics(), "diagnostics");
        assert_eq!(x.telemetry().total(), y.telemetry().total(), "work totals");
        assert_eq!(
            x.telemetry().metric_updates(),
            y.telemetry().metric_updates(),
            "metric updates"
        );
        assert_eq!(x.telemetry().step_searches(), y.telemetry().step_searches());
        assert_eq!(x.metadata().tuning(), y.metadata().tuning());
        assert_eq!(x.metadata().mass_diagonal(), y.metadata().mass_diagonal());
    }
}

#[test]
fn unflagged_custom_is_the_diagonal_default() {
    let scales = vec![1.0, 2.0, 0.5];
    let target = Gaussian::new(scales.clone(), 0.6);
    let default = run(&target, &scales, None, 4).unwrap();
    let custom = run(&target, &scales, Some(Adaptation::Custom(warmup(None))), 4).unwrap();
    assert_same_run(&default, &custom);
    for chain in custom.chains() {
        assert!(chain.telemetry().dense_auto_select().is_none());
    }
}

#[test]
fn diagonal_branch_is_bit_identical_to_the_default_diagonal_run() {
    let scales = vec![0.01, 1.0, 30.0, 0.3];
    for threads in [4, 1] {
        let default_target = Gaussian::new(scales.clone(), 0.0);
        let default = run(&default_target, &scales, None, threads).unwrap();
        let auto_target = Gaussian::new(scales.clone(), 0.0);
        let auto = run(
            &auto_target,
            &scales,
            Some(Adaptation::Custom(warmup(Some(hessian())))),
            threads,
        )
        .unwrap();
        let decision = auto.chains()[0]
            .telemetry()
            .dense_auto_select()
            .unwrap()
            .clone();
        assert!(!decision.chose_dense(), "{decision:?}");
        assert_eq!(decision.min_linearity(), Some(0.5));
        assert!(decision.linearity() > 0.99, "{decision:?}");
        assert!(decision.hessian_gain() < 2.0, "{decision:?}");
        assert_eq!(decision.fit_count(), 4 * (50 + 100));
        assert_same_run(&default, &auto);
        assert_eq!(
            default_target.calls.load(Ordering::Relaxed),
            auto_target.calls.load(Ordering::Relaxed),
            "target calls"
        );
        for chain in auto.chains() {
            assert_eq!(chain.telemetry().dense_auto_select(), Some(&decision));
            assert_eq!(
                chain.metadata().warmup().unwrap().dense_auto_select(),
                Some(&hessian())
            );
        }
    }
}

#[test]
fn funnel_takes_the_diagonal_branch_bit_identically() {
    let scales = vec![1.0; 4];
    let default = run(&Funnel, &scales, None, 4).unwrap();
    let auto = run(
        &Funnel,
        &scales,
        Some(Adaptation::Custom(warmup(Some(hessian())))),
        4,
    )
    .unwrap();
    let decision = auto.chains()[0].telemetry().dense_auto_select().unwrap();
    assert!(!decision.chose_dense(), "{decision:?}");
    assert!(decision.linearity() < 0.5, "{decision:?}");
    assert_same_run(&default, &auto);
}

#[test]
fn correlated_gaussian_takes_the_dense_branch() {
    let scales = vec![1.0, 3.0, 0.2, 1.0, 5.0];
    let target = Gaussian::new(scales.clone(), 0.95);
    let auto = || Some(Adaptation::Custom(warmup(Some(hessian()))));
    let posterior = run(&target, &scales, auto(), 4).unwrap();
    let decision = posterior.chains()[0]
        .telemetry()
        .dense_auto_select()
        .unwrap()
        .clone();
    assert!(decision.chose_dense(), "{decision:?}");
    assert!(decision.linearity() > 0.99, "{decision:?}");
    assert!(decision.hessian_gain() >= 5.0, "{decision:?}");
    assert_eq!(decision.window_index(), 2);
    assert_eq!(decision.transition(), 249);
    let default = run(&target, &scales, None, 4).unwrap();
    for (chain, diagonal) in posterior.chains().iter().zip(default.chains()) {
        assert_eq!(chain.telemetry().dense_auto_select(), Some(&decision));
        assert_eq!(chain.diagnostics().len(), 800);
        assert_eq!(chain.samples().len(), 200 * 5);
        // The first 250 transitions are the diagonal run's.
        assert_eq!(&chain.diagnostics()[..250], &diagonal.diagnostics()[..250]);
        let updates = chain.telemetry().metric_updates();
        // Diagonal windows 0, 1, 2 (the last superseded), then dense 2 and
        // every later window of the schedule.
        let windows: Vec<usize> = updates.iter().map(|u| u.window_index()).collect();
        let mut expected: Vec<usize> = diagonal
            .telemetry()
            .metric_updates()
            .iter()
            .map(|u| u.window_index())
            .collect();
        expected.insert(3, 2);
        assert_eq!(windows, expected);
        for update in &updates[..3] {
            assert!(update.mass_dense().is_none(), "diagonal driver installs");
        }
        for update in &updates[3..] {
            let m = update.mass_dense().unwrap();
            assert!(off_diagonal_max(m, 5) > 0.0, "dense branch installs dense");
        }
        assert_eq!(chain.metadata().discarded(), 600);
    }
    // Retained draws recover the correlation.
    let draws: Vec<&[f64; 5]> = posterior
        .chains()
        .iter()
        .flat_map(|c| c.samples().as_chunks::<5>().0.iter())
        .collect();
    let n = draws.len() as f64;
    let mean = |i: usize| draws.iter().map(|d| d[i]).sum::<f64>() / n;
    let (m0, m1) = (mean(0), mean(1));
    let cov = draws.iter().map(|d| (d[0] - m0) * (d[1] - m1)).sum::<f64>() / n;
    let v0 = draws.iter().map(|d| (d[0] - m0).powi(2)).sum::<f64>() / n;
    let v1 = draws.iter().map(|d| (d[1] - m1).powi(2)).sum::<f64>() / n;
    let corr = cov / (v0 * v1).sqrt();
    assert!((0.85..0.99).contains(&corr), "correlation {corr}");
    let again = run(&target, &scales, auto(), 4).unwrap();
    for (a, b) in posterior.chains().iter().zip(again.chains()) {
        assert_eq!(a.samples(), b.samples(), "deterministic");
    }
    let serial = run(&target, &scales, auto(), 1).unwrap();
    for (a, b) in posterior.chains().iter().zip(serial.chains()) {
        assert_eq!(a.samples(), b.samples(), "thread-count invariant");
    }
}

#[test]
fn validation() {
    assert!(DenseAutoSelectConfig::hessian_fit(2, 5.0, 0.0).is_err());
    assert!(DenseAutoSelectConfig::hessian_fit(2, 5.0, 1.5).is_err());
    assert!(DenseAutoSelectConfig::hessian_fit(2, 5.0, f64::NAN).is_err());
    assert!(DenseAutoSelectConfig::hessian_fit(0, 5.0, 0.5).is_err());
    assert_eq!(DenseAutoSelectConfig::default().min_linearity(), None);
    assert_eq!(hessian().min_linearity(), Some(0.5));
    let scales = vec![1.0, 1.0];
    let target = Gaussian::new(scales.clone(), 0.5);
    let auto = || Adaptation::Custom(warmup(Some(hessian())));
    let single = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(1)
        .seed(1)
        .adaptation(auto())
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&scales, 1))
        .unwrap_err();
    assert_eq!(single.kind(), ErrorKind::Configuration, "single chain");
    let dense = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(2)
        .threads(2)
        .seed(1)
        .metric(Metric::dense())
        .adaptation(auto())
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&scales, 2))
        .unwrap_err();
    assert_eq!(dense.kind(), ErrorKind::Configuration, "dense facade");
    let restart = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(4)
        .seed(1)
        .adaptation(Adaptation::Custom(
            warmup(Some(hessian()))
                .with_trapped_chain_restart(TrappedChainRestartConfig::default()),
        ))
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&scales, 4))
        .unwrap_err();
    assert_eq!(restart.kind(), ErrorKind::Configuration, "with restart");
    let beyond = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(2)
        .seed(1)
        .adaptation(Adaptation::Custom(warmup(Some(
            DenseAutoSelectConfig::hessian_fit(9, 5.0, 0.5).unwrap(),
        ))))
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(&scales, 2))
        .unwrap_err();
    assert_eq!(beyond.kind(), ErrorKind::Configuration, "beyond schedule");
}

#[test]
fn above_the_dense_dimension_cap_the_flag_is_the_diagonal_run() {
    let d = 300;
    let scales: Vec<f64> = (0..d).map(|i| 0.5 + (i % 7) as f64 * 0.3).collect();
    let target = Gaussian::new(scales.clone(), 0.0);
    let short = |a: Option<Adaptation>| {
        let s = Sampler::new()
            .warmup(300)
            .draws(50)
            .chains(2)
            .seed(85)
            .limits(Limits::new().admit_worst_case());
        let s = match a {
            Some(a) => s.adaptation(a),
            None => s,
        };
        s.run(&target, &starts(&scales, 2)).unwrap()
    };
    let default = short(None);
    let auto = short(Some(Adaptation::Custom(warmup(Some(hessian())))));
    assert_same_run(&default, &auto);
    assert!(auto.chains()[0].telemetry().dense_auto_select().is_none());
}
