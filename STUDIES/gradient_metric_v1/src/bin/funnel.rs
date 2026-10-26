//! WP71 `gradient_metric_v1`, funnel sanity arm: Neal's 10-D funnel at the
//! sampler defaults, with the adaptation as the arm: `default` =
//! `Adaptation::default()`; `gradmetric` / `gradmetric-overlap` =
//! `Adaptation::Custom` with the sampler's own warmup defaults plus the
//! research flag `DiagonalMetricEstimator::GradientInformed` /
//! `GradientInformedOverlap`. Nothing else differs; one build
//! (`owalnuts/research`) serves every arm.
//!
//! Usage: `funnel <default|gradmetric|gradmetric-overlap> <warmup> <draws> <seed> <out.json>`
//!
//! Copied from `STUDIES/refinement_levels10_v1/src/bin/funnel.rs` (WP68,
//! itself WP66's / WP53's harness). Changes from WP68: the arm selects the
//! adaptation instead of the build; each chain records its metric updates.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, mcse_mean, rhat};
use owalnuts::sampler::{
    Adaptation, DEFAULT_CHAIN_RESCUE, DEFAULT_MAX_REFINEMENT_LEVELS, DEFAULT_METRIC_REGULARIZATION,
    DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler, Target, TargetError, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::{DiagonalMetricEstimator, StopReason, TransitionDiagnostics};
use serde_json::{Value, json};
use std::{env, error::Error, fs, path::Path, time::Instant};

const DIMENSION: usize = 10;
const EXACT_TAIL_MASS: f64 = 0.047_790_352_272_814_7;
const EXACT_TAIL_MASS_6: f64 = 0.022_750_131_948_179_2;
const EXACT_OMEGA_VARIANCE: f64 = 9.0;
const BATCHES_PER_CHAIN: usize = 40;
const PREFIX_DRAWS: usize = 20_000;

struct Funnel;

/// The arm is the adaptation; tuning is `Tuning::default()` in every arm.
fn arm(name: &str) -> Result<(Tuning, Adaptation), String> {
    let estimator = match name {
        "default" => return Ok((Tuning::default(), Adaptation::default())),
        "gradmetric" => DiagonalMetricEstimator::GradientInformed,
        "gradmetric-overlap" => DiagonalMetricEstimator::GradientInformedOverlap,
        other => {
            return Err(format!(
                "unknown arm {other:?} (default, gradmetric, gradmetric-overlap)"
            ));
        }
    };
    if DEFAULT_CHAIN_RESCUE.is_some() {
        return Err("DEFAULT_CHAIN_RESCUE is set; the candidate arms assume none".into());
    }
    let warmup = WarmupConfig::new(0.8)
        .map_err(|e| e.to_string())?
        .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
        .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
        .with_diagonal_metric_estimator(estimator);
    Ok((Tuning::default(), Adaptation::Custom(warmup)))
}

fn fnv(hash: &mut u64, values: &[f64]) {
    for v in values {
        for b in v.to_bits().to_le_bytes() {
            *hash ^= u64::from(b);
            *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
        }
    }
}

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
        let value =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}

const STOPS: [&str; 6] = [
    "MaximumDepth",
    "OuterUTurn",
    "RecursiveUTurn",
    "RefinementExhausted",
    "ReverseCoarserAccepted",
    "InvalidEvaluation",
];

fn stop_index(stop: StopReason) -> usize {
    match stop {
        StopReason::MaximumDepth => 0,
        StopReason::OuterUTurn => 1,
        StopReason::RecursiveUTurn => 2,
        StopReason::RefinementExhausted => 3,
        StopReason::ReverseCoarserAccepted => 4,
        StopReason::InvalidEvaluation => 5,
        _ => 5,
    }
}

/// Aggregate of retained transitions in one starting-omega class.
#[derive(Clone)]
struct ClassStats {
    n: usize,
    depth: Vec<usize>,
    stops: [usize; 6],
    uturn_depth_le3: usize,
    level: Vec<usize>,
    level_none: usize,
    moved: usize,
    divergent: usize,
    energy_error_sum: f64,
    energy_accept_sum: f64,
    energy_errors: Vec<f64>,
    refinement_attempts: usize,
    reverse_coarser_rejections: usize,
    macro_length_sum: f64,
    orbit_states_sum: usize,
    target_evaluations: usize,
}

