//! Bit-exact fingerprints of complete multi-chain runs.
//!
//! These hashes were computed on the kernel before the hot-path
//! optimisation work and pin every retained draw of four chains on Neal's
//! funnel (paper tuning) and noncentered Eight Schools (adapted diagonal
//! warmup). Any change in floating-point operation order in the kernel
//! changes them.

use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, MultiChainOutput, RunConfig, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    sample_chains_with_target_budget,
};

const FUNNEL_DIMENSION: usize = 10;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const SCHOOL_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SCHOOL_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

struct EightSchools;

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        10
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.);
        gradient[0] = -mu / 25.;
        gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..8 {
            let theta = mu + tau * z[j];
            let residual = SCHOOL_Y[j] - theta;
            let likelihood_gradient = residual / SCHOOL_SE[j].powi(2);
            value += normal_log_density(SCHOOL_Y[j], theta, SCHOOL_SE[j])
                + normal_log_density(z[j], 0., 1.);
            gradient[0] += likelihood_gradient;
            gradient[1] += likelihood_gradient * tau * z[j];
            gradient[j + 2] = -z[j] + likelihood_gradient * tau;
        }
        if value.is_finite() && gradient.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite target evaluation"))
        }
    }
}

fn nz(value: usize) -> NonZeroUsize {
    NonZeroUsize::new(value).expect("nonzero")
}

fn fnv(hash: &mut u64, value: u64) {
    *hash ^= value;
    *hash = hash.wrapping_mul(0x100_0000_01b3);
}

/// FNV-1a over the bit patterns of every retained draw of every chain, then
/// over each chain's exact target-call total.
fn fingerprint(output: &MultiChainOutput) -> (u64, usize) {
    let mut hash = 0xcbf2_9ce4_8422_2325;
    let mut calls = 0;
    for chain in output.chains() {
        for value in chain.samples() {
            fnv(&mut hash, value.to_bits());
        }
        let chain_calls = chain.telemetry().total().target_calls_total();
        fnv(&mut hash, chain_calls as u64);
        calls += chain_calls;
    }
    (hash, calls)
}

#[test]
fn funnel_paper_tuning_four_chains_are_bit_exact() {
    let tuning = KernelTuning::new(0.36, nz(10), nz(1), nz(8), 0.21).unwrap();
    let config = RunConfig::new(0, nz(400), 0x5eed_f0f0).with_tuning(tuning);
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; FUNNEL_DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let worst = config.worst_case_target_evaluations(nz(4)).unwrap();
    let output = sample_chains_with_target_budget(
        &Funnel,
        &starts,
        &DiagonalMass::identity(nz(FUNNEL_DIMENSION)),
        &config,
        nz(1),
        TargetEvaluationAdmissionLimit::new(nz(worst)),
        &TargetEvaluationBudget::new(nz(worst)),
    )
    .unwrap();
    let (hash, calls) = fingerprint(&output);
    assert_eq!(
        (hash, calls),
        (FUNNEL_FINGERPRINT, FUNNEL_CALLS),
        "funnel fingerprint {hash:016x} with {calls} calls"
    );
}

#[test]
fn eight_schools_adapted_four_chains_are_bit_exact() {
    let tuning = KernelTuning::new(0.3, nz(8), nz(1), nz(8), 1.0)
        .unwrap()
        .with_divergence_threshold(1000.0)
        .unwrap();
    let warmup = WarmupConfig::new(0.95).unwrap().with_mass_adaptation(true);
    let config = RunConfig::new(300, nz(300), 0x5eed_0008)
        .with_tuning(tuning)
        .with_warmup(warmup);
    let starts: Vec<Vec<f64>> = [-2., -1., 0., 1.]
        .into_iter()
        .map(|log_tau| {
            let mut q = vec![0.0; 10];
            q[1] = log_tau;
            q
        })
        .collect();
    let worst = config.worst_case_target_evaluations(nz(4)).unwrap();
    let output = sample_chains_with_target_budget(
        &EightSchools,
        &starts,
        &DiagonalMass::identity(nz(10)),
        &config,
        nz(1),
        TargetEvaluationAdmissionLimit::new(nz(worst)),
        &TargetEvaluationBudget::new(nz(worst)),
    )
    .unwrap();
    let (hash, calls) = fingerprint(&output);
    assert_eq!(
        (hash, calls),
        (EIGHT_SCHOOLS_FINGERPRINT, EIGHT_SCHOOLS_CALLS),
        "eight schools fingerprint {hash:016x} with {calls} calls"
    );
}

// Baseline values (kernel before the hot-path work); see the module docs.
const FUNNEL_FINGERPRINT: u64 = 0x387f_e4f4_c00c_3a05;
const FUNNEL_CALLS: usize = 74_014;
// The adapted Eight Schools run differs between the debug and release
// profiles on the baseline kernel already (the warmup path is sensitive to
// profile-dependent floating-point lowering); both baselines are pinned.
const EIGHT_SCHOOLS_FINGERPRINT: u64 = if cfg!(debug_assertions) {
    0xcd59_b77f_fe72_c8b6
} else {
    0x5600_757f_2a08_6a12
};
const EIGHT_SCHOOLS_CALLS: usize = 38_464;
