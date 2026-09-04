//! `owalnuts::sampler` is a thin wrapper: every `Sampler::run` path must be
//! bit-identical to the `walnutpie` facade it dispatches to.

use std::num::NonZeroUsize;
use std::sync::Arc;
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use owalnuts::sampler::{
    Adaptation, Cancellation, ChainOutput, DEFAULT_CHAIN_RESCUE, DEFAULT_METRIC_REGULARIZATION,
    DEFAULT_RANDOM_START_CHAINS, DEFAULT_U_TURN_RULE, DEFAULT_WARMUP_EXHAUSTION, Error, ErrorKind,
    Init, Limits, Metric, Sampler, StructuredBlockMass, StructuredCovarianceBlock,
    StructuredRefreshConfig, Target, TargetError, Tuning, WindowSummary, uniform_starts,
};
use owalnuts::walnutpie::{
    DenseMass, DiagonalMass, KernelOptions, KernelTuning, PaperAdaptationConfig, RunConfig,
    RunControl, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    sample_chains, sample_chains_dense, sample_chains_structured, sample_chains_structured_refresh,
    sample_chains_with_control, sample_chains_with_target_budget,
};

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
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

struct Flag(AtomicBool);

impl Cancellation for Flag {
    fn is_cancelled(&self) -> bool {
        self.0.load(Ordering::Relaxed)
    }
}

const WARMUP: usize = 60;
const DRAWS: usize = 8;
const SEED: u64 = 0x5eed_0002;

fn nz(value: usize) -> NonZeroUsize {
    NonZeroUsize::new(value).unwrap()
}

fn starts(dimension: usize) -> Vec<Vec<f64>> {
    (0..3)
        .map(|chain| {
            (0..dimension)
                .map(|i| 0.1 * (chain as f64 + 1.0) * ((i % 3) as f64 - 1.0))
                .collect()
        })
        .collect()
}

/// The same numbers and kernel options as `Tuning::default()`: `h = 0.5`,
/// depth 10, one micro-step, eight levels, `delta = 1`, and the momentum-sum
/// U-turn rule (the post-WP31 default; `KernelOptions::default()` is the
/// frozen endpoint rule).
fn kernel_tuning() -> KernelTuning {
    KernelTuning::new(0.5, nz(10), nz(1), nz(8), 1.0)
        .unwrap()
        .with_options(KernelOptions {
            u_turn: DEFAULT_U_TURN_RULE,
            ..KernelOptions::default()
        })
}

fn config(warmup: Option<WarmupConfig>) -> RunConfig {
    // `Sampler` caches the initial evaluation by default (0.2.0); mirror it.
    let config = RunConfig::new(WARMUP, nz(DRAWS), SEED)
        .with_tuning(kernel_tuning())
        .with_cached_initial_evaluation(true);
    match warmup {
        Some(warmup) => config.with_warmup(warmup),
        None => config,
    }
}

fn sampler() -> Sampler {
    Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .seed(SEED)
        .threads(1)
        .tuning(Tuning::default())
        // Compare against the plain facades, which admit conservatively.
        .limits(Limits::new().admit_conservative())
}

/// Equal draws, diagnostics, and telemetry; metadata records the thread count.
fn assert_same_run(left: &[ChainOutput], right: &[ChainOutput]) {
    assert_eq!(left.len(), right.len());
    for (left, right) in left.iter().zip(right) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
    }
}

