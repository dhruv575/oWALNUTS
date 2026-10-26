//! WP74 synthetic two-mode cell (`STUDIES/chain_disagreement_splits_v1`):
//! the WP69 two-mode harness plus the observe-only `split_rules::evaluate`
//! record (only the `defaults` arm is run in WP74). WP69 header follows.
//! (`STUDIES/trapped_chain_restart_confirmation_v1`). Copied from the WP52
//! two-mode harness `STUDIES/init_rule_confirmation_v1/src/bin/two_mode.rs`
//! and parametrised; every change is listed in `PREREGISTRATION.md`.
//!
//! A d = 10 mixture `0.7 N(+4 e1, I) + 0.3 N(-4 e1, I)`: unit covariances,
//! means 8 standard deviations apart along the first coordinate, symmetric
//! about the centre of the uniform(-2, 2)^10 start box. A draw is "in the
//! major mode" iff `x1 > b = -ln(0.7 / 0.3) / 8`.
//!
//! Usage: `two_mode run <defaults|restart> <seed> <out.json>`: one cell, 4
//! chains x 1,000 warmup / 1,000 retained at the sampler defaults, starts
//! `Init::best_of(16)` (both arms). `restart` adds
//! `Adaptation::Custom(... .with_trapped_chain_restart(TrappedChainRestartConfig::step_rule()))`
//! to the configuration `Adaptation::default()` builds.
#![forbid(unsafe_code)]

#[path = "../split_rules.rs"]
mod split_rules;

use owalnuts::diagnostics::{Summary, ess_bulk};
use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Init, Limits, Metric,
    Sampler, Target, TargetError, Tuning, WarmupConfig, candidate_starts, uniform_starts,
};
use owalnuts::walnutpie::TrappedChainRestartConfig;
use serde_json::json;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 10;
const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const HALF_SEPARATION: f64 = 4.0;
const WEIGHT_MAJOR: f64 = 0.7;
const WEIGHT_MINOR: f64 = 0.3;

fn boundary() -> f64 {
    -(WEIGHT_MAJOR / WEIGHT_MINOR).ln() / (4.0 * HALF_SEPARATION)
}

struct TwoMode {
    calls: AtomicUsize,
}

impl TwoMode {
    fn new() -> Self {
        Self {
            calls: AtomicUsize::new(0),
        }
    }
    fn calls(&self) -> usize {
        self.calls.load(Ordering::Relaxed)
    }
}

impl Target for TwoMode {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let rest: f64 = position[1..].iter().map(|x| x * x).sum();
        let x1 = position[0];
        let a = WEIGHT_MAJOR.ln() - 0.5 * (x1 - HALF_SEPARATION).powi(2);
        let b = WEIGHT_MINOR.ln() - 0.5 * (x1 + HALF_SEPARATION).powi(2);
        let top = a.max(b);
        let log_mix = top + ((a - top).exp() + (b - top).exp()).ln();
        let r_major = (a - log_mix).exp();
        let r_minor = (b - log_mix).exp();
        gradient[0] = -(r_major * (x1 - HALF_SEPARATION) + r_minor * (x1 + HALF_SEPARATION));
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -x;
        }
        let value = log_mix - 0.5 * rest;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite two-mode evaluation"))
        }
    }
}

struct Starts {
    starts: Vec<Vec<f64>>,
    start_log_densities: Vec<f64>,
    candidate_log_densities: Vec<Vec<f64>>,
    chosen: Vec<usize>,
    rule: serde_json::Value,
}

fn draw_starts(target: &TwoMode, arm: &str, seed: u64) -> Result<Starts, Box<dyn Error>> {
    match arm {
        "uniform" => {
            let Init::Uniform {
                radius,
                max_attempts,
            } = Init::uniform()
            else {
                unreachable!("Init::uniform() is Init::Uniform")
            };
            let starts = uniform_starts(target, CHAINS, seed, radius, max_attempts)?;
            let mut gradient = vec![0.0; DIMENSION];
            let densities = starts
                .iter()
                .map(|s| target.log_density_gradient(s, &mut gradient))
                .collect::<Result<Vec<_>, _>>()
                .map_err(|e| format!("{e:?}"))?;
            Ok(Starts {
                starts,
                candidate_log_densities: densities.iter().map(|d| vec![*d]).collect(),
                start_log_densities: densities,
                chosen: vec![0; CHAINS],
                rule: json!({"rule": "sampler::Init::uniform()", "radius": radius,
                             "max_attempts": max_attempts, "candidates": 1}),
            })
        }
        "best_of_16" => {
            let Init::Candidates {
                radius,
                candidates,
                max_attempts,
                selection,
            } = Init::best_of(16)
            else {
                unreachable!("Init::best_of is Init::Candidates")
            };
            let report = candidate_starts(
                target,
                CHAINS,
                seed,
                radius,
                candidates,
                max_attempts,
                selection,
            )?;
            Ok(Starts {
                starts: report.starts,
                start_log_densities: report.start_log_densities,
                candidate_log_densities: report.candidate_log_densities,
                chosen: report.chosen,
                rule: json!({"rule": "sampler::Init::best_of(16)", "radius": radius,
                             "candidates": candidates, "max_attempts": max_attempts,
                             "selection": format!("{selection:?}")}),
            })
        }
        other => Err(format!("unknown arm {other:?} (expected uniform, best_of_16)").into()),
    }
}

