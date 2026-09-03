//! Kernel efficiency harness: oWALNUTS kernel variants against a reference
//! NUTS at the same adapted step and metric (`STUDIES/kernel_efficiency_v1`).
//!
//! For every target and seed the study's warmup (`h0 = 0.1`, depth 10, four
//! refinement levels, `delta = 1`, dual averaging at 0.8, adapted
//! diagonal) runs once per chain; its final step, metric and last state are
//! then handed to every arm, which samples `draws` transitions per chain
//! with a fixed kernel. Arms are the oWALNUTS kernel under opt-in
//! [`KernelOptions`] and a compact clean-room NUTS (Stan's algorithm:
//! multinomial sampling within subtrees, biased progressive sampling across
//! doublings, the generalised no-U-turn criterion with the 2.21+ cross
//! checks, divergence at `H - H0 > 1000`).
//!
//! ```text
//! cargo run --release --example kernel_efficiency -- [--seeds N] [--draws N] [--warmup N] [--out DIR]
//! ```

use std::collections::BTreeMap;
use std::error::Error;
use std::num::NonZeroUsize;

use owalnuts::diagnostics::ess_bulk;
use owalnuts::walnutpie::{
    DiagonalMass, ExhaustionRule, KernelOptions, KernelTuning, RunConfig, StopReason, Target,
    TargetError, UTurnRule, WarmupConfig, sample_chains,
};
use rand::rngs::SmallRng;
use rand::{Rng, SeedableRng};
use rand_distr::StandardNormal;
use serde_json::{Value, json};

// ----------------------------------------------------------------------------
// Targets

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

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = -x;
            value += x * x;
        }
        Ok(-0.5 * value)
    }
}

/// `N(0, Sigma)` with `Sigma^-1 = R diag(lambda) R'`, `lambda` log-spaced
/// over `[1, condition]` and `R` a fixed random rotation, so no diagonal
/// metric can whiten it.
struct CorrelatedGaussian {
    dimension: usize,
    precision: Vec<f64>,
}

impl CorrelatedGaussian {
    fn new(dimension: usize, condition: f64, seed: u64) -> Self {
        let mut rng = SmallRng::seed_from_u64(seed);
        // Gram-Schmidt on a Gaussian matrix gives a Haar-distributed rotation.
        let mut basis: Vec<Vec<f64>> = Vec::with_capacity(dimension);
        for _ in 0..dimension {
            let mut v: Vec<f64> = (0..dimension)
                .map(|_| rng.sample::<f64, _>(StandardNormal))
                .collect();
            for b in &basis {
                let dot: f64 = v.iter().zip(b).map(|(x, y)| x * y).sum();
                for (x, y) in v.iter_mut().zip(b) {
                    *x -= dot * y;
                }
            }
            let norm = v.iter().map(|x| x * x).sum::<f64>().sqrt();
            v.iter_mut().for_each(|x| *x /= norm);
            basis.push(v);
        }
        let mut precision = vec![0.0; dimension * dimension];
        for (k, b) in basis.iter().enumerate() {
            let lambda = condition.powf(k as f64 / (dimension - 1) as f64);
            for i in 0..dimension {
                for j in 0..dimension {
                    precision[i * dimension + j] += lambda * b[i] * b[j];
                }
            }
        }
        Self {
            dimension,
            precision,
        }
    }
}

impl Target for CorrelatedGaussian {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let d = self.dimension;
        let mut value = 0.0;
        for i in 0..d {
            let row = &self.precision[i * d..(i + 1) * d];
            let pq: f64 = row.iter().zip(q).map(|(p, x)| p * x).sum();
            gradient[i] = -pq;
            value += q[i] * pq;
        }
        Ok(-0.5 * value)
    }
}

// ----------------------------------------------------------------------------
// Reference NUTS (Stan's base_nuts, 2.21+), diagonal metric: shared module.

#[path = "support/reference_nuts.rs"]
mod reference_nuts;
use reference_nuts::RefNuts;

// ----------------------------------------------------------------------------
// Arms

#[derive(Clone, Copy)]
enum Arm {
    Reference,
    Walnuts(WalnutsArm),
}

#[derive(Clone, Copy)]
struct WalnutsArm {
    levels: usize,
    max_error: f64,
    options: KernelOptions,
    cache: bool,
}

