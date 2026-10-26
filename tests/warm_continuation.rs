//! Warm continuation (`Sampler::run_warm`, `WarmState`): every chain must be
//! bit-identical to the single-chain run the WP84 harness
//! (`STUDIES/online_sv_quote_v1/rust/src/main.rs`, `warm_tick`) built from the
//! public API, and the state must round-trip through a `Posterior` and a
//! `SessionChunk`.

use std::num::NonZeroUsize;

use owalnuts::sampler::{
    Adaptation, ErrorKind, Limits, Metric, Posterior, Sampler, StructuredBlockMass,
    StructuredCovarianceBlock, Target, TargetError, Tuning, WarmChain, WarmState,
};
use owalnuts::walnutpie::{
    DiagonalMass, ResourceLimits, RunConfig, TargetEvaluationAdmissionLimit,
    TargetEvaluationBudget, preflight_chains_with_target_budget,
};

/// Independent Gaussian coordinates with scales `1, 2, 3, ...`, so the
/// adapted diagonal mass differs per coordinate and per chain.
struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for (i, (g, x)) in gradient.iter_mut().zip(q).enumerate() {
            let variance = (1 + i) as f64;
            *g = -x / variance;
            value -= 0.5 * x * x / variance;
        }
        Ok(value)
    }
}

const SEED: u64 = 0x5eed_0084;

fn starts(chains: usize, dimension: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|c| {
            (0..dimension)
                .map(|i| 0.3 * (c as f64 + 1.0) * if (c + i) % 2 == 0 { 1.0 } else { -1.0 })
                .collect()
        })
        .collect()
}

/// A completed adapted run whose state the warm path carries.
fn adapted(target: &Gaussian, chains: usize) -> Posterior {
    Sampler::new()
        .warmup(120)
        .draws(10)
        .seed(SEED)
        .threads(2)
        .tuning(Tuning::new().max_depth(5))
        .run(target, &starts(chains, target.dimension()))
        .unwrap()
}

/// The WP84 harness construction of one warm chain: a single-chain sampler
/// with the carried start, step and fixed diagonal mass, no warmup, no
/// adaptation, seed `seed + chain`.
fn harness_chain(
    target: &Gaussian,
    chain: &WarmChain,
    seed: u64,
    draws: usize,
    tuning: &Tuning,
) -> Posterior {
    Sampler::new()
        .warmup(0)
        .draws(draws)
        .seed(seed)
        .threads(1)
        .metric(Metric::fixed_diagonal(chain.mass_diagonal.clone()))
        .adaptation(Adaptation::None)
        .tuning(tuning.clone().step_size(chain.step_size))
        .limits(Limits::new().admit_worst_case())
        .run(target, &[chain.position.clone()])
        .unwrap()
}

fn assert_chains_identical(warm: &Posterior, oracle: &[Posterior]) {
    assert_eq!(warm.chain_count(), oracle.len());
    for (chain, (observed, expected)) in warm.chains().iter().zip(oracle).enumerate() {
        let expected = &expected.chains()[0];
        assert_eq!(
            observed.samples(),
            expected.samples(),
            "chain {chain} draws"
        );
        assert_eq!(
            observed.diagnostics(),
            expected.diagnostics(),
            "chain {chain} diagnostics"
        );
        assert_eq!(
            observed.metadata().effective_seed(),
            expected.metadata().effective_seed()
        );
        assert_eq!(
            observed.metadata().tuning().step_size(),
            expected.metadata().tuning().step_size()
        );
        assert_eq!(
            observed.metadata().mass_diagonal(),
            expected.metadata().mass_diagonal()
        );
    }
}

#[test]
fn posterior_warm_state_is_the_last_draw_final_step_and_mass() {
    let target = Gaussian(6);
    let posterior = adapted(&target, 4);
    let state = posterior.warm_state().unwrap();
    assert_eq!(state.dimension(), 6);
    assert_eq!(state.chain_count(), 4);
    for (chain, carried) in posterior.chains().iter().zip(state.chains()) {
        assert_eq!(
            carried.position,
            chain.sample(chain.retained() - 1).unwrap()
        );
        assert_eq!(carried.step_size, chain.metadata().tuning().step_size());
        assert_eq!(carried.mass_diagonal, chain.metadata().mass_diagonal());
    }
    // Adaptation made the chains' states differ.
    assert_ne!(state.chains()[0].step_size, state.chains()[1].step_size);
    assert_ne!(
        state.chains()[0].mass_diagonal,
        state.chains()[1].mass_diagonal
    );
}