struct Fnv(u64);
impl Fnv {
    fn new() -> Self {
        Self(0xcbf2_9ce4_8422_2325)
    }
    fn f64(&mut self, x: f64) {
        for b in x.to_bits().to_le_bytes() {
            self.0 ^= u64::from(b);
            self.0 = self.0.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
    fn hex(&self) -> String {
        format!("{:016x}", self.0)
    }
}

fn is_major(x1: f64) -> bool {
    x1 > boundary()
}

fn run(arm: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let target = TwoMode::new();
    let adaptation = match arm {
        "defaults" => Adaptation::default(),
        "restart" => Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_trapped_chain_restart(TrappedChainRestartConfig::step_rule()),
        ),
        other => return Err(format!("unknown arm {other:?} (expected defaults, restart)").into()),
    };
    let chosen = draw_starts(&target, "best_of_16", seed)?;
    let init_calls = target.calls();
    let measurement_calls = 0;
    let tuning = Tuning::default();
    let sampler = Sampler::new()
        .adaptation(adaptation)
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .metric(Metric::diagonal())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let begin = Instant::now();
    let posterior = sampler.run(&target, &chosen.starts)?;
    let wall = begin.elapsed().as_secs_f64();
    let summary = Summary::from_chains(posterior.chains(), None)?;
    let max_rhat = summary
        .parameters
        .iter()
        .map(|p| p.rhat)
        .fold(f64::NAN, f64::max);
    let min_bulk = summary
        .parameters
        .iter()
        .map(|p| p.ess_bulk)
        .fold(f64::NAN, f64::min);
    let mut chains_json = Vec::new();
    let mut x1_columns: Vec<Vec<f64>> = Vec::new();
    let mut major_total = 0usize;
    let mut all_hash = Fnv::new();
    for (index, chain) in posterior.chains().iter().enumerate() {
        let mut h = Fnv::new();
        for i in 0..chain.retained() {
            for &v in chain.sample(i).expect("draw") {
                h.f64(v);
                all_hash.f64(v);
            }
        }
        let checks: Vec<serde_json::Value> = chain
            .telemetry()
            .trapped_chain_checks()
            .iter()
            .map(|c| {
                json!({"step": c.step(), "median_step": c.median_step(), "threshold": c.threshold(),
                       "restarted": c.restarted(), "abandoned_target_calls": c.abandoned_target_calls(),
                       "replacement_start": c.replacement_start(),
                       "replacement_start_log_density": c.replacement_start_log_density()})
            })
            .collect();
        let x1: Vec<f64> = (0..chain.retained())
            .map(|i| chain.sample(i).expect("draw")[0])
            .collect();
        let in_major = x1.iter().filter(|&&v| is_major(v)).count();
        major_total += in_major;
        let crossings = x1
            .windows(2)
            .filter(|w| is_major(w[0]) != is_major(w[1]))
            .count();
        let fraction = in_major as f64 / x1.len() as f64;
        let start_x1 = chosen.starts[index][0];
        let retained = chain.telemetry().retained();
        chains_json.push(json!({
            "start_x1": start_x1,
            "start_mode": if is_major(start_x1) { "major" } else { "minor" },
            "start_log_density": chosen.start_log_densities[index],
            "first_retained_x1": x1[0],
            "retained_fraction_major": fraction,
            "end_mode": if fraction > 0.5 { "major" } else { "minor" },
            "retained_boundary_crossings": crossings,
            "x1_mean": x1.iter().sum::<f64>() / x1.len() as f64,
            "divergences": retained.divergences(),
            "final_step_size": chain.metadata().tuning().step_size(),
            "mass_diagonal": chain.metadata().mass_diagonal(),
            "draw_hash": h.hex(),
            "total_target_calls": chain.telemetry().total().target_calls_total(),
            "step_at_transition_99": chain.diagnostics().get(99).map(|d| d.step_size()),
            "trapped_chain_checks": checks,
        }));
        x1_columns.push(x1);
    }
    let gradients_total: usize = target.calls() - measurement_calls;
    let pooled = major_total as f64 / (CHAINS * RETAINED) as f64;
    let x1_refs: Vec<&[f64]> = x1_columns.iter().map(Vec::as_slice).collect();
    let payload = json!({
        "schema": "chain-disagreement-splits-v1-two-mode",
        "draw_hash": all_hash.hex(),
        "target": {"dimension": DIMENSION, "weights": [WEIGHT_MAJOR, WEIGHT_MINOR],
                   "major_mean_x1": HALF_SEPARATION, "minor_mean_x1": -HALF_SEPARATION,
                   "covariance": "identity", "boundary_x1": boundary(),
                   "exact_major_weight": WEIGHT_MAJOR},
        "arm": arm, "seed": seed,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "init": chosen.rule,
        "starts": chosen.starts,
        "start_log_densities": chosen.start_log_densities,
        "candidate_log_densities": chosen.candidate_log_densities,
        "chosen_candidate": chosen.chosen,
        "init_evaluations": init_calls - measurement_calls,
        "gradients_total": gradients_total,
        "max_split_rhat": max_rhat,
        "x1_split_rhat": summary.parameters[0].rhat,
        "rhat_per_coordinate": summary.parameters.iter().map(|p| p.rhat).collect::<Vec<_>>(),
        "min_bulk_ess": min_bulk,
        "x1_bulk_ess": ess_bulk(&x1_refs),
        "chain_disagreement": summary.chain_disagreement.as_ref().map(|d| json!({
            "max_rhat": d.max_rhat, "max_rhat_without": d.max_rhat_without, "chains": d.chains})),
        "chain_warnings": summary.chain_warnings.iter().map(|w| format!("{w:?}")).collect::<Vec<_>>(),
        "chain_warning_chains": summary.chain_warnings.iter().map(|w| w.chain()).collect::<Vec<_>>(),
        "chain_warnings_fired": !summary.chain_warnings.is_empty(),
        "pooled_fraction_major": pooled,
        "chains_starting_minor": chains_json.iter().filter(|c| c["start_mode"] == "minor").count(),
        "chains_ending_minor": chains_json.iter().filter(|c| c["end_mode"] == "minor").count(),
        "chains_data": chains_json,
        "split_rules": split_rules::evaluate(posterior.chains()),
        "wall_seconds": wall,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "two-mode {arm} seed {seed}: start minor {}, end minor {}, max split R-hat {max_rhat:.4}, \
         pooled major {pooled:.3}, warnings {}",
        payload["chains_starting_minor"], payload["chains_ending_minor"],
        summary.chain_warnings.len()
    );
    Ok(())
}

fn starts_only(arm: &str, first: u64, count: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let target = TwoMode::new();
    let mut histogram = [0usize; CHAINS + 1];
    let mut per_seed = Vec::new();
    for seed in first..first + count {
        let chosen = draw_starts(&target, arm, seed)?;
        let minor = chosen.starts.iter().filter(|s| !is_major(s[0])).count();
        histogram[minor] += 1;
        per_seed.push(minor);
    }
    let chains_minor: usize = per_seed.iter().sum();
    let payload = json!({
        "schema": "init-rule-confirmation-v1-two-mode-starts",
        "arm": arm, "first_seed": first, "count": count,
        "histogram_chains_starting_minor": histogram,
        "fraction_chains_starting_minor": chains_minor as f64 / (count as usize * CHAINS) as f64,
        "fraction_seeds_all_major": histogram[0] as f64 / count as f64,
        "fraction_seeds_all_minor": histogram[CHAINS] as f64 / count as f64,
        "fraction_seeds_single_mode": (histogram[0] + histogram[CHAINS]) as f64 / count as f64,
        "per_seed_chains_starting_minor": per_seed,
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!("two-mode starts {arm}: histogram {histogram:?}");
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [cmd, arm, seed, out] if cmd == "run" => match seed.parse::<u64>() {
            Ok(s) => run(arm, s, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        [cmd, arm, first, count, out] if cmd == "starts" => {
            match (first.parse::<u64>(), count.parse::<u64>()) {
                (Ok(f), Ok(c)) => starts_only(arm, f, c, Path::new(out)),
                _ => Err("first seed and count must be integers".into()),
            }
        }
        _ => Err("usage: run <defaults|restart> <seed> <out.json> | starts <arm> <first> <count> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
