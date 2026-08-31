use std::{
    num::NonZeroUsize,
    sync::{
        Arc, Barrier, Mutex, OnceLock,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
    thread,
};

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, BlockDiagonalMass, CONSERVATIVE_MAX_TARGET_EVALUATIONS,
    DEFAULT_DIVERGENCE_THRESHOLD, DEFAULT_MAX_DEPTH, DEFAULT_MAX_ERROR,
    DEFAULT_MAX_REFINEMENT_LEVELS, DEFAULT_MIN_MICRO_STEPS, DEFAULT_STEP_SIZE,
    DIRECT_ORIGINAL_Q_REVISION, DenseMass, DiagonalMass, DirectOriginalQMass, ErrorKind,
    InitialStepSearchConfig, KernelTuning, LowRankArrowheadMass, PROJECTED_ARROWHEAD_REVISION,
    ProjectedArrowheadWarmup, ProjectedMetricOutcome, ProposalObservation,
    ProposalObservationControl, ProposalObserver, ProposalPhase, ProposalTargetOutcome,
    RESEARCH_MAX_TARGET_EVALUATIONS, ResearchRestartReferenceMultiplier,
    ResearchTargetEvaluationLimit, RunConfig, RunControl, StopReason, StructuredBlockMass,
    StructuredCovarianceBlock, Target, TargetError, TargetErrorKind,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, TargetEvaluationLimitProvenance,
    WarmupConfig, preflight_chains, preflight_chains_with_target_budget, sample,
    sample_block_dense, sample_chains, sample_chains_dense,
    sample_chains_dense_with_target_budget_and_control, sample_chains_direct_original_q,
    sample_chains_projected_arrowhead, sample_chains_structured, sample_chains_with_control,
    sample_chains_with_target_budget, sample_dense, sample_direct_original_q,
    sample_projected_arrowhead,
};

#[derive(Default)]
struct RecordingObserver(Mutex<Vec<ProposalObservation>>);
impl ProposalObserver for RecordingObserver {
    fn observe(&self, observation: &ProposalObservation) {
        self.0.lock().unwrap().push(observation.clone())
    }
}
use rand::{SeedableRng, rngs::SmallRng};

fn golden_mix(hash: &mut u64, value: u64) {
    *hash ^= value;
    *hash = hash.wrapping_mul(0x100_0000_01b3);
}

fn fixed_chain_golden(output: &owalnuts::walnutpie::ChainOutput) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325;
    for value in output.samples() {
        golden_mix(&mut hash, value.to_bits());
    }
    for diagnostic in output.diagnostics() {
        for value in [
            diagnostic.depth(),
            diagnostic.target_evaluations(),
            diagnostic.direction_draws(),
            diagnostic.uniform_draws(),
            diagnostic.leaves_attempted(),
            diagnostic.leaves_built(),
            diagnostic.refinement_attempts(),
            diagnostic.reverse_coarser_rejections(),
        ] {
            golden_mix(&mut hash, value as u64);
        }
        golden_mix(&mut hash, diagnostic.initial_hamiltonian().to_bits());
        golden_mix(
            &mut hash,
            diagnostic.maximum_absolute_energy_error().to_bits(),
        );
        golden_mix(&mut hash, diagnostic.divergent() as u64);
    }
    let work = output.telemetry().total();
    for value in [
        work.transitions(),
        work.momentum_refreshes(),
        work.standard_normal_components(),
        work.target_calls_total(),
        work.direction_draws(),
        work.uniform_draws(),
        work.leaves_attempted(),
        work.leaves_built(),
    ] {
        golden_mix(&mut hash, value as u64);
    }
    hash
}

#[test]
fn fixed_metric_architecture_goldens_cover_all_existing_paths() {
    let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 0x0a11_ce55);
    let initial = [0.25, -0.5];
    let identity = sample(
        &Gaussian,
        &initial,
        &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
        &config,
    )
    .unwrap();
    let diagonal = sample(
        &Gaussian,
        &initial,
        &DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap(),
        &config,
    )
    .unwrap();
    let dense_mass = DenseMass::from_matrix(vec![1.5, 0.25, 0.25, 0.75], 2).unwrap();
    let dense = sample_dense(&Gaussian, &initial, &dense_mass, &config).unwrap();
    let block_mass = BlockDiagonalMass::from_blocks(vec![(vec![1.5], 1), (vec![0.75], 1)]).unwrap();
    let block = sample_block_dense(&Gaussian, &initial, &block_mass, &config).unwrap();
    let path_mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
        scale: vec![1.0, 1.4],
        rho: 0.35,
    }])
    .unwrap();
    let path = sample_chains_structured(
        &Gaussian,
        &[initial.to_vec()],
        &path_mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();

    let mut arrow_hash = 0xcbf2_9ce4_8422_2325;
    let arrow = LowRankArrowheadMass::new(
        vec![vec![1.2]],
        StructuredCovarianceBlock::BidiagonalCholesky {
            diagonal: vec![0.9],
            subdiagonal: vec![],
        },
        vec![vec![0.2]],
        vec![vec![-0.3]],
    )
    .unwrap();
    let mut rng = SmallRng::seed_from_u64(0x0a11_ce55);
    let momentum = arrow.sample_momentum(&mut rng).unwrap();
    for value in momentum
        .iter()
        .chain(arrow.drift(&momentum).unwrap().iter())
    {
        golden_mix(&mut arrow_hash, value.to_bits());
    }
    golden_mix(
        &mut arrow_hash,
        arrow.kinetic_energy(&momentum).unwrap().to_bits(),
    );

    let observed = [
        fixed_chain_golden(&identity),
        fixed_chain_golden(&diagonal),
        fixed_chain_golden(&dense),
        fixed_chain_golden(&block),
        fixed_chain_golden(&path.chains()[0]),
        arrow_hash,
    ];
    assert_eq!(
        observed,
        [
            0xf635_6610_5cea_a4bd,
            0x3e52_efbd_ca18_6c76,
            0xee75_fd9e_ae07_9e70,
            0xc8eb_3a80_789d_3423,
            0x37d3_da49_0ea1_7b05,
            0x020f_e236_d01c_09d1,
        ]
    );
}

#[test]
fn direct_original_q_metrics_have_distinct_deterministic_goldens() {
    let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 0x00d1_2ec7);
    let initial = [0.25, -0.5];
    let masses = [
        DirectOriginalQMass::Dense(DenseMass::from_matrix(vec![1.5, 0.25, 0.25, 0.75], 2).unwrap()),
        DirectOriginalQMass::BlockDiagonal(
            BlockDiagonalMass::from_blocks(vec![(vec![1.5], 1), (vec![0.75], 1)]).unwrap(),
        ),
        DirectOriginalQMass::StructuredPath(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
                scale: vec![1.0, 1.4],
                rho: 0.35,
            }])
            .unwrap(),
        ),
        DirectOriginalQMass::LowRankArrowhead(
            LowRankArrowheadMass::new(
                vec![vec![1.2]],
                StructuredCovarianceBlock::BidiagonalCholesky {
                    diagonal: vec![0.9],
                    subdiagonal: vec![],
                },
                vec![vec![0.2]],
                vec![vec![-0.3]],
            )
            .unwrap(),
        ),
    ];
    let observed = masses.map(|mass| {
        let output = sample_direct_original_q(&Gaussian, &initial, &mass, &config).unwrap();
        assert_eq!(
            output.metadata().algorithm_revision(),
            DIRECT_ORIGINAL_Q_REVISION
        );
        fixed_chain_golden(&output)
    });
    assert_eq!(
        observed,
        [
            0x9a7c_6c16_a39f_ed74,
            0x1775_af1b_4c81_8256,
            0xa37e_8a1d_ab51_1db5,
            0x77ea_3130_3362_1721,
        ]
    );
}

#[test]
fn direct_original_q_multichain_is_parallel_identical() {
    let mass = DirectOriginalQMass::StructuredPath(
        StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.0, 1.4],
            rho: 0.35,
        }])
        .unwrap(),
    );
    let starts = vec![vec![0.25, -0.5], vec![-0.1, 0.3]];
    let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 0x051a_11e1);
    let sequential = sample_chains_direct_original_q(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let parallel = sample_chains_direct_original_q(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .unwrap();
    for (left, right) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
    }
}

struct TenDimensionalGaussian;