impl ClassStats {
    fn new(max_depth: usize, levels: usize) -> Self {
        Self {
            n: 0,
            depth: vec![0; max_depth + 1],
            stops: [0; 6],
            uturn_depth_le3: 0,
            level: vec![0; levels],
            level_none: 0,
            moved: 0,
            divergent: 0,
            energy_error_sum: 0.0,
            energy_accept_sum: 0.0,
            energy_errors: Vec::new(),
            refinement_attempts: 0,
            reverse_coarser_rejections: 0,
            macro_length_sum: 0.0,
            orbit_states_sum: 0,
            target_evaluations: 0,
        }
    }

    fn add(&mut self, d: &TransitionDiagnostics) {
        self.n += 1;
        let depth = d.depth().min(self.depth.len() - 1);
        self.depth[depth] += 1;
        self.stops[stop_index(d.stop())] += 1;
        if matches!(
            d.stop(),
            StopReason::OuterUTurn | StopReason::RecursiveUTurn
        ) && d.depth() <= 3
        {
            self.uturn_depth_le3 += 1;
        }
        match d.selected_refinement_level() {
            Some(level) => {
                let level = level.min(self.level.len() - 1);
                self.level[level] += 1;
            }
            None => self.level_none += 1,
        }
        self.moved += usize::from(d.position_changed());
        self.divergent += usize::from(d.divergent());
        let error = d.maximum_absolute_energy_error();
        if error.is_finite() {
            self.energy_error_sum += error;
            self.energy_accept_sum += (-error).exp().min(1.0);
            self.energy_errors.push(error);
        }
        self.refinement_attempts += d.refinement_attempts();
        self.reverse_coarser_rejections += d.reverse_coarser_rejections();
        self.macro_length_sum += d.trajectory_macro_length();
        self.orbit_states_sum += d.orbit_states();
        self.target_evaluations += d.target_evaluations();
    }

    fn merge(&mut self, other: &Self) {
        self.n += other.n;
        for (a, b) in self.depth.iter_mut().zip(&other.depth) {
            *a += b;
        }
        for (a, b) in self.stops.iter_mut().zip(&other.stops) {
            *a += b;
        }
        self.uturn_depth_le3 += other.uturn_depth_le3;
        for (a, b) in self.level.iter_mut().zip(&other.level) {
            *a += b;
        }
        self.level_none += other.level_none;
        self.moved += other.moved;
        self.divergent += other.divergent;
        self.energy_error_sum += other.energy_error_sum;
        self.energy_accept_sum += other.energy_accept_sum;
        self.energy_errors.extend_from_slice(&other.energy_errors);
        self.refinement_attempts += other.refinement_attempts;
        self.reverse_coarser_rejections += other.reverse_coarser_rejections;
        self.macro_length_sum += other.macro_length_sum;
        self.orbit_states_sum += other.orbit_states_sum;
        self.target_evaluations += other.target_evaluations;
    }

