//! Pre-freeze calibration of the R1 scale on analytic Gaussians (no study
//! evidence): runs the `r1` and `r2` arms on standard Gaussians of the given
//! dimension and prints, per chain, the window-boundary quantiles and the
//! installed `delta`.
//!
//! Usage: `calibrate <arm> <dimension> <seed>`
#![forbid(unsafe_code)]

#[path = "../arms.rs"]
mod arms;

use arms::Arm;
use owalnuts::sampler::{Init, Limits, Metric, Sampler, Target, TargetError};
use std::{env, error::Error};

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        for (out, value) in g.iter_mut().zip(q) {
            *out = -*value;
        }
        Ok(-0.5 * q.iter().map(|v| v * v).sum::<f64>())
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<String> = env::args().skip(1).collect();
    let arm = Arm::parse(&args[0])?;
    let dimension: usize = args[1].parse()?;
    let seed: u64 = args[2].parse()?;
    let sampler = Sampler::new()
        .warmup(1000)
        .draws(1000)
        .chains(4)
        .threads(4)
        .seed(seed)
        .metric(Metric::diagonal())
        .adaptation(arm.adaptation()?)
        .tuning(arm.tuning())
        .limits(Limits::new().admit_worst_case());
    let posterior = sampler.run_with_init(&Gaussian(dimension), &Init::uniform())?;
    for (c, chain) in posterior.chains().iter().enumerate() {
        let updates = chain.telemetry().adaptive_delta_updates();
        let qs: Vec<String> = updates
            .iter()
            .map(|u| {
                format!(
                    "{}:q={:.3},d={:.3},f={:.4}",
                    u.transition() + 1,
                    u.quantile().unwrap_or(f64::NAN),
                    u.max_error_after(),
                    u.fraction_above_before().unwrap_or(f64::NAN)
                )
            })
            .collect();
        println!(
            "{} D={dimension} seed={seed} chain {c}: h={:.4} delta={:.3} | {}",
            arm.name,
            chain.metadata().tuning().step_size(),
            chain.metadata().tuning().max_error(),
            qs.join(" ")
        );
    }
    Ok(())
}