impl Target for TenDimensionalGaussian {
    fn dimension(&self) -> usize {
        10
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (out, value) in gradient.iter_mut().zip(position) {
            *out = -*value;
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

fn projected_fixture() -> (LowRankArrowheadMass, ProjectedArrowheadWarmup) {
    let basis = vec![
        vec![1.0, 0.0],
        vec![0.0, 1.0],
        vec![0.0, 0.0],
        vec![0.0, 0.0],
    ];
    let global_lower = (0..6)
        .map(|i| (0..6).map(|j| f64::from(i == j)).collect())
        .collect();
    let mass = LowRankArrowheadMass::new(
        global_lower,
        StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.0; 4],
            rho: 0.2,
        },
        basis.clone(),
        vec![vec![0.0; 2]; 6],
    )
    .unwrap();
    let warmup =
        ProjectedArrowheadWarmup::new(basis, NonZeroUsize::new(4).unwrap(), 0.1, 1.0e-6, 1.0e8)
            .unwrap();
    (mass, warmup)
}

#[test]
fn projected_arrowhead_installs_only_at_window_boundaries_and_accounts_work() {
    let (mass, projected) = projected_fixture();
    let warmup = WarmupConfig::new(0.8).unwrap();
    let config = RunConfig::new(40, NonZeroUsize::new(4).unwrap(), 0x2a11_ce55).with_warmup(warmup);
    let output = sample_projected_arrowhead(
        &TenDimensionalGaussian,
        &[0.1; 10],
        &mass,
        &projected,
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(
        output.chain().metadata().algorithm_revision(),
        PROJECTED_ARROWHEAD_REVISION
    );
    assert_eq!(output.chain().samples().len(), 40);
    assert_eq!(output.chain().diagnostics().len(), 44);
    assert_eq!(output.chain().telemetry().total().transitions(), 44);
    assert_eq!(output.chain().telemetry().total().momentum_refreshes(), 44);
    assert_eq!(output.chain().telemetry().total().target_calls_initial(), 1);
    assert!(!output.metric_updates().is_empty());
    assert!(output.metric_updates().iter().all(|event| {
        event.rank() == 2
            && matches!(
                event.outcome(),
                ProjectedMetricOutcome::Installed
                    | ProjectedMetricOutcome::InsufficientSamples
                    | ProjectedMetricOutcome::IllConditionedFallback
                    | ProjectedMetricOutcome::FactorizationFallback
                    | ProjectedMetricOutcome::NonfiniteFallback
            )
    }));
}

#[test]
fn projected_arrowhead_boundary_step_search_is_cached_and_deterministic() {
    let (mass, projected) = projected_fixture();
    let config = RunConfig::new(30, NonZeroUsize::new(2).unwrap(), 0x2a11_ce56)
        .with_warmup(WarmupConfig::new(0.8).unwrap());
    let left = sample_projected_arrowhead(
        &TenDimensionalGaussian,
        &[0.0; 10],
        &mass,
        &projected,
        &config,
        &RunControl::new(),
    )
    .unwrap();
    let right = sample_projected_arrowhead(
        &TenDimensionalGaussian,
        &[0.0; 10],
        &mass,
        &projected,
        &config,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(left, right);

    let probes = 2;
    let search = InitialStepSearchConfig::new(
        NonZeroUsize::new(probes).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(32).unwrap(),
    )
    .unwrap();
    let searched = RunConfig::new(30, NonZeroUsize::new(1).unwrap(), 1).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_initial_step_search(search),
    );
    let searched_left = sample_projected_arrowhead(
        &TenDimensionalGaussian,
        &[0.0; 10],
        &mass,
        &projected,
        &searched,
        &RunControl::new(),
    )
    .unwrap();
    let searched_right = sample_projected_arrowhead(
        &TenDimensionalGaussian,
        &[0.0; 10],
        &mass,
        &projected,
        &searched,
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(searched_left, searched_right);
    assert_eq!(
        searched_left
            .chain()
            .telemetry()
            .total()
            .target_calls_initial(),
        1
    );
    let searches = searched_left.chain().telemetry().step_searches();
    assert!(!searches.is_empty());
    assert!(
        searches
            .iter()
            .all(|event| event.search().probes() == probes)
    );
    assert_eq!(
        searched_left
            .chain()
            .telemetry()
            .total()
            .momentum_refreshes(),
        searched_left.chain().diagnostics().len() + searches.len() * probes
    );
}

#[test]
fn pooled_projected_barrier_is_parallel_identical_shared_and_cache_exact() {
    let (mass, projected) = projected_fixture();
    let search = InitialStepSearchConfig::new(
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(64).unwrap(),
    )
    .unwrap();
    let config = RunConfig::new(40, NonZeroUsize::new(4).unwrap(), 0x706f_6f6c).with_warmup(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_initial_step_search(search),
    );
    let positions = vec![vec![0.0; 10], vec![0.1; 10], vec![-0.1; 10], vec![0.2; 10]];
    let sequential = sample_chains_projected_arrowhead(
        &TenDimensionalGaussian,
        &positions,
        &mass,
        &projected,
        &config,
        NonZeroUsize::new(1).unwrap(),
        &RunControl::new(),
    )
    .unwrap();
    let parallel = sample_chains_projected_arrowhead(
        &TenDimensionalGaussian,
        &positions,
        &mass,
        &projected,
        &config,
        NonZeroUsize::new(4).unwrap(),
        &RunControl::new(),
    )
    .unwrap();
    assert_eq!(sequential.final_mass(), parallel.final_mass());
    assert_eq!(sequential.metric_updates(), parallel.metric_updates());
    for (left, right) in sequential
        .chains()
        .chains()
        .iter()
        .zip(parallel.chains().chains())
    {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
        assert_eq!(left.telemetry().total().target_calls_initial(), 1);
        assert!(!left.telemetry().step_searches().is_empty());
        assert!(left.diagnostics().iter().all(|diagnostic| {
            diagnostic.stop() != StopReason::MaximumDepth
                || diagnostic
                    .final_uturn_margin()
                    .is_some_and(|margin| margin >= 0.0)
        }));
    }
    assert!(sequential.metric_updates().iter().all(|update| {
        update.sample_count() % positions.len() == 0
            && update.generation() <= sequential.metric_updates().len()
    }));
}

struct Gaussian;

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        for (gradient, position) in gradient.iter_mut().zip(position) {
            *gradient = -*position;
        }
        Ok(-0.5 * position.iter().map(|value| value * value).sum::<f64>())
    }
}

#[test]
fn stochastic_public_facade_returns_samples_diagnostics_and_run_identity() {
    let initial_positions = vec![vec![0.25, -0.5], vec![-0.75, 0.125]];
    let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
    let config = RunConfig::new(2, NonZeroUsize::new(4).unwrap(), 0x5eed);
    let output = sample_chains(
        &Gaussian,
        &initial_positions,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .unwrap();

    assert_eq!(output.chains().len(), 2);
    assert_eq!(output.algorithm_revision(), ALGORITHM_REVISION);
    for (chain, initial_position) in output.chains().iter().zip(&initial_positions) {
        assert_eq!(chain.samples().len(), 8);
        assert_eq!(chain.diagnostics().len(), 6);
        assert!(chain.samples().iter().all(|value| value.is_finite()));
        assert_eq!(chain.metadata().initial_position(), initial_position);
        assert_eq!(chain.metadata().thread_count(), 2);
        assert_eq!(chain.metadata().mass_diagonal(), mass.diagonal());
        assert_eq!(chain.telemetry().total().transitions(), 6);
    }
    assert_ne!(output.chains()[0].samples(), output.chains()[1].samples());
}

#[test]
fn default_tuning_preserves_the_qualified_public_behavior() {
    let implicit = RunConfig::new(1, NonZeroUsize::new(3).unwrap(), 17);
    let explicit = implicit.clone().with_tuning(KernelTuning::default());
    assert_eq!(implicit, explicit);
    assert_eq!(implicit.tuning().step_size(), DEFAULT_STEP_SIZE);
    assert_eq!(implicit.tuning().max_depth(), DEFAULT_MAX_DEPTH);
    assert_eq!(implicit.tuning().min_micro_steps(), DEFAULT_MIN_MICRO_STEPS);
    assert_eq!(
        implicit.tuning().max_refinement_levels(),
        DEFAULT_MAX_REFINEMENT_LEVELS
    );
    assert_eq!(implicit.tuning().max_error(), DEFAULT_MAX_ERROR);
    assert_eq!(
        implicit.tuning().divergence_threshold(),
        DEFAULT_DIVERGENCE_THRESHOLD
    );

    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    assert_eq!(
        sample(&Gaussian, &[0.25, -0.5], &mass, &implicit).unwrap(),
        sample(&Gaussian, &[0.25, -0.5], &mass, &explicit).unwrap()
    );
}

#[test]
fn checkpoint_telemetry_is_behavior_and_rng_identical() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let initial = [0.3, -0.4];
    let plain = RunConfig::new(120, NonZeroUsize::new(20).unwrap(), 0x71d)
        .with_warmup(WarmupConfig::new(0.9).unwrap());
    let instrumented = RunConfig::new(120, NonZeroUsize::new(20).unwrap(), 0x71d).with_warmup(
        WarmupConfig::new(0.9)
            .unwrap()
            .with_telemetry_checkpoints(vec![0, 1, 74, 75, 99, 100, 119])
            .unwrap(),
    );
    let left = sample(&Gaussian, &initial, &mass, &plain).unwrap();
    let right = sample(&Gaussian, &initial, &mass, &instrumented).unwrap();
    assert_eq!(left.samples(), right.samples());
    assert_eq!(left.diagnostics(), right.diagnostics());
    assert_eq!(left.telemetry().total(), right.telemetry().total());
    assert_eq!(left.telemetry().discarded(), right.telemetry().discarded());
    assert_eq!(left.telemetry().retained(), right.telemetry().retained());
    assert_eq!(left.metadata().tuning(), right.metadata().tuning());
    assert_eq!(
        left.metadata().mass_diagonal(),
        right.metadata().mass_diagonal()
    );
    assert!(left.telemetry().warmup_checkpoints().is_empty());
    assert_eq!(right.telemetry().warmup_checkpoints().len(), 7);
    for checkpoint in right.telemetry().warmup_checkpoints() {
        assert!((0.0..=1.0).contains(&checkpoint.current_coarse_endpoint().mean().unwrap()));
        if let Some(mean) = checkpoint.accepted_trajectory().mean() {
            assert!((0.0..=1.0).contains(&mean));
        }
    }
}

#[test]
fn research_restart_multiplier_is_exact_at_every_installed_restart() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    for multiplier in [
        ResearchRestartReferenceMultiplier::One,
        ResearchRestartReferenceMultiplier::Ten,
    ] {
        let config = RunConfig::new(200, NonZeroUsize::new(2).unwrap(), 0x91a).with_warmup(
            WarmupConfig::new(0.9)
                .unwrap()
                .with_research_restart_reference_multiplier(multiplier),
        );
        let output = sample(&Gaussian, &[0.2, -0.1], &mass, &config).unwrap();
        let restarts: Vec<_> = output
            .telemetry()
            .metric_updates()
            .iter()
            .filter(|update| update.dual_averaging_after_restart().is_some())
            .collect();
        assert!(!restarts.is_empty());
        for update in restarts {
            assert_eq!(update.restart_reference_multiplier(), Some(multiplier));
            let step = update.step_after_restart().unwrap();
            let dual = update.dual_averaging_after_restart().unwrap();
            assert_eq!(dual.iteration(), 0);
            assert_eq!(dual.mu(), (multiplier.value() * step).ln());
            assert_eq!(dual.log_step(), step.ln());
            assert_eq!(dual.log_step_bar(), step.ln());
        }
    }
}