fn structured_mass() -> StructuredBlockMass {
    StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
        diagonal: (0..10).map(|i| 1.0 + 0.05 * i as f64).collect(),
        subdiagonal: vec![0.2; 9],
    }])
    .unwrap()
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
fn identity_metric_matches_the_diagonal_facade_without_mass_adaptation() {
    let target = Gaussian(3);
    let posterior = sampler()
        .metric(Metric::Identity)
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_mass_adaptation(false),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains());
    assert_eq!(posterior.chain_count(), 3);
    assert_eq!(posterior.dimension(), 3);
    assert_eq!(posterior.draws_per_chain(), DRAWS);
    assert_eq!(posterior.draws().count(), 3 * DRAWS);
    assert_eq!(posterior.parameter(0).count(), 3 * DRAWS);
    assert_eq!(posterior.seed(), SEED);
    assert_eq!(posterior.algorithm_revision(), direct.algorithm_revision());
    assert_eq!(
        posterior.total_target_calls(),
        direct
            .chains()
            .iter()
            .map(|chain| chain.telemetry().total().target_calls_total())
            .sum::<usize>()
    );
    assert_eq!(posterior.into_inner(), direct);
}

#[test]
fn adaptive_and_fixed_diagonal_metrics_match_the_diagonal_facade() {
    let target = Gaussian(3);
    let adaptive = sampler().run(&target, &starts(3)).unwrap();
    let direct = sample_chains(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(adaptive.chains(), direct.chains());
    assert!(adaptive.metric_updates().is_empty());

    let fixed = sampler()
        .metric(Metric::fixed_diagonal(vec![0.5, 2.0, 1.0]))
        .adaptation(Adaptation::None)
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains(
        &target,
        &starts(3),
        &DiagonalMass::from_diagonal(vec![0.5, 2.0, 1.0]).unwrap(),
        &config(None),
        nz(1),
    )
    .unwrap();
    assert_eq!(fixed.chains(), direct.chains());

    let started = sampler()
        .metric(Metric::Diagonal {
            adapt: true,
            initial: Some(vec![0.5, 2.0, 1.0]),
        })
        .adaptation(Adaptation::DualAveraging { target_accept: 0.9 })
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains(
        &target,
        &starts(3),
        &DiagonalMass::from_diagonal(vec![0.5, 2.0, 1.0]).unwrap(),
        &config(Some(
            WarmupConfig::new(0.9)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(started.chains(), direct.chains());
}

#[test]
fn default_multi_chain_warmup_is_explicit_no_rescue_bit_for_bit() {
    let target = Gaussian(3);
    let starts = starts(3);
    let default = sampler().run(&target, &starts).unwrap();
    let explicit = sampler()
        .adaptation(Adaptation::Custom(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        ))
        .run(&target, &starts)
        .unwrap();

    assert_eq!(DEFAULT_CHAIN_RESCUE, None);
    assert!(
        default
            .telemetry()
            .all(|telemetry| telemetry.chain_rescues().is_empty())
    );
    assert_eq!(default, explicit);
}

#[test]
fn adaptive_dense_metric_matches_the_dense_facade() {
    let target = Gaussian(3);
    let posterior = sampler()
        .metric(Metric::dense())
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains_dense(
        &target,
        &starts(3),
        &DenseMass::identity(nz(3)).unwrap(),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains());

    let matrix = vec![1.5, 0.25, 0.0, 0.25, 0.75, 0.0, 0.0, 0.0, 1.0];
    let fixed = sampler()
        .metric(Metric::fixed_dense(matrix.clone()))
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains_dense(
        &target,
        &starts(3),
        &DenseMass::from_matrix(matrix, 3).unwrap(),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_mass_adaptation(false),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(fixed.chains(), direct.chains());
}

#[test]
fn fixed_structured_metric_matches_the_structured_facade() {
    let target = Gaussian(10);
    let mass = structured_mass();
    let posterior = sampler()
        .metric(Metric::Structured(mass.clone()))
        .run(&target, &starts(10))
        .unwrap();
    let direct = sample_chains_structured(
        &target,
        &starts(10),
        &mass,
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_mass_adaptation(false),
        )),
        nz(1),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains());
}

#[test]
fn structured_refresh_matches_the_refresh_facade() {
    let target = Gaussian(10);
    let mass = structured_mass();
    let posterior = sampler()
        .metric(Metric::structured_refresh(mass.clone(), variance_refresh))
        .run(&target, &starts(10))
        .unwrap();
    let direct = sample_chains_structured_refresh(
        &target,
        &starts(10),
        &mass,
        &variance_refresh,
        &StructuredRefreshConfig::default(),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains().chains());
    assert_eq!(posterior.metric_updates(), direct.metric_updates());
    assert_eq!(posterior.final_masses(), direct.final_masses());
    assert_eq!(
        posterior.algorithm_revision(),
        direct.chains().algorithm_revision()
    );
    assert!(
        posterior
            .metric_updates()
            .iter()
            .any(|chain| !chain.is_empty())
    );
}

#[test]
fn paper_adaptation_matches_the_paper_warmup_configuration() {
    let target = Gaussian(3);
    let paper = PaperAdaptationConfig::default();
    // At the sampler defaults (depth 10, eight refinement levels) 150 warmup
    // transitions exceed the conservative facade ceiling, so both sides admit
    // the exact worst case, as `Sampler` does by default.
    let base = RunConfig::new(150, nz(DRAWS), SEED)
        .with_tuning(kernel_tuning())
        .with_cached_initial_evaluation(true)
        .with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_paper_adaptation(paper)
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        );
    let worst = base.worst_case_target_evaluations(nz(3)).unwrap();
    let posterior = sampler()
        .warmup(150)
        .metric(Metric::Identity)
        .adaptation(Adaptation::Paper(paper))
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains_with_target_budget(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &base,
        nz(1),
        TargetEvaluationAdmissionLimit::new(nz(worst)),
        &TargetEvaluationBudget::new(nz(worst)),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains());
    assert!(
        posterior
            .telemetry()
            .all(|telemetry| !telemetry.paper_adaptation_updates().is_empty())
    );
    assert!(
        posterior
            .telemetry()
            .all(|telemetry| telemetry.chain_rescues().is_empty())
    );
}

#[test]
fn evaluation_budget_matches_the_budgeted_facade() {
    let target = Gaussian(3);
    let base = config(Some(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
            .with_mass_adaptation(false),
    ));
    let worst = base.worst_case_target_evaluations(nz(3)).unwrap();
    assert_eq!(
        sampler()
            .metric(Metric::Identity)
            .worst_case_target_evaluations(3)
            .unwrap(),
        worst
    );
    let posterior = sampler()
        .metric(Metric::Identity)
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts(3))
        .unwrap();
    let direct = sample_chains_with_target_budget(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &base,
        nz(1),
        TargetEvaluationAdmissionLimit::new(nz(worst)),
        &TargetEvaluationBudget::new(nz(worst)),
    )
    .unwrap();
    assert_eq!(posterior.chains(), direct.chains());
    assert_eq!(
        posterior
            .metadata()
            .map(|metadata| metadata.effective_max_target_evaluations())
            .collect::<Vec<_>>(),
        vec![worst; 3]
    );

    // An explicit ceiling that the run exhausts fails the same way.
    let exhausted = sampler()
        .metric(Metric::Identity)
        .limits(Limits::new().max_target_evaluations(worst))
        .run(&target, &starts(3));
    assert_eq!(exhausted.unwrap().chains(), direct.chains());
    let tiny = TargetEvaluationBudget::new(nz(5));
    let direct_error = sample_chains_with_target_budget(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &base,
        nz(1),
        TargetEvaluationAdmissionLimit::new(nz(worst)),
        &tiny,
    )
    .unwrap_err();
    // The sampler admits against the same number it budgets, so a ceiling
    // below the worst case is rejected at admission before any callback.
    let sampler_error = sampler()
        .metric(Metric::Identity)
        .limits(Limits::new().max_target_evaluations(5))
        .run(&target, &starts(3))
        .unwrap_err();
    assert_ne!(direct_error.kind(), ErrorKind::Cancelled);
    assert_ne!(sampler_error.kind(), ErrorKind::Cancelled);

    // Structured metrics have no budgeted admission; the runtime budget is
    // applied by wrapping the target, which is bit-identical when it holds.
    let mass = structured_mass();
    let budgeted = sampler()
        .metric(Metric::Structured(mass.clone()))
        .limits(Limits::new().max_target_evaluations(usize::MAX))
        .run(&Gaussian(10), &starts(10))
        .unwrap();
    let plain = sampler()
        .metric(Metric::Structured(mass))
        .run(&Gaussian(10), &starts(10))
        .unwrap();
    assert_eq!(budgeted.chains(), plain.chains());
}

#[test]
fn cancellation_and_timeout_match_run_control() {
    let target = Gaussian(3);
    let flag = Arc::new(Flag(AtomicBool::new(true)));
    let cancelled = sampler()
        .limits(Limits::new().cancellation(flag.clone()))
        .run(&target, &starts(3))
        .unwrap_err();
    let direct = sample_chains_with_control(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
        &RunControl::new().with_cancellation(&*flag),
    )
    .unwrap_err();
    assert_eq!(cancelled.kind(), ErrorKind::Cancelled);
    assert_eq!(cancelled.kind(), direct.kind());
    assert_eq!(cancelled.chain(), direct.chain());

    let timed_out = sampler()
        .limits(Limits::new().timeout(Duration::ZERO))
        .run(&target, &starts(3))
        .unwrap_err();
    let direct = sample_chains_with_control(
        &target,
        &starts(3),
        &DiagonalMass::identity(nz(3)),
        &config(Some(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION),
        )),
        nz(1),
        &RunControl::new().with_timeout(Duration::ZERO).unwrap(),
    )
    .unwrap_err();
    assert_eq!(timed_out.kind(), direct.kind());

    // A flag that is never raised changes nothing.
    flag.0.store(false, Ordering::Relaxed);
    let controlled = sampler()
        .limits(Limits::new().admit_conservative().cancellation(flag))
        .run(&target, &starts(3))
        .unwrap();
    let free = sampler().run(&target, &starts(3)).unwrap();
    assert_eq!(controlled, free);
}

