//! `NonfinitePositionPolicy` (research-only): the default `Abort` ends a run
//! whose integrator overflowed with `ErrorKind::Numerical`; the opt-in
//! `RejectLeaf` treats the overflowed point as a zero-density leaf and the run
//! completes. When the event never occurs the two policies are bit-identical.
//! Motivated by `STUDIES/sspd_target_fatal_diag_v1`; measured in
//! `STUDIES/nonfinite_position_policy_v1`.
#![cfg(feature = "research")]

use owalnuts::sampler::{
    Adaptation, ErrorKind, Metric, NonfinitePositionPolicy, Sampler, Target, Tuning,
};
use owalnuts::walnutpie::TargetError;

/// `log p(x) = -G |x|` with a constant-magnitude gradient `G = 1e308`. Finite
/// at the start (`x = 0.1`), but the first half-kick at step 4 overflows the
/// momentum to infinity and the drift carries the position with it.
struct Cliff;

impl Target for Cliff {
    fn dimension(&self) -> usize {
        1
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        const G: f64 = 1e308;
        let x = position[0];
        if x.abs() >= 1.0 {
            return Err(TargetError::recoverable("cliff: |x| >= 1"));
        }
        gradient[0] = -G * x.signum();
        Ok(-G * x.abs())
    }
}

fn cliff_sampler(policy: NonfinitePositionPolicy) -> Sampler {
    Sampler::new()
        .warmup(0)
        .draws(5)
        .chains(1)
        .seed(11)
        .metric(Metric::fixed_diagonal(vec![1.0]))
        .adaptation(Adaptation::None)
        .tuning(
            Tuning::new()
                .step_size(4.0)
                .max_depth(3)
                .max_refinement_levels(2)
                .nonfinite_position(policy),
        )
}

#[test]
fn default_policy_is_abort_and_threads_to_kernel_tuning() {
    assert_eq!(
        Tuning::default().to_kernel().unwrap().nonfinite_position(),
        NonfinitePositionPolicy::Abort
    );
    assert_eq!(
        Tuning::default()
            .nonfinite_position(NonfinitePositionPolicy::RejectLeaf)
            .to_kernel()
            .unwrap()
            .nonfinite_position(),
        NonfinitePositionPolicy::RejectLeaf
    );
}

#[test]
fn abort_ends_the_run_with_a_numerical_error() {
    let error = cliff_sampler(NonfinitePositionPolicy::Abort)
        .run(&Cliff, &[vec![0.1]])
        .expect_err("the overflowed position must abort the run");
    assert_eq!(error.kind(), ErrorKind::Numerical);
}

#[test]
fn reject_leaf_completes_and_counts_the_event() {
    let posterior = cliff_sampler(NonfinitePositionPolicy::RejectLeaf)
        .run(&Cliff, &[vec![0.1]])
        .expect("the overflowed position is a rejected leaf");
    assert_eq!(posterior.draws_per_chain(), 5);
    // Every leaf is invalid, so every draw is the (finite) start.
    for draw in posterior.draws() {
        assert_eq!(draw, &[0.1]);
    }
    let rejections: usize = posterior
        .telemetry()
        .map(|telemetry| telemetry.total().nonfinite_position_rejections())
        .sum();
    assert!(
        rejections >= 5,
        "expected one rejection per transition, got {rejections}"
    );
}

/// A 3-D standard normal never overflows, so the two policies must produce
/// bit-identical draws and work counts.
struct Normal3;

impl Target for Normal3 {
    fn dimension(&self) -> usize {
        3
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(position) {
            *g = -x;
        }
        Ok(-0.5 * position.iter().map(|x| x * x).sum::<f64>())
    }
}

#[test]
fn policies_are_bit_identical_when_the_event_never_occurs() {
    let run = |policy| {
        Sampler::new()
            .warmup(60)
            .draws(40)
            .chains(2)
            .seed(7)
            .tuning(Tuning::new().nonfinite_position(policy))
            .run(&Normal3, &[vec![0.5, -0.5, 0.25], vec![-1.0, 1.0, 0.0]])
            .unwrap()
    };
    let abort = run(NonfinitePositionPolicy::Abort);
    let reject = run(NonfinitePositionPolicy::RejectLeaf);
    assert_eq!(
        abort.draws().collect::<Vec<_>>(),
        reject.draws().collect::<Vec<_>>()
    );
    assert_eq!(abort.total_target_calls(), reject.total_target_calls());
    for (a, r) in abort.telemetry().zip(reject.telemetry()) {
        assert_eq!(a.total(), r.total());
        assert_eq!(r.total().nonfinite_position_rejections(), 0);
    }
}
