//! Warmup-time chain rescue (`WarmupConfig::with_chain_rescue`,
//! `STUDIES/chain_rescue_v1`): determinism, firing on a trapped start,
//! silence on a Gaussian, and the retained phase left alone.

use std::num::NonZeroUsize;

use owalnuts::sampler::{Adaptation, Metric, Sampler, WarmupConfig};
use owalnuts::walnutpie::{
    ChainRescueConfig, ChainRescueCriterion, ChainRescueOutcome, ChainRescueSkip, DiagonalMass,
    KernelTuning, RunConfig, Target, TargetError, sample_chains,
};

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = -x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

/// A standard Gaussian plus a tiny, narrow spike far away: a chain started
/// in the spike stays there (the density between the modes is negligible)
/// at a log density far below the main mode's.
struct Trap;

const TRAP_CENTER: f64 = 15.0;
const TRAP_SD: f64 = 0.3;
const TRAP_LOG_WEIGHT: f64 = -14.0;

impl Target for Trap {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let main = -0.5 * q.iter().map(|x| x * x).sum::<f64>();
        let spike = TRAP_LOG_WEIGHT
            - 2.0 * TRAP_SD.ln()
            - 0.5
                * q.iter()
                    .map(|x| ((x - TRAP_CENTER) / TRAP_SD).powi(2))
                    .sum::<f64>();
        let max = main.max(spike);
        let value = max + ((main - max).exp() + (spike - max).exp()).ln();
        let w_main = (main - value).exp();
        let w_spike = (spike - value).exp();
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = w_main * (-x) + w_spike * (-(x - TRAP_CENTER) / (TRAP_SD * TRAP_SD));
        }
        Ok(value)
    }
}

fn warmup(rescue: Option<ChainRescueConfig>) -> WarmupConfig {
    let warmup = WarmupConfig::new(0.8).unwrap();
    match rescue {
        Some(rescue) => warmup.with_chain_rescue(rescue),
        None => warmup,
    }
}

fn config(discarded: usize, retained: usize, rescue: Option<ChainRescueConfig>) -> RunConfig {
    RunConfig::new(discarded, NonZeroUsize::new(retained).unwrap(), 0x5eed)
        .with_tuning(
            KernelTuning::new(
                0.5,
                NonZeroUsize::new(8).unwrap(),
                NonZeroUsize::new(1).unwrap(),
                NonZeroUsize::new(4).unwrap(),
                1.0,
            )
            .unwrap(),
        )
        .with_warmup(warmup(rescue))
}

fn starts(dimension: usize, scale: f64) -> Vec<Vec<f64>> {
    (0..4)
        .map(|chain| {
            (0..dimension)
                .map(|i| {
                    scale
                        * ((chain as f64 + 1.0) * 0.5 - 1.25)
                        * if i % 2 == 0 { 1.0 } else { -1.0 }
                })
                .collect()
        })
        .collect()
}

