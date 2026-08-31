#![forbid(unsafe_code)]

//! Truncated-Gaussian stationarity runner (WP10). A 2-D standard normal is
//! truncated to `x_0 > 0` purely through `TargetError::recoverable`; every
//! retained draw must satisfy the constraint and the moments must match the
//! exact half-normal / normal marginals. Usage: `runner --preflight out.json`
//! or `runner --sample out.json`.

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, RunConfig, StopReason, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, preflight_chains_with_target_budget,
    sample_chains_with_target_budget,
};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs,
    num::NonZeroUsize,
    path::{Path, PathBuf},
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

struct HalfSpaceGaussian {
    calls: AtomicUsize,
    failures: AtomicUsize,
}

impl Target for HalfSpaceGaussian {
    fn dimension(&self) -> usize {
        2
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        if q[0] <= 0.0 {
            self.failures.fetch_add(1, Ordering::Relaxed);
            return Err(TargetError::recoverable("outside the half space"));
        }
        gradient[0] = -q[0];
        gradient[1] = -q[1];
        Ok(-0.5 * (q[0] * q[0] + q[1] * q[1]))
    }
}

fn load(dir: &Path, file: &str) -> Result<Value, Box<dyn Error>> {
    Ok(serde_json::from_slice(&fs::read(dir.join(file))?)?)
}

fn stop_name(stop: StopReason) -> &'static str {
    match stop {
        StopReason::MaximumDepth => "maximum_depth",
        StopReason::OuterUTurn => "outer_uturn",
        StopReason::RecursiveUTurn => "recursive_uturn",
        StopReason::RefinementExhausted => "refinement_exhausted",
        StopReason::ReverseCoarserAccepted => "reverse_coarser_accepted",
        StopReason::InvalidEvaluation => "invalid_evaluation",
        _ => "other",
    }
}

fn main() -> Result<(), Box<dyn Error>> {
    let dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut arguments = env::args().skip(1);
    let mode = arguments.next().ok_or("mode required")?;
    let output = PathBuf::from(arguments.next().ok_or("output path required")?);
    if output.exists() {
        return Err("refusing to overwrite an artifact".into());
    }
    // `PROTOCOL_FILE` selects a post-hoc protocol; the default is the frozen one.
    let protocol_file = env::var("PROTOCOL_FILE").unwrap_or_else(|_| "protocol.json".to_string());
    let protocol = load(&dir, &protocol_file)?;
    let arm = &protocol["arm"];
    let u = |k: &str| -> Result<usize, Box<dyn Error>> {
        Ok(usize::try_from(arm[k].as_u64().ok_or(k.to_string())?)?)
    };
    let f = |k: &str| -> Result<f64, Box<dyn Error>> { Ok(arm[k].as_f64().ok_or(k.to_string())?) };
    let tuning = KernelTuning::new(
        f("step_size")?,
        NonZeroUsize::new(u("max_depth")?).ok_or("depth")?,
        NonZeroUsize::new(u("min_micro_steps")?).ok_or("min micro")?,
        NonZeroUsize::new(u("max_refinement_levels")?).ok_or("levels")?,
        f("max_error")?,
    )?;
    let config = RunConfig::new(
        u("discarded")?,
        NonZeroUsize::new(u("retained")?).ok_or("retained")?,
        arm["base_seed"].as_u64().ok_or("seed")?,
    )
    .with_tuning(tuning);
    let starts: Vec<Vec<f64>> = protocol["starts"]
        .as_array()
        .ok_or("starts")?
        .iter()
        .map(|s| {
            s.as_array()
                .unwrap()
                .iter()
                .map(|v| v.as_f64().unwrap())
                .collect()
        })
        .collect();
    let mass = DiagonalMass::identity(NonZeroUsize::new(2).unwrap());
    let target = HalfSpaceGaussian {
        calls: AtomicUsize::new(0),
        failures: AtomicUsize::new(0),
    };
    // The exact worst-case bound (depth 6 x 6 levels x 4 x 50,500 transitions)
    // exceeds the conservative 113M admission ceiling, so the explicit
    // budgeted entry points are used with the exact bound as admission limit
    // and a 1e9 runtime callback cap, as in the funnel and Stock-Watson runners.
    let exact = config.worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())?;
    let cap = 1_000_000_000usize.min(exact);
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(cap).unwrap());
    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    if mode == "--preflight" {
        let report =
            preflight_chains_with_target_budget(&target, &starts, &mass, &config, admission, &budget)?;
        let result = json!({
            "schema": "owalnuts-invalid-evaluation-parity-truncated-preflight/v1",
            "algorithm_revision": ALGORITHM_REVISION,
            "worst_case_target_evaluations": report.worst_case_target_evaluations(),
            "admission_ceiling": report.admission_ceiling(),
            "runtime_callback_cap": budget.maximum(),
            "total_transitions": report.total_transitions(),
            "target_callbacks_started": target.calls.load(Ordering::Relaxed),
            "budget_started": budget.started(),
        });
        fs::write(output, serde_json::to_vec_pretty(&result)?)?;
        return Ok(());
    }
    if mode != "--sample" {
        return Err("mode must be --preflight or --sample".into());
    }
    let threads = NonZeroUsize::new(1).unwrap();
    let started = Instant::now();
    let chains = sample_chains_with_target_budget(
        &target, &starts, &mass, &config, threads, admission, &budget,
    )
    .map_err(|e| format!("arm failed closed ({:?}): {e}", e.kind()))?;
    let wall = started.elapsed().as_secs_f64();
    let mut samples = Vec::new();
    let mut chain_reports = Vec::new();
    for chain in chains.chains() {
        let rows: Vec<Vec<f64>> = (0..chain.retained())
            .map(|d| chain.sample(d).unwrap().to_vec())
            .collect();
        let retained = chain.telemetry().retained();
        let diagnostics = &chain.diagnostics()[chain.metadata().discarded()..];
        let mut stops = serde_json::Map::new();
        for d in diagnostics {
            let e = stops.entry(stop_name(d.stop())).or_insert(json!(0));
            *e = json!(e.as_u64().unwrap() + 1);
        }
        let depths: Vec<usize> = diagnostics.iter().map(|d| d.depth()).collect();
        chain_reports.push(json!({
            "retained": {
                "target_calls": retained.target_calls_total(),
                "divergences": retained.divergences(),
                "invalid_evaluation_stops": retained.invalid_evaluation_stops(),
                "refinement_exhaustion_stops": retained.refinement_exhaustion_stops(),
                "reverse_coarser_stops": retained.reverse_coarser_stops(),
                "maximum_depth_stops": retained.maximum_depth_stops(),
                "recoverable_target_failures": retained.recoverable_target_failures(),
                "zero_density_evaluations": retained.zero_density_evaluations(),
                "leaves_attempted": retained.leaves_attempted(),
                "leaves_built": retained.leaves_built(),
                "stops": stops,
                "mean_depth": depths.iter().sum::<usize>() as f64 / depths.len().max(1) as f64,
            }
        }));
        samples.push(rows);
    }
    let result = json!({
        "schema": "owalnuts-invalid-evaluation-parity-truncated-arm/v1",
        "algorithm_revision": ALGORITHM_REVISION,
        "arm": arm,
        "wall_seconds": wall,
        "total_target_calls": target.calls.load(Ordering::Relaxed),
        "total_recoverable_failures": target.failures.load(Ordering::Relaxed),
        "chains": chain_reports,
        "samples": samples,
    });
    fs::write(output, serde_json::to_vec(&result)?)?;
    Ok(())
}
