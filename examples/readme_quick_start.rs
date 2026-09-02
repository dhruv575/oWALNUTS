//! The README quick start, verbatim: a `Target`, the `Sampler` builder at its
//! defaults, and a `diagnostics::Summary`. Run with
//! `cargo run --release --example readme_quick_start`.

use owalnuts::diagnostics::Summary;
use owalnuts::sampler::{Sampler, Target, TargetError};

/// A standard Gaussian in five dimensions.
struct Gaussian;

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        5
    }
    fn log_density_gradient(&self, q: &[f64], grad: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in grad.iter_mut().zip(q) {
            *g = -x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let posterior = Sampler::new()
        .warmup(1_000)
        .draws(1_000)
        .chains(4)
        .seed(0x5eed)
        .run_from_random_starts(&Gaussian)?; // uniform(-2, 2) starts, retried until finite

    let summary = Summary::from_output(posterior.inner(), None)?;
    println!("{summary}"); // mean, sd, MCSE, quantiles, ESS, R-hat, then sampler health
    println!("target calls: {}", posterior.total_target_calls());
    Ok(())
}
