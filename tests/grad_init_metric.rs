//! Research-only gradient-scaled initial metric
//! (`WarmupConfig::with_initial_metric(InitialMetric::GradientScaled { .. })`,
//! `STUDIES/grad_init_metric_v1`, WP94; nutpie's initial mass matrix, WP89):
//! off by default and bit-identical when unflagged, the exact per-chain
//! initial mass on a badly scaled Gaussian, the clamp bounds, determinism
//! across thread counts, one- and four-chain runs through the low-level and
//! the sampler facades, the admission bound and validation.
#![cfg(feature = "research")]

use std::num::NonZeroUsize;

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_TRAPPED_CHAIN_RESTART,
    DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler, WarmupConfig,
};
use owalnuts::walnutpie::{
    DenseMass, DiagonalMass, ErrorKind, InitialMetric, KernelTuning, MultiChainOutput, RunConfig,
    Target, TargetError, sample, sample_chains, sample_chains_dense,
};

/// Independent Gaussian with standard deviations `SCALES`.
struct Scaled;

const SCALES: [f64; 4] = [0.01, 0.3, 1.0, 50.0];

impl Target for Scaled {
    fn dimension(&self) -> usize {
        SCALES.len()
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for ((g, x), s) in gradient.iter_mut().zip(q).zip(SCALES) {
            *g = -x / (s * s);
            value -= 0.5 * (x / s) * (x / s);
        }
        Ok(value)
    }
}

fn nz(value: usize) -> NonZeroUsize {
    NonZeroUsize::new(value).unwrap()
}

fn warmup(initial: Option<InitialMetric>) -> WarmupConfig {
    let warmup = WarmupConfig::new(0.8).unwrap();
    match initial {
        Some(initial) => warmup.with_initial_metric(initial).unwrap(),
        None => warmup,
    }
}

fn config(initial: Option<InitialMetric>, discarded: usize, retained: usize) -> RunConfig {
    RunConfig::new(discarded, nz(retained), 0x94)
        .with_tuning(KernelTuning::new(0.5, nz(8), nz(1), nz(4), 1.0).unwrap())
        .with_warmup(warmup(initial))
}

fn starts(chains: usize) -> Vec<Vec<f64>> {
    (0..chains)
        .map(|chain| {
            SCALES
                .iter()
                .enumerate()
                .map(|(i, s)| s * (0.3 * chain as f64 - 0.4) * if i % 2 == 0 { 1.0 } else { -1.0 })
                .collect()
        })
        .collect()
}

/// nutpie's rule computed from the target itself, so the expectation is exact.
fn expected_mass(start: &[f64], lower: f64, upper: f64) -> Vec<f64> {
    let mut g = vec![0.0; start.len()];
    Scaled.log_density_gradient(start, &mut g).unwrap();
    g.iter()
        .map(|g| {
            let m = g.abs().clamp(lower, upper);
            if m.is_finite() { m } else { 1.0 }
        })
        .collect()
}

/// Per chain: FNV-1a over every retained draw's bits, and the chain's total target calls.
fn fingerprint(output: &MultiChainOutput, retained: usize) -> Vec<(u64, usize)> {
    output
        .chains()
        .iter()
        .map(|chain| {
            let mut hash = 0xcbf2_9ce4_8422_2325u64;
            for i in 0..retained {
                for &x in chain.sample(i).unwrap() {
                    for b in x.to_bits().to_le_bytes() {
                        hash ^= u64::from(b);
                        hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
                    }
                }
            }
            (hash, chain.telemetry().total().target_calls_total())
        })
        .collect()
}

const RETAINED: usize = 200;

#[test]
fn default_is_as_given_and_explicit_as_given_is_bit_identical() {
    assert_eq!(
        WarmupConfig::default().initial_metric(),
        InitialMetric::AsGiven
    );
    assert_eq!(InitialMetric::default(), InitialMetric::AsGiven);
    assert_eq!(
        InitialMetric::nutpie(),
        InitialMetric::GradientScaled {
            lower: 1e-20,
            upper: 1e20
        }
    );
    let mass = DiagonalMass::identity(nz(SCALES.len()));
    let starts = starts(4);
    for threads in [1, 4] {
        let plain = sample_chains(
            &Scaled,
            &starts,
            &mass,
            &config(None, 300, RETAINED),
            nz(threads),
        )
        .unwrap();
        let explicit = sample_chains(
            &Scaled,
            &starts,
            &mass,
            &config(Some(InitialMetric::AsGiven), 300, RETAINED),
            nz(threads),
        )
        .unwrap();
        assert_eq!(
            fingerprint(&plain, RETAINED),
            fingerprint(&explicit, RETAINED)
        );
        for chain in explicit.chains() {
            assert_eq!(chain.metadata().initial_mass_diagonal(), mass.diagonal());
        }
    }
    assert_eq!(
        config(None, 1000, 100)
            .worst_case_target_evaluations(nz(4))
            .unwrap(),
        config(Some(InitialMetric::AsGiven), 1000, 100)
            .worst_case_target_evaluations(nz(4))
            .unwrap()
    );
}