#[test]
fn checkpointed_warmup_is_parallel_sequential_identical() {
    let positions = vec![vec![0.2, -0.1], vec![-0.4, 0.3], vec![0.1, 0.5]];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let warmup = WarmupConfig::new(0.9)
        .unwrap()
        .with_telemetry_checkpoints(vec![0, 1, 74, 75, 99, 119])
        .unwrap()
        .with_research_restart_reference_multiplier(ResearchRestartReferenceMultiplier::Ten);
    let config = RunConfig::new(120, NonZeroUsize::new(5).unwrap(), 0x2244).with_warmup(warmup);
    let sequential = sample_chains(
        &Gaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let parallel = sample_chains(
        &Gaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(3).unwrap(),
    )
    .unwrap();
    for (left, right) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
    }
}

#[test]
fn telemetry_checkpoint_validation_fails_closed() {
    assert!(
        WarmupConfig::new(0.9)
            .unwrap()
            .with_telemetry_checkpoints(vec![2, 2])
            .is_err()
    );
    let warmup = WarmupConfig::new(0.9)
        .unwrap()
        .with_telemetry_checkpoints(vec![10])
        .unwrap();
    let config = RunConfig::new(10, NonZeroUsize::new(1).unwrap(), 7).with_warmup(warmup);
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    assert!(preflight_chains(&Gaussian, &[vec![0.0, 0.0]], &mass, &config).is_err());
}

#[test]
fn public_health_accessors_threshold_and_phase_totals_are_exact() {
    let base = KernelTuning::new(
        1.4,
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(4).unwrap(),
        10.0,
    )
    .unwrap();
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let probe = sample(
        &Gaussian,
        &[0.8, -0.4],
        &mass,
        &RunConfig::new(3, NonZeroUsize::new(5).unwrap(), 0xbee)
            .with_tuning(base.with_divergence_threshold(f64::MAX).unwrap()),
    )
    .unwrap();
    let observed = probe
        .diagnostics()
        .iter()
        .map(|d| d.maximum_absolute_energy_error())
        .filter(|x| x.is_finite())
        .fold(0.0_f64, f64::max);
    assert!(observed > 0.0);

    let exact = sample(
        &Gaussian,
        &[0.8, -0.4],
        &mass,
        &RunConfig::new(3, NonZeroUsize::new(5).unwrap(), 0xbee)
            .with_tuning(base.with_divergence_threshold(observed).unwrap()),
    )
    .unwrap();
    assert!(exact.diagnostics().iter().all(|d| !d.divergent()));

    let strict = sample(
        &Gaussian,
        &[0.8, -0.4],
        &mass,
        &RunConfig::new(3, NonZeroUsize::new(5).unwrap(), 0xbee)
            .with_tuning(base.with_divergence_threshold(observed / 2.0).unwrap()),
    )
    .unwrap();
    assert!(strict.diagnostics().iter().any(|d| d.divergent()));
    for diagnostic in strict.diagnostics() {
        assert!(diagnostic.initial_hamiltonian().is_finite());
        assert!(diagnostic.minimum_hamiltonian() <= diagnostic.initial_hamiltonian());
        assert!(diagnostic.maximum_hamiltonian() >= diagnostic.initial_hamiltonian());
        assert!(diagnostic.refinement_attempts() >= 1);
        let _ = diagnostic.selected_refinement_level();
        let _ = diagnostic.reverse_coarser_rejections();
    }
    let warmup_divergences = strict.telemetry().discarded().divergences();
    let retained_divergences = strict.telemetry().retained().divergences();
    assert_eq!(
        strict.telemetry().total().divergences(),
        warmup_divergences + retained_divergences
    );
    assert_eq!(
        strict.telemetry().total().divergences(),
        strict
            .diagnostics()
            .iter()
            .filter(|d| d.divergent())
            .count()
    );
    let totals = strict.telemetry().total();
    assert_eq!(
        totals.reverse_coarser_rejections(),
        strict
            .diagnostics()
            .iter()
            .map(|d| d.reverse_coarser_rejections())
            .sum()
    );
    let _ = totals.invalid_evaluation_stops();
    let _ = totals.refinement_exhaustion_stops();
    let _ = totals.reverse_coarser_stops();
}

#[test]
fn divergence_threshold_validation_is_public() {
    let base = KernelTuning::default();
    for invalid in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        assert_eq!(
            base.with_divergence_threshold(invalid).unwrap_err().kind(),
            ErrorKind::Configuration
        );
    }
}

struct RotatedGaussian;

impl Target for RotatedGaussian {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        // Covariance [[2, 1], [1, 2]], precision M = (1/3)[[2,-1],[-1,2]].
        gradient[0] = -(2.0 * q[0] - q[1]) / 3.0;
        gradient[1] = -(-q[0] + 2.0 * q[1]) / 3.0;
        Ok(0.5 * (q[0] * gradient[0] + q[1] * gradient[1]))
    }
}

#[test]
fn dense_precision_metric_is_deterministic_and_exactly_accounted() {
    let mass =
        DenseMass::from_matrix(vec![2.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0, 2.0 / 3.0], 2).unwrap();
    let config = RunConfig::new(4, NonZeroUsize::new(12).unwrap(), 0xd3_5e);
    let first = sample_dense(&RotatedGaussian, &[0.2, -0.1], &mass, &config).unwrap();
    let second = sample_dense(&RotatedGaussian, &[0.2, -0.1], &mass, &config).unwrap();
    assert_eq!(first, second);
    assert!(first.samples().iter().all(|x| x.is_finite()));
    assert_eq!(first.telemetry().total().transitions(), 16);
    assert_eq!(first.telemetry().total().momentum_refreshes(), 16);
    assert_eq!(first.telemetry().total().standard_normal_components(), 32);
    assert_eq!(
        first.telemetry().total().target_calls_total(),
        first
            .diagnostics()
            .iter()
            .map(|d| d.target_evaluations())
            .sum()
    );

    let mut rng = SmallRng::seed_from_u64(91);
    for _ in 0..100 {
        let p = mass.sample_momentum(&mut rng).unwrap();
        let velocity = mass.drift(&p).unwrap();
        let reconstructed = [
            mass.matrix()[0] * velocity[0] + mass.matrix()[1] * velocity[1],
            mass.matrix()[2] * velocity[0] + mass.matrix()[3] * velocity[1],
        ];
        assert!((reconstructed[0] - p[0]).abs() < 2e-14);
        assert!((reconstructed[1] - p[1]).abs() < 2e-14);
        assert!(mass.kinetic_energy(&p).unwrap().is_finite());
    }
}