#[test]
fn run_warm_is_bit_identical_to_the_harness_construction_per_chain() {
    let target = Gaussian(6);
    let state = adapted(&target, 4).warm_state().unwrap();
    let tuning = Tuning::new().max_depth(6);
    let draws = 50;
    let seed = 0xabcd;
    let oracle: Vec<Posterior> = state
        .chains()
        .iter()
        .enumerate()
        .map(|(c, chain)| harness_chain(&target, chain, seed + c as u64, draws, &tuning))
        .collect();
    for threads in [1, 4] {
        let warm = Sampler::new()
            .draws(draws)
            .seed(seed)
            .threads(threads)
            .tuning(tuning.clone())
            .run_warm(&target, &state)
            .unwrap();
        assert_chains_identical(&warm, &oracle);
        assert_eq!(warm.seed(), seed);
        assert_eq!(warm.draws_per_chain(), draws);
        for chain in warm.chains() {
            assert_eq!(chain.metadata().base_seed(), seed);
            assert_eq!(chain.metadata().thread_count(), threads);
            assert_eq!(chain.metadata().discarded(), 0);
        }
    }
    // The ignored settings (warmup, metric, adaptation) change nothing.
    let warm = Sampler::new()
        .warmup(1_000)
        .draws(draws)
        .seed(seed)
        .tuning(tuning.clone())
        .metric(Metric::dense())
        .adaptation(Adaptation::DualAveraging { target_accept: 0.9 })
        .run_warm(&target, &state)
        .unwrap();
    assert_chains_identical(&warm, &oracle);
}

#[test]
fn run_warm_with_one_chain_equals_run_with_the_same_seed() {
    let target = Gaussian(5);
    let state = adapted(&target, 1).warm_state().unwrap();
    let chain = &state.chains()[0];
    let warm = Sampler::new()
        .draws(40)
        .seed(SEED + 7)
        .run_warm(&target, &state)
        .unwrap();
    let plain = Sampler::new()
        .warmup(0)
        .draws(40)
        .seed(SEED + 7)
        .metric(Metric::fixed_diagonal(chain.mass_diagonal.clone()))
        .adaptation(Adaptation::None)
        .tuning(Tuning::new().step_size(chain.step_size))
        .run(&target, &[chain.position.clone()])
        .unwrap();
    assert_eq!(warm.chains()[0].samples(), plain.chains()[0].samples());
    assert_eq!(
        warm.chains()[0].diagnostics(),
        plain.chains()[0].diagnostics()
    );
    assert_eq!(warm.chains()[0].metadata(), plain.chains()[0].metadata());
}

#[test]
fn extended_state_runs_on_a_larger_target_and_chains_through_ticks() {
    let small = Gaussian(6);
    let large = Gaussian(8);
    let state = adapted(&small, 3).warm_state().unwrap();
    let grown = state.extend_to(8, 0.0, 1.0).unwrap();
    assert_eq!(grown.dimension(), 8);
    for (before, after) in state.chains().iter().zip(grown.chains()) {
        assert_eq!(&after.position[..6], &before.position[..]);
        assert_eq!(&after.position[6..], &[0.0, 0.0]);
        assert_eq!(&after.mass_diagonal[..6], &before.mass_diagonal[..]);
        assert_eq!(&after.mass_diagonal[6..], &[1.0, 1.0]);
        assert_eq!(after.step_size, before.step_size);
    }
    let tuning = Tuning::default();
    let warm = Sampler::new()
        .draws(30)
        .seed(SEED)
        .run_warm(&large, &grown)
        .unwrap();
    let oracle: Vec<Posterior> = grown
        .chains()
        .iter()
        .enumerate()
        .map(|(c, chain)| harness_chain(&large, chain, SEED + c as u64, 30, &tuning))
        .collect();
    assert_chains_identical(&warm, &oracle);

    // The next tick starts from the warm run's own state.
    let next = warm.warm_state().unwrap();
    for (chain, carried) in warm.chains().iter().zip(next.chains()) {
        assert_eq!(carried.position, chain.sample(29).unwrap());
    }
    assert_eq!(
        next.chains()
            .iter()
            .map(|c| c.step_size)
            .collect::<Vec<_>>(),
        grown
            .chains()
            .iter()
            .map(|c| c.step_size)
            .collect::<Vec<_>>()
    );
    let tick2 = Sampler::new()
        .draws(30)
        .seed(SEED + 1)
        .run_warm(&large, &next)
        .unwrap();
    let oracle2: Vec<Posterior> = next
        .chains()
        .iter()
        .enumerate()
        .map(|(c, chain)| harness_chain(&large, chain, SEED + 1 + c as u64, 30, &tuning))
        .collect();
    assert_chains_identical(&tick2, &oracle2);
}

