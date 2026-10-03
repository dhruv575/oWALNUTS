//! Target-only benchmark. Never uses generating parameters unless explicitly supplied.
use owalnuts::sampler::Target;
use serde_json::{Value, json};
use std::{error::Error, hint::black_box, time::Instant};

pub fn benchmark<T: Target>(
    target: &T,
    positions: &[Vec<f64>],
    iterations: usize,
    autodiff: bool,
) -> Result<Value, Box<dyn Error>> {
    if iterations == 0
        || positions.is_empty()
        || positions
            .iter()
            .any(|q| q.len() != target.dimension() || q.iter().any(|v| !v.is_finite()))
    {
        return Err(
            "positive iterations and nonempty finite correctly-sized positions required".into(),
        );
    }
    let mut gradient = vec![0.0; target.dimension()];
    let cold = Instant::now();
    let first_logp = target.log_density_gradient(&positions[0], &mut gradient)?;
    let cold_seconds = cold.elapsed().as_secs_f64();
    let first_gradient = gradient.clone();
    let stats = if autodiff {
        let s = owalnuts_autodiff::last_tape_stats();
        json!({"nodes":s.nodes,"partials":s.partials,"indices":s.indices})
    } else {
        Value::Null
    };
    for q in positions {
        target.log_density_gradient(q, &mut gradient)?;
    }
    // Independent blocks expose measurement variability without changing the positions.
    let mut block_seconds = Vec::with_capacity(5);
    let mut checksum = 0.0;
    for _ in 0..5 {
        let started = Instant::now();
        for i in 0..iterations {
            let lp = target.log_density_gradient(
                black_box(&positions[i % positions.len()]),
                black_box(&mut gradient),
            )?;
            checksum += black_box(lp) + black_box(gradient[i % gradient.len()]);
        }
        block_seconds.push(started.elapsed().as_secs_f64());
    }
    let total_seconds: f64 = block_seconds.iter().sum();
    Ok(
        json!({"dimension":target.dimension(),"position_count":positions.len(),"iterations_per_block":iterations,"blocks":5,"measured_calls":5*iterations,"cold_seconds":cold_seconds,"block_seconds":block_seconds,"seconds_per_call":total_seconds/(5*iterations) as f64,"total_seconds":total_seconds,"tape_stats_first_position":stats,"first_logp":first_logp,"first_gradient":first_gradient,"checksum":checksum,"scope":"fused target log-density and gradient only; excludes sampler, JSON, and canonical-coordinate conversion"}),
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use owalnuts::sampler::TargetError;
    struct Gaussian;
    impl Target for Gaussian {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            g[0] = -q[0];
            g[1] = -q[1];
            Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
        }
    }
    #[test]
    fn counts_and_contract() {
        let r = benchmark(&Gaussian, &[vec![1.0, 2.0]], 3, false).unwrap();
        assert_eq!(r["measured_calls"], 15);
        assert_eq!(r["first_logp"], -2.5);
        assert_eq!(r["first_gradient"], json!([-1.0, -2.0]));
        assert!(benchmark(&Gaussian, &[vec![0.0]], 3, false).is_err());
        assert!(benchmark(&Gaussian, &[vec![0.0, 0.0]], 0, false).is_err());
    }
}
