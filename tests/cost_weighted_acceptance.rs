//! WP82 (`STUDIES/centered_eight_schools_refinement_v1`): the research-only
//! dual-averaging statistic `DualAveragingAcceptance::CostWeightedCoarseEndpoint`.
//!
//! * With one refinement level every leaf costs one evaluation, and the
//!   statistic must be bit-identical to the default `CurrentCoarseEndpoint`.
//! * On the centred eight schools, where leaves refine, it must differ and
//!   adapt a step no larger than the default's on most chains (refined leaves
//!   carry low coarse values and now count by their cost).
//! * Off by default: `WarmupConfig::new` still uses `CurrentCoarseEndpoint`.

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Posterior,
    Sampler, Target, TargetError, Tuning,
};
use owalnuts::walnutpie::{DualAveragingAcceptance, WarmupConfig};

/// The centred eight schools in unconstrained coordinates (mu, log tau, theta[8]).
struct CentredEightSchools;

const Y: [f64; 8] = [28.0, 8.0, -3.0, 7.0, -1.0, 1.0, 18.0, 12.0];
const SIGMA: [f64; 8] = [15.0, 10.0, 16.0, 11.0, 9.0, 11.0, 10.0, 18.0];

impl Target for CentredEightSchools {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, x: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let (mu, log_tau) = (x[0], x[1]);
        let tau = log_tau.exp();
        // mu ~ N(0, 5), tau ~ half-Cauchy(0, 5), Jacobian log tau.
        let mut lp = -0.5 * mu * mu / 25.0 - (1.0 + tau * tau / 25.0).ln() + log_tau;
        g[0] = -mu / 25.0;
        g[1] = -2.0 * tau * tau / 25.0 / (1.0 + tau * tau / 25.0) + 1.0;
        for j in 0..8 {
            let theta = x[2 + j];
            let z = (theta - mu) / tau;
            lp += -0.5 * z * z - log_tau;
            let r = (Y[j] - theta) / SIGMA[j];
            lp += -0.5 * r * r;
            g[0] += z / tau;
            g[1] += z * z - 1.0;
            g[2 + j] = -z / tau + r / SIGMA[j];
        }
        if !lp.is_finite() || g.iter().any(|v| !v.is_finite()) {
            // Overflow far in a tail: a recoverable failure, as BridgeStan reports it.
            return Err(TargetError::recoverable("nonfinite log density"));
        }
        Ok(lp)
    }
}

const SEED: u64 = 0x5eed_8200;
const DRAWS: usize = 200;

fn starts() -> Vec<Vec<f64>> {
    (0..4)
        .map(|c| {
            (0..10)
                .map(|i| 0.4 * (c as f64 - 1.5) + 0.05 * i as f64)
                .collect()
        })
        .collect()
}

fn warmup(statistic: DualAveragingAcceptance) -> Adaptation {
    Adaptation::Custom(
        WarmupConfig::new(0.8)
            .unwrap()
            .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
            .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
            .with_dual_averaging_acceptance(statistic),
    )
}

fn run(tuning: Tuning, statistic: DualAveragingAcceptance) -> Posterior {
    Sampler::new()
        .warmup(300)
        .draws(DRAWS)
        .chains(4)
        .seed(SEED)
        .threads(2)
        .limits(Limits::new().admit_worst_case())
        .tuning(tuning)
        .adaptation(warmup(statistic))
        .run(&CentredEightSchools, &starts())
        .unwrap()
}

fn draws(posterior: &Posterior) -> Vec<Vec<u64>> {
    posterior
        .chains()
        .iter()
        .map(|chain| {
            (0..DRAWS)
                .flat_map(|i| {
                    chain
                        .sample(i)
                        .unwrap()
                        .iter()
                        .map(|v| v.to_bits())
                        .collect::<Vec<_>>()
                })
                .collect()
        })
        .collect()
}

fn steps(posterior: &Posterior) -> Vec<f64> {
    posterior
        .chains()
        .iter()
        .map(|chain| chain.metadata().tuning().step_size())
        .collect()
}

#[test]
fn off_by_default() {
    assert_eq!(
        WarmupConfig::new(0.8).unwrap().dual_averaging_acceptance(),
        DualAveragingAcceptance::CurrentCoarseEndpoint
    );
}

#[test]
fn single_level_is_bit_identical_to_the_default_statistic() {
    let tuning = Tuning::default().max_refinement_levels(1);
    let a = run(
        tuning.clone(),
        DualAveragingAcceptance::CurrentCoarseEndpoint,
    );
    let b = run(tuning, DualAveragingAcceptance::CostWeightedCoarseEndpoint);
    assert_eq!(draws(&a), draws(&b));
    assert_eq!(steps(&a), steps(&b));
}

#[test]
fn refined_leaves_shrink_the_adapted_step() {
    let a = run(
        Tuning::default(),
        DualAveragingAcceptance::CurrentCoarseEndpoint,
    );
    let b = run(
        Tuning::default(),
        DualAveragingAcceptance::CostWeightedCoarseEndpoint,
    );
    assert_ne!(draws(&a), draws(&b));
    let (sa, sb) = (steps(&a), steps(&b));
    let smaller = sa.iter().zip(&sb).filter(|(a, b)| b < a).count();
    assert!(smaller >= 3, "default {sa:?} vs cost-weighted {sb:?}");
}