#[test]
fn parallel_and_sequential_runs_are_identical_and_chains_replicate_a_start() {
    let target = Gaussian(10);
    let sequential = sampler().run(&target, &starts(10)).unwrap();
    let parallel = sampler().threads(3).run(&target, &starts(10)).unwrap();
    let default_threads = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .seed(SEED)
        .run(&target, &starts(10))
        .unwrap();
    assert_same_run(sequential.chains(), parallel.chains());
    assert_same_run(sequential.chains(), default_threads.chains());
    assert_eq!(
        parallel
            .metadata()
            .map(|metadata| metadata.thread_count())
            .collect::<Vec<_>>(),
        vec![3; 3]
    );

    let mass = structured_mass();
    let sequential = sampler()
        .metric(Metric::structured_refresh(mass.clone(), variance_refresh))
        .run(&target, &starts(10))
        .unwrap();
    let parallel = sampler()
        .threads(3)
        .metric(Metric::structured_refresh(mass, variance_refresh))
        .run(&target, &starts(10))
        .unwrap();
    assert_same_run(sequential.chains(), parallel.chains());
    assert_eq!(sequential.metric_updates(), parallel.metric_updates());

    let replicated = sampler()
        .chains(3)
        .run(&target, &[starts(10)[0].clone()])
        .unwrap();
    let explicit = sampler()
        .run(&target, &vec![starts(10)[0].clone(); 3])
        .unwrap();
    assert_eq!(replicated.chains(), explicit.chains());
    assert_eq!(
        sampler()
            .chains(2)
            .run(&target, &starts(10))
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
}

#[test]
fn invalid_builders_fail_closed() {
    let target = Gaussian(3);
    let errors = [
        sampler().draws(0).run(&target, &starts(3)),
        sampler().threads(0).run(&target, &starts(3)),
        sampler()
            .tuning(Tuning::new().max_depth(0))
            .run(&target, &starts(3)),
        sampler()
            .adaptation(Adaptation::None)
            .run(&target, &starts(3)),
        sampler()
            .metric(Metric::Structured(structured_mass()))
            .run(&target, &starts(3)),
        sampler().run(&target, &[]),
    ];
    for error in errors {
        assert!(error.is_err());
    }
    assert!(
        sampler()
            .metric(Metric::Identity)
            .adaptation(Adaptation::None)
            .run(&target, &starts(3))
            .is_ok()
    );
}

// ---------------------------------------------------------------------------
// Init: Stan-style uniform(-r, r) starts with retries.

/// A standard normal that is a recoverable zero-density failure wherever the
/// first coordinate is negative (a Stan exception) or exceeds one (a
/// gradient overflow mapped by the BridgeStan integration).
struct HalfLine(usize);

impl Target for HalfLine {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (out, value) in gradient.iter_mut().zip(position) {
            *out = -*value;
        }
        if position[0] < 0.0 {
            return Err(TargetError::recoverable("log of a negative argument"));
        }
        if position[0] > 1.0 {
            return Err(TargetError::recoverable("gradient overflow"));
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

/// A target that (wrongly, but as raw callbacks can) returns `Ok(NaN)` left
/// of zero and a nonfinite gradient right of one: the start search must
/// reject both without relying on the error path.
struct RawNan;

impl Target for RawNan {
    fn dimension(&self) -> usize {
        2
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        gradient[0] = -position[0];
        gradient[1] = -position[1];
        if position[0] < 0.0 {
            return Ok(f64::NAN);
        }
        if position[0] > 1.0 {
            gradient[1] = f64::INFINITY;
        }
        Ok(-0.5 * (position[0] * position[0] + position[1] * position[1]))
    }
}

struct Void;

impl Target for Void {
    fn dimension(&self) -> usize {
        2
    }
    fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
        Err(TargetError::recoverable("nowhere is evaluable"))
    }
}

#[test]
fn uniform_starts_are_deterministic_inside_the_box_and_evaluable() {
    let target = HalfLine(3);
    let first = uniform_starts(&target, 4, SEED, 2.0, 100).unwrap();
    let second = uniform_starts(&target, 4, SEED, 2.0, 100).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.len(), 4);
    for start in &first {
        assert_eq!(start.len(), 3);
        assert!(start.iter().all(|x| x.abs() < 2.0));
        // Retries stopped only at a finite log density and gradient.
        assert!(start[0] >= 0.0 && start[0] <= 1.0, "{start:?}");
    }
    let other = uniform_starts(&target, 4, SEED + 1, 2.0, 100).unwrap();
    assert_ne!(first, other);
    for start in uniform_starts(&RawNan, 8, SEED, 2.0, 100).unwrap() {
        assert!(start[0] >= 0.0 && start[0] <= 1.0, "{start:?}");
    }
    // The start RNG is independent of the chain seeds: a wider box changes
    // the coordinates, not the retry logic.
    let wide = uniform_starts(&Gaussian(3), 2, SEED, 5.0, 1).unwrap();
    assert!(wide.iter().flatten().any(|x| x.abs() > 2.0));
}

#[test]
fn uniform_starts_fail_clearly_after_max_attempts() {
    let error = uniform_starts(&Void, 2, SEED, 2.0, 7).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Numerical);
    let message = error.to_string();
    assert!(message.contains("chain 0"), "{message}");
    assert!(message.contains("after 7"), "{message}");
    assert!(message.contains("nowhere is evaluable"), "{message}");

    // A start box that is entirely in the NaN region exhausts the attempts
    // with the last failure named.
    struct Negative;
    impl Target for Negative {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(&self, _: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            g[0] = 0.0;
            Ok(f64::NEG_INFINITY)
        }
    }
    let error = uniform_starts(&Negative, 1, SEED, 2.0, 3).unwrap_err();
    assert!(error.to_string().contains("log density is -inf"), "{error}");

    assert_eq!(
        uniform_starts(&Gaussian(2), 1, SEED, 0.0, 3)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        uniform_starts(&Gaussian(2), 1, SEED, 2.0, 0)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        uniform_starts(&Gaussian(2), 0, SEED, 2.0, 1)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
}

#[test]
fn uniform_starts_propagate_fatal_target_errors() {
    struct Broken;
    impl Target for Broken {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
            Err(TargetError::new("bug"))
        }
    }
    let error = uniform_starts(&Broken, 1, SEED, 2.0, 100).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert!(error.to_string().contains("bug"), "{error}");
}

