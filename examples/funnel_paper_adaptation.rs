//! Neal's 10-D funnel with the JMLR Appendix C warmup (`PaperAdaptationConfig`).
//!
//! The funnel is the paper's headline target: `omega ~ Normal(0, 3)` and
//! `x_i | omega ~ Normal(0, exp(omega))` for nine `x_i`. Its `omega` marginal is
//! known exactly, so `P(omega < -5) = 0.0478` is a direct bias check. Starting
//! from a conservative `delta = 1`, `h = 0.1`, paper adaptation moves both
//! toward the funnel's own scale and the retained draws reproduce the exact
//! tail mass within Monte-Carlo error (see
//! `STUDIES/paper_funnel_adaptive_v2`, ledger entry
//! `WP9-PAPER-H-RULE-STABILISATION-V2`).
//!
//! Deep refinement with deep trees exceeds the conservative admission ceiling,
//! so the run is admitted through `sample_chains_with_target_budget` with the
//! exact worst-case target-evaluation count as its limit.

use std::error::Error;
use std::num::NonZeroUsize;

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, PaperAdaptationConfig, RunConfig, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    sample_chains_with_target_budget,
};

const DIMENSION: usize = 10;
/// Exact `P(omega < -5)` for `omega ~ Normal(0, 3)`.
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            // Far below the neck the density is numerically zero; the kernel
            // refines through this region exactly as the upstream reference.
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let nz = |value: usize| NonZeroUsize::new(value).expect("nonzero");

    // Conservative fixed kernel that the paper rules will tune: delta = 1.0,
    // h = 0.1, up to eight refinement levels, trees up to depth ten.
    let tuning = KernelTuning::new(0.1, nz(10), nz(1), nz(8), 1.0)?;
    let warmup = WarmupConfig::default()
        .with_mass_adaptation(false)
        .with_paper_adaptation(PaperAdaptationConfig::default());
    let discarded = 2_000;
    let retained = 20_000;
    let config = RunConfig::new(discarded, nz(retained), 0x0f0f_2026)
        .with_tuning(tuning)
        .with_warmup(warmup);

    // Four dispersed starts along the funnel axis.
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let chains = nz(starts.len());
    let mass = DiagonalMass::identity(nz(DIMENSION));

    let worst_case = config.worst_case_target_evaluations(chains)?;
    let budget = TargetEvaluationBudget::new(nz(worst_case));
    let output = sample_chains_with_target_budget(
        &Funnel,
        &starts,
        &mass,
        &config,
        chains,
        TargetEvaluationAdmissionLimit::new(nz(worst_case)),
        &budget,
    )?;

    let mut below = 0usize;
    let mut total = 0usize;
    // Batch means over blocks of retained draws give an autocorrelation-aware
    // standard error for the tail-mass estimate.
    const BATCH: usize = 500;
    let mut batch_means: Vec<f64> = Vec::new();
    for (index, chain) in output.chains().iter().enumerate() {
        let tuning = chain.metadata().tuning();
        let updates = chain.telemetry().paper_adaptation_updates();
        let work = chain.telemetry().total();
        println!(
            "chain {index}: final delta={:.3} h={:.3} after {} paper updates; target calls={}, depth caps={}",
            tuning.max_error(),
            tuning.step_size(),
            updates.len(),
            work.target_calls_total(),
            work.maximum_depth_stops(),
        );
        let mut in_batch = 0usize;
        for draw in 0..chain.retained() {
            let omega = chain.sample(draw).expect("draw")[0];
            total += 1;
            if omega < -5.0 {
                below += 1;
                in_batch += 1;
            }
            if (draw + 1) % BATCH == 0 {
                batch_means.push(in_batch as f64 / BATCH as f64);
                in_batch = 0;
            }
        }
    }
    let estimate = below as f64 / total as f64;
    let batches = batch_means.len() as f64;
    let batch_variance = batch_means
        .iter()
        .map(|mean: &f64| (mean - estimate) * (mean - estimate))
        .sum::<f64>()
        / (batches - 1.0);
    let standard_error = (batch_variance / batches).sqrt();
    println!(
        "P(omega < -5): estimate {estimate:.4} vs exact {EXACT_TAIL_MASS:.4} \
         (batch-means s.e. {standard_error:.4}, z = {:+.2}, {total} draws; revision {})",
        (estimate - EXACT_TAIL_MASS) / standard_error,
        output.chains()[0].metadata().algorithm_revision(),
    );
    Ok(())
}
