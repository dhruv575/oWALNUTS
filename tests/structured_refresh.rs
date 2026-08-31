//! Boundary-refreshed structured metrics: installation seam exactness,
//! fallback semantics, determinism, preflight, and a local-level learning
//! check.

use std::{
    num::NonZeroUsize,
    sync::atomic::{AtomicUsize, Ordering},
};

use owalnuts::walnutpie::{
    ChainOutput, DirectOriginalQMass, Error, ErrorKind, InitialStepSearchConfig, KernelTuning,
    PaperAdaptationConfig, RunConfig, RunControl, STRUCTURED_REFRESH_REVISION, StepSearchReason,
    StructuredBlockMass, StructuredCovarianceBlock, StructuredRefreshConfig,
    StructuredRefreshOutcome, StructuredRefreshRestartPolicy, Target, TargetError, WarmupConfig,
    WarmupWindowConfig, WindowSummary, preflight_chains_structured_refresh,
    sample_chains_structured_refresh, sample_direct_original_q, sample_structured_refresh,
};

struct TenDimensionalGaussian;

impl Target for TenDimensionalGaussian {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (out, value) in gradient.iter_mut().zip(position) {
            *out = -*value;
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

fn fixture_mass() -> StructuredBlockMass {
    StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
        diagonal: (0..10).map(|i| 1.0 + 0.05 * i as f64).collect(),
        subdiagonal: vec![0.2; 9],
    }])
    .unwrap()
}

fn fixed_step_config(seed: u64, adapt_mass: bool) -> RunConfig {
    RunConfig::new(40, NonZeroUsize::new(8).unwrap(), seed).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_step_size_adaptation(false)
            .with_mass_adaptation(adapt_mass),
    )
}

fn identity_refresh(
    _: &WindowSummary,
    current: &StructuredBlockMass,
) -> Result<StructuredBlockMass, Error> {
    Ok(current.clone())
}

fn variance_refresh(
    summary: &WindowSummary,
    current: &StructuredBlockMass,
) -> Result<StructuredBlockMass, Error> {
    let coordinates: Vec<usize> = (0..current.dimension()).collect();
    let precision = summary.regularized_precision(&coordinates)?;
    StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
        diagonal: precision.iter().map(|p| p.sqrt()).collect(),
        subdiagonal: vec![0.0; current.dimension() - 1],
    }])
}

#[test]
fn identity_refresh_matches_the_fixed_direct_driver_exactly() {
    let mass = fixture_mass();
    let refreshed = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &identity_refresh,
        &StructuredRefreshConfig::default(),
        &fixed_step_config(0x5e7a, true),
        &RunControl::new(),
    )
    .unwrap();
    let fixed = sample_direct_original_q(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &DirectOriginalQMass::StructuredPath(mass.clone()),
        &fixed_step_config(0x5e7a, false),
    )
    .unwrap();
    assert_eq!(
        refreshed.chain().metadata().algorithm_revision(),
        STRUCTURED_REFRESH_REVISION
    );
    assert_eq!(refreshed.chain().samples(), fixed.samples());
    assert_eq!(refreshed.chain().diagnostics().len(), 48);
    for (left, right) in refreshed
        .chain()
        .diagnostics()
        .iter()
        .zip(fixed.diagnostics())
    {
        assert_eq!(left.depth(), right.depth());
        assert_eq!(left.direction_draws(), right.direction_draws());
        assert_eq!(left.uniform_draws(), right.uniform_draws());
        assert_eq!(left.leaves_built(), right.leaves_built());
    }
    // The persistent cache evaluates the initial state exactly once.
    assert_eq!(
        refreshed.chain().telemetry().total().target_calls_initial(),
        1
    );
    let windows = refreshed
        .chain()
        .metadata()
        .warmup_schedule()
        .map(|schedule| schedule.windows().len())
        .unwrap_or(0);
    assert!(windows >= 1);
    assert_eq!(refreshed.metric_updates().len(), windows);
    for (index, update) in refreshed.metric_updates().iter().enumerate() {
        assert_eq!(update.window_index(), index);
        assert_eq!(update.outcome(), StructuredRefreshOutcome::Installed);
        assert_eq!(update.generation(), index + 1);
        assert!(update.sample_count() >= 2);
        assert!(!update.dual_averaging_restarted());
        assert!(update.covariance_diagonal_range().is_some());
    }
    assert_eq!(refreshed.final_mass(), &mass);
}

