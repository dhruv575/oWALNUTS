//! Warmup-time chain rescue (`WarmupConfig::with_chain_rescue`,
//! `STUDIES/chain_rescue_v1` and `chain_rescue_v2`): determinism, observation,
//! confirmation, firing on a trapped start, silence on a Gaussian, and the
//! retained phase left alone.

use std::num::NonZeroUsize;

use owalnuts::sampler::{Adaptation, Metric, Sampler, WarmupConfig};
use owalnuts::walnutpie::{
    ChainRescueConfig, ChainRescueCriterion, ChainRescueMode, ChainRescueOutcome,
    ChainRescuePolicy, ChainRescueSkip, DiagonalMass, ErrorKind, KernelTuning, ResourceLimits,
    RunConfig, Target, TargetError, preflight_chains, sample_chains,
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

#[derive(Clone, Copy)]
enum MemoryCeiling {
    Result,
    Working,
}

fn limits_with(ceiling: MemoryCeiling, bytes: usize) -> ResourceLimits {
    let defaults = ResourceLimits::default();
    ResourceLimits::new(
        NonZeroUsize::new(defaults.max_dimension()).unwrap(),
        NonZeroUsize::new(defaults.max_chains()).unwrap(),
        NonZeroUsize::new(defaults.max_total_transitions()).unwrap(),
        NonZeroUsize::new(defaults.max_target_evaluations()).unwrap(),
        NonZeroUsize::new(match ceiling {
            MemoryCeiling::Result => bytes,
            MemoryCeiling::Working => defaults.max_result_bytes(),
        })
        .unwrap(),
        NonZeroUsize::new(match ceiling {
            MemoryCeiling::Result => defaults.max_working_bytes(),
            MemoryCeiling::Working => bytes,
        })
        .unwrap(),
    )
    .unwrap()
}

fn memory_admitted(
    ceiling: MemoryCeiling,
    bytes: usize,
    rescue: Option<ChainRescueConfig>,
) -> bool {
    let target = Gaussian(16);
    let starts = starts(16, 1.0);
    let mass = DiagonalMass::identity(NonZeroUsize::new(16).unwrap());
    let run = config(400, 20, rescue).with_limits(limits_with(ceiling, bytes));
    preflight_chains(&target, &starts, &mass, &run).is_ok()
}

fn minimum_admitted_memory(ceiling: MemoryCeiling, rescue: Option<ChainRescueConfig>) -> usize {
    let defaults = ResourceLimits::default();
    let mut low = 1usize;
    let mut high = match ceiling {
        MemoryCeiling::Result => defaults.max_result_bytes(),
        MemoryCeiling::Working => defaults.max_working_bytes(),
    };
    assert!(memory_admitted(ceiling, high, rescue.clone()));
    while low < high {
        let middle = low + (high - low) / 2;
        if memory_admitted(ceiling, middle, rescue.clone()) {
            high = middle;
        } else {
            low = middle + 1;
        }
    }
    low
}

fn assert_execution_identical(
    observed: &owalnuts::walnutpie::ChainOutput,
    disabled: &owalnuts::walnutpie::ChainOutput,
) {
    assert_eq!(observed.samples(), disabled.samples());
    assert_eq!(observed.diagnostics(), disabled.diagnostics());

    let observed_telemetry = observed.telemetry();
    let disabled_telemetry = disabled.telemetry();
    assert_eq!(
        observed_telemetry.discarded(),
        disabled_telemetry.discarded()
    );
    assert_eq!(observed_telemetry.retained(), disabled_telemetry.retained());
    assert_eq!(observed_telemetry.total(), disabled_telemetry.total());
    assert_eq!(
        observed_telemetry.initial_step_search(),
        disabled_telemetry.initial_step_search()
    );
    assert_eq!(
        observed_telemetry.initial_fast(),
        disabled_telemetry.initial_fast()
    );
    assert_eq!(observed_telemetry.slow(), disabled_telemetry.slow());
    assert_eq!(
        observed_telemetry.terminal_fast(),
        disabled_telemetry.terminal_fast()
    );
    assert_eq!(
        observed_telemetry.step_searches(),
        disabled_telemetry.step_searches()
    );
    assert_eq!(
        observed_telemetry.metric_updates(),
        disabled_telemetry.metric_updates()
    );
    assert_eq!(
        observed_telemetry.warmup_checkpoints(),
        disabled_telemetry.warmup_checkpoints()
    );
    assert_eq!(
        observed_telemetry.paper_adaptation_updates(),
        disabled_telemetry.paper_adaptation_updates()
    );

    assert_eq!(
        observed.metadata().qualified_step_size(),
        disabled.metadata().qualified_step_size()
    );
    assert_eq!(
        observed.metadata().mass_diagonal(),
        disabled.metadata().mass_diagonal()
    );
    assert_eq!(observed.metadata().tuning(), disabled.metadata().tuning());
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
fn observe_only_is_execution_identical_to_disabled_on_gaussian_and_trap() {
    let threads = NonZeroUsize::new(4).unwrap();

    let gaussian = Gaussian(3);
    let gaussian_mass = DiagonalMass::identity(NonZeroUsize::new(3).unwrap());
    let gaussian_starts = starts(3, 2.0);
    let gaussian_plain = sample_chains(
        &gaussian,
        &gaussian_starts,
        &gaussian_mass,
        &config(400, 100, None),
        threads,
    )
    .unwrap();
    let gaussian_observed = sample_chains(
        &gaussian,
        &gaussian_starts,
        &gaussian_mass,
        &config(400, 100, Some(ChainRescueConfig::observe_only())),
        threads,
    )
    .unwrap();
    for (observed, disabled) in gaussian_observed
        .chains()
        .iter()
        .zip(gaussian_plain.chains())
    {
        assert_execution_identical(observed, disabled);
        assert!(!observed.telemetry().chain_rescues().is_empty());
        assert!(
            observed
                .telemetry()
                .chain_rescues()
                .iter()
                .all(|update| matches!(update.outcome(), ChainRescueOutcome::Kept))
        );
    }

    let trap = Trap;
    let trap_mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut trap_starts = starts(2, 1.0);
    trap_starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let trap_plain = sample_chains(
        &trap,
        &trap_starts,
        &trap_mass,
        &config(500, 100, None),
        threads,
    )
    .unwrap();
    let trap_observed = sample_chains(
        &trap,
        &trap_starts,
        &trap_mass,
        &config(500, 100, Some(ChainRescueConfig::observe_only())),
        threads,
    )
    .unwrap();
    for (observed, disabled) in trap_observed.chains().iter().zip(trap_plain.chains()) {
        assert_execution_identical(observed, disabled);
        assert!(
            observed
                .telemetry()
                .chain_rescues()
                .iter()
                .all(|update| !matches!(update.outcome(), ChainRescueOutcome::Restarted { .. }))
        );
    }
    assert!(
        trap_observed.chains()[3]
            .telemetry()
            .chain_rescues()
            .iter()
            .any(|update| matches!(
                update.outcome(),
                ChainRescueOutcome::ObservedHit {
                    criterion: ChainRescueCriterion::LogDensity
                }
            ))
    );
}

#[test]
fn observe_and_two_hit_are_parallel_deterministic() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(2, 1.0);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];

    for rescue in [
        ChainRescueConfig::observe_only(),
        ChainRescueConfig::two_hit(),
    ] {
        let parallel = sample_chains(
            &target,
            &starts,
            &mass,
            &config(500, 100, Some(rescue.clone())),
            NonZeroUsize::new(4).unwrap(),
        )
        .unwrap();
        let sequential = sample_chains(
            &target,
            &starts,
            &mass,
            &config(500, 100, Some(rescue)),
            NonZeroUsize::new(1).unwrap(),
        )
        .unwrap();
        for (parallel, sequential) in parallel.chains().iter().zip(sequential.chains()) {
            assert_eq!(parallel.samples(), sequential.samples());
            assert_eq!(parallel.diagnostics(), sequential.diagnostics());
            assert_eq!(parallel.telemetry(), sequential.telemetry());
            assert_eq!(
                parallel.metadata().qualified_step_size(),
                sequential.metadata().qualified_step_size()
            );
            assert_eq!(
                parallel.metadata().mass_diagonal(),
                sequential.metadata().mass_diagonal()
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
    if let ChainRescueOutcome::Restarted {
        source,
        criterion,
        source_position,
        step_after,
    } = first_restart.outcome()
    {
        assert_eq!(first_restart.proposed_source_chain(), Some(*source));
        assert_eq!(
            first_restart.observed_canonical_criterion(),
            Some(*criterion)
        );
        assert!(*source_position < first_restart.window_transitions());
        assert!(step_after.is_finite() && *step_after > 0.0);
        assert_eq!(first_restart.pre_action_unconstrained_position().len(), 2);
        let installed = first_restart
            .installed_unconstrained_position()
            .expect("restart records the exact installed source-window draw");
        assert_eq!(installed.len(), 2);
        assert_ne!(
            installed
                .iter()
                .map(|value| value.to_bits())
                .collect::<Vec<_>>(),
            first_restart
                .pre_action_unconstrained_position()
                .iter()
                .map(|value| value.to_bits())
                .collect::<Vec<_>>(),
            "pre-action and installed positions have distinct semantics"
        );
    }
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
fn two_hit_waits_for_the_second_same_hit_and_then_resets() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(2, 1.0);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let threads = NonZeroUsize::new(4).unwrap();
    let observed = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 100, Some(ChainRescueConfig::observe_only())),
        threads,
    )
    .unwrap();
    let rescued = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 100, Some(ChainRescueConfig::two_hit())),
        threads,
    )
    .unwrap();

    let records = rescued.chains()[3].telemetry().chain_rescues();
    let first_hit = records
        .iter()
        .position(|update| {
            matches!(
                update.outcome(),
                ChainRescueOutcome::PendingFirstHit {
                    criterion: ChainRescueCriterion::LogDensity
                }
            )
        })
        .expect("trap has a first density hit");
    let first = &records[first_hit];
    assert_eq!(first.prior_criterion(), None);
    assert_eq!(first.prior_streak(), 0);
    assert_eq!(
        first.resulting_criterion(),
        Some(ChainRescueCriterion::LogDensity)
    );
    assert_eq!(first.resulting_streak(), 1);
    assert_eq!(first.installed_unconstrained_position(), None);
    assert!(!matches!(
        first.outcome(),
        ChainRescueOutcome::Restarted { .. }
    ));

    let second = &records[first_hit + 1];
    let ChainRescueOutcome::Restarted {
        source,
        criterion,
        source_position,
        step_after,
    } = second.outcome()
    else {
        panic!("second same hit did not restart: {:?}", second.outcome());
    };
    assert_eq!(*criterion, ChainRescueCriterion::LogDensity);
    assert_eq!(second.proposed_source_chain(), Some(*source));
    assert!(*source_position < second.window_transitions());
    assert!(step_after.is_finite() && *step_after > 0.0);
    assert_eq!(
        second
            .installed_unconstrained_position()
            .expect("restart position")
            .len(),
        2
    );
    assert_eq!(
        second.prior_criterion(),
        Some(ChainRescueCriterion::LogDensity)
    );
    assert_eq!(second.prior_streak(), 1);
    assert_eq!(second.resulting_criterion(), None);
    assert_eq!(second.resulting_streak(), 0);

    // Up through the second boundary's pre-action snapshot, two-hit has
    // neither mutated the chain nor advanced its RNG on the first hit.
    let observed_records = observed.chains()[3].telemetry().chain_rescues();
    for (two_hit, observe) in records[..=first_hit + 1]
        .iter()
        .zip(&observed_records[..=first_hit + 1])
    {
        assert_eq!(
            two_hit.pre_action_unconstrained_position(),
            observe.pre_action_unconstrained_position()
        );
        assert_eq!(two_hit.current_step(), observe.current_step());
        assert_eq!(two_hit.median_log_density(), observe.median_log_density());
        assert_eq!(two_hit.log_density_iqr(), observe.log_density_iqr());
        assert_eq!(two_hit.step_hit(), observe.step_hit());
        assert_eq!(two_hit.density_hit(), observe.density_hit());
        assert_eq!(
            two_hit.proposed_source_chain(),
            observe.proposed_source_chain()
        );
    }

    let rescued_mean = rescued.chains()[3].samples().iter().sum::<f64>() / (2.0 * 100.0);
    assert!(
        rescued_mean.abs() < 1.0,
        "after the second hit chain 3 samples the main mode (mean {rescued_mean})"
    );
}