fn arms() -> Vec<(&'static str, Arm)> {
    let opt = |u_turn, exhaustion| KernelOptions { u_turn, exhaustion };
    let (e, x) = (UTurnRule::Endpoints, ExhaustionRule::Stop);
    let accept = ExhaustionRule::AcceptBelowDivergenceThreshold;
    let w = |levels, max_error, options, cache| {
        Arm::Walnuts(WalnutsArm {
            levels,
            max_error,
            options,
            cache,
        })
    };
    vec![
        ("nuts-ref", Arm::Reference),
        ("default", w(4, 1.0, opt(e, x), false)),
        ("default+cache", w(4, 1.0, opt(e, x), true)),
        ("delta1000", w(4, 1000.0, opt(e, x), false)),
        ("exhaust-accept", w(4, 1.0, opt(e, accept), false)),
        (
            "cross",
            w(4, 1.0, opt(UTurnRule::EndpointsWithCross, x), false),
        ),
        ("rhosum", w(4, 1.0, opt(UTurnRule::MomentumSum, x), false)),
        (
            "exhaust-accept+rhosum",
            w(4, 1.0, opt(UTurnRule::MomentumSum, accept), false),
        ),
        ("levels1-accept", w(1, 1.0, opt(e, accept), false)),
        (
            "levels1-accept+rhosum",
            w(1, 1.0, opt(UTurnRule::MomentumSum, accept), false),
        ),
        (
            "rhosum+cache",
            w(4, 1.0, opt(UTurnRule::MomentumSum, x), true),
        ),
        (
            "exhaust-accept+rhosum+cache",
            w(4, 1.0, opt(UTurnRule::MomentumSum, accept), true),
        ),
    ]
}

// ----------------------------------------------------------------------------
// Measurement

struct ChainRun {
    /// Draw-major samples.
    samples: Vec<f64>,
    gradients: usize,
    depth_sum: usize,
    leaves_sum: usize,
    stops: BTreeMap<&'static str, usize>,
    refined: usize,
    divergent: usize,
    transitions: usize,
    /// Initial-state evaluations (a re-evaluation of the current state at the
    /// start of a transition; zero in the reference NUTS).
    initial_evaluations: usize,
}

fn nz(v: usize) -> NonZeroUsize {
    NonZeroUsize::new(v).expect("nonzero")
}

struct Adapted {
    step: f64,
    mass: Vec<f64>,
    start: Vec<f64>,
}

fn warmup<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    warmup: usize,
    seed: u64,
) -> Result<Vec<Adapted>, Box<dyn Error>> {
    let tuning = KernelTuning::new(0.1, nz(10), nz(1), nz(4), 1.0)?;
    let config = RunConfig::new(warmup, nz(1), seed)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.8)?.with_mass_adaptation(true));
    let mass = DiagonalMass::identity(nz(target.dimension()));
    let output = sample_chains(target, starts, &mass, &config, nz(4))?;
    Ok(output
        .chains()
        .iter()
        .map(|chain| Adapted {
            step: chain.metadata().tuning().step_size(),
            mass: chain.metadata().mass_diagonal().to_vec(),
            start: chain.sample(0).expect("one retained draw").to_vec(),
        })
        .collect())
}

fn run_walnuts<T: Target>(
    target: &T,
    adapted: &Adapted,
    arm: WalnutsArm,
    draws: usize,
    seed: u64,
) -> Result<ChainRun, Box<dyn Error>> {
    let tuning = KernelTuning::new(adapted.step, nz(10), nz(1), nz(arm.levels), arm.max_error)?
        .with_options(arm.options);
    let config = RunConfig::new(0, nz(draws), seed)
        .with_tuning(tuning)
        .with_cached_initial_evaluation(arm.cache);
    let mass = DiagonalMass::from_diagonal(adapted.mass.clone())?;
    let output = sample_chains(
        target,
        std::slice::from_ref(&adapted.start),
        &mass,
        &config,
        nz(1),
    )?;
    let chain = &output.chains()[0];
    let mut run = ChainRun {
        samples: chain.samples().to_vec(),
        gradients: 0,
        depth_sum: 0,
        leaves_sum: 0,
        stops: BTreeMap::new(),
        refined: 0,
        divergent: 0,
        transitions: 0,
        initial_evaluations: chain.telemetry().retained().target_calls_initial(),
    };
    for d in chain.diagnostics() {
        run.transitions += 1;
        run.gradients += d.target_evaluations();
        run.depth_sum += d.depth();
        run.leaves_sum += d.leaves_built();
        run.refined += usize::from(d.selected_refinement_level().is_some_and(|l| l > 0));
        run.divergent += usize::from(d.divergent());
        let stop = match d.stop() {
            StopReason::MaximumDepth => "max_depth",
            StopReason::OuterUTurn => "outer_uturn",
            StopReason::RecursiveUTurn => "recursive_uturn",
            StopReason::RefinementExhausted => "refinement_exhausted",
            StopReason::ReverseCoarserAccepted => "reverse_coarser",
            StopReason::InvalidEvaluation => "invalid",
            _ => "other",
        };
        *run.stops.entry(stop).or_default() += 1;
    }
    Ok(run)
}