#[test]
fn gradient_scaled_initial_mass_is_the_clamped_absolute_start_gradient_per_chain() {
    let identity = DiagonalMass::identity(nz(SCALES.len()));
    let starts = starts(4);
    let mut runs = Vec::new();
    for threads in [1, 4] {
        let output = sample_chains(
            &Scaled,
            &starts,
            &identity,
            &config(Some(InitialMetric::nutpie()), 300, RETAINED),
            nz(threads),
        )
        .unwrap();
        assert_eq!(output.chains().len(), 4);
        for (chain, start) in output.chains().iter().zip(&starts) {
            let expected = expected_mass(start, 1e-20, 1e20);
            assert_eq!(
                chain.metadata().initial_mass_diagonal(),
                expected.as_slice()
            );
            // The scaled start metric is far from the identity on the badly scaled coordinates.
            assert!(expected[0] > 10.0 && expected[3] < 0.1, "{expected:?}");
            // Adaptation then moved on from it.
            assert_ne!(chain.metadata().mass_diagonal(), expected.as_slice());
        }
        runs.push(fingerprint(&output, RETAINED));
    }
    assert_eq!(runs[0], runs[1], "thread count must not change the draws");
    // The initial metric changes the draws (it is not a no-op).
    let plain = sample_chains(
        &Scaled,
        &starts,
        &identity,
        &config(None, 300, RETAINED),
        nz(1),
    )
    .unwrap();
    assert_ne!(fingerprint(&plain, RETAINED), runs[0]);
}

#[test]
fn single_chain_run_completes_and_the_clamp_bounds_apply() {
    // Coordinate 0 starts at the mode (zero gradient -> the lower bound); coordinate 1's
    // gradient magnitude 0.3 / 0.09 exceeds the upper bound 2.
    let start = vec![0.0, 0.3, 1.0, 50.0];
    let identity = DiagonalMass::identity(nz(SCALES.len()));
    let rule = InitialMetric::GradientScaled {
        lower: 1e-3,
        upper: 2.0,
    };
    let output = sample(
        &Scaled,
        &start,
        &identity,
        &config(Some(rule), 300, RETAINED),
    )
    .unwrap();
    let expected = expected_mass(&start, 1e-3, 2.0);
    assert_eq!(expected[0], 1e-3);
    assert_eq!(expected[1], 2.0);
    assert_eq!(expected[2], 1.0);
    assert_eq!(
        output.metadata().initial_mass_diagonal(),
        expected.as_slice()
    );
    assert!(output.sample(RETAINED - 1).is_some());
}

#[test]
fn sampler_facade_runs_one_and_four_chains_with_the_guard_default() {
    let custom = || {
        Adaptation::Custom(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_trapped_chain_restart(DEFAULT_TRAPPED_CHAIN_RESTART)
                .with_initial_metric(InitialMetric::nutpie())
                .unwrap(),
        )
    };
    for chains in [1, 4] {
        let starts = starts(chains);
        let posterior = Sampler::new()
            .warmup(300)
            .draws(RETAINED)
            .chains(chains)
            .seed(0x94)
            .threads(chains)
            .metric(Metric::diagonal())
            .adaptation(custom())
            .limits(Limits::new().admit_worst_case())
            .run(&Scaled, &starts)
            .unwrap();
        assert_eq!(posterior.chains().len(), chains);
        for (chain, start) in posterior.chains().iter().zip(&starts) {
            assert_eq!(
                chain.metadata().initial_mass_diagonal(),
                expected_mass(start, 1e-20, 1e20).as_slice()
            );
        }
    }
    // The identity metric does not adapt the mass: rejected.
    let error = Sampler::new()
        .warmup(300)
        .draws(RETAINED)
        .chains(4)
        .seed(0x94)
        .metric(Metric::Identity)
        .adaptation(custom())
        .run(&Scaled, &starts(4))
        .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration, "{error}");
}

#[test]
fn admission_bound_counts_one_evaluation_per_chain_start_and_per_possible_restart() {
    let plain = config(None, 1000, 100);
    let scaled = config(Some(InitialMetric::nutpie()), 1000, 100);
    assert_eq!(
        scaled.worst_case_target_evaluations(nz(4)).unwrap(),
        plain.worst_case_target_evaluations(nz(4)).unwrap() + 4
    );
    let guarded = |initial| {
        RunConfig::new(1000, nz(100), 0x94)
            .with_warmup(warmup(initial).with_trapped_chain_restart(DEFAULT_TRAPPED_CHAIN_RESTART))
    };
    assert_eq!(
        guarded(Some(InitialMetric::nutpie()))
            .worst_case_target_evaluations(nz(4))
            .unwrap(),
        guarded(None).worst_case_target_evaluations(nz(4)).unwrap() + 4 + 2
    );
}

#[test]
fn validation_and_facade_rejections() {
    for (lower, upper) in [
        (0.0, 1.0),
        (2.0, 1.0),
        (f64::NAN, 1.0),
        (1.0, f64::INFINITY),
        (-1.0, 1.0),
    ] {
        let error = WarmupConfig::new(0.8)
            .unwrap()
            .with_initial_metric(InitialMetric::GradientScaled { lower, upper })
            .unwrap_err();
        assert_eq!(error.kind(), ErrorKind::Configuration, "{lower} {upper}");
    }
    let identity = DiagonalMass::identity(nz(SCALES.len()));
    // Mass adaptation off.
    let fixed = RunConfig::new(300, nz(RETAINED), 0x94)
        .with_warmup(warmup(Some(InitialMetric::nutpie())).with_mass_adaptation(false));
    let error = sample_chains(&Scaled, &starts(4), &identity, &fixed, nz(1)).unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration, "{error}");
    // Dense facade.
    let dense = DenseMass::from_matrix(
        (0..SCALES.len() * SCALES.len())
            .map(|k| {
                if k % (SCALES.len() + 1) == 0 {
                    1.0
                } else {
                    0.0
                }
            })
            .collect(),
        SCALES.len(),
    )
    .unwrap();
    let error = sample_chains_dense(
        &Scaled,
        &starts(4),
        &dense,
        &config(Some(InitialMetric::nutpie()), 300, RETAINED),
        nz(1),
    )
    .unwrap_err();
    assert_eq!(error.kind(), ErrorKind::Configuration, "{error}");
}