#[test]
fn rescue_telemetry_obeys_score_and_state_invariants() {
    let target = Trap;
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let mut starts = starts(2, 1.0);
    starts[3] = vec![TRAP_CENTER, TRAP_CENTER];
    let output = sample_chains(
        &target,
        &starts,
        &mass,
        &config(500, 50, Some(ChainRescueConfig::observe_only())),
        NonZeroUsize::new(4).unwrap(),
    )
    .unwrap();

    for (chain, chain_output) in output.chains().iter().enumerate() {
        for update in chain_output.telemetry().chain_rescues() {
            assert_eq!(update.chain(), chain);
            assert_eq!(update.pre_action_unconstrained_position().len(), 2);
            assert_eq!(update.skip_reason(), None);
            assert!(update.eligible());
            assert_eq!(
                update.step_threshold(),
                update.median_step().map(|median| 0.1 * median)
            );
            assert_eq!(
                update.density_threshold(),
                update.density_spread().map(|spread| 3.0 * spread)
            );
            assert_eq!(
                update.density_gap(),
                update
                    .density_reference()
                    .zip(update.median_log_density())
                    .map(|(reference, score)| reference - score)
            );
            let canonical = if update.step_hit() {
                Some(ChainRescueCriterion::Step)
            } else if update.density_hit() {
                Some(ChainRescueCriterion::LogDensity)
            } else {
                None
            };
            assert_eq!(update.observed_canonical_criterion(), canonical);
            assert!(update.proposed_source_chain().is_some());
            assert_eq!(update.prior_criterion(), None);
            assert_eq!(update.prior_streak(), 0);
            assert_eq!(update.resulting_criterion(), None);
            assert_eq!(update.resulting_streak(), 0);
            assert_eq!(update.installed_unconstrained_position(), None);
            match (canonical, update.outcome()) {
                (Some(expected), ChainRescueOutcome::ObservedHit { criterion }) => {
                    assert_eq!(*criterion, expected)
                }
                (None, ChainRescueOutcome::Kept) => {}
                pair => panic!("inconsistent observe outcome: {pair:?}"),
            }
        }
    }
}

