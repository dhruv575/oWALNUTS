//! `ReverseCoarserPolicy` (research-only): the default `StopOrbit` ends the
//! orbit at a leaf whose reverse-coarsening check fails, like a divergence;
//! the opt-in `ZeroWeightBeyond` keeps the leaf's endpoint and every leaf
//! beyond it at zero weight and lets the orbit run to its U-turn. When no
//! leaf fails the check the two policies are bit-identical. Measured in
//! `STUDIES/reverse_coarser_policy_v1`.
#![cfg(feature = "research")]

use owalnuts::diagnostics::{ess_bulk, mean, sd};
use owalnuts::sampler::{Adaptation, Metric, ReverseCoarserPolicy, Sampler, Target, Tuning};
use owalnuts::walnutpie::TargetError;

/// Independent Gaussians with the given standard deviations, sampled under
/// the identity metric: the stiffest coordinate sets how often a level-0
/// leaf exceeds `delta` and refines.
struct Diagonal(Vec<f64>);

impl Target for Diagonal {
    fn dimension(&self) -> usize {
        self.0.len()
    }
    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let mut log_density = 0.0;
        for ((g, x), s) in gradient.iter_mut().zip(position).zip(&self.0) {
            let v = s * s;
            *g = -x / v;
            log_density -= 0.5 * x * x / v;
        }
        Ok(log_density)
    }
}

fn totals(posterior: &owalnuts::sampler::Posterior) -> (usize, usize, usize, usize) {
    posterior.telemetry().fold((0, 0, 0, 0), |acc, t| {
        let w = t.total();
        (
            acc.0 + w.reverse_coarser_stops(),
            acc.1 + w.reverse_coarser_rejections(),
            acc.2 + w.reverse_coarser_continuations(),
            acc.3 + w.zero_weight_leaves(),
        )
    })
}

#[test]
fn default_policy_is_stop_orbit_and_threads_to_kernel_tuning() {
    assert_eq!(
        Tuning::default()
            .to_kernel()
            .unwrap()
            .reverse_coarser_policy(),
        ReverseCoarserPolicy::StopOrbit
    );
    assert_eq!(
        Tuning::default()
            .reverse_coarser_policy(ReverseCoarserPolicy::ZeroWeightBeyond)
            .to_kernel()
            .unwrap()
            .reverse_coarser_policy(),
        ReverseCoarserPolicy::ZeroWeightBeyond
    );
}

/// At a small step no leaf refines, so no reverse check can fail: the two
/// policies must produce bit-identical draws and work counts.
#[test]
fn policies_are_bit_identical_when_no_leaf_fails_the_check() {
    let run = |policy| {
        Sampler::new()
            .warmup(0)
            .draws(60)
            .chains(2)
            .seed(19)
            .metric(Metric::fixed_diagonal(vec![1.0; 3]))
            .adaptation(Adaptation::None)
            .tuning(Tuning::new().step_size(0.2).reverse_coarser_policy(policy))
            .run(
                &Diagonal(vec![1.0, 1.0, 1.0]),
                &[vec![0.5, -0.5, 0.25], vec![-1.0, 1.0, 0.0]],
            )
            .unwrap()
    };
    let stop = run(ReverseCoarserPolicy::StopOrbit);
    let beyond = run(ReverseCoarserPolicy::ZeroWeightBeyond);
    assert_eq!(
        stop.draws().collect::<Vec<_>>(),
        beyond.draws().collect::<Vec<_>>()
    );
    assert_eq!(stop.total_target_calls(), beyond.total_target_calls());
    for (a, b) in stop.telemetry().zip(beyond.telemetry()) {
        assert_eq!(a.total(), b.total());
    }
    assert_eq!(totals(&stop), (0, 0, 0, 0));
    assert_eq!(totals(&beyond), (0, 0, 0, 0));
}

