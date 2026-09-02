//! The evaluation mapping without a compiled Stan library: a Rust stand-in
//! for a Stan-like model whose log density is `NaN` in one region and whose
//! gradient overflows in another must be a recoverable (zero-density)
//! failure, never a fatal one, exactly as CmdStan and nutpie reject such a
//! proposal instead of aborting the run.

use owalnuts::walnutpie::{TargetError, TargetErrorKind};
use owalnuts_bridgestan::map_evaluation;

/// A Stan-like model: `x ~ normal(0, 1)` with `log(x)` entering the density
/// (NaN for negative `x`, `-inf` at zero) and a gradient term that overflows
/// to `inf` for large `x` while the density itself is still finite.
fn stan_like(x: f64, gradient: &mut [f64]) -> f64 {
    let value = -0.5 * x * x + x.ln() * 1e-3;
    let overflow = if x > 100.0 { (x * 10.0).exp() } else { 0.0 };
    gradient[0] = -x + 1e-3 / x + overflow;
    value
}

fn classify(x: f64) -> Result<f64, TargetError> {
    let mut gradient = [0.0];
    let value = stan_like(x, &mut gradient);
    map_evaluation(value, &gradient)
}

#[test]
fn finite_region_passes_through() {
    let value = classify(1.5).expect("finite");
    assert!((value - (-1.125 + 1.5f64.ln() * 1e-3)).abs() < 1e-12);
}

#[test]
fn nan_region_is_recoverable_with_a_message() {
    for x in [-0.5, -1.0, -3.0, -1e6] {
        let err = classify(x).unwrap_err();
        assert_eq!(err.kind(), TargetErrorKind::Recoverable, "x = {x}");
        assert!(err.message().contains("NaN"), "{}", err.message());
    }
}

#[test]
fn negative_infinity_is_recoverable() {
    let err = classify(0.0).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    assert!(err.message().contains("-inf"));
}

#[test]
fn gradient_overflow_is_recoverable() {
    let err = classify(150.0).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    assert!(err.message().contains("gradient"), "{}", err.message());
}

#[test]
fn positive_infinity_is_recoverable() {
    let err = map_evaluation(f64::INFINITY, &[0.0]).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    assert!(err.message().contains("inf"));
}

#[test]
fn nonfinite_gradient_with_finite_density_is_recoverable() {
    let err = map_evaluation(-1.0, &[0.0, f64::NAN, 1.0]).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
    assert!(err.message().contains("gradient"));
    let err = map_evaluation(-1.0, &[f64::NEG_INFINITY]).unwrap_err();
    assert_eq!(err.kind(), TargetErrorKind::Recoverable);
}

#[test]
fn the_kernel_survives_a_nan_region() {
    // Drive the full sampler through a target that uses the mapping: the run
    // must complete and count the excursions as recoverable failures.
    use owalnuts::sampler::{Sampler, Target};
    use std::sync::atomic::{AtomicUsize, Ordering};

    struct NanRegion(AtomicUsize);
    impl Target for NanRegion {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(
            &self,
            position: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            // Standard normal with a NaN log density (as Stan's `log` of a
            // negative argument would give) left of -2.5.
            let x = position[0];
            let (value, grad) = if x < -2.5 {
                (f64::NAN, f64::NAN)
            } else {
                (-0.5 * x * x, -x)
            };
            gradient[0] = grad;
            let out = map_evaluation(value, gradient);
            if out.is_err() {
                self.0.fetch_add(1, Ordering::Relaxed);
            }
            out
        }
    }
    let target = NanRegion(AtomicUsize::new(0));
    let posterior = Sampler::new()
        .warmup(200)
        .draws(400)
        .seed(11)
        .run(&target, &[vec![0.5], vec![-0.5]])
        .expect("NaN region is a rejected proposal, not a fatal error");
    assert_eq!(posterior.draws_per_chain(), 400);
    assert!(posterior.draws().all(|d| d[0] >= -2.5));
    assert!(
        target.0.load(Ordering::Relaxed) > 0,
        "the region was never visited"
    );
}