#[test]
fn extend_with_fills_per_chain_and_coordinate_and_rejects_shrinking() {
    let state = WarmState::new(vec![
        WarmChain {
            position: vec![1.0, 2.0],
            step_size: 0.3,
            mass_diagonal: vec![1.5, 2.5],
        },
        WarmChain {
            position: vec![-1.0, -2.0],
            step_size: 0.4,
            mass_diagonal: vec![0.5, 0.25],
        },
    ])
    .unwrap();
    let grown = state
        .extend_with(4, |chain, coordinate| {
            (
                chain as f64 + coordinate as f64 / 10.0,
                10.0 + coordinate as f64,
            )
        })
        .unwrap();
    assert_eq!(grown.chains()[0].position, vec![1.0, 2.0, 0.2, 0.3]);
    assert_eq!(grown.chains()[1].position, vec![-1.0, -2.0, 1.2, 1.3]);
    assert_eq!(grown.chains()[0].mass_diagonal, vec![1.5, 2.5, 12.0, 13.0]);
    assert_eq!(grown.chains()[1].mass_diagonal, vec![0.5, 0.25, 12.0, 13.0]);
    assert_eq!(state.extend_to(2, 0.0, 1.0).unwrap(), state);
    let error = state.extend_to(1, 0.0, 1.0).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    // The fill is validated like any state.
    assert_eq!(
        state.extend_to(3, f64::NAN, 1.0).unwrap_err().kind(),
        ErrorKind::Configuration
    );
    assert_eq!(
        state.extend_to(3, 0.0, 0.0).unwrap_err().kind(),
        ErrorKind::Configuration
    );
    assert_eq!(grown.clone().into_chains().len(), 2);
}

#[test]
fn warm_state_rejects_malformed_chains() {
    let good = || WarmChain {
        position: vec![0.0, 1.0],
        step_size: 0.5,
        mass_diagonal: vec![1.0, 2.0],
    };
    let kind = |chains: Vec<WarmChain>| WarmState::new(chains).unwrap_err().kind();
    assert_eq!(kind(Vec::new()), ErrorKind::Configuration);
    assert_eq!(
        kind(vec![WarmChain {
            position: Vec::new(),
            step_size: 0.5,
            mass_diagonal: Vec::new(),
        }]),
        ErrorKind::Configuration
    );
    let mut short_mass = good();
    short_mass.mass_diagonal.pop();
    assert_eq!(kind(vec![short_mass]), ErrorKind::Configuration);
    let mut other_dimension = good();
    other_dimension.position.push(0.0);
    other_dimension.mass_diagonal.push(1.0);
    assert_eq!(
        kind(vec![good(), other_dimension]),
        ErrorKind::Configuration
    );
    let mut nonfinite = good();
    nonfinite.position[0] = f64::INFINITY;
    assert_eq!(kind(vec![nonfinite]), ErrorKind::Configuration);
    let mut zero_step = good();
    zero_step.step_size = 0.0;
    assert_eq!(kind(vec![zero_step]), ErrorKind::Configuration);
    let mut nan_step = good();
    nan_step.step_size = f64::NAN;
    assert_eq!(kind(vec![nan_step]), ErrorKind::Configuration);
    let mut negative_mass = good();
    negative_mass.mass_diagonal[1] = -1.0;
    assert_eq!(kind(vec![negative_mass]), ErrorKind::Configuration);
    assert!(WarmState::new(vec![good(), good()]).is_ok());
}

