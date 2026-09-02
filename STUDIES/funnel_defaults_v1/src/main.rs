//! `STUDIES/funnel_defaults_v1` driver.
//!
//! Usage:
//!
//! ```text
//! funnel-defaults-v1 cell <target> <arm> <seed> <out.json> [warmup] [draws]
//! funnel-defaults-v1 summarize <cells-dir> <summary.json> <table.md>
//! ```
//!
//! Targets: `funnel` (Neal's 10-D funnel, `omega ~ N(0, 9)`, `x_i | omega ~
//! N(0, e^omega)`, fixed starts `omega in {-3, -1, 1, 3}`), `eight` (the
//! noncentered Eight Schools of the strict track, `mu, log tau, z[8]`, starts
//! `log tau in {-2, -1, 0, 1}`), `gauss100` (100-D standard Gaussian,
//! uniform(-2, 2) starts). Every cell runs `Sampler` at its defaults (adapted
//! diagonal metric, dual averaging 0.8, `h0 = 0.5`, depth 10, `delta = 1`,
//! four refinement levels, cached initial evaluation, worst-case admission)
//! plus the arm's override; 4 chains on 4 threads.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, mcse_mean, rhat};
use owalnuts::sampler::{
    Adaptation, Init, PaperAdaptationConfig, Posterior, Sampler, Target, TargetError, Tuning,
    WarmupConfig,
};
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::{env, error::Error, fs, path::Path, time::Instant};

const FUNNEL_DIMENSION: usize = 10;
/// Exact `P(omega < -5)` for `omega ~ Normal(0, 3)`.
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const EXACT_OMEGA_VARIANCE: f64 = 9.0;
const CHAINS: usize = 4;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let omega = q[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = q[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&q[1..]) {
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

/// Noncentered Eight Schools as in `STUDIES/eight_schools_v9_rebench_v1`.
struct EightSchoolsNoncentered;

impl Target for EightSchoolsNoncentered {
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
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite target evaluation"))
        }
    }
}

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        for (g, x) in gradient.iter_mut().zip(q) {
            *g = -*x;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}

/// The preregistered arms: each is `Tuning::default()` / `Adaptation::default()`
/// plus the listed override.
pub const ARMS: [&str; 9] = [
    "defaults",
    "levels8",
    "delta0.5",
    "delta0.25",
    "levels8+delta0.5",
    "paper-4",
    "paper-8",
    "stan-style",
    "nuts-1",
];

fn arm(name: &str) -> Result<(Tuning, Adaptation), Box<dyn Error>> {
    let tuning = Tuning::default();
    let adaptation = Adaptation::default();
    Ok(match name {
        "defaults" => (tuning, adaptation),
        "levels8" => (tuning.max_refinement_levels(8), adaptation),
        "delta0.5" => (tuning.max_error(0.5), adaptation),
        "delta0.25" => (tuning.max_error(0.25), adaptation),
        "levels8+delta0.5" => (tuning.max_refinement_levels(8).max_error(0.5), adaptation),
        "paper-4" => (tuning, Adaptation::Paper(PaperAdaptationConfig::default())),
        "paper-8" => (
            tuning.max_refinement_levels(8),
            Adaptation::Paper(PaperAdaptationConfig::default()),
        ),
        "stan-style" => (tuning, Adaptation::Custom(WarmupConfig::stan_style(0.8)?)),
        "nuts-1" => (tuning.max_refinement_levels(1), adaptation),
        other => return Err(format!("unknown arm {other:?}").into()),
    })
}

fn columns(posterior: &Posterior, k: usize) -> Vec<Vec<f64>> {
    let dimension = posterior.dimension();
    (0..posterior.chain_count())
        .map(|c| {
            posterior
                .chain_draws(c)
                .expect("chain")
                .chunks(dimension)
                .map(|row| row[k])
                .collect()
        })
        .collect()
}

fn views(columns: &[Vec<f64>]) -> Vec<&[f64]> {
    columns.iter().map(Vec::as_slice).collect()
}

