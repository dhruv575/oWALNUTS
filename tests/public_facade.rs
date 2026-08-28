use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, RunConfig, Target, TargetError, sample_chains,
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
