//! End-to-end use of the internal fixed-diagonal beta.

use std::error::Error;
use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    DiagonalMass, ResourceLimits, RunConfig, Target, TargetError, sample, sample_chains,
};

struct Gaussian {
    dimension: usize,
}

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (gradient_value, position_value) in gradient.iter_mut().zip(position) {
            *gradient_value = -*position_value;
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let target = Gaussian { dimension: 2 };
    let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0])?;
    let limits = ResourceLimits::new(
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(4).unwrap(),
        NonZeroUsize::new(1_000).unwrap(),
        NonZeroUsize::new(113_000).unwrap(),
        NonZeroUsize::new(1024 * 1024).unwrap(),
        NonZeroUsize::new(1024 * 1024).unwrap(),
    )?;
    let config = RunConfig::new(8, NonZeroUsize::new(16).unwrap(), 0x5eed)
        .with_limits(limits)
        .with_maximum_depth_stop_limit(24);

    let single = sample(&target, &[0.2, -0.1], &mass, &config)?;
    println!(
        "single: draws={}, first={:?}, diagnostics={}, target calls={}, revision={}",
        single.retained(),
        single.sample(0),
        single.diagnostics().len(),
        single.telemetry().total().target_calls_total(),
        single.metadata().algorithm_revision(),
    );
    println!(
        "mass={:?}, effective seed={}",
        single.metadata().mass_diagonal(),
        single.metadata().effective_seed(),
    );

    let starts = vec![vec![0.2, -0.1], vec![-0.2, 0.1]];
    let sequential = sample_chains(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )?;
    let parallel = sample_chains(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )?;
    for (sequential, parallel) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(sequential.samples(), parallel.samples());
        assert_eq!(sequential.diagnostics(), parallel.diagnostics());
        assert_eq!(sequential.telemetry(), parallel.telemetry());
    }
    for (index, chain) in parallel.chains().iter().enumerate() {
        println!(
            "chain {index}: samples={}, max-depth stops={}, stop={:?}",
            chain.samples().len(),
            chain.telemetry().total().maximum_depth_stops(),
            chain.diagnostics().last().map(|item| item.stop()),
        );
    }
    Ok(())
}