fn coordinate_summary(posterior: &Posterior, k: usize) -> (f64, f64, f64) {
    let cols = columns(posterior, k);
    let refs = views(&cols);
    (ess_bulk(&refs), ess_tail(&refs), rhat(&refs))
}

fn run_cell(
    which: &str,
    name: &str,
    seed: u64,
    warmup: usize,
    draws: usize,
    out: &Path,
) -> Result<(), Box<dyn Error>> {
    let (tuning, adaptation) = arm(name)?;
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(CHAINS)
        .seed(seed)
        .threads(CHAINS)
        .adaptation(adaptation)
        .tuning(tuning);
    let start = Instant::now();
    let posterior = match which {
        "funnel" => {
            let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
                .iter()
                .map(|omega| {
                    let mut q = vec![0.0; FUNNEL_DIMENSION];
                    q[0] = *omega;
                    q
                })
                .collect();
            sampler.run(&Funnel, &starts)?
        }
        "eight" => {
            let starts: Vec<Vec<f64>> = [-2.0, -1.0, 0.0, 1.0]
                .iter()
                .map(|log_tau| {
                    let mut q = vec![0.0; 10];
                    q[1] = *log_tau;
                    q
                })
                .collect();
            sampler.run(&EightSchoolsNoncentered, &starts)?
        }
        "gauss100" => sampler.run_with_init(&Gaussian(100), &Init::uniform())?,
        other => return Err(format!("unknown target {other:?}").into()),
    };
    let wall = start.elapsed().as_secs_f64();
    let dimension = posterior.dimension();

    let mut retained_calls = 0usize;
    let mut warmup_calls = 0usize;
    let mut divergences = 0usize;
    let mut exhaustions = 0usize;
    let mut depth_caps = 0usize;
    let mut invalid = 0usize;
    let mut warmup_exhaustions = 0usize;
    for chain in posterior.chains() {
        let r = chain.telemetry().retained();
        let d = chain.telemetry().discarded();
        retained_calls += r.target_calls_total();
        warmup_calls += d.target_calls_total();
        divergences += r.divergences();
        exhaustions += r.refinement_exhaustion_stops();
        depth_caps += r.maximum_depth_stops();
        invalid += r.invalid_evaluation_stops();
        warmup_exhaustions += d.refinement_exhaustion_stops();
    }
    let final_step: Vec<f64> = posterior
        .chains()
        .iter()
        .map(|c| c.metadata().tuning().step_size())
        .collect();
    let final_delta: Vec<f64> = posterior
        .chains()
        .iter()
        .map(|c| c.metadata().tuning().max_error())
        .collect();

    let mut bulk = Vec::with_capacity(dimension);
    let mut tail = Vec::with_capacity(dimension);
    let mut rhats = Vec::with_capacity(dimension);
    for k in 0..dimension {
        let (b, t, r) = coordinate_summary(&posterior, k);
        bulk.push(b);
        tail.push(t);
        rhats.push(r);
    }
    let fmin = |v: &[f64]| v.iter().cloned().fold(f64::INFINITY, f64::min);
    let fmax = |v: &[f64]| v.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let fmean = |v: &[f64]| v.iter().sum::<f64>() / v.len() as f64;

    let mut payload = json!({
        "schema": "funnel-defaults-v1-cell",
        "target": which, "arm": name, "seed": seed,
        "chains": CHAINS, "warmup": warmup, "draws": draws,
        "algorithm_revision": posterior.algorithm_revision(),
        "wall_seconds": wall,
        "retained_target_calls": retained_calls,
        "warmup_target_calls": warmup_calls,
        "retained_divergences": divergences,
        "retained_refinement_exhaustions": exhaustions,
        "retained_depth_caps": depth_caps,
        "retained_invalid": invalid,
        "warmup_refinement_exhaustions": warmup_exhaustions,
        "final_step_sizes": final_step,
        "final_max_errors": final_delta,
        "bulk_ess": {"min": fmin(&bulk), "mean": fmean(&bulk)},
        "tail_ess": {"min": fmin(&tail), "mean": fmean(&tail)},
        "max_rhat": fmax(&rhats),
        "mean_bulk_ess_per_retained_call": fmean(&bulk) / retained_calls as f64,
        "min_bulk_ess_per_retained_call": fmin(&bulk) / retained_calls as f64,
    });
    if which == "funnel" {
        let omega = columns(&posterior, 0);
        let indicator: Vec<Vec<f64>> = omega
            .iter()
            .map(|c| c.iter().map(|w| f64::from(*w < -5.0)).collect())
            .collect();
        let n = indicator.iter().map(Vec::len).sum::<usize>() as f64;
        let estimate = indicator.iter().flatten().sum::<f64>() / n;
        let mcse = mcse_mean(&views(&indicator));
        let z = (estimate - EXACT_TAIL_MASS) / mcse;
        let flat: Vec<f64> = omega.iter().flatten().cloned().collect();
        let mean = flat.iter().sum::<f64>() / n;
        let variance = flat.iter().map(|w| (w - mean).powi(2)).sum::<f64>() / (n - 1.0);
        let omega_refs = views(&omega);
        let x1 = columns(&posterior, 1);
        let x1_refs = views(&x1);
        let per_chain: Vec<f64> = indicator
            .iter()
            .map(|c| c.iter().sum::<f64>() / c.len() as f64)
            .collect();
        payload["tail_mass"] = json!({
            "estimate": estimate, "mcse": mcse, "exact": EXACT_TAIL_MASS, "z": z,
            "per_chain": per_chain,
        });
        payload["omega"] = json!({
            "mean": mean, "mcse_mean": mcse_mean(&omega_refs),
            "variance": variance, "exact_variance": EXACT_OMEGA_VARIANCE,
            "bulk_ess": bulk[0], "tail_ess": tail[0], "rhat": rhats[0],
        });
        payload["x1"] = json!({
            "bulk_ess": bulk[1], "tail_ess": tail[1], "rhat": rhats[1],
            "mcse_mean": mcse_mean(&x1_refs),
        });
    }
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{which} {name} {seed}: wall {wall:.1}s retained calls {retained_calls} div {divergences} exhaust {exhaustions} depth-cap {depth_caps} min bulk {:.0} {}",
        fmin(&bulk),
        payload.get("tail_mass").map_or(String::new(), |t| format!(
            "tail {:.4} +- {:.4} z {:+.2} var {:.2}",
            t["estimate"].as_f64().unwrap_or(f64::NAN),
            t["mcse"].as_f64().unwrap_or(f64::NAN),
            t["z"].as_f64().unwrap_or(f64::NAN),
            payload["omega"]["variance"].as_f64().unwrap_or(f64::NAN)
        ))
    );
    Ok(())
}