#[test]
fn failed_skipped_and_mismatched_refreshes_keep_the_previous_mass() {
    let mass = fixture_mass();
    let config = fixed_step_config(0x5e7b, true);
    let reference = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &identity_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();

    let failing =
        |_: &WindowSummary, _: &StructuredBlockMass| -> Result<StructuredBlockMass, Error> {
            Err(Error::metric_candidate("no candidate"))
        };
    let failed = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &failing,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(failed.chain().samples(), reference.chain().samples());
    assert!(!failed.metric_updates().is_empty());
    for update in failed.metric_updates() {
        assert_eq!(update.outcome(), StructuredRefreshOutcome::RefreshFailed);
        assert_eq!(update.failure(), Some("no candidate"));
        assert_eq!(update.generation(), 0);
        assert!(update.covariance_diagonal_range().is_none());
    }
    assert_eq!(failed.final_mass(), &mass);

    let wrong_dimension = |_: &WindowSummary, _: &StructuredBlockMass| {
        StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: vec![1.0; 3],
            subdiagonal: vec![0.0; 2],
        }])
    };
    let mismatched = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &wrong_dimension,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(mismatched.chain().samples(), reference.chain().samples());
    assert!(
        mismatched
            .metric_updates()
            .iter()
            .all(|update| update.outcome() == StructuredRefreshOutcome::DimensionMismatch)
    );
    assert_eq!(mismatched.final_mass(), &mass);

    let too_few = StructuredRefreshConfig::default()
        .with_minimum_samples(NonZeroUsize::new(1_000_000).unwrap());
    let skipped = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &identity_refresh,
        &too_few,
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert!(
        skipped
            .metric_updates()
            .iter()
            .all(|update| update.outcome() == StructuredRefreshOutcome::InsufficientSamples)
    );
    assert_eq!(skipped.chain().samples(), reference.chain().samples());

    let panicking = |_: &WindowSummary,
                     _: &StructuredBlockMass|
     -> Result<StructuredBlockMass, Error> { panic!("refresh panic") };
    let error = sample_structured_refresh(
        &TenDimensionalGaussian,
        &[0.3; 10],
        &mass,
        &panicking,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Panic);
}

