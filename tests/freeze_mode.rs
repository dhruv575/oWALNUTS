//! The freeze mode of `STUDIES/freeze_mode_v1` on a synthetic target, so
//! that the escape rule is tested without BridgeStan.
//!
//! `WallTarget` is a standard Gaussian with an exponential wall
//! `-exp(k (x_0 - 1))` on the right of `x_0 = 1`; an overflowing wall is a
//! recoverable failure, as a Stan model overflowing its likelihood is. A
//! uniform(-2, 2) start with `x_0 = 1.6` sits at log density `-e^60 ~ -1e26`,
//! whose unit in the last place (~2e10) exceeds the divergence threshold: no
//! leapfrog step can change a coordinate without an energy error above 1000,
//! so the frozen kernel pins there (`ExhaustionRule::Stop`: every leaf is
//! exhausted, dual averaging settles at `h ~ 1/|grad|` where `q + h v == q`).
//! `ExhaustionRule::AcceptUnlessDivergent` slides the chain down the wall
//! the way NUTS does (energy drops are accepted, the trajectory's own
//! instability carries it) and reaches the Gaussian bulk within warmup.

use owalnuts::sampler::{Adaptation, Init, Metric, Sampler, Target, Tuning, WarmupConfig};
use owalnuts::walnutpie::{ExhaustionRule, KernelOptions, TargetError};

const DIMENSION: usize = 4;

struct WallTarget {
    steepness: f64,
}

impl Target for WallTarget {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let wall = (self.steepness * (position[0] - 1.0)).exp();
        let slope = self.steepness * wall;
        if !slope.is_finite() {
            return Err(TargetError::recoverable("wall overflowed"));
        }
        let mut value = 0.0;
        for (g, x) in gradient.iter_mut().zip(position) {
            value -= 0.5 * x * x;
            *g = -x;
        }
        gradient[0] -= slope;
        let value = value - wall;
        if !value.is_finite() || gradient.iter().any(|g| !g.is_finite()) {
            return Err(TargetError::recoverable("nonfinite log density"));
        }
        Ok(value)
    }
}

fn start() -> Vec<Vec<f64>> {
    vec![vec![1.6, -0.3, 0.8, -1.2]]
}

fn sampler(options: KernelOptions) -> Sampler {
    Sampler::new()
        .warmup(300)
        .draws(100)
        .chains(1)
        .seed(0x5eed_f2ee)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default().kernel_options(options))
}

#[test]
fn frozen_kernel_pins_at_a_wall_start() {
    let target = WallTarget { steepness: 100.0 };
    let posterior = sampler(KernelOptions::default())
        .run_with_init(&target, &Init::Given(start()))
        .unwrap();
    let chain = &posterior.chains()[0];
    let diagnostics = chain.diagnostics();
    // Not one transition moves the position; every retained transition is a
    // refinement exhaustion; the adapted step collapsed far below anything
    // that could move a coordinate of order one.
    assert!(diagnostics.iter().all(|d| !d.position_changed()));
    assert_eq!(
        chain.telemetry().retained().refinement_exhaustion_stops(),
        100
    );
    assert!(chain.metadata().tuning().step_size() < 1e-8);
    for draw in 0..100 {
        assert_eq!(chain.sample(draw).unwrap(), start()[0].as_slice());
    }
}

#[test]
fn accept_unless_divergent_escapes_the_wall_start() {
    let target = WallTarget { steepness: 100.0 };
    let options = KernelOptions {
        exhaustion: ExhaustionRule::AcceptUnlessDivergent,
        ..KernelOptions::default()
    };
    let posterior = sampler(options)
        .run_with_init(&target, &Init::Given(start()))
        .unwrap();
    let chain = &posterior.chains()[0];
    let diagnostics = chain.diagnostics();
    let moved_in_warmup = diagnostics[..300]
        .iter()
        .filter(|d| d.position_changed())
        .count();
    assert!(moved_in_warmup > 100, "moved {moved_in_warmup} of 300");
    // The retained draws are in the Gaussian bulk to the left of the wall.
    let mean_x0 = (0..100).map(|i| chain.sample(i).unwrap()[0]).sum::<f64>() / 100.0;
    assert!(mean_x0 < 1.0 && mean_x0 > -3.0, "mean x0 {mean_x0}");
    assert!(chain.metadata().tuning().step_size() > 1e-3);
}

#[test]
fn accept_unless_divergent_is_bit_identical_where_nothing_exhausts() {
    // The rule only engages on a leaf exhausted at every level; with the wall
    // switched off (a plain Gaussian, nothing exhausts) the two kernels make
    // identical draws.
    let target = WallTarget { steepness: 0.0 };
    let init = Init::Given(vec![vec![-0.5, 0.2, -0.1, 0.4]]);
    let frozen = sampler(KernelOptions::default())
        .run_with_init(&target, &init)
        .unwrap();
    let options = KernelOptions {
        exhaustion: ExhaustionRule::AcceptUnlessDivergent,
        ..KernelOptions::default()
    };
    let signed = sampler(options).run_with_init(&target, &init).unwrap();
    assert_eq!(
        frozen.chains()[0]
            .telemetry()
            .total()
            .refinement_exhaustion_stops(),
        0
    );
    assert_eq!(frozen.chains()[0].samples(), signed.chains()[0].samples());
}

#[test]
fn warmup_only_rule_escapes_and_keeps_the_frozen_rule_for_retained_draws() {
    let target = WallTarget { steepness: 100.0 };
    let warmup = WarmupConfig::new(0.8)
        .unwrap()
        .with_warmup_exhaustion_rule(ExhaustionRule::AcceptUnlessDivergent);
    let posterior = sampler(KernelOptions::default())
        .adaptation(Adaptation::Custom(warmup))
        .run_with_init(&target, &Init::Given(start()))
        .unwrap();
    let chain = &posterior.chains()[0];
    let mean_x0 = (0..100).map(|i| chain.sample(i).unwrap()[0]).sum::<f64>() / 100.0;
    assert!(mean_x0 < 1.0 && mean_x0 > -3.0, "mean x0 {mean_x0}");
    assert!(chain.metadata().tuning().step_size() > 1e-3);
    // The retained kernel is the frozen one.
    assert_eq!(
        chain.metadata().tuning().options().exhaustion,
        ExhaustionRule::Stop
    );
}
