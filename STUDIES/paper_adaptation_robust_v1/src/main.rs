//! Appendix C robustness study: one (model, arm, seed) cell, or the analysis.
//!
//! Usage:
//!   `paper-adaptation-robust-v1 run <model> <arm> <seed> <out.json>`
//!   `paper-adaptation-robust-v1 analyze <cells dir> <out.md> <summary.json>`
//!
//! `run` loads `$POSTERIORDB_MODELS/<model>_model.so` and `<model>.data.json`
//! (the BridgeStan libraries compiled for `STUDIES/posteriordb_bench_v1`),
//! draws four uniform(-2, 2) starts with `owalnuts::sampler::uniform_starts`
//! from the cell seed, runs 1,000 warmup + 1,000 retained transitions on four
//! parallel chains with the v1 tuning and the arm's warmup, and writes the
//! preregistered estimands plus the raw paper-adaptation telemetry to JSON.
//! `analyze` folds the cells into the results table and applies the
//! preregistered decision rule. See `PREREGISTRATION.md`.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::Summary;
use owalnuts::sampler::uniform_starts;
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, PaperAdaptationConfig, RunConfig, Target,
    WarmupConfig, sample_chains,
};
use owalnuts_bridgestan::{StanTarget, default_preload};
use serde_json::{Value, json};
use std::{
    collections::BTreeMap, env, error::Error, fs, num::NonZeroUsize, path::Path, time::Instant,
};

const CHAINS: usize = 4;
const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const STEP_SIZE: f64 = 0.1;
const MAX_DEPTH: usize = 8;
const MIN_MICRO_STEPS: usize = 1;
const MAX_REFINEMENT_LEVELS: usize = 4;
const MAX_ERROR: f64 = 1.0;
const TARGET_ACCEPT: f64 = 0.8;
const START_RADIUS: f64 = 2.0;
const START_ATTEMPTS: usize = 100;

pub const MODELS: [&str; 7] = [
    "kidiq__kidscore_momhsiq",
    "sblrc__blr",
    "earnings__logearn_interaction",
    "diamonds__diamonds",
    "nes2000__nes",
    "mesquite__logmesquite_logvash",
    "hmm_example__hmm_example",
];
/// Round 1 (preregistered) arms, then the round 2 and round 3 amendment
/// arms (see `PREREGISTRATION.md`).
pub const ARMS: [&str; 11] = [
    "da",
    "paper",
    "floor",
    "defer",
    "guarded",
    "guarded-trim",
    "zero",
    "floor-zero",
    "guarded-zero",
    "zero-wide",
    "guarded-zero-wide",
];
pub const SEEDS: [u64; 2] = [77201, 77202];
/// v1 `owalnuts-da` seed-median min bulk ESS per gradient (x1e3), from
/// `STUDIES/posteriordb_bench_v1/artifacts/results-table.md` (arviz, over the
/// constrained reference parameters); orientation only.
const V1_DA_ESS_PER_GRAD_X1E3: [(&str, f64); 7] = [
    ("kidiq__kidscore_momhsiq", 2.668),
    ("sblrc__blr", 0.295),
    ("earnings__logearn_interaction", 0.015),
    ("diamonds__diamonds", 0.022),
    ("nes2000__nes", 2.401),
    ("mesquite__logmesquite_logvash", 2.827),
    ("hmm_example__hmm_example", 8.310),
];
const RATIO_BAR: f64 = 0.8;

fn nz(n: usize) -> NonZeroUsize {
    NonZeroUsize::new(n).expect("nonzero")
}

pub fn paper_config(arm: &str) -> Result<Option<PaperAdaptationConfig>, Box<dyn Error>> {
    let base = PaperAdaptationConfig::default();
    let floor = |c: PaperAdaptationConfig| c.with_min_max_error(0.05);
    let defer = |c: PaperAdaptationConfig| {
        c.with_first_update_after(150)
            .with_metric_update_required(true)
    };
    Ok(match arm {
        "da" => None,
        "paper" => Some(base),
        "floor" => Some(floor(base)?),
        "defer" => Some(defer(base)),
        "guarded" => Some(defer(floor(base)?).with_unhealthy_orbits_excluded(true)),
        "guarded-trim" => Some(
            defer(floor(base)?)
                .with_unhealthy_orbits_excluded(true)
                .with_trim_fraction(0.1)?,
        ),
        "zero" => Some(base.with_exhausted_transitions_as_zero(true)),
        "floor-zero" => Some(floor(base)?.with_exhausted_transitions_as_zero(true)),
        "guarded-zero" => Some(
            defer(floor(base)?)
                .with_unhealthy_orbits_excluded(true)
                .with_exhausted_transitions_as_zero(true),
        ),
        "zero-wide" => Some(
            base.with_exhausted_transitions_as_zero(true)
                .with_step_relative_bound(1e6)?,
        ),
        "guarded-zero-wide" => Some(
            defer(floor(base)?)
                .with_unhealthy_orbits_excluded(true)
                .with_exhausted_transitions_as_zero(true)
                .with_step_relative_bound(1e6)?,
        ),
        other => return Err(format!("unknown arm {other:?}").into()),
    })
}