#[test]
fn chains_are_sequential_parallel_identical_and_restart_policies_are_honoured() {
    let mass = fixture_mass();
    let search = InitialStepSearchConfig::new(
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(16).unwrap(),
    )
    .unwrap();
    let config = RunConfig::new(60, NonZeroUsize::new(6).unwrap(), 0x5e7c).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_mass_adaptation(true)
            .with_initial_step_search(search),
    );
    let starts = vec![vec![0.5; 10], vec![-0.5; 10], vec![0.1; 10]];
    let sequential = sample_chains_structured_refresh(
        &TenDimensionalGaussian,
        &starts,
        &mass,
        &variance_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        NonZeroUsize::new(1).unwrap(),
        &RunControl::new(),
    )
    .unwrap();
    let parallel = sample_chains_structured_refresh(
        &TenDimensionalGaussian,
        &starts,
        &mass,
        &variance_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        NonZeroUsize::new(3).unwrap(),
        &RunControl::new(),
    )
    .unwrap();
    // `thread_count` metadata differs by design; everything else must agree.
    assert_eq!(sequential.metric_updates(), parallel.metric_updates());
    assert_eq!(sequential.final_masses(), parallel.final_masses());
    for (left, right) in sequential
        .chains()
        .chains()
        .iter()
        .zip(parallel.chains().chains())
    {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
    }
    assert_eq!(sequential.chains().chains().len(), 3);
    assert_eq!(
        sequential.chains().algorithm_revision(),
        STRUCTURED_REFRESH_REVISION
    );
    for (chain, updates) in sequential.metric_updates().iter().enumerate() {
        assert!(
            updates
                .iter()
                .any(|update| update.outcome() == StructuredRefreshOutcome::Installed)
        );
        for update in updates
            .iter()
            .filter(|update| update.outcome() == StructuredRefreshOutcome::Installed)
        {
            assert!(update.dual_averaging_restarted());
            assert!(update.step_after_search().is_some());
            assert_eq!(update.step_after_restart(), update.step_after_search());
        }
        assert_ne!(sequential.final_masses()[chain], mass);
        let output = &sequential.chains().chains()[chain];
        assert!(
            output
                .telemetry()
                .step_searches()
                .iter()
                .any(|event| matches!(event.reason(), StepSearchReason::Initial))
        );
    }
    let single = sample_structured_refresh(
        &TenDimensionalGaussian,
        &starts[0],
        &mass,
        &variance_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(
        single.chain().samples(),
        sequential.chains().chains()[0].samples()
    );

    let continued = sample_structured_refresh(
        &TenDimensionalGaussian,
        &starts[0],
        &mass,
        &variance_refresh,
        &StructuredRefreshConfig::default()
            .with_restart_policy(StructuredRefreshRestartPolicy::ContinueDualAveraging),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert!(
        continued
            .metric_updates()
            .iter()
            .filter(|update| update.outcome() == StructuredRefreshOutcome::Installed)
            .all(|update| !update.dual_averaging_restarted())
    );
}

#[test]
fn preflight_is_zero_callback_and_invalid_configurations_fail_closed() {
    struct Counted(AtomicUsize);
    impl Target for Counted {
        fn dimension(&self) -> usize {
            10
        }
        fn log_density_gradient(
            &self,
            position: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            self.0.fetch_add(1, Ordering::AcqRel);
            TenDimensionalGaussian.log_density_gradient(position, gradient)
        }
    }
    let target = Counted(AtomicUsize::new(0));
    let mass = fixture_mass();
    let starts = vec![vec![0.0; 10], vec![1.0; 10]];
    let report =
        preflight_chains_structured_refresh(&target, &starts, &mass, &fixed_step_config(1, true))
            .unwrap();
    assert_eq!(report.chains(), 2);
    assert_eq!(report.dimension(), 10);

    let no_warmup = RunConfig::new(40, NonZeroUsize::new(8).unwrap(), 1);
    assert_eq!(
        preflight_chains_structured_refresh(&target, &starts, &mass, &no_warmup)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    let no_mass_adaptation = fixed_step_config(1, false);
    assert_eq!(
        preflight_chains_structured_refresh(&target, &starts, &mass, &no_mass_adaptation)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    let paper = RunConfig::new(40, NonZeroUsize::new(8).unwrap(), 1).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_paper_adaptation(PaperAdaptationConfig::default()),
    );
    assert_eq!(
        preflight_chains_structured_refresh(&target, &starts, &mass, &paper)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        preflight_chains_structured_refresh(
            &target,
            &[vec![0.0; 3]],
            &mass,
            &fixed_step_config(1, true)
        )
        .unwrap_err()
        .kind(),
        ErrorKind::Configuration
    );
    let error = sample_chains_structured_refresh(
        &target,
        &starts,
        &mass,
        &identity_refresh,
        &StructuredRefreshConfig::default(),
        &no_mass_adaptation,
        NonZeroUsize::new(2).unwrap(),
        &RunControl::new(),
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert_eq!(target.0.load(Ordering::Acquire), 0);
}

/// Gaussian local-level path with tridiagonal precision
/// `H = Q_rw(sigma) + diag(c)`; log density `-x'Hx/2`.
struct LocalLevelPath {
    diagonal: Vec<f64>,
    off: f64,
}

impl LocalLevelPath {
    fn new(t: usize) -> Self {
        let sigma: f64 = 0.1;
        let s2 = 1.0 / (sigma * sigma);
        let mut diagonal = vec![0.0; t];
        for (i, value) in diagonal.iter_mut().enumerate() {
            if i + 1 < t {
                *value += s2;
            }
            if i > 0 {
                *value += s2;
            }
            *value += 4.0 + (i % 3) as f64;
        }
        Self { diagonal, off: -s2 }
    }

    fn precision_block(&self) -> StructuredBlockMass {
        let t = self.diagonal.len();
        let mut d = vec![0.0; t];
        let mut l = vec![0.0; t - 1];
        d[0] = self.diagonal[0].sqrt();
        for i in 1..t {
            l[i - 1] = self.off / d[i - 1];
            d[i] = (self.diagonal[i] - l[i - 1] * l[i - 1]).sqrt();
        }
        StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: d,
            subdiagonal: l,
        }])
        .unwrap()
    }

    /// Exact marginal variances from a dense Gauss–Jordan inverse of `H`.
    fn marginal_variances(&self) -> Vec<f64> {
        let t = self.diagonal.len();
        let mut a = vec![0.0; t * t];
        for i in 0..t {
            a[i * t + i] = self.diagonal[i];
            if i + 1 < t {
                a[i * t + i + 1] = self.off;
                a[(i + 1) * t + i] = self.off;
            }
        }
        let mut inv = vec![0.0; t * t];
        for i in 0..t {
            inv[i * t + i] = 1.0;
        }
        for col in 0..t {
            let pivot = a[col * t + col];
            for j in 0..t {
                a[col * t + j] /= pivot;
                inv[col * t + j] /= pivot;
            }
            for row in 0..t {
                if row != col {
                    let factor = a[row * t + col];
                    for j in 0..t {
                        a[row * t + j] -= factor * a[col * t + j];
                        inv[row * t + j] -= factor * inv[col * t + j];
                    }
                }
            }
        }
        (0..t).map(|i| inv[i * t + i]).collect()
    }
}