#[test]
fn run_with_init_matches_run_from_the_drawn_starts() {
    let target = HalfLine(3);
    let init = Init::Uniform {
        radius: 2.0,
        max_attempts: 100,
    };
    let posterior = sampler()
        .chains(3)
        .metric(Metric::Identity)
        .run_with_init(&target, &init)
        .unwrap();
    let starts = uniform_starts(&target, 3, SEED, 2.0, 100).unwrap();
    let direct = sampler()
        .metric(Metric::Identity)
        .run(&target, &starts)
        .unwrap();
    assert_eq!(posterior.chains(), direct.chains());
    assert_eq!(posterior.chain_count(), 3);

    // `Init::Given` is `run`; `run_from_random_starts` is `Init::uniform()`
    // with four chains when none were requested.
    let given = sampler()
        .metric(Metric::Identity)
        .run_with_init(&target, &Init::Given(starts.clone()))
        .unwrap();
    assert_eq!(given.chains(), direct.chains());
    let random = sampler()
        .metric(Metric::Identity)
        .run_from_random_starts(&target)
        .unwrap();
    assert_eq!(random.chain_count(), DEFAULT_RANDOM_START_CHAINS);
    assert_eq!(Init::default(), Init::uniform());
    let again = sampler()
        .metric(Metric::Identity)
        .run_from_random_starts(&target)
        .unwrap();
    assert_eq!(random.chains(), again.chains());
}

