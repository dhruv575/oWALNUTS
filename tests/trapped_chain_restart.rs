//! Research-only trapped-chain restart (`WarmupConfig::with_trapped_chain_restart`,
//! `STUDIES/trapped_chain_restart_v1`, WP67): silence and bit-identity on a
//! Gaussian, restart of a chain started in a narrow trap, independence of the
//! untouched chains, determinism, validation and admission accounting.
#![cfg(feature = "research")]

use std::num::NonZeroUsize;

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler,
    WarmupConfig,
};
use owalnuts::walnutpie::{
    ChainRescueConfig, DiagonalMass, ErrorKind, KernelTuning, RunConfig, Target, TargetError,
    TrappedChainRestartConfig, sample_chains,
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

/// A standard Gaussian plus a tiny, very narrow spike far away: a chain
/// started in the spike stays there and adapts a step about `TRAP_SD` times
/// the other chains' step.
struct Trap;

const TRAP_CENTER: f64 = 15.0;
const TRAP_SD: f64 = 0.003;
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

fn config(discarded: usize, retained: usize, restart: bool) -> RunConfig {
    let warmup = WarmupConfig::new(0.8).unwrap();
    let warmup = if restart {
        warmup.with_trapped_chain_restart(TrappedChainRestartConfig::step_rule())
    } else {
        warmup
    };
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
        .with_warmup(warmup)
}

fn starts(chains: usize, dimension: usize, scale: f64) -> Vec<Vec<f64>> {
    (0..chains)
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
fn unflagged_run_is_bit_identical_and_records_one_check_per_chain() {
    let target = Gaussian(3);
    let mass = DiagonalMass::identity(NonZeroUsize::new(3).unwrap());
    let starts = starts(4, 3, 2.0);
    for threads in [1, 4] {
        let threads = NonZeroUsize::new(threads).unwrap();
        let plain =
            sample_chains(&target, &starts, &mass, &config(600, 200, false), threads).unwrap();
        let restart =
            sample_chains(&target, &starts, &mass, &config(600, 200, true), threads).unwrap();
        for (chain, (a, b)) in plain.chains().iter().zip(restart.chains()).enumerate() {
            assert_eq!(a.samples(), b.samples(), "chain {chain} draws");
            assert_eq!(
                a.diagnostics(),
                b.diagnostics(),
                "chain {chain} diagnostics"
            );
            assert_eq!(
                a.telemetry().total(),
                b.telemetry().total(),
                "chain {chain} work"
            );
            assert!(a.telemetry().trapped_chain_checks().is_empty());
            let checks = b.telemetry().trapped_chain_checks();
            assert_eq!(checks.len(), 1, "one check per chain");
            let check = &checks[0];
            assert_eq!(check.chain(), chain);
            assert_eq!(
                check.transition(),
                99,
                "end of the first slow window 75..100"
            );
            assert!(!check.restarted());
            assert_eq!(check.step(), b.diagnostics()[99].step_size());
            assert!(check.step() >= check.threshold());
            assert!((check.threshold() - 0.1 * check.median_step()).abs() == 0.0);
            assert_eq!(check.abandoned_target_calls(), 0);
            assert!(check.replacement_start().is_none());
            assert!(check.abandoned_log_density().is_finite());
        }
    }
}

#[test]
fn fewer_than_three_chains_or_no_slow_window_is_the_plain_run() {
    let target = Gaussian(2);
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let threads = NonZeroUsize::new(2).unwrap();
    let two = starts(2, 2, 1.0);
    let plain = sample_chains(&target, &two, &mass, &config(300, 100, false), threads).unwrap();
    let restart = sample_chains(&target, &two, &mass, &config(300, 100, true), threads).unwrap();
    for (a, b) in plain.chains().iter().zip(restart.chains()) {
        assert_eq!(
            a.samples(),
            b.samples(),
            "two chains: the restart path is not entered"
        );
        assert_eq!(a.diagnostics(), b.diagnostics());
        assert_eq!(a.telemetry(), b.telemetry(), "no check record");
    }
    // A first slow window shorter than 10 transitions (10-transition warmup:
    // fallback schedule 1 + 8 + 1): no check.
    let four = starts(4, 2, 1.0);
    let plain = sample_chains(&target, &four, &mass, &config(10, 50, false), threads).unwrap();
    let restart = sample_chains(&target, &four, &mass, &config(10, 50, true), threads).unwrap();
    for (a, b) in plain.chains().iter().zip(restart.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert!(b.telemetry().trapped_chain_checks().is_empty());
    }
}

#[test]
fn a_chain_started_in_a_narrow_trap_is_restarted_from_an_independent_start() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(4, 2, 1.0);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let threads = NonZeroUsize::new(4).unwrap();
    let plain = sample_chains(&target, &starts, &mass, &config(500, 300, false), threads).unwrap();
    let trapped_mean = plain.chains()[3].samples().iter().sum::<f64>() / 600.0;
    assert!(
        trapped_mean > 10.0,
        "without the restart chain 3 stays in the spike (mean {trapped_mean})"
    );
    let restarted =
        sample_chains(&target, &starts, &mass, &config(500, 300, true), threads).unwrap();
    let check = &restarted.chains()[3].telemetry().trapped_chain_checks()[0];
    assert!(check.restarted(), "chain 3 is flagged: {check:?}");
    assert!(check.step() < check.threshold());
    assert!(check.abandoned_target_calls() > 0);
    let replacement = check.replacement_start().expect("replacement start");
    assert!(replacement.iter().all(|x| x.abs() <= 2.0));
    assert!(check.replacement_start_log_density().unwrap().is_finite());
    assert!(check.replacement_candidate_evaluations().unwrap() >= 16);
    assert_eq!(
        restarted.chains()[3].metadata().initial_position(),
        replacement,
        "the restarted run records its own start"
    );
    assert_eq!(
        restarted.chains()[3].metadata().effective_seed(),
        check.replacement_seed().unwrap()
    );
    assert_eq!(restarted.chains()[3].retained(), 300);
    assert_eq!(restarted.chains()[3].diagnostics().len(), 800);
    let mean = restarted.chains()[3].samples().iter().sum::<f64>() / 600.0;
    assert!(
        mean.abs() < 1.0,
        "the restarted chain samples the main mode (mean {mean})"
    );
    for chain in 0..3 {
        assert_eq!(
            plain.chains()[chain].samples(),
            restarted.chains()[chain].samples(),
            "untouched chain {chain} is bit-identical"
        );
        assert!(!restarted.chains()[chain].telemetry().trapped_chain_checks()[0].restarted());
    }
    let again = sample_chains(&target, &starts, &mass, &config(500, 300, true), threads).unwrap();
    assert_eq!(restarted, again, "deterministic");
    let sequential = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 300, true),
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    for (a, b) in restarted.chains().iter().zip(sequential.chains()) {
        assert_eq!(
            a.samples(),
            b.samples(),
            "thread count does not change draws"
        );
    }
}