#[test]
fn rescue_result_and_working_memory_are_preflight_accounted() {
    let plain_result = minimum_admitted_memory(MemoryCeiling::Result, None);
    let observe_result = minimum_admitted_memory(
        MemoryCeiling::Result,
        Some(ChainRescueConfig::observe_only()),
    );
    let restart_result = minimum_admitted_memory(
        MemoryCeiling::Result,
        Some(ChainRescueConfig::restart_from_best()),
    );
    assert!(plain_result < observe_result);
    assert!(observe_result < restart_result);
    assert!(memory_admitted(
        MemoryCeiling::Result,
        observe_result,
        Some(ChainRescueConfig::observe_only())
    ));
    assert!(!memory_admitted(
        MemoryCeiling::Result,
        observe_result - 1,
        Some(ChainRescueConfig::observe_only())
    ));
    assert!(memory_admitted(
        MemoryCeiling::Result,
        observe_result - 1,
        None
    ));

    let plain_working = minimum_admitted_memory(MemoryCeiling::Working, None);
    let observe_working = minimum_admitted_memory(
        MemoryCeiling::Working,
        Some(ChainRescueConfig::observe_only()),
    );
    let restart_working = minimum_admitted_memory(
        MemoryCeiling::Working,
        Some(ChainRescueConfig::restart_from_best()),
    );
    assert!(plain_working < observe_working);
    assert!(observe_working < restart_working);
    assert!(memory_admitted(
        MemoryCeiling::Working,
        restart_working,
        Some(ChainRescueConfig::restart_from_best())
    ));
    assert!(!memory_admitted(
        MemoryCeiling::Working,
        restart_working - 1,
        Some(ChainRescueConfig::restart_from_best())
    ));
    assert!(memory_admitted(
        MemoryCeiling::Working,
        restart_working - 1,
        Some(ChainRescueConfig::observe_only())
    ));

    let target = Gaussian(16);
    let starts = starts(16, 1.0);
    let mass = DiagonalMass::identity(NonZeroUsize::new(16).unwrap());
    let rejected = config(400, 20, Some(ChainRescueConfig::restart_from_best()))
        .with_limits(limits_with(MemoryCeiling::Working, restart_working - 1));
    assert_eq!(
        preflight_chains(&target, &starts, &mass, &rejected)
            .unwrap_err()
            .kind(),
        ErrorKind::ResourceLimit
    );
}

