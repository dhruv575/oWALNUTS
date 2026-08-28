use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DEFAULT_MAX_DEPTH, DEFAULT_MAX_ERROR, DEFAULT_MAX_REFINEMENT_LEVELS,
    DEFAULT_MIN_MICRO_STEPS, DEFAULT_STEP_SIZE, DiagonalMass, ErrorKind, KernelTuning, RunConfig,
    Target, TargetError, WarmupConfig, sample, sample_chains,
};

struct Gaussian;

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (gradient, position) in gradient.iter_mut().zip(position) {
            *gradient = -*position;
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

#[test]
fn stochastic_public_facade_returns_samples_diagnostics_and_run_identity() {
    let initial_positions = vec![vec![0.25, -0.5], vec![-0.75, 0.125]];
    let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
    let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 0x5eed);
    let output = sample_chains(
        &Gaussian,
        &initial_positions,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .unwrap();

    assert_eq!(output.chains().len(), 2);
    assert_eq!(output.algorithm_revision(), ALGORITHM_REVISION);
    for (chain, initial_position) in output.chains().iter().zip(&initial_positions) {
        assert_eq!(chain.samples().len(), 8);
        assert_eq!(chain.diagnostics().len(), 6);
        assert!(chain.samples().iter().all(|value| value.is_finite()));
        assert_eq!(chain.metadata().initial_position(), initial_position);
        assert_eq!(chain.metadata().thread_count(), 2);
        assert_eq!(chain.metadata().mass_diagonal(), mass.diagonal());
        assert_eq!(chain.telemetry().total().transitions(), 6);
    }
    assert_ne!(output.chains()[0].samples(), output.chains()[1].samples());
}

#[test]
fn default_tuning_preserves_the_qualified_public_behavior() {
    let implicit = RunConfig::new(1, NonZeroUsize::new(3).unwrap(), 17);
    let explicit = implicit.clone().with_tuning(KernelTuning::default());
    assert_eq!(implicit, explicit);
    assert_eq!(implicit.tuning().step_size(), DEFAULT_STEP_SIZE);
    assert_eq!(implicit.tuning().max_depth(), DEFAULT_MAX_DEPTH);
    assert_eq!(implicit.tuning().min_micro_steps(), DEFAULT_MIN_MICRO_STEPS);
    assert_eq!(
        implicit.tuning().max_refinement_levels(),
        DEFAULT_MAX_REFINEMENT_LEVELS
    );
    assert_eq!(implicit.tuning().max_error(), DEFAULT_MAX_ERROR);

    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    assert_eq!(
        sample(&Gaussian, &[0.25, -0.5], &mass, &implicit).unwrap(),
        sample(&Gaussian, &[0.25, -0.5], &mass, &explicit).unwrap()
    );
}

#[test]
fn configured_tuning_is_public_and_metadata_records_actual_values() {
    let tuning = KernelTuning::new(
        0.25,
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(3).unwrap(),
        0.125,
    )
    .unwrap();
    let config = RunConfig::new(0, NonZeroUsize::new(2).unwrap(), 9).with_tuning(tuning);
    assert_eq!(config.tuning(), &tuning);

    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let output = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    let metadata = output.metadata();
    assert_eq!(metadata.qualified_step_size(), 0.25);
    assert_eq!(metadata.max_depth(), 2);
    assert_eq!(metadata.min_micro_steps(), 2);
    assert_eq!(metadata.max_refinement_levels(), 3);
    assert_eq!(metadata.max_error(), 0.125);
}

#[test]
fn tuning_rejects_nonfinite_nonpositive_and_overflowing_values() {
    let one = NonZeroUsize::new(1).unwrap();
    for step_size in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let error = KernelTuning::new(step_size, one, one, one, 1.0).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration);
    }
    for max_error in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let error = KernelTuning::new(0.5, one, one, one, max_error).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration);
    }

    let too_large = NonZeroUsize::new(usize::BITS as usize + 1).unwrap();
    assert_eq!(
        KernelTuning::new(0.5, too_large, one, one, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        KernelTuning::new(0.5, one, one, too_large, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        KernelTuning::new(0.5, one, NonZeroUsize::new(usize::MAX).unwrap(), one, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Overflow
    );
}

#[test]
fn warmup_is_opt_in_deterministic_and_fixed_before_retention() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let config = RunConfig::new(100, NonZeroUsize::new(20).unwrap(), 0x51eed)
        .with_warmup(WarmupConfig::default());
    let first = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    let second = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.metadata().warmup(), config.warmup());
    assert_eq!(first.metadata().initial_tuning(), config.tuning());
    assert_eq!(first.metadata().initial_mass_diagonal(), mass.diagonal());
    assert_ne!(first.metadata().mass_diagonal(), mass.diagonal());
    assert_eq!(first.telemetry().discarded().transitions(), 100);
    assert_eq!(first.telemetry().retained().transitions(), 20);
}