fn run_reference<T: Target>(target: &T, adapted: &Adapted, draws: usize, seed: u64) -> ChainRun {
    let mut nuts = RefNuts::new(
        target,
        adapted.step,
        adapted.mass.iter().map(|m| m.recip()).collect(),
        10,
    );
    let mut rng = SmallRng::seed_from_u64(seed);
    let d = target.dimension();
    let mut z = nuts.initial(adapted.start.clone());
    let mut run = ChainRun {
        samples: Vec::with_capacity(draws * d),
        gradients: 0,
        depth_sum: 0,
        leaves_sum: 0,
        stops: BTreeMap::new(),
        refined: 0,
        divergent: 0,
        transitions: 0,
        initial_evaluations: 0,
    };
    for _ in 0..draws {
        let (next, stats) = nuts.transition(&z, &mut rng);
        z = next;
        run.samples.extend_from_slice(&z.q);
        run.transitions += 1;
        run.gradients += stats.leapfrogs;
        run.depth_sum += stats.depth;
        run.leaves_sum += stats.leapfrogs;
        run.divergent += usize::from(stats.divergent);
        let stop = if stats.divergent {
            "divergent"
        } else if stats.max_depth {
            "max_depth"
        } else {
            "uturn"
        };
        *run.stops.entry(stop).or_default() += 1;
    }
    run
}

fn summarise(name: &str, runs: &[ChainRun], dimension: usize, draws: usize) -> Value {
    let per_coordinate = |f: &dyn Fn(f64) -> f64| -> f64 {
        (0..dimension)
            .map(|k| {
                let columns: Vec<Vec<f64>> = runs
                    .iter()
                    .map(|r| {
                        (0..draws)
                            .map(|i| f(r.samples[i * dimension + k]))
                            .collect()
                    })
                    .collect();
                let views: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
                ess_bulk(&views)
            })
            .fold(f64::INFINITY, f64::min)
    };
    let min_ess = per_coordinate(&|x| x);
    let min_ess_sq = per_coordinate(&|x| x * x);
    let gradients: usize = runs.iter().map(|r| r.gradients).sum();
    let transitions: usize = runs.iter().map(|r| r.transitions).sum();
    let mut stops: BTreeMap<&str, f64> = BTreeMap::new();
    for r in runs {
        for (k, v) in &r.stops {
            *stops.entry(k).or_default() += *v as f64 / transitions as f64;
        }
    }
    let leaves: usize = runs.iter().map(|r| r.leaves_sum).sum();
    json!({
        "arm": name,
        "min_bulk_ess": min_ess,
        "min_bulk_ess_squares": min_ess_sq,
        "gradients": gradients,
        "ess_per_gradient": min_ess / gradients as f64,
        "ess_sq_per_gradient": min_ess_sq / gradients as f64,
        "gradients_per_transition": gradients as f64 / transitions as f64,
        "leaves_per_transition": leaves as f64 / transitions as f64,
        "non_leaf_gradients_per_transition": (gradients - leaves) as f64 / transitions as f64,
        "initial_evaluations_per_transition": runs.iter().map(|r| r.initial_evaluations).sum::<usize>() as f64 / transitions as f64,
        "mean_depth": runs.iter().map(|r| r.depth_sum).sum::<usize>() as f64 / transitions as f64,
        "refined_fraction": runs.iter().map(|r| r.refined).sum::<usize>() as f64 / transitions as f64,
        "divergent": runs.iter().map(|r| r.divergent).sum::<usize>(),
        "stops": stops,
    })
}