#[test]
fn rescue_with_skipped_boundaries_or_one_chain_is_the_plain_run() {
    let target = Gaussian(2);
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let starts = starts(2, 1.0);
    let threads = NonZeroUsize::new(2).unwrap();
    // Every window is shorter than the minimum: every boundary is skipped
    // and the draws are the plain run's.
    let skipped = ChainRescueConfig::two_hit()
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
        assert!(with.telemetry().chain_rescues().iter().all(|update| {
            !update.eligible()
                && update.skip_reason() == Some(ChainRescueSkip::ShortWindow)
                && update.observed_canonical_criterion().is_none()
                && update.resulting_criterion().is_none()
                && update.resulting_streak() == 0
        }));
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
fn sampler_default_is_silent_and_custom_supports_every_rescue_policy() {
    let target = Gaussian(2);
    let default = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(3)
        .run_from_random_starts(&target)
        .unwrap();
    assert!(
        default
            .telemetry()
            .all(|telemetry| telemetry.chain_rescues().is_empty())
    );

    for rescue in [
        ChainRescueConfig::restart_from_best(),
        ChainRescueConfig::observe_only(),
        ChainRescueConfig::two_hit(),
        ChainRescueConfig::pool_at_boundaries(),
    ] {
        let posterior = Sampler::new()
            .warmup(300)
            .draws(50)
            .chains(3)
            .adaptation(Adaptation::Custom(warmup(Some(rescue))))
            .run_from_random_starts(&target)
            .unwrap();
        assert!(
            posterior
                .telemetry()
                .all(|telemetry| !telemetry.chain_rescues().is_empty())
        );
    }

    let dense = Sampler::new()
        .warmup(300)
        .draws(50)
        .chains(3)
        .metric(Metric::dense())
        .adaptation(Adaptation::Custom(warmup(Some(
            ChainRescueConfig::restart_from_best(),
        ))))
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
    assert_eq!(owalnuts::sampler::DEFAULT_CHAIN_RESCUE, None);
    assert_eq!(
        ChainRescueConfig::observe_only().mode(),
        ChainRescueMode::RestartFromBest
    );
    assert_eq!(
        ChainRescueConfig::observe_only().policy(),
        ChainRescuePolicy::ObserveOnly
    );
    assert_eq!(
        ChainRescueConfig::two_hit().policy(),
        ChainRescuePolicy::TwoHit
    );
    assert!(
        ChainRescueConfig::pool_at_boundaries()
            .with_policy(ChainRescuePolicy::TwoHit)
            .is_err()
    );
    assert!(
        ChainRescueConfig::pool_at_boundaries()
            .with_policy(ChainRescuePolicy::ObserveOnly)
            .is_err()
    );
}