#[test]
fn run_warm_validates_dimension_chain_count_and_draws() {
    let target = Gaussian(4);
    let state = adapted(&target, 2).warm_state().unwrap();
    let error = Sampler::new()
        .draws(5)
        .run_warm(&Gaussian(5), &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(error.message().contains("dimension"), "{error}");
    let error = Sampler::new()
        .draws(5)
        .chains(3)
        .run_warm(&target, &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(error.message().contains("chain count"), "{error}");
    assert!(
        Sampler::new()
            .draws(5)
            .chains(2)
            .run_warm(&target, &state)
            .is_ok()
    );
    let error = Sampler::new()
        .draws(0)
        .run_warm(&target, &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    let error = Sampler::new()
        .draws(5)
        .threads(0)
        .run_warm(&target, &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
}

#[test]
fn run_warm_applies_the_run_limits_to_the_whole_run() {
    let target = Gaussian(4);
    let state = adapted(&target, 4).warm_state().unwrap();
    // A shared evaluation budget below what four chains need.
    let error = Sampler::new()
        .draws(200)
        .limits(Limits::new().max_target_evaluations(8))
        .run_warm(&target, &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit, "{error}");
    // The result-size ceiling covers every chain, before any target call.
    let error = Sampler::new()
        .draws(200)
        .limits(Limits::new().max_result_bytes_unchecked(NonZeroUsize::new(1).unwrap()))
        .run_warm(&target, &state)
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit);
    assert_eq!(error.message(), "result data exceeds its resource limit");
    // Conservative admission is honoured as in `run`.
    let state_big = state.clone();
    let conservative = Sampler::new()
        .draws(5)
        .limits(Limits::new().admit_conservative())
        .run_warm(&target, &state_big);
    let worst = Sampler::new()
        .warmup(0)
        .draws(5)
        .worst_case_target_evaluations(4)
        .unwrap();
    assert_eq!(
        conservative.is_ok(),
        worst <= owalnuts::walnutpie::CONSERVATIVE_MAX_TARGET_EVALUATIONS
    );
}

#[test]
fn warm_state_refuses_dense_and_structured_runs() {
    let target = Gaussian(10);
    let dense = Sampler::new()
        .warmup(60)
        .draws(4)
        .seed(SEED)
        .tuning(Tuning::new().max_depth(4))
        .metric(Metric::dense())
        .run(&target, &starts(2, 10))
        .unwrap();
    let error = dense.warm_state().unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(error.message().contains("dense"), "{error}");
    let fixed_dense = Sampler::new()
        .warmup(0)
        .draws(4)
        .seed(SEED)
        .tuning(Tuning::new().max_depth(4))
        .metric(Metric::fixed_dense(
            (0..100)
                .map(|i| if i % 11 == 0 { 1.0 } else { 0.0 })
                .collect(),
        ))
        .adaptation(Adaptation::None)
        .run(&target, &starts(2, 10))
        .unwrap();
    assert_eq!(
        fixed_dense.warm_state().unwrap_err().kind(),
        ErrorKind::Configuration
    );
    let structured = Sampler::new()
        .warmup(0)
        .draws(4)
        .seed(SEED)
        .tuning(Tuning::new().max_depth(4))
        .metric(Metric::Structured(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky {
                diagonal: (0..10).map(|i| 1.0 + 0.05 * i as f64).collect(),
                subdiagonal: vec![0.2; 9],
            }])
            .unwrap(),
        ))
        .adaptation(Adaptation::None)
        .run(&target, &starts(2, 10))
        .unwrap();
    let error = structured.warm_state().unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration);
    assert!(error.message().contains("structured"), "{error}");
    // Identity and fixed-diagonal runs carry.
    let identity = Sampler::new()
        .warmup(0)
        .draws(4)
        .metric(Metric::Identity)
        .adaptation(Adaptation::None)
        .run(&target, &starts(2, 10))
        .unwrap();
    let state = identity.warm_state().unwrap();
    assert!(
        state
            .chains()
            .iter()
            .all(|c| c.mass_diagonal == vec![1.0; 10])
    );
}