    fn json(&self) -> Value {
        let n = self.n.max(1) as f64;
        let mut errors = self.energy_errors.clone();
        errors.sort_by(f64::total_cmp);
        let quantile = |q: f64| -> Option<f64> {
            if errors.is_empty() {
                None
            } else {
                let i = ((errors.len() - 1) as f64 * q).round() as usize;
                Some(errors[i])
            }
        };
        let top = *self.level.last().unwrap_or(&0);
        let mean_depth = self
            .depth
            .iter()
            .enumerate()
            .map(|(d, c)| d * c)
            .sum::<usize>() as f64
            / n;
        json!({
            "n": self.n,
            "depth_histogram": self.depth,
            "mean_depth": mean_depth,
            "stops": STOPS.iter().zip(self.stops).map(|(k, v)| (k.to_string(), json!(v))).collect::<serde_json::Map<_, _>>(),
            "uturn_depth_le3": self.uturn_depth_le3,
            "uturn_depth_le3_fraction": self.uturn_depth_le3 as f64 / n,
            "depth_cap_fraction": self.stops[0] as f64 / n,
            "exhaustion_stop_fraction": self.stops[3] as f64 / n,
            "selected_level_histogram": self.level,
            "selected_level_none": self.level_none,
            "top_level_selected": top,
            "top_level_fraction": top as f64 / n,
            "moved_fraction": self.moved as f64 / n,
            "divergences": self.divergent,
            "mean_max_abs_energy_error": self.energy_error_sum / n,
            "mean_energy_acceptance_proxy": self.energy_accept_sum / n,
            "max_abs_energy_error_q50": quantile(0.5),
            "max_abs_energy_error_q90": quantile(0.9),
            "max_abs_energy_error_q99": quantile(0.99),
            "mean_refinement_attempts": self.refinement_attempts as f64 / n,
            "reverse_coarser_rejections": self.reverse_coarser_rejections,
            "mean_macro_length": self.macro_length_sum / n,
            "mean_orbit_states": self.orbit_states_sum as f64 / n,
            "mean_target_evaluations": self.target_evaluations as f64 / n,
        })
    }
}

const CLASSES: [&str; 3] = ["bulk", "neck", "deep"];

fn class_of(omega: f64) -> usize {
    if omega >= -5.0 {
        0
    } else if omega >= -7.0 {
        1
    } else {
        2
    }
}

fn std_normal_cdf(x: f64) -> f64 {
    // Only reported next to the estimates; the analysis recomputes the exact
    // values with Python's `math.erfc`.
    0.5 * erfc(-x / std::f64::consts::SQRT_2)
}

/// Complementary error function (W. J. Cody's rational approximations as in
/// Numerical Recipes `erfcc`, relative error < 1.2e-7).
fn erfc(x: f64) -> f64 {
    let z = x.abs();
    let t = 1.0 / (1.0 + 0.5 * z);
    let r = t
        * (-z * z - 1.265_512_23
            + t * (1.000_023_68
                + t * (0.374_091_96
                    + t * (0.096_784_18
                        + t * (-0.186_288_06
                            + t * (0.278_868_07
                                + t * (-1.135_203_98
                                    + t * (1.488_515_87
                                        + t * (-0.822_152_23 + t * 0.170_872_77)))))))))
            .exp();
    if x >= 0.0 { r } else { 2.0 - r }
}