#[test]
fn dense_window_adaptation_learns_rotated_geometry_with_fallback_telemetry() {
    let identity = DenseMass::identity(NonZeroUsize::new(2).unwrap()).unwrap();
    let config = RunConfig::new(240, NonZeroUsize::new(8).unwrap(), 0xad_a7)
        .with_warmup(WarmupConfig::default());
    let first = sample_dense(&RotatedGaussian, &[0.2, -0.1], &identity, &config).unwrap();
    let second = sample_dense(&RotatedGaussian, &[0.2, -0.1], &identity, &config).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.telemetry().total().transitions(), 248);
    assert_eq!(first.telemetry().discarded().transitions(), 240);
    assert_eq!(first.telemetry().retained().transitions(), 8);
    assert_eq!(
        first.telemetry().initial_fast().transitions()
            + first.telemetry().slow().transitions()
            + first.telemetry().terminal_fast().transitions(),
        240
    );
    assert_eq!(
        first.telemetry().total().target_calls_total(),
        first
            .diagnostics()
            .iter()
            .map(|d| d.target_evaluations())
            .sum()
    );
    let installed = first
        .telemetry()
        .metric_updates()
        .iter()
        .filter_map(|update| update.mass_dense())
        .next_back()
        .expect("at least one sufficiently sampled dense window");
    assert!(
        installed[1].abs() > 0.01,
        "dense adaptation must retain learned rotation"
    );
    assert!(first.telemetry().metric_updates().iter().all(|update| {
        update
            .condition_estimate()
            .is_none_or(|condition| condition.is_finite())
            && update.ridge().is_finite()
            && update.shrinkage().is_finite()
    }));
    let successful_updates = first
        .telemetry()
        .metric_updates()
        .iter()
        .filter(|update| update.mass_dense().is_some())
        .count();
    let restarts = first
        .telemetry()
        .step_searches()
        .iter()
        .filter(|event| {
            matches!(
                event.reason(),
                owalnuts::walnutpie::StepSearchReason::DualAveragingRestart { .. }
            )
        })
        .count();
    assert_eq!(restarts, successful_updates);

    let diagonal = sample(
        &RotatedGaussian,
        &[0.2, -0.1],
        &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
        &config,
    )
    .unwrap();
    assert_eq!(
        first.metadata().warmup_schedule(),
        diagonal.metadata().warmup_schedule()
    );
    assert_eq!(
        first.telemetry().initial_fast().transitions(),
        diagonal.telemetry().initial_fast().transitions()
    );
    assert_eq!(
        first.telemetry().slow().transitions(),
        diagonal.telemetry().slow().transitions()
    );
    assert_eq!(
        first.telemetry().terminal_fast().transitions(),
        diagonal.telemetry().terminal_fast().transitions()
    );
    assert!(first.metadata().tuning().step_size().is_finite());
}

#[test]
fn dense_multichain_is_sequential_parallel_identical_in_physical_coordinates() {
    let mass =
        DenseMass::from_matrix(vec![2.0 / 3.0, -1.0 / 3.0, -1.0 / 3.0, 2.0 / 3.0], 2).unwrap();
    let positions = vec![vec![0.2, -0.1], vec![-0.3, 0.4], vec![0.7, -0.2]];
    let config = RunConfig::new(40, NonZeroUsize::new(5).unwrap(), 0xc4a1)
        .with_warmup(WarmupConfig::default());
    let sequential = sample_chains_dense(
        &RotatedGaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let parallel = sample_chains_dense(
        &RotatedGaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(3).unwrap(),
    )
    .unwrap();
    assert_eq!(sequential.chains().len(), parallel.chains().len());
    for (left, right) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
        assert!(left.samples().iter().all(|value| value.is_finite()));
    }
    assert_eq!(sequential.base_seed(), config.seed());
    assert_eq!(parallel.base_seed(), config.seed());
}

struct PositionFailure;

impl Target for PositionFailure {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        if (position[0] + 0.3).abs() < 1.0e-14 || (position[0] + 0.8).abs() < 1.0e-14 {
            return Err(TargetError::new("designated failing initial position"));
        }
        gradient.copy_from_slice(&[-position[0], -position[1]]);
        Ok(-0.5 * position.iter().map(|x| x * x).sum::<f64>())
    }
}

#[test]
fn dense_multichain_errors_choose_lowest_failing_chain() {
    let mass = DenseMass::identity(NonZeroUsize::new(2).unwrap()).unwrap();
    let positions = vec![vec![0.2, 0.1], vec![-0.3, 0.2], vec![-0.8, 0.4]];
    let config = RunConfig::new(0, NonZeroUsize::new(2).unwrap(), 99);
    for threads in [1, 3] {
        let error = sample_chains_dense(
            &PositionFailure,
            &positions,
            &mass,
            &config,
            NonZeroUsize::new(threads).unwrap(),
        )
        .unwrap_err();
        assert_eq!(error.chain(), Some(1));
        assert_eq!(error.kind(), ErrorKind::Target);
    }
}

#[test]
fn configured_tuning_is_public_and_metadata_records_actual_values() {
    let tuning = KernelTuning::new(
        0.25,
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(3).unwrap(),
        0.125,
    )
    .unwrap();
    let config = RunConfig::new(0, NonZeroUsize::new(2).unwrap(), 9).with_tuning(tuning);
    assert_eq!(config.tuning(), &tuning);

    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let output = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    let metadata = output.metadata();
    assert_eq!(metadata.qualified_step_size(), 0.25);
    assert_eq!(metadata.max_depth(), 2);
    assert_eq!(metadata.min_micro_steps(), 2);
    assert_eq!(metadata.max_refinement_levels(), 3);
    assert_eq!(metadata.max_error(), 0.125);
    assert_eq!(
        metadata.divergence_threshold(),
        DEFAULT_DIVERGENCE_THRESHOLD
    );
}

#[test]
fn tuning_rejects_nonfinite_nonpositive_and_overflowing_values() {
    let one = NonZeroUsize::new(1).unwrap();
    for step_size in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let error = KernelTuning::new(step_size, one, one, one, 1.0).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration);
    }
    for max_error in [0.0, -1.0, f64::NAN, f64::INFINITY] {
        let error = KernelTuning::new(0.5, one, one, one, max_error).unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration);
    }

    let too_large = NonZeroUsize::new(usize::BITS as usize + 1).unwrap();
    assert_eq!(
        KernelTuning::new(0.5, too_large, one, one, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        KernelTuning::new(0.5, one, one, too_large, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        KernelTuning::new(0.5, one, NonZeroUsize::new(usize::MAX).unwrap(), one, 1.0)
            .unwrap_err()
            .kind(),
        ErrorKind::Overflow
    );
}

#[test]
fn warmup_is_opt_in_deterministic_and_fixed_before_retention() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let config = RunConfig::new(100, NonZeroUsize::new(20).unwrap(), 0x51eed)
        .with_warmup(WarmupConfig::default());
    let first = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    let second = sample(&Gaussian, &[0.25, -0.5], &mass, &config).unwrap();
    assert_eq!(first, second);
    assert_eq!(first.metadata().warmup(), config.warmup());
    assert_eq!(first.metadata().initial_tuning(), config.tuning());
    assert_eq!(first.metadata().initial_mass_diagonal(), mass.diagonal());
    assert_ne!(first.metadata().mass_diagonal(), mass.diagonal());
    assert_eq!(first.telemetry().discarded().transitions(), 100);
    assert_eq!(first.telemetry().retained().transitions(), 20);
}

struct BoundedGaussian;

impl Target for BoundedGaussian {
    fn dimension(&self) -> usize {
        1
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        if position[0].abs() > 0.45 {
            return Err(TargetError::recoverable(
                "proposal is below representable density",
            ));
        }
        gradient[0] = -position[0];
        Ok(-0.5 * position[0] * position[0])
    }
}

