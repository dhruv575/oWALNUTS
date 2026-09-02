//! End-to-end use of `owalnuts::sampler` on a 2-D Gaussian: a fixed
//! diagonal metric, multi-chain output, telemetry, and thread-count
//! determinism.

use std::error::Error;

use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};

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
    let sampler = Sampler::new()
        .warmup(8)
        .draws(16)
        .seed(0x5eed)
        .metric(Metric::fixed_diagonal(vec![0.5, 2.0]))
        .adaptation(Adaptation::None)
        .tuning(Tuning::new().step_size(0.6).max_depth(3))
        .limits(Limits::new().max_depth_stops(24));

    let single = sampler.run(&target, &[vec![0.2, -0.1]])?;
    let chain = &single.chains()[0];
    println!(
        "single: draws={}, first={:?}, diagnostics={}, target calls={}, revision={}",
        chain.retained(),
        single.draw(0, 0),
        chain.diagnostics().len(),
        single.total_target_calls(),
        single.algorithm_revision(),
    );
    println!(
        "mass={:?}, effective seed={}",
        chain.metadata().mass_diagonal(),
        chain.metadata().effective_seed(),
    );

    let starts = vec![vec![0.2, -0.1], vec![-0.2, 0.1]];
    let sequential = sampler.threads(1).run(&target, &starts)?;
    let parallel = Sampler::new()
        .warmup(8)
        .draws(16)
        .seed(0x5eed)
        .metric(Metric::fixed_diagonal(vec![0.5, 2.0]))
        .adaptation(Adaptation::None)
        .tuning(Tuning::new().step_size(0.6).max_depth(3))
        .limits(Limits::new().max_depth_stops(24))
        .threads(2)
        .run(&target, &starts)?;
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
    let mean: Vec<f64> = (0..2)
        .map(|index| parallel.parameter(index).sum::<f64>() / (parallel.draws().count() as f64))
        .collect();
    println!(
        "posterior mean over {} draws: {mean:?}",
        parallel.draws().count()
    );
    Ok(())
}