fn run(
    arm_name: &str,
    warmup: usize,
    draws: usize,
    seed: u64,
    out: &Path,
) -> Result<(), Box<dyn Error>> {
    if out.exists() {
        return Err(format!("output already exists: {}", out.display()).into());
    }
    let (tuning, adaptation) = arm(arm_name)?;
    let kernel = tuning.to_kernel()?;
    let max_depth = kernel.max_depth();
    let levels = kernel.max_refinement_levels();
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(4)
        .threads(4)
        .seed(seed)
        .metric(Metric::diagonal())
        .adaptation(adaptation.clone())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case());
    let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
        .into_iter()
        .map(|omega| {
            let mut q = vec![0.0; DIMENSION];
            q[0] = omega;
            q
        })
        .collect();
    let begin = Instant::now();
    let posterior = sampler.run(&Funnel, &starts)?;
    let wall = begin.elapsed().as_secs_f64();

    let thresholds_low: Vec<f64> = (1..=10).map(|c| -(c as f64)).collect();
    let thresholds_high: Vec<f64> = (1..=10).map(|c| c as f64).collect();

    let batch = (draws / BATCHES_PER_CHAIN).max(1);
    let mut below = 0usize;
    let mut total = 0usize;
    let mut batch_means: Vec<f64> = Vec::new();
    let mut chains_json = Vec::new();
    let mut columns: Vec<Vec<Vec<f64>>> = vec![Vec::new(); DIMENSION];
    let mut indicator_columns: Vec<Vec<f64>> = Vec::new();
    let mut indicator6_columns: Vec<Vec<f64>> = Vec::new();
    let mut per_chain_tail = Vec::new();
    let mut nonfinite = 0usize;
    let mut pooled_classes: Vec<ClassStats> =
        vec![ClassStats::new(max_depth, levels); CLASSES.len()];
    let mut low_counts = vec![0usize; thresholds_low.len()];
    let mut high_counts = vec![0usize; thresholds_high.len()];
    let mut prefix_below = 0usize;
    let mut prefix_total = 0usize;
    let mut cell_hash: u64 = 0xcbf2_9ce4_8422_2325;
    for chain in posterior.chains() {
        let chain_tuning = chain.metadata().tuning();
        let work = chain.telemetry().total();
        let retained = chain.telemetry().retained();
        let discarded = chain.telemetry().discarded();
        let warmup_end = chain.telemetry().warmup_end();
        let n = chain.retained();
        let diagnostics = chain.diagnostics();
        let first_retained = diagnostics.len() - n;

        // Per-chain omega trace and derived statistics.
        let omega: Vec<f64> = (0..n).map(|t| chain.sample(t).expect("draw")[0]).collect();
        let mut chain_hash: u64 = 0xcbf2_9ce4_8422_2325;
        fnv(&mut chain_hash, chain.samples());
        fnv(&mut cell_hash, chain.samples());
        let mut classes: Vec<ClassStats> = vec![ClassStats::new(max_depth, levels); CLASSES.len()];
        for t in 1..n {
            classes[class_of(omega[t - 1])].add(&diagnostics[first_retained + t]);
        }
        for (pooled, c) in pooled_classes.iter_mut().zip(&classes) {
            pooled.merge(c);
        }
        let quarter = (n / 4).max(1);
        let quarters: Vec<f64> = (0..4)
            .map(|q| {
                let lo = q * quarter;
                let hi = if q == 3 { n } else { (q + 1) * quarter };
                omega[lo..hi].iter().filter(|w| **w < -5.0).count() as f64 / (hi - lo) as f64
            })
            .collect();
        let mut entries = 0usize;
        let mut excursions: Vec<usize> = Vec::new();
        let mut run_length = 0usize;
        for (t, w) in omega.iter().enumerate() {
            if *w < -5.0 {
                if run_length == 0 && t > 0 {
                    entries += 1;
                }
                run_length += 1;
            } else if run_length > 0 {
                excursions.push(run_length);
                run_length = 0;
            }
        }
        if run_length > 0 {
            excursions.push(run_length);
        }
        let chain_low: Vec<f64> = thresholds_low
            .iter()
            .map(|c| omega.iter().filter(|w| *w < c).count() as f64 / n as f64)
            .collect();
        let chain_high: Vec<f64> = thresholds_high
            .iter()
            .map(|c| omega.iter().filter(|w| *w > c).count() as f64 / n as f64)
            .collect();
        for (k, c) in thresholds_low.iter().enumerate() {
            low_counts[k] += omega.iter().filter(|w| **w < *c).count();
        }
        for (k, c) in thresholds_high.iter().enumerate() {
            high_counts[k] += omega.iter().filter(|w| **w > *c).count();
        }
        let prefix = n.min(PREFIX_DRAWS);
        let chain_prefix_below = omega[..prefix].iter().filter(|w| **w < -5.0).count();
        prefix_below += chain_prefix_below;
        prefix_total += prefix;

        // Warmup acceptance statistic by phase (positions are not retained).
        let schedule = chain.metadata().warmup_schedule();
        let warmup_diag = &diagnostics[..first_retained];
        let acc: Vec<f64> = warmup_diag
            .iter()
            .filter_map(|d| d.acceptance_statistic())
            .collect();
        let last_window: Vec<f64> = match warmup_end {
            Some(w) => warmup_diag[w.start().min(first_retained)..w.end().min(first_retained)]
                .iter()
                .filter_map(|d| d.acceptance_statistic())
                .collect(),
            None => Vec::new(),
        };
        let terminal: Vec<f64> = warmup_diag
            .iter()
            .skip(first_retained.saturating_sub(50))
            .filter_map(|d| d.acceptance_statistic())
            .collect();
        let mean = |v: &[f64]| {
            if v.is_empty() {
                None
            } else {
                Some(v.iter().sum::<f64>() / v.len() as f64)
            }
        };
        let warmup_top_level = warmup_diag
            .iter()
            .filter(|d| d.selected_refinement_level() == Some(levels - 1))
            .count();
        let warmup_exhaustion_stops = warmup_diag
            .iter()
            .filter(|d| d.stop() == StopReason::RefinementExhausted)
            .count();

        chains_json.push(json!({
            "final_max_error": chain_tuning.max_error(),
            "final_step_size": chain_tuning.step_size(),
            "warmup_end_step_size": warmup_end.map(|w| w.step_size()),
            "warmup_end_median_log_density": warmup_end.map(|w| w.median_log_density()),
            "mass_diagonal": chain.metadata().mass_diagonal(),
            "metric_updates": chain.telemetry().metric_updates().iter().map(|u| json!({
                "window_index": u.window_index(), "sample_count": u.sample_count(),
                "outcome": format!("{:?}", u.outcome()), "step_before": u.step_before(),
                "step_after_restart": u.step_after_restart(), "mass_diagonal": u.mass_diagonal(),
            })).collect::<Vec<_>>(),
            "target_calls": work.target_calls_total(),
            "retained_target_calls": retained.target_calls_total(),
            "depth_caps": retained.maximum_depth_stops(),
            "divergences": retained.divergences(),
            "refinement_exhaustions": retained.refinement_exhaustion_stops(),
            "invalid_stops": retained.invalid_evaluation_stops(),
            "warmup_divergences": discarded.divergences(),
            "warmup_refinement_exhaustions": discarded.refinement_exhaustion_stops(),
            "refinement_level_built": retained.refinement_level_built(),
            "warmup_refinement_level_built": discarded.refinement_level_built(),
            "reverse_coarser_stops": retained.reverse_coarser_stops(),
            "nonfinite_position_rejections_retained": retained.nonfinite_position_rejections(),
            "nonfinite_position_rejections_warmup": discarded.nonfinite_position_rejections(),
            "warmup_schedule": schedule.map(|s| format!("{s:?}")),
            "warmup_acceptance_mean": mean(&acc),
            "warmup_last_slow_window_acceptance_mean": mean(&last_window),
            "warmup_last50_acceptance_mean": mean(&terminal),
            "warmup_top_level_transitions": warmup_top_level,
            "warmup_exhaustion_stops": warmup_exhaustion_stops,
            "retained_classes": CLASSES.iter().zip(&classes).map(|(k, c)| (k.to_string(), c.json())).collect::<serde_json::Map<_, _>>(),
            "tail_by_quarter": quarters,
            "neck_entries": entries,
            "excursions": excursions.len(),
            "mean_excursion_length": if excursions.is_empty() { 0.0 } else { excursions.iter().sum::<usize>() as f64 / excursions.len() as f64 },
            "max_excursion_length": excursions.iter().copied().max().unwrap_or(0),
            "min_omega": omega.iter().copied().fold(f64::INFINITY, f64::min),
            "max_omega": omega.iter().copied().fold(f64::NEG_INFINITY, f64::max),
            "first_draw_omega": omega.first().copied(),
            "lower_tail_profile": chain_low,
            "upper_tail_profile": chain_high,
            "prefix_tail_mass": chain_prefix_below as f64 / prefix as f64,
            "draws_fnv": format!("{chain_hash:016x}"),
        }));

        let mut in_batch = 0usize;
        let mut chain_below = 0usize;
        let mut chain_columns: Vec<Vec<f64>> = vec![Vec::with_capacity(draws); DIMENSION];
        let mut indicator = Vec::with_capacity(draws);
        let mut indicator6 = Vec::with_capacity(draws);
        for draw in 0..n {
            let sample = chain.sample(draw).expect("draw");
            if sample.iter().any(|v| !v.is_finite()) {
                nonfinite += 1;
            }
            for (col, v) in chain_columns.iter_mut().zip(sample) {
                col.push(*v);
            }
            let w = sample[0];
            total += 1;
            let is_below = w < -5.0;
            indicator.push(f64::from(is_below));
            indicator6.push(f64::from(w < -6.0));
            if is_below {
                below += 1;
                in_batch += 1;
                chain_below += 1;
            }
            if (draw + 1) % batch == 0 {
                batch_means.push(in_batch as f64 / batch as f64);
                in_batch = 0;
            }
        }
        per_chain_tail.push(chain_below as f64 / n as f64);
        for (all, col) in columns.iter_mut().zip(chain_columns) {
            all.push(col);
        }
        indicator_columns.push(indicator);
        indicator6_columns.push(indicator6);
    }
    let estimate = below as f64 / total as f64;
    let batches = batch_means.len() as f64;
    let batch_variance = batch_means
        .iter()
        .map(|mean| (mean - estimate) * (mean - estimate))
        .sum::<f64>()
        / (batches - 1.0);
    let batch_se = (batch_variance / batches).sqrt();
    let z_batch = (estimate - EXACT_TAIL_MASS) / batch_se;
    let indicator_refs: Vec<&[f64]> = indicator_columns.iter().map(Vec::as_slice).collect();
    let mcse = mcse_mean(&indicator_refs);
    let z = (estimate - EXACT_TAIL_MASS) / mcse;
    let indicator6_refs: Vec<&[f64]> = indicator6_columns.iter().map(Vec::as_slice).collect();
    let estimate6 = indicator6_columns.iter().flatten().sum::<f64>() / total as f64;
    let mcse6 = mcse_mean(&indicator6_refs);

    let mut coord = Vec::with_capacity(DIMENSION);
    for col in &columns {
        let refs: Vec<&[f64]> = col.iter().map(Vec::as_slice).collect();
        coord.push((ess_bulk(&refs), ess_tail(&refs), rhat(&refs)));
    }
    let min_bulk = coord.iter().map(|c| c.0).fold(f64::INFINITY, f64::min);
    let min_tail = coord.iter().map(|c| c.1).fold(f64::INFINITY, f64::min);
    let max_rhat = coord.iter().map(|c| c.2).fold(f64::NEG_INFINITY, f64::max);
    let omega_cols = &columns[0];
    let flat_n = total as f64;
    let omega_mean = omega_cols.iter().flatten().sum::<f64>() / flat_n;
    let omega_variance = omega_cols
        .iter()
        .flatten()
        .map(|w| (w - omega_mean).powi(2))
        .sum::<f64>()
        / (flat_n - 1.0);
    let calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let retained_calls: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().target_calls_total())
        .sum();
    let warnings = posterior.chain_warnings();
    let warnings_json: Vec<Value> = warnings
        .iter()
        .map(|w| {
            let debug = format!("{w:?}");
            let kind = debug.split([' ', '{']).next().unwrap_or("").to_string();
            json!({"chain": w.chain(), "kind": kind, "message": w.to_string(), "debug": debug})
        })
        .collect();
    let profile_low: Vec<Value> = thresholds_low
        .iter()
        .zip(&low_counts)
        .map(|(c, k)| {
            let exact = std_normal_cdf(c / 3.0);
            let est = *k as f64 / total as f64;
            json!({"c": c, "estimate": est, "count": k, "exact_approx": exact, "relative_error": est / exact - 1.0})
        })
        .collect();
    let profile_high: Vec<Value> = thresholds_high
        .iter()
        .zip(&high_counts)
        .map(|(c, k)| {
            let exact = std_normal_cdf(-c / 3.0);
            let est = *k as f64 / total as f64;
            json!({"c": c, "estimate": est, "count": k, "exact_approx": exact, "relative_error": est / exact - 1.0})
        })
        .collect();
    let payload = json!({
        "schema": "gradient-metric-v1-funnel",
        "default_max_refinement_levels": DEFAULT_MAX_REFINEMENT_LEVELS,
        "draws_fnv": format!("{cell_hash:016x}"),
        "arm": arm_name,
        "adaptation": format!("{adaptation:?}"),
        "u_turn": format!("{:?}", kernel.options().u_turn),
        "exhaustion_retained": format!("{:?}", kernel.options().exhaustion),
        "metric_regularization": format!("{:?}", owalnuts::sampler::DEFAULT_METRIC_REGULARIZATION),
        "warmup_exhaustion_rule": format!("{:?}", owalnuts::sampler::DEFAULT_WARMUP_EXHAUSTION),
        "kernel_tuning": {"step_size": kernel.step_size(), "max_depth": max_depth,
                          "max_refinement_levels": levels,
                          "max_error": kernel.max_error()},
        "starts": starts,
        "seed": seed,
        "chains": 4, "threads": 4, "warmup": warmup, "draws": draws,
        "tail_mass": {"estimate": estimate, "mcse": mcse, "z": z,
                      "batch_means_se": batch_se, "z_batch_means": z_batch, "batch": batch,
                      "exact": EXACT_TAIL_MASS, "below": below, "total": total,
                      "batches": batch_means.len(), "per_chain": per_chain_tail,
                      "prefix_draws_per_chain": PREFIX_DRAWS.min(draws),
                      "prefix_estimate": prefix_below as f64 / prefix_total as f64},
        "tail_mass_6": {"estimate": estimate6, "mcse": mcse6,
                        "z": (estimate6 - EXACT_TAIL_MASS_6) / mcse6, "exact": EXACT_TAIL_MASS_6},
        "lower_tail_profile": profile_low,
        "upper_tail_profile": profile_high,
        "omega": {"mean": omega_mean, "variance": omega_variance,
                  "exact_variance": EXACT_OMEGA_VARIANCE,
                  "bulk_ess": coord[0].0, "tail_ess": coord[0].1, "rhat": coord[0].2},
        "min_bulk_ess": min_bulk,
        "min_tail_ess": min_tail,
        "max_rhat": max_rhat,
        "per_coordinate": coord.iter().map(|c| json!({"bulk_ess": c.0, "tail_ess": c.1, "rhat": c.2})).collect::<Vec<_>>(),
        "nonfinite_draws": nonfinite,
        "target_calls_total": calls,
        "retained_target_calls": retained_calls,
        "min_bulk_ess_per_gradient": min_bulk / calls as f64,
        "retained_classes": CLASSES.iter().zip(&pooled_classes).map(|(k, c)| (k.to_string(), c.json())).collect::<serde_json::Map<_, _>>(),
        "chain_warnings": warnings_json,
        "chain_warning_lines": owalnuts::diagnostics::ChainWarning::lines(&warnings),
        "wall_seconds_pinned_cotenanted": wall,
        "chains_data": chains_json,
        "algorithm_revision": posterior.algorithm_revision(),
    });
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    let divergences: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().retained().divergences())
        .sum();
    let neck = &pooled_classes[1];
    let deep = &pooled_classes[2];
    eprintln!(
        "funnel {arm_name} {warmup}/{draws} seed {seed}: P(omega < -5) {estimate:.4} +- {mcse:.4} \
         (z {z:+.2}), P(omega > 5) {:.4}, divergences {divergences}, min bulk ESS {min_bulk:.0}, \
         neck/deep transitions {}/{} (top level {}/{}, exhausted {}/{}), {calls} target calls, \
         warnings {}, wall {wall:.1}s",
        high_counts[4] as f64 / total as f64,
        neck.n,
        deep.n,
        neck.level.last().unwrap_or(&0),
        deep.level.last().unwrap_or(&0),
        neck.stops[3],
        deep.stops[3],
        warnings.len()
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [arm, warmup, draws, seed, out] => {
            match (warmup.parse::<usize>(), draws.parse::<usize>(), seed.parse::<u64>()) {
                (Ok(w), Ok(d), Ok(s)) => run(arm, w, d, s, Path::new(out)),
                _ => Err("warmup, draws and seed must be integers".into()),
            }
        }
        _ => Err("usage: funnel <default|gradmetric|gradmetric-overlap> <warmup> <draws> <seed> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