#[test]
fn recoverable_target_failures_are_deterministic_rejections_with_exact_partitions() {
    assert_eq!(
        TargetError::recoverable("underflow").kind(),
        TargetErrorKind::Recoverable
    );
    assert_eq!(TargetError::new("bug").kind(), TargetErrorKind::Fatal);

    let mass = DiagonalMass::identity(NonZeroUsize::new(1).unwrap());
    let config = RunConfig::new(24, NonZeroUsize::new(24).unwrap(), 0x5e10)
        .with_warmup(WarmupConfig::default());
    let first = sample(&BoundedGaussian, &[0.0], &mass, &config).unwrap();
    let second = sample(&BoundedGaussian, &[0.0], &mass, &config).unwrap();
    assert_eq!(first, second);

    let discarded = first.telemetry().discarded().recoverable_target_failures();
    let retained = first.telemetry().retained().recoverable_target_failures();
    assert!(discarded > 0);
    assert!(retained > 0);
    assert_eq!(
        first.telemetry().total().recoverable_target_failures(),
        discarded + retained
    );
    assert_eq!(
        first.telemetry().total().recoverable_target_failures(),
        first
            .diagnostics()
            .iter()
            .map(|diagnostic| diagnostic.recoverable_target_failures())
            .sum()
    );
    assert!(first.diagnostics().iter().all(|diagnostic| {
        diagnostic.recoverable_target_failures() == 0
            || (diagnostic.stop() == owalnuts::walnutpie::StopReason::InvalidEvaluation
                && diagnostic.divergent()
                && diagnostic.maximum_absolute_energy_error().is_infinite())
    }));
    assert_eq!(
        first.telemetry().total().divergences(),
        first.diagnostics().iter().filter(|d| d.divergent()).count()
    );
    assert_eq!(
        first.telemetry().total().target_calls_total(),
        first
            .diagnostics()
            .iter()
            .map(|diagnostic| diagnostic.target_evaluations())
            .sum()
    );
}

#[test]
fn research_target_evaluation_opt_in_is_bounded_and_has_provenance() {
    let search = InitialStepSearchConfig::new(
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(CONSERVATIVE_MAX_TARGET_EVALUATIONS).unwrap(),
    )
    .unwrap();
    let base = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 17)
        .with_warmup(WarmupConfig::default().with_initial_step_search(search));
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());

    let error = sample(&Gaussian, &[0.0, 0.0], &mass, &base).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit);
    assert_eq!(
        error.message(),
        "target-evaluation bound exceeds its resource limit"
    );

    let raised = CONSERVATIVE_MAX_TARGET_EVALUATIONS
        .checked_add(1_000)
        .unwrap();
    let research_limit =
        ResearchTargetEvaluationLimit::new(NonZeroUsize::new(raised).unwrap()).unwrap();
    let research = base.with_research_target_evaluation_limit(research_limit);
    let output = sample(&Gaussian, &[0.0, 0.0], &mass, &research).unwrap();
    assert_eq!(output.metadata().effective_max_target_evaluations(), raised);
    assert_eq!(
        output.metadata().target_evaluation_limit_provenance(),
        TargetEvaluationLimitProvenance::ExplicitResearchOptIn
    );
    assert_eq!(output.metadata().limits(), research.limits());

    assert!(
        ResearchTargetEvaluationLimit::new(
            NonZeroUsize::new(CONSERVATIVE_MAX_TARGET_EVALUATIONS).unwrap()
        )
        .is_err()
    );
    assert!(
        ResearchTargetEvaluationLimit::new(
            NonZeroUsize::new(RESEARCH_MAX_TARGET_EVALUATIONS.checked_add(1).unwrap()).unwrap()
        )
        .is_err()
    );
}

fn legacy_bound_config() -> RunConfig {
    let tuning = KernelTuning::new(
        0.3,
        NonZeroUsize::new(10).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(8).unwrap(),
        0.5,
    )
    .unwrap();
    RunConfig::new(2_000, NonZeroUsize::new(50_000).unwrap(), 42)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.9).unwrap().with_mass_adaptation(true))
}

#[test]
fn budgeted_admission_accepts_exact_legacy_multichain_bound_without_callbacks() {
    let config = legacy_bound_config();
    let positions = vec![vec![0.0, 0.0]; 4];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(64_000_000).unwrap());
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(4).unwrap())
        .unwrap();
    assert_eq!(exact, 81_283_696_000);
    let report = preflight_chains_with_target_budget(
        &Gaussian,
        &positions,
        &mass,
        &config,
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .unwrap();
    assert_eq!(report.worst_case_target_evaluations(), exact);
    assert_eq!(report.admission_ceiling(), exact);
    assert_eq!(budget.started(), 0);
}

#[test]
fn legacy_bound_remains_rejected_by_every_unbudgeted_ceiling() {
    let config = legacy_bound_config();
    let positions = vec![vec![0.0, 0.0]; 4];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let error = preflight_chains(&Gaussian, &positions, &mass, &config).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit);
    let research = config.with_research_target_evaluation_limit(
        ResearchTargetEvaluationLimit::new(
            NonZeroUsize::new(RESEARCH_MAX_TARGET_EVALUATIONS).unwrap(),
        )
        .unwrap(),
    );
    assert!(preflight_chains(&Gaussian, &positions, &mass, &research).is_err());
}

#[test]
fn budgeted_admission_rejects_short_ceiling_oversized_cap_and_reused_budget() {
    let config = RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 1);
    let positions = vec![vec![0.0, 0.0]];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    let short = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact - 1).unwrap());
    assert!(
        preflight_chains_with_target_budget(&Gaussian, &positions, &mass, &config, short, &budget)
            .is_err()
    );

    let small_admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    let oversized = TargetEvaluationBudget::new(NonZeroUsize::new(exact + 1).unwrap());
    assert!(
        preflight_chains_with_target_budget(
            &Gaussian,
            &positions,
            &mass,
            &config,
            small_admission,
            &oversized
        )
        .is_err()
    );

    let reused = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    let wrapped = reused.wrap(&Gaussian);
    let mut gradient = [0.0; 2];
    wrapped
        .log_density_gradient(&[0.0, 0.0], &mut gradient)
        .unwrap();
    assert!(
        sample_chains_with_target_budget(
            &Gaussian,
            &positions,
            &mass,
            &config,
            NonZeroUsize::new(1).unwrap(),
            small_admission,
            &reused
        )
        .is_err()
    );
}

#[test]
fn target_budget_is_exact_under_contention_without_overshoot() {
    struct Counted(AtomicUsize);
    impl Target for Counted {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(
            &self,
            _: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            self.0.fetch_add(1, Ordering::Relaxed);
            gradient[0] = 0.0;
            Ok(0.0)
        }
    }
    let target = Arc::new(Counted(AtomicUsize::new(0)));
    let budget = Arc::new(TargetEvaluationBudget::new(NonZeroUsize::new(7).unwrap()));
    let barrier = Arc::new(Barrier::new(32));
    let handles = (0..32)
        .map(|_| {
            let target = Arc::clone(&target);
            let budget = Arc::clone(&budget);
            let barrier = Arc::clone(&barrier);
            thread::spawn(move || {
                barrier.wait();
                let mut gradient = [0.0];
                budget
                    .wrap(target.as_ref())
                    .log_density_gradient(&[0.0], &mut gradient)
                    .is_ok()
            })
        })
        .collect::<Vec<_>>();
    assert_eq!(
        handles
            .into_iter()
            .map(|handle| handle.join().unwrap())
            .filter(|succeeded| *succeeded)
            .count(),
        7
    );
    assert_eq!(budget.started(), 7);
    assert_eq!(target.0.load(Ordering::Relaxed), 7);
}

#[test]
fn budget_exhaustion_covers_initial_search_and_is_fatal() {
    let search = InitialStepSearchConfig::new(
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(2).unwrap(),
        NonZeroUsize::new(4).unwrap(),
    )
    .unwrap();
    let config = RunConfig::new(1, NonZeroUsize::new(1).unwrap(), 9).with_warmup(
        WarmupConfig::new(0.9)
            .unwrap()
            .with_initial_step_search(search),
    );
    let positions = vec![vec![0.0, 0.0]];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(1).unwrap());
    let error = sample_chains_with_target_budget(
        &Gaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert!(
        error
            .target_source()
            .is_some_and(|source| source.message().contains("budget exhausted"))
    );
    assert_eq!(budget.started(), 1);
}

#[test]
fn fatal_target_error_consumes_one_budget_reservation() {
    struct Fails;
    impl Target for Fails {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
            Err(TargetError::new("intentional target error"))
        }
    }
    let config = RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 3);
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    let error = sample_chains_with_target_budget(
        &Fails,
        &[vec![0.0]],
        &DiagonalMass::identity(NonZeroUsize::new(1).unwrap()),
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert_eq!(budget.started(), 1);
}

#[test]
fn retained_execution_exhaustion_and_target_panic_do_not_overshoot() {
    let config = RunConfig::new(0, NonZeroUsize::new(2).unwrap(), 4);
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(1).unwrap());
    let error = sample_chains_with_target_budget(
        &Gaussian,
        &[vec![0.0, 0.0]],
        &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Target);
    assert_eq!(budget.started(), 1);

    struct Panics;
    impl Target for Panics {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(&self, _: &[f64], _: &mut [f64]) -> Result<f64, TargetError> {
            panic!("intentional budgeted target panic")
        }
    }
    let panic_config = RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 5);
    let panic_exact = panic_config
        .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
        .unwrap();
    let panic_budget = TargetEvaluationBudget::new(NonZeroUsize::new(panic_exact).unwrap());
    let panic_error = sample_chains_with_target_budget(
        &Panics,
        &[vec![0.0]],
        &DiagonalMass::identity(NonZeroUsize::new(1).unwrap()),
        &panic_config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(panic_exact).unwrap()),
        &panic_budget,
    )
    .unwrap_err();
    assert_eq!(panic_error.kind(), ErrorKind::Panic);
    assert_eq!(panic_budget.started(), 1);
}