/// A fixed step chosen so that the stiff coordinates' level-0 leaves sit
/// near `delta`: refinement engages and a fraction of the refined leaves
/// fails the reverse check. Under `StopOrbit` those failures end orbits;
/// under `ZeroWeightBeyond` they never do, the run counts the continued
/// leaves, and the moments of every coordinate stay exact.
#[test]
fn zero_weight_beyond_never_stops_and_keeps_the_target_exact() {
    let sds = vec![1.0, 1.0, 0.45, 0.35];
    let target = Diagonal(sds.clone());
    let starts = vec![
        vec![0.3, -0.2, 0.1, 0.05],
        vec![-0.4, 0.5, -0.1, 0.02],
        vec![0.1, 0.1, 0.2, -0.05],
        vec![-0.2, -0.3, -0.15, 0.04],
    ];
    let run = |policy, seed| {
        Sampler::new()
            .warmup(0)
            .draws(3000)
            .chains(4)
            .seed(seed)
            .metric(Metric::fixed_diagonal(vec![1.0; 4]))
            .adaptation(Adaptation::None)
            .tuning(
                Tuning::new()
                    .step_size(0.55)
                    .max_depth(6)
                    .reverse_coarser_policy(policy),
            )
            .run(&target, &starts)
            .unwrap()
    };
    let stop = run(ReverseCoarserPolicy::StopOrbit, 23);
    let beyond = run(ReverseCoarserPolicy::ZeroWeightBeyond, 23);

    let (stop_stops, stop_rejections, stop_continuations, stop_zero) = totals(&stop);
    assert!(
        stop_stops > 0 && stop_rejections >= stop_stops,
        "the step must produce reverse-coarser stops under StopOrbit: {stop_stops} stops, {stop_rejections} rejections"
    );
    assert_eq!((stop_continuations, stop_zero), (0, 0));

    let (beyond_stops, beyond_rejections, beyond_continuations, beyond_zero) = totals(&beyond);
    assert_eq!(beyond_stops, 0, "ZeroWeightBeyond must never stop an orbit");
    assert!(beyond_continuations > 0);
    assert_eq!(beyond_rejections, beyond_continuations);
    assert!(beyond_zero >= beyond_continuations);

    for (posterior, label) in [(&stop, "StopOrbit"), (&beyond, "ZeroWeightBeyond")] {
        let chains = posterior.chains();
        for (coordinate, s) in sds.iter().enumerate() {
            let columns: Vec<Vec<f64>> = chains
                .iter()
                .map(|chain| {
                    (0..chain.retained())
                        .map(|d| chain.sample(d).unwrap()[coordinate])
                        .collect()
                })
                .collect();
            let views: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
            let ess = ess_bulk(&views);
            let m = mean(&views);
            let v = sd(&views).powi(2);
            let z_mean = m / (s / ess.sqrt());
            // Var(sample variance) ~ 2 s^4 / ess for a Gaussian.
            let z_var = (v - s * s) / (s * s * (2.0 / ess).sqrt());
            assert!(
                ess >= 200.0 && z_mean.abs() < 4.0 && z_var.abs() < 4.0,
                "{label} coordinate {coordinate}: ess {ess:.0}, z_mean {z_mean:.2}, z_var {z_var:.2}"
            );
        }
    }
}

/// Without step adaptation the `AdaptSelected` variant builds the same orbits
/// as `ZeroWeightBeyond`: identical draws and work.
#[test]
fn adapt_selected_is_bit_identical_to_zero_weight_beyond_at_a_fixed_step() {
    let target = Diagonal(vec![1.0, 1.0, 0.45, 0.35]);
    let starts = vec![vec![0.3, -0.2, 0.1, 0.05], vec![-0.4, 0.5, -0.1, 0.02]];
    let run = |policy| {
        Sampler::new()
            .warmup(0)
            .draws(400)
            .chains(2)
            .seed(29)
            .metric(Metric::fixed_diagonal(vec![1.0; 4]))
            .adaptation(Adaptation::None)
            .tuning(
                Tuning::new()
                    .step_size(0.55)
                    .max_depth(6)
                    .reverse_coarser_policy(policy),
            )
            .run(&target, &starts)
            .unwrap()
    };
    let beyond = run(ReverseCoarserPolicy::ZeroWeightBeyond);
    let selected = run(ReverseCoarserPolicy::ZeroWeightBeyondAdaptSelected);
    assert!(
        totals(&beyond).2 > 0,
        "the step must produce continued leaves"
    );
    assert_eq!(
        beyond.draws().collect::<Vec<_>>(),
        selected.draws().collect::<Vec<_>>()
    );
    assert_eq!(beyond.total_target_calls(), selected.total_target_calls());
    assert_eq!(totals(&beyond), totals(&selected));
}

/// With dual averaging on, keeping the zero-weight tail out of the statistic
/// removes its dilution of the failed leaf's low value, so `AdaptSelected`
/// installs a smaller step than `ZeroWeightBeyond` on a target where the
/// check fails often.
#[test]
fn adapt_selected_installs_a_smaller_step_than_zero_weight_beyond() {
    let target = Diagonal(vec![1.0, 1.0, 0.45, 0.35]);
    let starts = vec![
        vec![0.3, -0.2, 0.1, 0.05],
        vec![-0.4, 0.5, -0.1, 0.02],
        vec![0.1, 0.1, 0.2, -0.05],
        vec![-0.2, -0.3, -0.15, 0.04],
    ];
    let median_step = |policy| {
        let posterior = Sampler::new()
            .warmup(600)
            .draws(100)
            .chains(4)
            .seed(31)
            .metric(Metric::fixed_diagonal(vec![1.0; 4]))
            .adaptation(Adaptation::DualAveraging { target_accept: 0.8 })
            .tuning(Tuning::new().max_depth(6).reverse_coarser_policy(policy))
            .run(&target, &starts)
            .unwrap();
        let mut steps: Vec<f64> = posterior
            .chains()
            .iter()
            .map(|c| c.metadata().tuning().step_size())
            .collect();
        steps.sort_by(|a, b| a.partial_cmp(b).unwrap());
        (steps[1] + steps[2]) / 2.0
    };
    let stop = median_step(ReverseCoarserPolicy::StopOrbit);
    let beyond = median_step(ReverseCoarserPolicy::ZeroWeightBeyond);
    let selected = median_step(ReverseCoarserPolicy::ZeroWeightBeyondAdaptSelected);
    assert!(
        selected < beyond,
        "AdaptSelected step {selected:.4} should be below ZeroWeightBeyond's {beyond:.4} (StopOrbit {stop:.4})"
    );
}