fn median(values: &mut Vec<f64>) -> f64 {
    values.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = values.len();
    if n == 0 {
        f64::NAN
    } else if n % 2 == 1 {
        values[n / 2]
    } else {
        0.5 * (values[n / 2 - 1] + values[n / 2])
    }
}

fn f(v: &Value, path: &[&str]) -> f64 {
    let mut cur = v;
    for p in path {
        cur = &cur[*p];
    }
    cur.as_f64().unwrap_or(f64::NAN)
}

fn summarize(cells_dir: &Path, summary_out: &Path, table_out: &Path) -> Result<(), Box<dyn Error>> {
    let mut cells: BTreeMap<(String, String), Vec<Value>> = BTreeMap::new();
    for entry in fs::read_dir(cells_dir)? {
        let path = entry?.path();
        if path.extension().is_some_and(|e| e == "json") {
            let v: Value = serde_json::from_slice(&fs::read(&path)?)?;
            let key = (
                v["target"].as_str().unwrap().to_string(),
                v["arm"].as_str().unwrap().to_string(),
            );
            cells.entry(key).or_default().push(v);
        }
    }
    let med = |vs: &[Value], path: &[&str]| median(&mut vs.iter().map(|v| f(v, path)).collect());
    let sum_usize =
        |vs: &[Value], key: &str| vs.iter().map(|v| v[key].as_u64().unwrap_or(0)).sum::<u64>();

    let mut arms: BTreeMap<String, Value> = BTreeMap::new();
    let base_eight = cells
        .get(&("eight".into(), "defaults".into()))
        .map(|vs| med(vs, &["mean_bulk_ess_per_retained_call"]))
        .unwrap_or(f64::NAN);
    let base_gauss = cells
        .get(&("gauss100".into(), "defaults".into()))
        .map(|vs| med(vs, &["mean_bulk_ess_per_retained_call"]))
        .unwrap_or(f64::NAN);
    let base_funnel_calls = cells
        .get(&("funnel".into(), "defaults".into()))
        .map(|vs| med(vs, &["retained_target_calls"]))
        .unwrap_or(f64::NAN);

    let mut table = String::new();
    table.push_str("## Funnel (4 chains x 2,000 / 20,000; seeds 82101-82103; seed medians unless listed per seed)\n\n");
    table.push_str("| arm | P(omega<-5) per seed (z) | all abs(z) <= 2 | var(omega) | bulk/tail ESS omega | bulk/tail ESS x1 | div / exhaust / depth-cap (sum of 3 seeds) | retained calls (x defaults) | wall s | final h (seed-median of chain mean) | final delta |\n|---|---|---|---|---|---|---|---|---|---|---|\n");
    for name in ARMS {
        let Some(vs) = cells.get(&("funnel".into(), name.into())) else {
            continue;
        };
        let mut sorted = vs.clone();
        sorted.sort_by_key(|v| v["seed"].as_u64());
        let per_seed: Vec<String> = sorted
            .iter()
            .map(|v| {
                format!(
                    "{:.4} ({:+.2})",
                    f(v, &["tail_mass", "estimate"]),
                    f(v, &["tail_mass", "z"])
                )
            })
            .collect();
        let zs: Vec<f64> = sorted.iter().map(|v| f(v, &["tail_mass", "z"])).collect();
        let qualifies = zs.len() == 3 && zs.iter().all(|z| z.abs() <= 2.0);
        let mean_of = |v: &Value, key: &str| {
            let a = v[key].as_array().unwrap();
            a.iter()
                .map(|x| x.as_f64().unwrap_or(f64::NAN))
                .sum::<f64>()
                / a.len() as f64
        };
        let calls = med(vs, &["retained_target_calls"]);
        let row = json!({
            "tail_mass_per_seed": sorted.iter().map(|v| f(v, &["tail_mass", "estimate"])).collect::<Vec<_>>(),
            "mcse_per_seed": sorted.iter().map(|v| f(v, &["tail_mass", "mcse"])).collect::<Vec<_>>(),
            "z_per_seed": zs,
            "all_seeds_within_2": qualifies,
            "omega_variance_median": med(vs, &["omega", "variance"]),
            "omega_bulk_ess_median": med(vs, &["omega", "bulk_ess"]),
            "omega_tail_ess_median": med(vs, &["omega", "tail_ess"]),
            "x1_bulk_ess_median": med(vs, &["x1", "bulk_ess"]),
            "x1_tail_ess_median": med(vs, &["x1", "tail_ess"]),
            "divergences_sum": sum_usize(vs, "retained_divergences"),
            "exhaustions_sum": sum_usize(vs, "retained_refinement_exhaustions"),
            "depth_caps_sum": sum_usize(vs, "retained_depth_caps"),
            "retained_calls_median": calls,
            "retained_calls_vs_defaults": calls / base_funnel_calls,
            "wall_median": med(vs, &["wall_seconds"]),
            "final_step_median": median(&mut vs.iter().map(|v| mean_of(v, "final_step_sizes")).collect()),
            "final_delta_median": median(&mut vs.iter().map(|v| mean_of(v, "final_max_errors")).collect()),
            "max_rhat_median": med(vs, &["max_rhat"]),
        });
        table.push_str(&format!(
            "| `{name}` | {} | {} | {:.2} | {:.0} / {:.0} | {:.0} / {:.0} | {} / {} / {} | {:.0} ({:.2}x) | {:.1} | {:.3} | {:.3} |\n",
            per_seed.join(", "),
            if qualifies { "**yes**" } else { "no" },
            row["omega_variance_median"].as_f64().unwrap_or(f64::NAN),
            row["omega_bulk_ess_median"].as_f64().unwrap_or(f64::NAN),
            row["omega_tail_ess_median"].as_f64().unwrap_or(f64::NAN),
            row["x1_bulk_ess_median"].as_f64().unwrap_or(f64::NAN),
            row["x1_tail_ess_median"].as_f64().unwrap_or(f64::NAN),
            row["divergences_sum"], row["exhaustions_sum"], row["depth_caps_sum"],
            calls, row["retained_calls_vs_defaults"].as_f64().unwrap_or(f64::NAN),
            row["wall_median"].as_f64().unwrap_or(f64::NAN),
            row["final_step_median"].as_f64().unwrap_or(f64::NAN),
            row["final_delta_median"].as_f64().unwrap_or(f64::NAN),
        ));
        arms.entry(name.to_string()).or_insert_with(|| json!({}))["funnel"] = row;
    }

    for (target, base, title) in [
        (
            "eight",
            base_eight,
            "Noncentered Eight Schools (4 chains x 1,000 / 1,000; seeds 82101-82103; seed medians)",
        ),
        (
            "gauss100",
            base_gauss,
            "100-D standard Gaussian (4 chains x 1,000 / 1,000; seeds 82101-82103; seed medians)",
        ),
    ] {
        table.push_str(&format!("\n## {title}\n\n"));
        table.push_str("| arm | mean bulk ESS | min bulk ESS | min tail ESS | max R-hat | retained calls | mean bulk ESS / call | x defaults | div / exhaust / depth-cap (sum) | wall s |\n|---|---|---|---|---|---|---|---|---|---|\n");
        for name in ARMS {
            let Some(vs) = cells.get(&(target.into(), name.into())) else {
                continue;
            };
            let per_call = med(vs, &["mean_bulk_ess_per_retained_call"]);
            let row = json!({
                "mean_bulk_ess_median": med(vs, &["bulk_ess", "mean"]),
                "min_bulk_ess_median": med(vs, &["bulk_ess", "min"]),
                "min_tail_ess_median": med(vs, &["tail_ess", "min"]),
                "max_rhat_median": med(vs, &["max_rhat"]),
                "retained_calls_median": med(vs, &["retained_target_calls"]),
                "mean_bulk_ess_per_call_median": per_call,
                "ess_per_call_vs_defaults": per_call / base,
                "divergences_sum": sum_usize(vs, "retained_divergences"),
                "exhaustions_sum": sum_usize(vs, "retained_refinement_exhaustions"),
                "depth_caps_sum": sum_usize(vs, "retained_depth_caps"),
                "wall_median": med(vs, &["wall_seconds"]),
            });
            table.push_str(&format!(
                "| `{name}` | {:.0} | {:.0} | {:.0} | {:.4} | {:.0} | {:.5} | {:.2}x | {} / {} / {} | {:.2} |\n",
                row["mean_bulk_ess_median"].as_f64().unwrap_or(f64::NAN),
                row["min_bulk_ess_median"].as_f64().unwrap_or(f64::NAN),
                row["min_tail_ess_median"].as_f64().unwrap_or(f64::NAN),
                row["max_rhat_median"].as_f64().unwrap_or(f64::NAN),
                row["retained_calls_median"].as_f64().unwrap_or(f64::NAN),
                per_call,
                row["ess_per_call_vs_defaults"].as_f64().unwrap_or(f64::NAN),
                row["divergences_sum"], row["exhaustions_sum"], row["depth_caps_sum"],
                row["wall_median"].as_f64().unwrap_or(f64::NAN),
            ));
            arms.entry(name.to_string()).or_insert_with(|| json!({}))[target] = row;
        }
    }

    // Decision rule (PREREGISTRATION.md section 4).
    let mut unbiased: Vec<(String, f64)> = Vec::new();
    let mut unbiased_and_cheap: Vec<(String, f64)> = Vec::new();
    for (name, row) in &arms {
        if name == "nuts-1" {
            continue;
        }
        if row["funnel"]["all_seeds_within_2"].as_bool() == Some(true) {
            let calls = row["funnel"]["retained_calls_median"]
                .as_f64()
                .unwrap_or(f64::NAN);
            unbiased.push((name.clone(), calls));
            let eight = row["eight"]["ess_per_call_vs_defaults"]
                .as_f64()
                .unwrap_or(0.0);
            let gauss = row["gauss100"]["ess_per_call_vs_defaults"]
                .as_f64()
                .unwrap_or(0.0);
            if eight >= 0.9 && gauss >= 0.9 {
                unbiased_and_cheap.push((name.clone(), calls));
            }
        }
    }
    let pick = |v: &mut Vec<(String, f64)>| {
        v.sort_by(|a, b| a.1.partial_cmp(&b.1).unwrap());
        v.first().map(|(n, _)| n.clone())
    };
    let choice_full = pick(&mut unbiased_and_cheap);
    let choice_fallback = pick(&mut unbiased);
    let decision = json!({
        "rule": "cheapest (funnel retained calls, seed median) among arms with |z| <= 2 on all three seeds AND >= 0.9x defaults mean-bulk-ESS/call on eight and gauss100; else cheapest with |z| <= 2; else none",
        "unbiased_arms": unbiased.iter().map(|(n, _)| n.clone()).collect::<Vec<_>>(),
        "unbiased_and_cheap_arms": unbiased_and_cheap.iter().map(|(n, _)| n.clone()).collect::<Vec<_>>(),
        "choice_full_rule": choice_full,
        "choice_fallback": choice_fallback,
    });
    table.push_str(&format!(
        "\n## Decision\n\nArms with |z| <= 2 on all three seeds (excluding the `nuts-1` control): {}. Of those, arms at >= 0.9x defaults ESS/call on both cost targets: {}. Full-rule choice: {}; fallback (cheapest unbiased): {}.\n",
        decision["unbiased_arms"], decision["unbiased_and_cheap_arms"], decision["choice_full_rule"], decision["choice_fallback"]
    ));
    let summary = json!({
        "schema": "funnel-defaults-v1-summary",
        "exact_tail_mass": EXACT_TAIL_MASS,
        "baseline": {"eight_ess_per_call": base_eight, "gauss100_ess_per_call": base_gauss, "funnel_retained_calls": base_funnel_calls},
        "arms": arms,
        "decision": decision,
        "cells": cells.values().map(Vec::len).sum::<usize>(),
    });
    fs::write(summary_out, serde_json::to_vec_pretty(&summary)?)?;
    fs::write(table_out, table.as_bytes())?;
    print!("{table}");
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [cmd, which, name, seed, out, rest @ ..] if cmd == "cell" => {
            let (default_warmup, default_draws) = if which == "funnel" {
                (2000, 20000)
            } else {
                (1000, 1000)
            };
            let warmup = rest
                .first()
                .map_or(default_warmup, |t| t.parse().unwrap_or(default_warmup));
            let draws = rest
                .get(1)
                .map_or(default_draws, |t| t.parse().unwrap_or(default_draws));
            match seed.parse::<u64>() {
                Ok(seed) => run_cell(which, name, seed, warmup, draws, Path::new(out)),
                Err(e) => Err(e.into()),
            }
        }
        [cmd, dir, summary, table] if cmd == "summarize" => {
            summarize(Path::new(dir), Path::new(summary), Path::new(table))
        }
        _ => Err("usage: cell <funnel|eight|gauss100> <arm> <seed> <out.json> [warmup] [draws] | summarize <cells-dir> <summary.json> <table.md>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