#[test]
fn inactive_budget_preserves_samples_diagnostics_and_telemetry_bit_for_bit() {
    let config = RunConfig::new(4, NonZeroUsize::new(12).unwrap(), 0xabc);
    let positions = vec![vec![0.25, -0.5], vec![-0.75, 0.125]];
    let mass = DiagonalMass::from_diagonal(vec![0.5, 2.0]).unwrap();
    let plain = sample_chains(
        &Gaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(2).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    let budgeted = sample_chains_with_target_budget(
        &Gaussian,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
    )
    .unwrap();
    for (left, right) in plain.chains().iter().zip(budgeted.chains()) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
        assert_eq!(
            right.metadata().target_evaluation_limit_provenance(),
            TargetEvaluationLimitProvenance::ExplicitBudgetedAdmission
        );
        assert_eq!(right.metadata().effective_max_target_evaluations(), exact);
    }
}

#[test]
fn proposal_observation_is_bounded_ordered_and_behavior_identical() {
    let starts = vec![vec![0.25, -0.5], vec![-0.75, 0.125]];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let config = RunConfig::new(2, NonZeroUsize::new(3).unwrap(), 991);
    let ordinary = sample_chains(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let observer = RecordingObserver::default();
    let observations =
        ProposalObservationControl::new(&observer, NonZeroUsize::new(10_000).unwrap(), 1);
    let control = RunControl::new().with_proposal_observations(&observations);
    let observed = sample_chains_with_control(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        &control,
    )
    .unwrap();
    for (a, b) in ordinary.chains().iter().zip(observed.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert_eq!(a.diagnostics(), b.diagnostics());
        assert_eq!(a.telemetry().total(), b.telemetry().total());
    }
    let events = observer.0.lock().unwrap();
    assert!(!events.is_empty());
    assert_eq!(observations.started(), events.len());
    assert!(
        events
            .iter()
            .all(|x| x.coordinates().len() == 1 && x.coordinates_truncated())
    );
    assert!(
        events
            .iter()
            .all(|x| x.outcome() == ProposalTargetOutcome::Finite)
    );
    assert!(
        events
            .windows(2)
            .all(|x| x[0].chain() < x[1].chain() || x[0].transition() <= x[1].transition())
    );
    assert!(events.iter().any(|x| x.is_discarded()) && events.iter().any(|x| !x.is_discarded()));
    assert!(events.iter().any(|x| x.phase() == ProposalPhase::Forward));
}

#[test]
fn proposal_observation_first_event_cap_and_parallel_chain_identity() {
    let observer = RecordingObserver::default();
    let observations = ProposalObservationControl::new(&observer, NonZeroUsize::new(1).unwrap(), 2);
    let control = RunControl::new().with_proposal_observations(&observations);
    let config = RunConfig::new(1, NonZeroUsize::new(2).unwrap(), 992);
    let starts = [vec![0.; 2], vec![1.; 2]];
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let plain = sample_chains(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .unwrap();
    let seen = sample_chains_with_control(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
        &control,
    )
    .unwrap();
    for (a, b) in plain.chains().iter().zip(seen.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert_eq!(a.diagnostics(), b.diagnostics());
        assert_eq!(a.telemetry().total(), b.telemetry().total())
    }
    let events = observer.0.lock().unwrap();
    assert_eq!(events.len(), 1);
    assert_eq!(events[0].target_call(), 1);
    assert_eq!(events[0].phase(), ProposalPhase::Initial);
    assert_eq!(events[0].phase_target_call(), 1);
}

#[test]
fn budgeted_dense_control_is_bit_identical_when_inactive() {
    let starts = vec![vec![0.25, -0.5], vec![-0.75, 0.125]];
    let mass = DenseMass::identity(NonZeroUsize::new(2).unwrap()).unwrap();
    let config = RunConfig::new(2, NonZeroUsize::new(3).unwrap(), 993);
    let ordinary = sample_chains_dense(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(2).unwrap())
        .unwrap();
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    let controlled = sample_chains_dense_with_target_budget_and_control(
        &Gaussian,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
        TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap()),
        &budget,
        &RunControl::new(),
    )
    .unwrap();
    for (left, right) in ordinary.chains().iter().zip(controlled.chains()) {
        assert_eq!(left.samples(), right.samples());
        assert_eq!(left.diagnostics(), right.diagnostics());
        assert_eq!(left.telemetry(), right.telemetry());
    }
}

#[test]
fn proposal_observation_classifies_recoverable_nonfinite() {
    struct Boundary;
    impl Target for Boundary {
        fn dimension(&self) -> usize {
            1
        }
        fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
            if q[0].abs() > 0.2 {
                return Err(TargetError::recoverable("outside"));
            }
            g[0] = -q[0];
            Ok(-0.5 * q[0] * q[0])
        }
    }
    let observer = RecordingObserver::default();
    let observations =
        ProposalObservationControl::new(&observer, NonZeroUsize::new(1000).unwrap(), 1);
    let control = RunControl::new().with_proposal_observations(&observations);
    let config = RunConfig::new(0, NonZeroUsize::new(2).unwrap(), 7);
    let _ = owalnuts::walnutpie::sample_with_control(
        &Boundary,
        &[0.],
        &DiagonalMass::identity(NonZeroUsize::new(1).unwrap()),
        &config,
        &control,
    )
    .unwrap();
    assert!(
        observer
            .0
            .lock()
            .unwrap()
            .iter()
            .any(|x| x.outcome() == ProposalTargetOutcome::Recoverable)
    );
}

#[test]
fn proposal_observer_panic_is_contained_without_partial_output() {
    struct Panics;
    impl ProposalObserver for Panics {
        fn observe(&self, _: &ProposalObservation) {
            panic!("observer")
        }
    }
    let observer = Panics;
    let observations = ProposalObservationControl::new(&observer, NonZeroUsize::new(2).unwrap(), 2);
    let control = RunControl::new().with_proposal_observations(&observations);
    let error = owalnuts::walnutpie::sample_with_control(
        &Gaussian,
        &[0.; 2],
        &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
        &RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 4),
        &control,
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Panic);
    assert_eq!(error.message(), "proposal observer panicked");
}

#[test]
fn proposal_observer_reentrancy_is_rejected_without_outer_corruption() {
    struct Reenter {
        control: OnceLock<&'static ProposalObservationControl<'static>>,
        entered: AtomicBool,
        nested: Mutex<Option<ErrorKind>>,
    }
    impl ProposalObserver for Reenter {
        fn observe(&self, _: &ProposalObservation) {
            if !self.entered.swap(true, Ordering::AcqRel) {
                let error = owalnuts::walnutpie::sample_with_control(
                    &Gaussian,
                    &[0.; 2],
                    &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
                    &RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 12),
                    &RunControl::new().with_proposal_observations(self.control.get().unwrap()),
                )
                .unwrap_err();
                *self.nested.lock().unwrap() = Some(error.kind());
            }
        }
    }
    let observer = Box::leak(Box::new(Reenter {
        control: OnceLock::new(),
        entered: AtomicBool::new(false),
        nested: Mutex::new(None),
    }));
    let observations = Box::leak(Box::new(ProposalObservationControl::new(
        observer,
        NonZeroUsize::new(100).unwrap(),
        2,
    )));
    assert!(observer.control.set(observations).is_ok());
    let outer = owalnuts::walnutpie::sample_with_control(
        &Gaussian,
        &[0.; 2],
        &DiagonalMass::identity(NonZeroUsize::new(2).unwrap()),
        &RunConfig::new(0, NonZeroUsize::new(1).unwrap(), 11),
        &RunControl::new().with_proposal_observations(observations),
    );
    assert!(outer.is_ok());
    assert_eq!(*observer.nested.lock().unwrap(), Some(ErrorKind::Panic));
}

#[test]
fn conservative_bound_overflow_fails_before_target_callbacks() {
    let config = RunConfig::new(usize::MAX, NonZeroUsize::new(1).unwrap(), 0);
    assert!(
        config
            .worst_case_target_evaluations(NonZeroUsize::new(1).unwrap())
            .is_err()
    );
}

// ── JMLR Appendix C paper adaptation ─────────────────────────────────────────

