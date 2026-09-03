//! Neal's 10-D funnel tail-mass check under opt-in kernel options.
//!
//! Same protocol as `funnel_paper_adaptation` (Appendix C warmup, identity
//! metric, `h = 0.1`, `delta = 1`, eight refinement levels, depth 10, four
//! dispersed starts, 2,000 warmup and 20,000 retained draws per chain), with
//! the kernel options and the initial-evaluation cache selected on the
//! command line, so the funnel bias result of `STUDIES/paper_funnel_adaptive_v2`
//! can be re-checked for every candidate default
//! (`STUDIES/kernel_efficiency_v1`).
//!
//! ```text
//! cargo run --release --example funnel_kernel_options -- [--uturn endpoints|cross|rhosum] [--exhaustion stop|accept] [--cache] [--draws N] [--warmup N] [--seed N] [--sampler-defaults]
//! ```
//!
//! `--sampler-defaults` replaces the paper protocol by the sampler's own
//! defaults (adaptive diagonal metric, dual averaging at 0.8, `Tuning::default()`
//! with the given kernel options), so a candidate can be checked at both
//! tunings (`STUDIES/kernel_gap_v1`).

use std::error::Error;

use owalnuts::sampler::{
    Adaptation, Limits, Metric, PaperAdaptationConfig, Sampler, Target, TargetError, Tuning,
};
use owalnuts::walnutpie::{ExhaustionRule, KernelOptions, UTurnRule};

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
    let mut options = KernelOptions::default();
    let mut cache = false;
    let mut draws = 20_000usize;
    let mut warmup = 2_000usize;
    let mut seed = 0x0f0f_2026u64;
    let mut sampler_defaults = false;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--cache" => cache = true,
            "--uturn" => {
                options.u_turn = match args.next().as_deref() {
                    Some("endpoints") => UTurnRule::Endpoints,
                    Some("cross") => UTurnRule::EndpointsWithCross,
                    Some("rhosum") => UTurnRule::MomentumSum,
                    other => return Err(format!("unknown --uturn {other:?}").into()),
                }
            }
            "--exhaustion" => {
                options.exhaustion = match args.next().as_deref() {
                    Some("stop") => ExhaustionRule::Stop,
                    Some("accept") => ExhaustionRule::AcceptBelowDivergenceThreshold,
                    other => return Err(format!("unknown --exhaustion {other:?}").into()),
                }
            }
            "--draws" => draws = args.next().ok_or("--draws needs a value")?.parse()?,
            "--warmup" => warmup = args.next().ok_or("--warmup needs a value")?.parse()?,
            "--seed" => seed = args.next().ok_or("--seed needs a value")?.parse()?,
            "--sampler-defaults" => sampler_defaults = true,
            other => return Err(format!("unknown flag {other}").into()),
        }
    }

    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .seed(seed)
        .cache_initial_evaluation(cache)
        .limits(Limits::new().admit_worst_case());
    let sampler = if sampler_defaults {
        sampler.tuning(Tuning::default().kernel_options(options))
    } else {
        sampler
            .metric(Metric::Identity)
            .adaptation(Adaptation::Paper(PaperAdaptationConfig::default()))
            .tuning(
                Tuning::new()
                    .step_size(0.1)
                    .max_depth(10)
                    .max_refinement_levels(8)
                    .max_error(1.0)
                    .kernel_options(options),
            )
    };
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let posterior = sampler.run(&Funnel, &starts)?;

    let mut below = 0usize;
    let mut total = 0usize;
    let mut calls = 0usize;
    const BATCH: usize = 500;
    let mut batch_means: Vec<f64> = Vec::new();
    for (index, chain) in posterior.chains().iter().enumerate() {
        let tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        calls += work.target_calls_total();
        println!(
            "chain {index}: final delta={:.3} h={:.3}; target calls={}, depth caps={}, divergences={}",
            tuning.max_error(),
            tuning.step_size(),
            work.target_calls_total(),
            work.maximum_depth_stops(),
            work.divergences(),
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
        "options {options:?} cache {cache} seed {seed} sampler-defaults {sampler_defaults}: P(omega < -5) estimate {estimate:.4} vs exact {EXACT_TAIL_MASS:.4} \
         (batch-means s.e. {standard_error:.4}, z = {:+.2}, {total} draws, {calls} target calls)",
        (estimate - EXACT_TAIL_MASS) / standard_error,
    );
    Ok(())
}