/// The structured paths have no budgeted admission variant; with the
/// `research` feature the sampler raises the `RunConfig` admission ceiling to
/// the worst case (`Limits::admit_worst_case`) so the sampler defaults are
/// admitted on a structured metric as on the diagonal path. 500 transitions
/// at depth 10 with eight refinement levels have a worst case above the
/// conservative 113M ceiling while a 2-D Gaussian does negligible work.
#[cfg(feature = "research")]
#[test]
fn structured_metric_is_admitted_with_its_worst_case_under_research() {
    use owalnuts::walnutpie::CONSERVATIVE_MAX_TARGET_EVALUATIONS;
    let mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
        diagonal: vec![1.0, 1.2],
        subdiagonal: vec![0.1],
    }])
    .unwrap();
    let sampler = Sampler::new()
        .warmup(300)
        .draws(200)
        .seed(SEED)
        .metric(Metric::Structured(mass));
    assert!(
        sampler.worst_case_target_evaluations(1).unwrap() > CONSERVATIVE_MAX_TARGET_EVALUATIONS
    );
    let posterior = sampler.run(&Gaussian(2), &starts(2)[..1]).unwrap();
    assert_eq!(posterior.draws_per_chain(), 200);
    let conservative = Sampler::new()
        .warmup(300)
        .draws(200)
        .seed(SEED)
        .metric(Metric::Structured(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: vec![1.0, 1.2],
                subdiagonal: vec![0.1],
            }])
            .unwrap(),
        ))
        .limits(Limits::new().admit_conservative())
        .run(&Gaussian(2), &starts(2)[..1]);
    assert_eq!(conservative.unwrap_err().kind(), ErrorKind::ResourceLimit);
}