fn run_config(arm: &str, seed: u64) -> Result<RunConfig, Box<dyn Error>> {
    let tuning = KernelTuning::new(
        STEP_SIZE,
        nz(MAX_DEPTH),
        nz(MIN_MICRO_STEPS),
        nz(MAX_REFINEMENT_LEVELS),
        MAX_ERROR,
    )?;
    let warmup = match paper_config(arm)? {
        None => WarmupConfig::new(TARGET_ACCEPT)?.with_mass_adaptation(true),
        Some(paper) => WarmupConfig::default()
            .with_mass_adaptation(true)
            .with_paper_adaptation(paper),
    };
    Ok(RunConfig::new(WARMUP, nz(RETAINED), seed)
        .with_tuning(tuning)
        .with_warmup(warmup))
}

fn median(values: &mut [f64]) -> f64 {
    values.sort_by(f64::total_cmp);
    let n = values.len();
    if n == 0 {
        f64::NAN
    } else if n % 2 == 1 {
        values[n / 2]
    } else {
        0.5 * (values[n / 2 - 1] + values[n / 2])
    }
}

fn run(model: &str, arm: &str, seed: u64, out: &Path) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let models = env::var("POSTERIORDB_MODELS")
        .map_err(|_| "set POSTERIORDB_MODELS to the directory holding <model>_model.so")?;
    let models = Path::new(&models);
    let so = models.join(format!("{model}_model.so"));
    let data = fs::read_to_string(models.join(format!("{model}.data.json")))?;
    let target = StanTarget::load(&so, &default_preload(), Some(&data), 1)?;
    let dimension = target.dimension();
    let starts = uniform_starts(&target, CHAINS, seed, START_RADIUS, START_ATTEMPTS)?;
    let start_calls = target.calls();
    let config = run_config(arm, seed)?;
    let mass = DiagonalMass::identity(nz(dimension));

    let begin = Instant::now();
    let result = sample_chains(&target, &starts, &mass, &config, nz(CHAINS));
    let wall = begin.elapsed().as_secs_f64();
    let output = match result {
        Ok(output) => output,
        Err(error) => {
            let payload = json!({
                "schema": "paper-adaptation-robust-v1-cell",
                "model": model, "arm": arm, "seed": seed,
                "status": "error", "error": error.to_string(),
                "wall_seconds": wall, "target_calls": target.calls(),
                "algorithm_revision": ALGORITHM_REVISION,
            });
            fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
            return Err(error.into());
        }
    };
    let summary = Summary::from_output(&output, None)?;
    let min_bulk = summary
        .parameters
        .iter()
        .map(|p| p.ess_bulk)
        .fold(f64::INFINITY, f64::min);
    let min_tail = summary
        .parameters
        .iter()
        .map(|p| p.ess_tail)
        .fold(f64::INFINITY, f64::min);
    let rhat_undefined = summary.parameters.iter().any(|p| !p.rhat.is_finite());
    let max_rhat = summary
        .parameters
        .iter()
        .map(|p| p.rhat)
        .fold(f64::NEG_INFINITY, f64::max);
    let gradients = target.calls() - start_calls;

    let mut chains = Vec::new();
    let mut frozen_chain = false;
    let mut deltas = Vec::new();
    let mut steps = Vec::new();
    let mut divergences = 0usize;
    for chain in output.chains() {
        let retained = chain.telemetry().retained();
        let discarded = chain.telemetry().discarded();
        let exhaustion = retained.refinement_exhaustion_stops();
        if exhaustion * 2 > RETAINED {
            frozen_chain = true;
        }
        divergences += retained.divergences();
        deltas.push(chain.metadata().tuning().max_error());
        steps.push(chain.metadata().tuning().step_size());
        let updates: Vec<Value> = chain
            .telemetry()
            .paper_adaptation_updates()
            .iter()
            .map(|u| {
                json!({
                    "transition": u.transition(),
                    "window_index": u.window_index(),
                    "orbits": u.orbits(),
                    "inflation_quantile": u.inflation_quantile(),
                    "energy_range_quantile": u.energy_range_quantile(),
                    "max_error_before": u.max_error_before(),
                    "max_error_after": u.max_error_after(),
                    "unrefined_fraction_mean": u.unrefined_fraction_mean(),
                    "step_before": u.step_before(),
                    "step_after": u.step_after(),
                    "outcome": format!("{:?}", u.outcome()),
                })
            })
            .collect();
        chains.push(json!({
            "retained_refinement_exhaustions": exhaustion,
            "retained_divergences": retained.divergences(),
            "retained_maximum_depth_stops": retained.maximum_depth_stops(),
            "retained_target_calls": retained.target_calls_total(),
            "warmup_target_calls": discarded.target_calls_total(),
            "warmup_divergences": discarded.divergences(),
            "final_max_error": chain.metadata().tuning().max_error(),
            "final_step_size": chain.metadata().tuning().step_size(),
            "paper_adaptation_updates": updates,
        }));
    }
    let frozen = frozen_chain || rhat_undefined;
    let payload = json!({
        "schema": "paper-adaptation-robust-v1-cell",
        "model": model, "arm": arm, "seed": seed, "status": "ok",
        "dimension": dimension,
        "chains": CHAINS, "warmup": WARMUP, "retained": RETAINED,
        "starts": starts, "start_search_calls": start_calls,
        "paper_config": paper_config(arm)?.map(|p| format!("{p:?}")),
        "wall_seconds": wall,
        "gradients": gradients,
        "min_bulk_ess": min_bulk,
        "min_tail_ess": min_tail,
        "max_rhat": if rhat_undefined { Value::Null } else { json!(max_rhat) },
        "rhat_undefined": rhat_undefined,
        "frozen": frozen,
        "bulk_ess_per_gradient": min_bulk / gradients as f64,
        "divergences": divergences,
        "final_delta_median": median(&mut deltas.clone()),
        "final_h_median": median(&mut steps.clone()),
        "chains_data": chains,
        "algorithm_revision": ALGORITHM_REVISION,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{model} {arm} {seed}: wall {wall:.2}s grads {gradients} minESS {min_bulk:.0} rhat {} frozen {frozen} delta {:.3e} h {:.3e}",
        if rhat_undefined {
            "nan".to_owned()
        } else {
            format!("{max_rhat:.3}")
        },
        median(&mut deltas.clone()),
        median(&mut steps.clone())
    );
    Ok(())
}