use owalnuts::walnutpie::{
    PAPER_ADAPTATION_REVISION, PAPER_STEP_RELATIVE_BOUND, PaperAdaptationConfig,
    PaperAdaptationOutcome, PaperRestartPolicy, PaperStepStatistic,
};

/// Ten-dimensional Neal funnel: `omega ~ N(0, 3^2)`, `x_i | omega ~ N(0, e^omega)`.
struct NealFunnel;

impl Target for NealFunnel {
    fn dimension(&self) -> usize {
        10
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let precision = (-omega).exp();
        let mut log_density = -omega * omega / 18.0;
        let mut omega_gradient = -omega / 9.0;
        for (x, slot) in position[1..].iter().zip(&mut gradient[1..]) {
            log_density -= 0.5 * x * x * precision + 0.5 * omega;
            omega_gradient += 0.5 * x * x * precision - 0.5;
            *slot = -x * precision;
        }
        gradient[0] = omega_gradient;
        Ok(log_density)
    }
}

fn paper_tuning(step: f64, max_error: f64, depth: usize, levels: usize) -> KernelTuning {
    KernelTuning::new(
        step,
        NonZeroUsize::new(depth).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(levels).unwrap(),
        max_error,
    )
    .unwrap()
}

#[test]
fn paper_adaptation_is_opt_in_frozen_before_retention_and_reported() {
    assert!(!PAPER_ADAPTATION_REVISION.is_empty());
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let discarded = 160;
    let warmup = WarmupConfig::default()
        .with_mass_adaptation(false)
        .with_telemetry_checkpoints((0..discarded).collect())
        .unwrap();
    let default_run = sample(
        &Gaussian,
        &[0.3, -0.2],
        &mass,
        &RunConfig::new(discarded, NonZeroUsize::new(30).unwrap(), 0x9a9e)
            .with_tuning(paper_tuning(0.1, 1.0, 4, 4))
            .with_warmup(warmup.clone()),
    )
    .unwrap();
    assert!(
        default_run
            .telemetry()
            .paper_adaptation_updates()
            .is_empty()
    );
    assert_eq!(default_run.metadata().tuning().max_error(), 1.0);

    let paper_run = sample(
        &Gaussian,
        &[0.3, -0.2],
        &mass,
        &RunConfig::new(discarded, NonZeroUsize::new(30).unwrap(), 0x9a9e)
            .with_tuning(paper_tuning(0.1, 1.0, 4, 4))
            .with_warmup(warmup.with_paper_adaptation(PaperAdaptationConfig::default())),
    )
    .unwrap();
    let updates = paper_run.telemetry().paper_adaptation_updates();
    assert!(!updates.is_empty());
    assert_eq!(
        updates
            .iter()
            .filter(|update| update.window_index().is_none())
            .count(),
        1,
        "exactly one initial-fast boundary update"
    );
    assert!(
        updates
            .windows(2)
            .all(|pair| pair[0].transition() < pair[1].transition())
    );
    assert!(
        updates
            .iter()
            .all(|update| update.transition() + 1 < discarded)
    );
    let installed: Vec<_> = updates
        .iter()
        .filter(|update| update.outcome() == PaperAdaptationOutcome::Installed)
        .collect();
    assert!(!installed.is_empty());
    for update in installed {
        assert!(update.max_error_after() <= 2.0);
        assert!(update.max_error_after() > 0.0);
        assert!(update.inflation_quantile().unwrap() >= 0.0);
        assert!(update.orbits() >= PaperAdaptationConfig::default().minimum_orbits());
        assert!(update.step_after().is_finite() && update.step_after() > 0.0);
    }
    for pair in updates.windows(2) {
        assert_eq!(pair[1].max_error_before(), pair[0].max_error_after());
    }
    let final_max_error = paper_run.metadata().tuning().max_error();
    assert_eq!(updates.last().unwrap().max_error_after(), final_max_error);
    let checkpoints = paper_run.telemetry().warmup_checkpoints();
    assert_eq!(checkpoints.len(), discarded);
    assert_eq!(
        checkpoints.last().unwrap().max_error_after(),
        final_max_error
    );
    assert!(
        checkpoints
            .iter()
            .filter_map(|checkpoint| checkpoint.unrefined_fraction())
            .all(|fraction| (0.0..=1.0).contains(&fraction))
    );
    assert_eq!(paper_run.metadata().initial_tuning().max_error(), 1.0);
    assert_eq!(
        paper_run.metadata().warmup().unwrap().paper_adaptation(),
        Some(&PaperAdaptationConfig::default())
    );
    assert_eq!(
        paper_run.telemetry().total().target_calls_total(),
        paper_run
            .diagnostics()
            .iter()
            .map(|diagnostic| diagnostic.target_evaluations())
            .sum::<usize>()
    );
}

#[test]
fn paper_adaptation_is_parallel_sequential_identical_and_preflights_without_callbacks() {
    struct Counted(AtomicUsize);
    impl Target for Counted {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(
            &self,
            position: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            self.0.fetch_add(1, Ordering::AcqRel);
            Gaussian.log_density_gradient(position, gradient)
        }
    }
    let target = Counted(AtomicUsize::new(0));
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let config = RunConfig::new(120, NonZeroUsize::new(10).unwrap(), 0xbeef)
        .with_tuning(paper_tuning(0.2, 1.0, 4, 4))
        .with_warmup(
            WarmupConfig::default().with_paper_adaptation(PaperAdaptationConfig::default()),
        );
    let positions = vec![vec![0.5, -0.5], vec![-0.25, 0.75], vec![0.0, 0.0]];
    let report = preflight_chains(&target, &positions, &mass, &config).unwrap();
    assert_eq!(target.0.load(Ordering::Acquire), 0);
    assert_eq!(report.chains(), 3);
    let sequential = sample_chains(
        &target,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let parallel = sample_chains(
        &target,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(3).unwrap(),
    )
    .unwrap();
    for (a, b) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert_eq!(a.diagnostics(), b.diagnostics());
        assert_eq!(a.telemetry(), b.telemetry());
        assert_eq!(a.metadata().tuning(), b.metadata().tuning());
        assert!(!a.telemetry().paper_adaptation_updates().is_empty());
    }
}