#[test]
fn rescue_is_deterministic_and_never_fires_on_a_gaussian() {
    let target = Gaussian(3);
    let mass = DiagonalMass::identity(NonZeroUsize::new(3).unwrap());
    let starts = starts(3, 2.0);
    let threads = NonZeroUsize::new(4).unwrap();
    for rescue in [
        ChainRescueConfig::restart_from_best(),
        ChainRescueConfig::pool_at_boundaries(),
    ] {
        let first = sample_chains(
            &target,
            &starts,
            &mass,
            &config(600, 200, Some(rescue.clone())),
            threads,
        )
        .unwrap();
        let second = sample_chains(
            &target,
            &starts,
            &mass,
            &config(600, 200, Some(rescue.clone())),
            threads,
        )
        .unwrap();
        assert_eq!(first, second, "same seed, same draws");
        let single = sample_chains(
            &target,
            &starts,
            &mass,
            &config(600, 200, Some(rescue.clone())),
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        for (parallel, sequential) in first.chains().iter().zip(single.chains()) {
            assert_eq!(
                parallel.samples(),
                sequential.samples(),
                "thread count does not change the draws"
            );
            assert_eq!(parallel.diagnostics(), sequential.diagnostics());
            assert_eq!(parallel.telemetry(), sequential.telemetry());
        }
        for chain in first.chains() {
            let records = chain.telemetry().chain_rescues();
            assert!(!records.is_empty(), "every boundary is recorded");
            assert!(
                records.iter().all(|u| u.transition() < 600),
                "records lie in warmup"
            );
            assert!(records.iter().all(|u| u.window_transitions() >= 10));
        }
        if rescue == ChainRescueConfig::restart_from_best() {
            let plain =
                sample_chains(&target, &starts, &mass, &config(600, 200, None), threads).unwrap();
            for (with, without) in first.chains().iter().zip(plain.chains()) {
                assert!(
                    with.telemetry()
                        .chain_rescues()
                        .iter()
                        .all(|u| *u.outcome() == ChainRescueOutcome::Kept),
                    "no chain of a Gaussian is an outlier"
                );
                assert_eq!(
                    with.samples(),
                    without.samples(),
                    "no rescue fired: the draws are the plain run's"
                );
                assert_eq!(with.diagnostics(), without.diagnostics());
                assert_eq!(with.metadata().tuning(), without.metadata().tuning());
            }
        } else {
            for chain in first.chains() {
                assert!(chain.telemetry().chain_rescues().iter().all(|u| matches!(
                    u.outcome(),
                    ChainRescueOutcome::Pooled { pooled_sample_count, .. } if *pooled_sample_count > 0
                )));
            }
            let masses: Vec<_> = first
                .chains()
                .iter()
                .map(|c| c.metadata().mass_diagonal().to_vec())
                .collect();
            assert!(
                masses.iter().all(|m| m == &masses[0]),
                "pooling installs one metric on every chain"
            );
        }
    }
}

#[test]
fn restart_rescues_a_chain_started_in_a_trap_by_the_density_rule() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(2, 1.0);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let threads = NonZeroUsize::new(4).unwrap();
    let plain = sample_chains(&target, &starts, &mass, &config(500, 300, None), threads).unwrap();
    let trapped_mean = plain.chains()[3].samples().iter().sum::<f64>() / (2.0 * 300.0);
    assert!(
        trapped_mean > 10.0,
        "without rescue chain 3 stays in the spike (mean {trapped_mean})"
    );

    let rescued = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 300, Some(ChainRescueConfig::restart_from_best())),
        threads,
    )
    .unwrap();
    let records = rescued.chains()[3].telemetry().chain_rescues();
    let first_restart = records
        .iter()
        .find(|u| matches!(u.outcome(), ChainRescueOutcome::Restarted { .. }))
        .expect("chain 3 is rescued");
    assert!(matches!(
        first_restart.outcome(),
        ChainRescueOutcome::Restarted { criterion: ChainRescueCriterion::LogDensity, source, .. } if *source != 3
    ));
    assert_eq!(
        first_restart.window_index(),
        0,
        "the first window already sees it"
    );
    for chain in 0..3 {
        assert!(
            rescued.chains()[chain]
                .telemetry()
                .chain_rescues()
                .iter()
                .all(|u| *u.outcome() == ChainRescueOutcome::Kept)
        );
    }
    let rescued_mean = rescued.chains()[3].samples().iter().sum::<f64>() / (2.0 * 300.0);
    assert!(
        rescued_mean.abs() < 1.0,
        "after the rescue chain 3 samples the main mode (mean {rescued_mean})"
    );
    // The mechanism is warmup-only: every record lies in the discarded phase
    // and the retained phase has the full draw count.
    assert!(records.iter().all(|u| u.transition() < 500));
    assert_eq!(rescued.chains()[3].retained(), 300);
    // Deterministic.
    let again = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 300, Some(ChainRescueConfig::restart_from_best())),
        threads,
    )
    .unwrap();
    assert_eq!(rescued, again);
}

#[test]
fn rescue_with_skipped_boundaries_or_one_chain_is_the_plain_run() {
    let target = Gaussian(2);
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let starts = starts(2, 1.0);
    let threads = NonZeroUsize::new(2).unwrap();
    // Every window is shorter than the minimum: every boundary is skipped
    // and the draws are the plain run's.
    let skipped = ChainRescueConfig::restart_from_best()
        .with_minimum_window_transitions(10_000)
        .unwrap();
    let plain = sample_chains(&target, &starts, &mass, &config(200, 50, None), threads).unwrap();
    let rescued = sample_chains(
        &target,
        &starts,
        &mass,
        &config(200, 50, Some(skipped)),
        threads,
    )
    .unwrap();
    for (with, without) in rescued.chains().iter().zip(plain.chains()) {
        assert_eq!(with.samples(), without.samples());
        assert_eq!(with.diagnostics(), without.diagnostics());
        assert!(with.telemetry().chain_rescues().iter().all(|u| matches!(
            u.outcome(),
            ChainRescueOutcome::Skipped(ChainRescueSkip::ShortWindow)
        )));
    }
    let one_plain = sample_chains(
        &target,
        &starts[..1],
        &mass,
        &config(200, 50, None),
        threads,
    )
    .unwrap();
    let one_rescued = sample_chains(
        &target,
        &starts[..1],
        &mass,
        &config(200, 50, Some(ChainRescueConfig::pool_at_boundaries())),
        threads,
    )
    .unwrap();
    // A single chain has nothing to compare against: the plain driver runs
    // and no record is written.
    assert_eq!(
        one_plain.chains()[0].samples(),
        one_rescued.chains()[0].samples()
    );
    assert_eq!(
        one_plain.chains()[0].telemetry(),
        one_rescued.chains()[0].telemetry()
    );
    assert!(
        one_rescued.chains()[0]
            .telemetry()
            .chain_rescues()
            .is_empty()
    );
}

#[test]
fn sampler_custom_adaptation_carries_the_rescue_and_dense_metric_rejects_it() {
    let target = Gaussian(2);
    let rescue = ChainRescueConfig::restart_from_best();
    let posterior = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(3)
        .adaptation(Adaptation::Custom(warmup(Some(rescue.clone()))))
        .run_from_random_starts(&target)
        .unwrap();
    assert!(posterior.telemetry().all(|t| !t.chain_rescues().is_empty()));
    let dense = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(3)
        .metric(Metric::dense())
        .adaptation(Adaptation::Custom(warmup(Some(rescue))))
        .run_from_random_starts(&target);
    assert!(dense.is_err());
    assert!(
        ChainRescueConfig::restart_from_best()
            .with_step_ratio(1.5)
            .is_err()
    );
    assert!(
        ChainRescueConfig::restart_from_best()
            .with_minimum_window_transitions(1)
            .is_err()
    );
}