impl Target for LocalLevelPath {
    fn dimension(&self) -> usize {
        self.diagonal.len()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let t = position.len();
        let mut log_density = 0.0;
        for i in 0..t {
            let mut hx = self.diagonal[i] * position[i];
            if i > 0 {
                hx += self.off * position[i - 1];
            }
            if i + 1 < t {
                hx += self.off * position[i + 1];
            }
            gradient[i] = -hx;
            log_density -= 0.5 * position[i] * hx;
        }
        Ok(log_density)
    }
}

fn mean_retained_depth(output: &ChainOutput, discarded: usize) -> f64 {
    let depths: Vec<usize> = output
        .diagnostics()
        .iter()
        .skip(discarded)
        .map(|d| d.depth())
        .collect();
    depths.iter().sum::<usize>() as f64 / depths.len() as f64
}

#[test]
fn local_level_refresh_learns_precision_and_the_exact_block_mixes_faster() {
    let t = 30;
    let target = LocalLevelPath::new(t);
    let identity = StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
        diagonal: vec![1.0; t],
        subdiagonal: vec![0.0; t - 1],
    }])
    .unwrap();
    let windows = WarmupWindowConfig::new(25, NonZeroUsize::new(100).unwrap(), 25).unwrap();
    let discarded = 400;
    let config = RunConfig::new(discarded, NonZeroUsize::new(300).unwrap(), 0x10ca_1e0e)
        .with_tuning(
            KernelTuning::new(
                0.05,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(3).unwrap(),
                1.0,
            )
            .unwrap(),
        )
        .with_warmup(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_mass_adaptation(true)
                .with_windows(windows),
        )
        .with_maximum_depth_stop_limit(usize::MAX);
    let start = vec![0.2; t];

    // Variance-based refresh: the installed diagonal must be closer to the
    // exact marginal precision than the identity it started from.
    let learned = sample_structured_refresh(
        &target,
        &start,
        &identity,
        &variance_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert!(
        learned
            .metric_updates()
            .iter()
            .any(|update| update.outcome() == StructuredRefreshOutcome::Installed)
    );
    let variances = target.marginal_variances();
    let installed = learned.final_mass().covariance_diagonal();
    let rms =
        |values: &[f64]| (values.iter().map(|v| v * v).sum::<f64>() / values.len() as f64).sqrt();
    let identity_error: Vec<f64> = variances.iter().map(|v| v.ln()).collect();
    let learned_error: Vec<f64> = installed
        .iter()
        .zip(&variances)
        .map(|(m, v)| (m * v).ln())
        .collect();
    assert!(
        rms(&learned_error) < 0.5 * rms(&identity_error),
        "learned {} identity {}",
        rms(&learned_error),
        rms(&identity_error)
    );

    // The exact posterior-precision block installed at the first boundary.
    let exact = target.precision_block();
    let exact_refresh = |_: &WindowSummary, _: &StructuredBlockMass| Ok(exact.clone());
    let refreshed = sample_structured_refresh(
        &target,
        &start,
        &identity,
        &exact_refresh,
        &StructuredRefreshConfig::default(),
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(refreshed.final_mass(), &exact);
    assert_eq!(refreshed.metric_updates()[0].generation(), 1);
    assert!(
        mean_retained_depth(refreshed.chain(), discarded)
            < mean_retained_depth(learned.chain(), discarded)
    );
    let mean0 = refreshed
        .chain()
        .samples()
        .chunks_exact(t)
        .map(|draw| draw[0])
        .sum::<f64>()
        / 300.0;
    assert!(mean0.abs() < 10.0 * variances[0].sqrt() / 300f64.sqrt());
    assert_eq!(refreshed.chain().telemetry().retained().divergences(), 0);
}