fn run_target<T: Target>(
    name: &str,
    target: &T,
    starts: &[Vec<f64>],
    seeds: &[u64],
    warmup_transitions: usize,
    draws: usize,
) -> Result<Value, Box<dyn Error>> {
    let mut per_seed = Vec::new();
    for &seed in seeds {
        let adapted = warmup(target, starts, warmup_transitions, seed)?;
        let mut arm_results = Vec::new();
        let mut default_samples: Vec<Vec<f64>> = Vec::new();
        for (arm_name, arm) in arms() {
            let runs: Vec<ChainRun> = adapted
                .iter()
                .enumerate()
                .map(|(chain, a)| {
                    let chain_seed =
                        seed ^ (0x9e37_79b9_7f4a_7c15u64.wrapping_mul(chain as u64 + 1));
                    match arm {
                        Arm::Reference => Ok(run_reference(target, a, draws, chain_seed)),
                        Arm::Walnuts(walnuts) => run_walnuts(target, a, walnuts, draws, chain_seed),
                    }
                })
                .collect::<Result<_, Box<dyn Error>>>()?;
            let mut summary = summarise(arm_name, &runs, target.dimension(), draws);
            if arm_name == "default" {
                default_samples = runs.iter().map(|r| r.samples.clone()).collect();
            }
            if arm_name == "default+cache" {
                let identical = runs
                    .iter()
                    .zip(&default_samples)
                    .all(|(r, d)| r.samples == *d);
                summary["draws_identical_to_default"] = json!(identical);
                println!("{:>34} draws identical to default: {identical}", "");
            }
            println!(
                "{name:<14} seed {seed} {arm_name:<24} ESS/grad {:.5}  ESS² /grad {:.5}  grad/tr {:>6.1}  leaves/tr {:>6.1}  depth {:.2}  refined {:.3}  stops {}",
                summary["ess_per_gradient"].as_f64().unwrap(),
                summary["ess_sq_per_gradient"].as_f64().unwrap(),
                summary["gradients_per_transition"].as_f64().unwrap(),
                summary["leaves_per_transition"].as_f64().unwrap(),
                summary["mean_depth"].as_f64().unwrap(),
                summary["refined_fraction"].as_f64().unwrap(),
                summary["stops"],
            );
            println!(
                "{:>34} non-leaf grad/tr {:.3} (initial re-evaluations {:.3})",
                "",
                summary["non_leaf_gradients_per_transition"]
                    .as_f64()
                    .unwrap(),
                summary["initial_evaluations_per_transition"]
                    .as_f64()
                    .unwrap(),
            );
            arm_results.push(summary);
        }
        per_seed.push(json!({
            "seed": seed,
            "adapted": adapted.iter().map(|a| json!({"step": a.step, "mass": a.mass})).collect::<Vec<_>>(),
            "arms": arm_results,
        }));
    }
    Ok(json!({ "target": name, "dimension": target.dimension(), "seeds": per_seed }))
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut seeds = 3usize;
    let mut draws = 1000usize;
    let mut warmup_transitions = 1000usize;
    let mut out: Option<String> = None;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = args.next().ok_or("flag needs a value")?;
        match arg.as_str() {
            "--seeds" => seeds = value.parse()?,
            "--draws" => draws = value.parse()?,
            "--warmup" => warmup_transitions = value.parse()?,
            "--out" => out = Some(value),
            other => return Err(format!("unknown flag {other}").into()),
        }
    }
    let seeds: Vec<u64> = (0..seeds as u64).map(|k| 0x6b0b_0001 + k).collect();

    let mut results = Vec::new();
    {
        let starts: Vec<Vec<f64>> = [-2., -1., 0., 1.]
            .into_iter()
            .map(|log_tau| {
                let mut q = vec![0.0; 10];
                q[1] = log_tau;
                q
            })
            .collect();
        results.push(run_target(
            "eight-schools",
            &EightSchools,
            &starts,
            &seeds,
            warmup_transitions,
            draws,
        )?);
    }
    {
        let starts: Vec<Vec<f64>> = (0..4).map(|c| vec![0.5 * (c as f64 - 1.5); 100]).collect();
        results.push(run_target(
            "gaussian-100",
            &Gaussian(100),
            &starts,
            &seeds,
            warmup_transitions,
            draws,
        )?);
    }
    {
        let target = CorrelatedGaussian::new(50, 100.0, 0x00c0_ffee);
        let starts: Vec<Vec<f64>> = (0..4).map(|c| vec![0.5 * (c as f64 - 1.5); 50]).collect();
        results.push(run_target(
            "corr-gaussian-50",
            &target,
            &starts,
            &seeds,
            warmup_transitions,
            draws,
        )?);
    }
    if let Some(dir) = out {
        std::fs::create_dir_all(&dir)?;
        let path = format!("{dir}/kernel_efficiency.json");
        std::fs::write(
            &path,
            serde_json::to_string_pretty(&json!({
                "draws": draws, "warmup": warmup_transitions, "seeds": seeds, "targets": results,
            }))?,
        )?;
        println!("wrote {path}");
    }
    Ok(())
}