#[test]
fn paper_step_options_are_additive_and_continue_or_pool_as_configured() {
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    let limit = ResearchTargetEvaluationLimit::new(
        NonZeroUsize::new(RESEARCH_MAX_TARGET_EVALUATIONS).unwrap(),
    )
    .unwrap();
    let discarded = 400;
    let run = |paper: PaperAdaptationConfig| {
        let config = RunConfig::new(discarded, NonZeroUsize::new(10).unwrap(), 0x5eed_9001)
            .with_tuning(paper_tuning(0.1, 1.0, 8, 6))
            .with_research_target_evaluation_limit(limit)
            .with_warmup(
                WarmupConfig::default()
                    .with_mass_adaptation(false)
                    .with_telemetry_checkpoints((0..discarded).collect())
                    .unwrap()
                    .with_paper_adaptation(paper),
            );
        sample(&NealFunnel, &[0.0; 10], &mass, &config).unwrap()
    };

    // Explicit defaults are bit-identical to the implicit default, which
    // since `v3` continues one dual-averaging stream through every `delta`
    // installation: delta still installs, no restart is ever reported, and
    // the iteration counter grows monotonically.
    let implicit = run(PaperAdaptationConfig::default());
    let explicit = run(PaperAdaptationConfig::default()
        .with_step_statistic(PaperStepStatistic::PerTransition)
        .with_restart_policy(PaperRestartPolicy::ContinueThroughLocalErrorInstall));
    assert_eq!(implicit.samples(), explicit.samples());
    assert_eq!(implicit.telemetry(), explicit.telemetry());
    let updates = implicit.telemetry().paper_adaptation_updates();
    assert!(
        updates
            .iter()
            .filter(|update| update.outcome() == PaperAdaptationOutcome::Installed)
            .count()
            >= 2,
        "the funnel smoke must install delta repeatedly"
    );
    assert!(
        updates
            .iter()
            .all(|update| !update.dual_averaging_restarted())
    );
    let checkpoints = implicit.telemetry().warmup_checkpoints();
    for update in updates {
        // Per-transition statistic equals the checkpoint's unrefined fraction.
        assert_eq!(
            update.step_statistic(),
            checkpoints[update.transition()].unrefined_fraction()
        );
    }
    let iterations: Vec<usize> = checkpoints
        .iter()
        .map(|checkpoint| checkpoint.dual_averaging().unwrap().iteration())
        .collect();
    assert!(iterations.windows(2).all(|pair| pair[1] >= pair[0]));
    // Every transition with a statistic advanced the single dual-averaging
    // stream; statistic-free transitions advanced nothing.
    assert_eq!(
        *iterations.last().unwrap(),
        checkpoints
            .iter()
            .filter(|checkpoint| checkpoint.unrefined_fraction().is_some())
            .count()
    );
    assert!(*iterations.last().unwrap() > discarded / 2);

    // Restart policy: every installation restarts dual averaging, so the
    // iteration counter drops somewhere and the draws differ.
    let restarted = run(PaperAdaptationConfig::default()
        .with_restart_policy(PaperRestartPolicy::RestartOnLocalErrorInstall));
    let restarted_updates = restarted.telemetry().paper_adaptation_updates();
    assert!(
        restarted_updates
            .iter()
            .filter(|update| update.outcome() == PaperAdaptationOutcome::Installed)
            .count()
            >= 2
    );
    for update in restarted_updates {
        assert_eq!(
            update.dual_averaging_restarted(),
            update.outcome() == PaperAdaptationOutcome::Installed
        );
    }
    let restarted_iterations: Vec<usize> = restarted
        .telemetry()
        .warmup_checkpoints()
        .iter()
        .map(|checkpoint| checkpoint.dual_averaging().unwrap().iteration())
        .collect();
    assert!(
        restarted_iterations
            .windows(2)
            .any(|pair| pair[1] < pair[0])
    );
    assert_ne!(restarted.samples(), implicit.samples());

    // Cumulative statistic: the reported statistic is the running mean of the
    // checkpoint fractions since the initial-fast boundary.
    let pooled =
        run(PaperAdaptationConfig::default().with_step_statistic(PaperStepStatistic::Cumulative));
    let checkpoints = pooled.telemetry().warmup_checkpoints();
    let initial_fast_end = pooled
        .telemetry()
        .paper_adaptation_updates()
        .iter()
        .find(|update| update.window_index().is_none())
        .unwrap()
        .transition();
    for update in pooled
        .telemetry()
        .paper_adaptation_updates()
        .iter()
        .filter(|update| update.window_index().is_some())
    {
        let fractions: Vec<f64> = checkpoints[initial_fast_end + 1..=update.transition()]
            .iter()
            .filter_map(|checkpoint| checkpoint.unrefined_fraction())
            .collect();
        let mean = fractions.iter().sum::<f64>() / fractions.len() as f64;
        assert!((update.step_statistic().unwrap() - mean).abs() < 1e-12);
    }
    assert_ne!(pooled.samples(), implicit.samples());

    // Sequential/parallel identity holds with both options enabled.
    let both = PaperAdaptationConfig::default()
        .with_step_statistic(PaperStepStatistic::Cumulative)
        .with_restart_policy(PaperRestartPolicy::ContinueThroughLocalErrorInstall);
    let config = RunConfig::new(200, NonZeroUsize::new(10).unwrap(), 0x5eed_9002)
        .with_tuning(paper_tuning(0.1, 1.0, 8, 6))
        .with_research_target_evaluation_limit(limit)
        .with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_paper_adaptation(both),
        );
    let positions = vec![vec![0.0; 10], vec![1.0; 10]];
    let sequential = sample_chains(
        &NealFunnel,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(1).unwrap(),
    )
    .unwrap();
    let parallel = sample_chains(
        &NealFunnel,
        &positions,
        &mass,
        &config,
        NonZeroUsize::new(2).unwrap(),
    )
    .unwrap();
    for (a, b) in sequential.chains().iter().zip(parallel.chains()) {
        assert_eq!(a.samples(), b.samples());
        assert_eq!(a.telemetry(), b.telemetry());
        assert_eq!(
            a.metadata().warmup().unwrap().paper_adaptation(),
            Some(&both)
        );
    }
}

#[test]
fn paper_step_never_updates_from_transitions_without_built_leaves() {
    // Every proposed position is a recoverable failure, so no leaf is ever
    // built: the step must stay at its initial value instead of running to
    // the dual-averaging ceiling, and every transition is reported as
    // statistic-free.
    struct Wall;
    impl Target for Wall {
        fn dimension(&self) -> usize {
            2
        }
        fn log_density_gradient(
            &self,
            position: &[f64],
            gradient: &mut [f64],
        ) -> Result<f64, TargetError> {
            if position != [0.0, 0.0] {
                return Err(TargetError::recoverable("outside the representable region"));
            }
            gradient.fill(0.0);
            Ok(0.0)
        }
    }
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let discarded = 200;
    let config = RunConfig::new(discarded, NonZeroUsize::new(5).unwrap(), 0x5eed_9003)
        .with_tuning(paper_tuning(0.1, 1.0, 3, 3))
        .with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_paper_adaptation(PaperAdaptationConfig::default()),
        );
    let output = sample(&Wall, &[0.0, 0.0], &mass, &config).unwrap();
    // The averaged iterate of a never-updated stream is the initial step
    // (up to exp(ln(h)) roundoff).
    assert!((output.metadata().tuning().step_size() - 0.1).abs() < 1e-15);
    assert_eq!(output.telemetry().total().leaves_built(), 0);
    let updates = output.telemetry().paper_adaptation_updates();
    assert!(!updates.is_empty());
    let mut counted = 0;
    for update in updates {
        assert_eq!(update.step_statistic(), None);
        assert_eq!(update.unrefined_fraction_mean(), None);
        assert!((update.step_after() - 0.1).abs() < 1e-15);
        counted += update.transitions_without_statistic();
    }
    assert_eq!(counted, updates.last().unwrap().transition() + 1);
    assert!(
        output
            .telemetry()
            .warmup_checkpoints()
            .iter()
            .all(|checkpoint| checkpoint.unrefined_fraction().is_none())
    );

    // A permanently unrefined statistic is held at the relative bound rather
    // than the dual-averaging ceiling.
    let gaussian = sample(
        &Gaussian,
        &[0.0, 0.0],
        &mass,
        &RunConfig::new(3_000, NonZeroUsize::new(5).unwrap(), 0x5eed_9004)
            .with_tuning(paper_tuning(1.0e-3, 1.0e4, 2, 2))
            .with_warmup(
                WarmupConfig::default()
                    .with_mass_adaptation(false)
                    .with_paper_adaptation(
                        PaperAdaptationConfig::default().with_local_error_adaptation(false),
                    ),
            ),
    )
    .unwrap();
    let step = gaussian.metadata().tuning().step_size();
    assert!(step <= 1.0e-3 * PAPER_STEP_RELATIVE_BOUND + 1e-12);
    assert!(step > 1.0e-3);
}

#[test]
fn paper_adaptation_rules_hold_on_the_funnel() {
    // Conservative start: coarse local threshold and a small macro step.
    // Depth 10 with eight refinement levels exceeds the conservative
    // constructor bound; the research ceiling admits it without callbacks.
    let mass = DiagonalMass::identity(NonZeroUsize::new(10).unwrap());
    let paper = PaperAdaptationConfig::default();
    let config = RunConfig::new(600, NonZeroUsize::new(20).unwrap(), 0xf0_11e1)
        .with_tuning(paper_tuning(0.1, 1.0, 10, 8))
        .with_research_target_evaluation_limit(
            ResearchTargetEvaluationLimit::new(
                NonZeroUsize::new(RESEARCH_MAX_TARGET_EVALUATIONS).unwrap(),
            )
            .unwrap(),
        )
        .with_warmup(
            WarmupConfig::default()
                .with_mass_adaptation(false)
                .with_paper_adaptation(paper),
        );
    let initial = vec![0.0; 10];
    let output = sample(&NealFunnel, &initial, &mass, &config).unwrap();
    let tuning = output.metadata().tuning();
    let updates = output.telemetry().paper_adaptation_updates();
    assert!(updates.len() >= 3);
    for update in updates {
        assert_eq!(update.outcome(), PaperAdaptationOutcome::Installed);
        // Closed-form K-quantile rule at every installation.
        let inflation = update.energy_range_quantile().unwrap() / update.max_error_before();
        assert!((update.inflation_quantile().unwrap() - inflation).abs() < 1e-12);
        let expected = paper.global_energy_bound() / inflation.max(1.0);
        assert!((update.max_error_after() - expected).abs() < 1e-12);
        assert!(update.max_error_after() <= paper.global_energy_bound());
    }
    // The Gamma rule reaches its target once the first slow window completes.
    for update in updates
        .iter()
        .filter(|update| update.window_index().is_some())
    {
        let fraction = update.unrefined_fraction_mean().unwrap();
        assert!(
            (fraction - paper.unrefined_fraction_target()).abs() < 0.1,
            "window unrefined fraction {fraction} should track Gamma"
        );
    }
    assert!(tuning.max_error() > 0.0 && tuning.max_error() <= paper.global_energy_bound());
    assert!(
        tuning.step_size() > 0.1 && tuning.step_size() < 5.0,
        "step {} should grow from the conservative start",
        tuning.step_size()
    );
    assert_eq!(output.telemetry().retained().divergences(), 0);
    assert_eq!(
        output.telemetry().retained().refinement_exhaustion_stops(),
        0
    );
}