#[test]
fn validation_combination_and_facades() {
    assert!(
        TrappedChainRestartConfig::step_rule()
            .with_step_ratio(1.0)
            .is_err()
    );
    assert!(
        TrappedChainRestartConfig::step_rule()
            .with_step_ratio(0.0)
            .is_err()
    );
    assert!(
        TrappedChainRestartConfig::step_rule()
            .with_replacement_start(0, 2.0, 100)
            .is_err()
    );
    assert_eq!(
        TrappedChainRestartConfig::default(),
        TrappedChainRestartConfig::step_rule()
    );
    let target = Gaussian(2);
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let both = config(300, 100, true).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_chain_rescue(ChainRescueConfig::restart_from_best())
            .with_trapped_chain_restart(TrappedChainRestartConfig::step_rule()),
    );
    let error = sample_chains(
        &target,
        &starts(4, 2, 1.0),
        &mass,
        &both,
        NonZeroUsize::new(4).unwrap(),
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);

    let custom = |restart: bool| {
        let warmup = WarmupConfig::new(0.8)
            .unwrap()
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION);
        Adaptation::Custom(if restart {
            warmup.with_trapped_chain_restart(TrappedChainRestartConfig::step_rule())
        } else {
            warmup
        })
    };
    let sampler = |adaptation: Adaptation| {
        Sampler::new()
            .warmup(300)
            .draws(100)
            .chains(4)
            .seed(7)
            .threads(4)
            .adaptation(adaptation)
            .limits(Limits::new().admit_worst_case())
    };
    let starts4 = starts(4, 2, 1.0);
    let defaults = sampler(Adaptation::default())
        .run(&target, &starts4)
        .unwrap();
    let with_restart = sampler(custom(true)).run(&target, &starts4).unwrap();
    for (a, b) in defaults.chains().iter().zip(with_restart.chains()) {
        assert_eq!(
            a.samples(),
            b.samples(),
            "facade: unflagged run is the default run"
        );
    }
    assert!(
        sampler(custom(true))
            .worst_case_target_evaluations(4)
            .unwrap()
            > sampler(custom(false))
                .worst_case_target_evaluations(4)
                .unwrap(),
        "admission accounts for a restart"
    );
    let dense = sampler(custom(true))
        .metric(Metric::dense())
        .run(&target, &starts4)
        .unwrap_err();
    assert_eq!(dense.kind(), ErrorKind::Configuration);
}