#[test]
fn session_chunk_warm_state_equals_the_posterior_warm_state() {
    let target = Gaussian(5);
    let settings = || {
        Sampler::new()
            .warmup(80)
            .draws(12)
            .seed(SEED)
            .threads(2)
            .tuning(Tuning::new().max_depth(5))
    };
    let full = settings().run(&target, &starts(3, 5)).unwrap();
    let session = settings()
        .start_session(Gaussian(5), &starts(3, 5))
        .unwrap();
    let warmup = session.adapt().unwrap();
    assert_eq!(
        warmup.warm_state().unwrap_err().kind(),
        ErrorKind::Configuration
    );
    let first = session.draw(5).unwrap();
    let second = session.draw(7).unwrap();
    session.close().unwrap();
    let from_chunk = second.warm_state().unwrap();
    assert_eq!(from_chunk, full.warm_state().unwrap());
    // An intermediate chunk carries its own last draw.
    let intermediate = first.warm_state().unwrap();
    for (chain, carried) in full.chains().iter().zip(intermediate.chains()) {
        assert_eq!(carried.position, chain.sample(4).unwrap());
    }
    // And the carried state continues like the posterior's.
    let a = Sampler::new()
        .draws(9)
        .seed(3)
        .run_warm(&target, &from_chunk)
        .unwrap();
    let b = Sampler::new()
        .draws(9)
        .seed(3)
        .run_warm(&target, &full.warm_state().unwrap())
        .unwrap();
    assert_eq!(a, b);
}

#[test]
fn max_result_bytes_unchecked_raises_the_ceiling_the_constructor_refuses() {
    let huge = NonZeroUsize::new(4 << 30).unwrap();
    let defaults = ResourceLimits::default();
    assert_eq!(defaults.max_result_bytes(), 512 * 1024 * 1024);
    assert!(
        ResourceLimits::new(
            NonZeroUsize::new(defaults.max_dimension()).unwrap(),
            NonZeroUsize::new(defaults.max_chains()).unwrap(),
            NonZeroUsize::new(defaults.max_total_transitions()).unwrap(),
            NonZeroUsize::new(defaults.max_target_evaluations()).unwrap(),
            huge,
            NonZeroUsize::new(defaults.max_working_bytes()).unwrap(),
        )
        .is_err()
    );
    let raised = defaults.clone().with_max_result_bytes_unchecked(huge);
    assert_eq!(raised.max_result_bytes(), 4 << 30);
    assert_eq!(raised.max_working_bytes(), defaults.max_working_bytes());
    assert_eq!(Limits::new().resource_limits(), defaults);
    assert_eq!(
        Limits::new()
            .max_result_bytes_unchecked(huge)
            .resource_limits(),
        raised
    );

    // The WP84 N = 1,000 reference shape: 4 chains x 22,000 draws x 1,004
    // coordinates (about 707 MB of draws) is refused at the default ceiling
    // and admitted at the raised one, in both cases before any target call.
    let target = Gaussian(1_004);
    let positions = vec![vec![0.0; 1_004]; 4];
    let mass = DiagonalMass::identity(NonZeroUsize::new(1_004).unwrap());
    let admit = |limits: ResourceLimits| {
        let config = RunConfig::new(0, NonZeroUsize::new(22_000).unwrap(), 1)
            .with_tuning(Tuning::default().to_kernel().unwrap())
            .with_limits(limits);
        let worst = config
            .worst_case_target_evaluations(NonZeroUsize::new(4).unwrap())
            .unwrap();
        let budget = TargetEvaluationBudget::new(NonZeroUsize::new(worst).unwrap());
        preflight_chains_with_target_budget(
            &target,
            &positions,
            &mass,
            &config,
            TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(worst).unwrap()),
            &budget,
        )
    };
    let error = admit(ResourceLimits::default()).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::ResourceLimit);
    assert_eq!(error.message(), "result data exceeds its resource limit");
    let report = admit(raised).unwrap();
    assert_eq!(report.chains(), 4);
    assert_eq!(report.total_transitions(), 88_000);

    // Through the sampler: a lowered ceiling reaches the run.
    let small = Gaussian(2);
    let error = Sampler::new()
        .warmup(0)
        .draws(3)
        .metric(Metric::Identity)
        .adaptation(Adaptation::None)
        .limits(Limits::new().max_result_bytes_unchecked(NonZeroUsize::new(16).unwrap()))
        .run(&small, &[vec![0.0, 0.0]])
        .unwrap_err();
    assert_eq!(error.message(), "result data exceeds its resource limit");
    assert!(
        Sampler::new()
            .warmup(0)
            .draws(3)
            .metric(Metric::Identity)
            .adaptation(Adaptation::None)
            .limits(Limits::new().max_result_bytes_unchecked(huge))
            .run(&small, &[vec![0.0, 0.0]])
            .is_ok()
    );
}