fn f(v: &Value, key: &str) -> f64 {
    v.get(key).and_then(Value::as_f64).unwrap_or(f64::NAN)
}

fn analyze(cells: &Path, out_md: &Path, out_json: &Path) -> Result<(), Box<dyn Error>> {
    let mut table: BTreeMap<(String, String), Vec<Value>> = BTreeMap::new();
    for entry in fs::read_dir(cells)? {
        let path = entry?.path();
        if path.extension().is_none_or(|e| e != "json") {
            continue;
        }
        let cell: Value = serde_json::from_str(&fs::read_to_string(&path)?)?;
        let key = (
            cell["model"].as_str().unwrap_or("?").to_owned(),
            cell["arm"].as_str().unwrap_or("?").to_owned(),
        );
        table.entry(key).or_default().push(cell);
    }
    let mut md = String::from("# paper_adaptation_robust_v1 — results\n\n");
    md.push_str("Seed medians over 2 seeds (4 chains, 1,000/1,000, unconstrained coordinates, `owalnuts::diagnostics`); `frozen` = cells (of 2) with a chain whose retained refinement exhaustions exceed 500 or with undefined R-hat; `r` = bulk ESS/gradient over the in-study `da` arm; `v1 da` = v1 seed-median min bulk ESS/gradient x1e3 (arviz, constrained reference parameters), orientation only.\n\n");
    md.push_str("| model | arm | frozen | error | grads | min bulk ESS | min tail ESS | bulk ESS/grad x1e3 | r vs da | max R-hat | div | final delta | final h | v1 da ESS/grad x1e3 |\n|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n");
    let mut summary = BTreeMap::new();
    let mut ratios: BTreeMap<String, BTreeMap<String, (bool, f64)>> = BTreeMap::new();
    for model in MODELS {
        let da_epg = table
            .get(&(model.to_owned(), "da".to_owned()))
            .map(|cells| {
                median(
                    &mut cells
                        .iter()
                        .filter(|c| c["status"] == "ok")
                        .map(|c| f(c, "bulk_ess_per_gradient"))
                        .collect::<Vec<_>>(),
                )
            })
            .unwrap_or(f64::NAN);
        let v1 = V1_DA_ESS_PER_GRAD_X1E3
            .iter()
            .find(|(m, _)| *m == model)
            .map_or(f64::NAN, |(_, v)| *v);
        for arm in ARMS {
            let Some(cells) = table.get(&(model.to_owned(), arm.to_owned())) else {
                continue;
            };
            let ok: Vec<&Value> = cells.iter().filter(|c| c["status"] == "ok").collect();
            let errors = cells.len() - ok.len();
            let frozen = ok
                .iter()
                .filter(|c| c["frozen"].as_bool().unwrap_or(false))
                .count();
            let stat = |key: &str| median(&mut ok.iter().map(|c| f(c, key)).collect::<Vec<_>>());
            let epg = stat("bulk_ess_per_gradient");
            let r = epg / da_epg;
            let rhat_undefined = ok
                .iter()
                .any(|c| c["rhat_undefined"].as_bool() == Some(true));
            let rhat = if rhat_undefined {
                "—".to_owned()
            } else {
                format!("{:.4}", stat("max_rhat"))
            };
            let div: Vec<String> = ok
                .iter()
                .map(|c| c["divergences"].as_u64().unwrap_or(0).to_string())
                .collect();
            md.push_str(&format!(
                "| {model} | {arm} | {frozen}/{} | {errors} | {:.0} | {:.0} | {:.0} | {:.3} | {} | {rhat} | {} | {:.3e} | {:.3e} | {v1:.3} |\n",
                cells.len(),
                stat("gradients"),
                stat("min_bulk_ess"),
                stat("min_tail_ess"),
                epg * 1e3,
                if arm == "da" { "1.000".to_owned() } else { format!("{r:.3}") },
                div.join(","),
                stat("final_delta_median"),
                stat("final_h_median"),
            ));
            let robust = frozen == 0 && errors == 0 && !rhat_undefined;
            ratios
                .entry(arm.to_owned())
                .or_default()
                .insert(model.to_owned(), (robust, r));
            summary.insert(
                format!("{model}/{arm}"),
                json!({"frozen_cells": frozen, "error_cells": errors, "cells": cells.len(),
                       "gradients": stat("gradients"), "min_bulk_ess": stat("min_bulk_ess"),
                       "min_tail_ess": stat("min_tail_ess"), "bulk_ess_per_gradient": epg,
                       "ratio_vs_da": r, "max_rhat": stat("max_rhat"), "rhat_undefined": rhat_undefined,
                       "final_delta": stat("final_delta_median"), "final_h": stat("final_h_median"),
                       "v1_da_ess_per_gradient_x1e3": v1}),
            );
        }
    }
    md.push_str("\n## Decision rule\n\n| arm | robust (no frozen/error cell on any model) | models with r >= 0.8 | geomean r | clears the bar |\n|---|---|---:|---:|---|\n");
    md.push_str(
        "
(`paper` is never a candidate; the winner is the first clearing arm in the listed order.)

",
    );
    let mut decision = BTreeMap::new();
    let mut winner: Option<String> = None;
    for arm in ARMS.iter().filter(|arm| **arm != "da") {
        let Some(per_model) = ratios.get(*arm) else {
            continue;
        };
        let robust = per_model.len() == MODELS.len() && per_model.values().all(|(ok, _)| *ok);
        let passing = per_model
            .values()
            .filter(|(ok, r)| *ok && *r >= RATIO_BAR)
            .count();
        let geomean = if per_model.values().all(|(_, r)| r.is_finite() && *r > 0.0) {
            (per_model.values().map(|(_, r)| r.ln()).sum::<f64>() / per_model.len() as f64).exp()
        } else {
            f64::NAN
        };
        let clears = robust && passing == MODELS.len();
        if clears && winner.is_none() && *arm != "paper" {
            winner = Some((*arm).to_owned());
        }
        md.push_str(&format!(
            "| {arm} | {robust} | {passing}/{} | {geomean:.3} | {clears} |\n",
            MODELS.len()
        ));
        decision.insert(
            (*arm).to_owned(),
            json!({"robust": robust, "models_passing": passing, "geomean_ratio": geomean, "clears": clears}),
        );
    }
    md.push_str(&format!(
        "\nPreregistered rule -> new `PaperAdaptationConfig::default()`: **{}**\n",
        winner
            .clone()
            .unwrap_or_else(|| "none (default unchanged)".to_owned())
    ));
    fs::write(out_md, &md)?;
    fs::write(
        out_json,
        serde_json::to_vec_pretty(
            &json!({"cells": summary, "decision": decision, "winner": winner}),
        )?,
    )?;
    print!("{md}");
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.iter().map(String::as_str).collect::<Vec<_>>().as_slice() {
        ["run", model, arm, seed, out] => match seed.parse::<u64>() {
            Ok(seed) => run(model, arm, seed, Path::new(out)),
            Err(_) => Err("seed must be an integer".into()),
        },
        ["analyze", cells, out_md, out_json] => {
            analyze(Path::new(cells), Path::new(out_md), Path::new(out_json))
        }
        _ => Err("usage: run <model> <arm> <seed> <out.json> | analyze <cells dir> <out.md> <summary.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
