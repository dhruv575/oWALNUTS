//! WP17: canonical-v3 (scale-non-centered innovations) versus canonical-v2
//! (a=1 centered) on sspd-10 / sspd-11 / sspd-05.
//!
//! Arms: V2-I (v2, adapted diagonal, standard DA), V3-D (v3, adapted
//! diagonal, standard DA), V3-A (v3, adapted diagonal, JMLR Appendix C
//! adaptation, 8 refinement levels), V2-A (secondary: v2 a=1 + Appendix C).
//! Arm N3 (NumPyro on the v3 density) lives in `numpyro_reference.py`.

mod canonical;
mod v3;

use std::fs;
use std::io::Write;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

use canonical::{CenteredTarget, Data, latent_path_from_innovations};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, Error, InitialStepSearchConfig, KernelTuning, MultiChainOutput,
    PAPER_ADAPTATION_REVISION, PaperAdaptationConfig, PaperAdaptationOutcome, RunConfig, RunControl,
    StopReason, Target, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains, preflight_chains_with_target_budget, sample_chains_with_control,
    sample_chains_with_target_budget_and_control,
};
use serde_json::{Value, json};

const FUNCTIONALS: [&str; 8] = ["mu", "sigma_x", "alpha", "beta", "gamma", "nu", "x_terminal", "x_path_mean"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Arm {
    V2I,
    V3D,
    V3A,
    V2A,
}

impl Arm {
    fn parse(s: &str) -> Option<Arm> {
        match s {
            "V2-I" => Some(Arm::V2I),
            "V3-D" => Some(Arm::V3D),
            "V3-A" => Some(Arm::V3A),
            "V2-A" => Some(Arm::V2A),
            _ => None,
        }
    }
    fn code(self) -> &'static str {
        match self {
            Arm::V2I => "V2-I",
            Arm::V3D => "V3-D",
            Arm::V3A => "V3-A",
            Arm::V2A => "V2-A",
        }
    }
    fn label(self) -> &'static str {
        match self {
            Arm::V2I => "canonical-v2 a=1 centered, identity initial diagonal, mass adaptation on, standard dual averaging (control)",
            Arm::V3D => "canonical-v3 scale-non-centered innovations, identity initial diagonal, mass adaptation on, standard dual averaging",
            Arm::V3A => "canonical-v3 scale-non-centered innovations, identity initial diagonal, mass adaptation on, JMLR Appendix C adaptation (Delta 2, p_a .95, Gamma .8), 8 refinement levels",
            Arm::V2A => "SECONDARY: canonical-v2 a=1 centered, identity initial diagonal, mass adaptation on, JMLR Appendix C adaptation, 8 refinement levels",
        }
    }
    fn is_v3(self) -> bool {
        matches!(self, Arm::V3D | Arm::V3A)
    }
    fn is_paper(self) -> bool {
        matches!(self, Arm::V3A | Arm::V2A)
    }
}

enum StudyTarget {
    V2(CenteredTarget),
    V3(v3::V3Target),
}

impl Target for StudyTarget {
    fn dimension(&self) -> usize {
        match self {
            StudyTarget::V2(t) => t.dimension(),
            StudyTarget::V3(t) => t.dimension(),
        }
    }
    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, owalnuts::walnutpie::TargetError> {
        match self {
            StudyTarget::V2(t) => t.log_density_gradient(position, gradient),
            StudyTarget::V3(t) => t.log_density_gradient(position, gradient),
        }
    }
}

impl StudyTarget {
    fn calls(&self) -> usize {
        match self {
            StudyTarget::V2(t) => t.calls.load(Ordering::Relaxed),
            StudyTarget::V3(t) => t.calls.load(Ordering::Relaxed),
        }
    }
}

struct Common {
    chains: usize,
    threads: usize,
    discarded: usize,
    retained: usize,
    max_depth: usize,
    wall_cap: f64,
    // standard arms
    std_initial_step: f64,
    std_levels: usize,
    std_max_error: f64,
    std_target_acceptance: f64,
    // paper arms
    paper_initial_step: f64,
    paper_levels: usize,
    paper_initial_max_error: f64,
    paper_delta: f64,
    paper_pa: f64,
    paper_gamma: f64,
    paper_callback_cap: usize,
}

fn common(protocol: &Value) -> Common {
    let c = &protocol["owalnuts_common"];
    let s = &protocol["standard_adaptation"];
    let p = &protocol["paper_adaptation"];
    let u = |v: &Value| v.as_u64().unwrap() as usize;
    let f = |v: &Value| v.as_f64().unwrap();
    Common {
        chains: u(&c["chains"]),
        threads: u(&c["threads"]),
        discarded: u(&c["discarded"]),
        retained: u(&c["retained"]),
        max_depth: u(&c["max_depth"]),
        wall_cap: f(&c["wall_cap_seconds"]),
        std_initial_step: f(&s["initial_step"]),
        std_levels: u(&s["max_refinement_levels"]),
        std_max_error: f(&s["max_error"]),
        std_target_acceptance: f(&s["target_acceptance"]),
        paper_initial_step: f(&p["initial_step"]),
        paper_levels: u(&p["max_refinement_levels"]),
        paper_initial_max_error: f(&p["initial_max_error"]),
        paper_delta: f(&p["global_energy_bound"]),
        paper_pa: f(&p["quantile_probability"]),
        paper_gamma: f(&p["unrefined_fraction_target"]),
        paper_callback_cap: u(&p["runtime_callback_cap"]),
    }
}

fn numbers(value: &Value) -> Vec<f64> {
    value.as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect()
}

fn sha256_hex(bytes: &[u8]) -> String {
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
    ];
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
    ];
    let mut msg = bytes.to_vec();
    let bit_len = (bytes.len() as u64).wrapping_mul(8);
    msg.push(0x80);
    while msg.len() % 64 != 56 {
        msg.push(0);
    }
    msg.extend_from_slice(&bit_len.to_be_bytes());
    for chunk in msg.chunks(64) {
        let mut w = [0u32; 64];
        for i in 0..16 {
            w[i] = u32::from_be_bytes([chunk[4 * i], chunk[4 * i + 1], chunk[4 * i + 2], chunk[4 * i + 3]]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16].wrapping_add(s0).wrapping_add(w[i - 7]).wrapping_add(s1);
        }
        let mut a = h;
        for i in 0..64 {
            let s1 = a[4].rotate_right(6) ^ a[4].rotate_right(11) ^ a[4].rotate_right(25);
            let ch = (a[4] & a[5]) ^ (!a[4] & a[6]);
            let t1 = a[7].wrapping_add(s1).wrapping_add(ch).wrapping_add(K[i]).wrapping_add(w[i]);
            let s0 = a[0].rotate_right(2) ^ a[0].rotate_right(13) ^ a[0].rotate_right(22);
            let maj = (a[0] & a[1]) ^ (a[0] & a[2]) ^ (a[1] & a[2]);
            let t2 = s0.wrapping_add(maj);
            a = [t1.wrapping_add(t2), a[0], a[1], a[2], a[3].wrapping_add(t1), a[4], a[5], a[6]];
        }
        for i in 0..8 {
            h[i] = h[i].wrapping_add(a[i]);
        }
    }
    h.iter().map(|x| format!("{x:08x}")).collect()
}

/// Functionals from a draw in the arm's own coordinates.
fn functionals(draw: &[f64], arm: Arm) -> [f64; 8] {
    let q = if arm.is_v3() { v3::to_innovations(draw) } else { canonical::to_innovations(draw, 1.0) };
    let path = latent_path_from_innovations(&q);
    let mean = path.iter().sum::<f64>() / path.len() as f64;
    [q[0], q[1].exp(), q[2].exp(), q[3].exp(), q[4].exp(), 2.0 + q[5].exp(), *path.last().unwrap(), mean]
}

fn run_config(c: &Common, seed: u64, arm: Arm) -> RunConfig {
    if arm.is_paper() {
        let tuning = KernelTuning::new(
            c.paper_initial_step,
            NonZeroUsize::new(c.max_depth).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(c.paper_levels).unwrap(),
            c.paper_initial_max_error,
        )
        .unwrap();
        let paper = PaperAdaptationConfig::new(c.paper_delta, c.paper_pa, c.paper_gamma).unwrap();
        let warmup = WarmupConfig::default()
            .with_mass_adaptation(true)
            .with_step_size_adaptation(true)
            .with_paper_adaptation(paper);
        RunConfig::new(c.discarded, NonZeroUsize::new(c.retained).unwrap(), seed)
            .with_tuning(tuning)
            .with_warmup(warmup)
            .with_maximum_depth_stop_limit(usize::MAX)
    } else {
        let tuning = KernelTuning::new(
            c.std_initial_step,
            NonZeroUsize::new(c.max_depth).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(c.std_levels).unwrap(),
            c.std_max_error,
        )
        .unwrap();
        let warmup = WarmupConfig::new(c.std_target_acceptance)
            .unwrap()
            .with_mass_adaptation(true)
            .with_step_size_adaptation(true)
            .with_initial_step_search(InitialStepSearchConfig::default());
        RunConfig::new(c.discarded, NonZeroUsize::new(c.retained).unwrap(), seed)
            .with_tuning(tuning)
            .with_warmup(warmup)
            .with_maximum_depth_stop_limit(usize::MAX)
    }
}

fn fmt(x: f64) -> Value {
    assert!(x.is_finite(), "non-finite value in JSON output");
    json!(x)
}

fn quantiles(mut v: Vec<f64>) -> Value {
    if v.is_empty() {
        return json!(null);
    }
    v.sort_by(f64::total_cmp);
    let q = |p: f64| v[((v.len() - 1) as f64 * p).round() as usize];
    json!({"p50": fmt(q(0.5)), "p90": fmt(q(0.9)), "p95": fmt(q(0.95)), "p99": fmt(q(0.99)), "max": fmt(*v.last().unwrap())})
}

fn outcome_name(o: PaperAdaptationOutcome) -> &'static str {
    match o {
        PaperAdaptationOutcome::Installed => "installed",
        PaperAdaptationOutcome::InsufficientOrbits => "insufficient_orbits",
        PaperAdaptationOutcome::NonFinite => "non_finite",
        PaperAdaptationOutcome::Disabled => "disabled",
        _ => "other",
    }
}

#[allow(clippy::too_many_arguments)]
fn summarize(
    arm: Arm,
    fixture: &str,
    fixture_sha: &str,
    seed: u64,
    c: &Common,
    kernel_commit: &str,
    preflight: (usize, usize, usize),
    calls: usize,
    wall: f64,
    output: &MultiChainOutput,
) -> Value {
    let levels = if arm.is_paper() { c.paper_levels } else { c.std_levels };
    let mut depth_hist = vec![0usize; c.max_depth + 1];
    let mut counts = [0usize; 6];
    let mut refinement_hist = vec![0usize; levels + 1];
    let mut retained_calls = 0usize;
    let mut total_calls = 0usize;
    let mut retained_transitions = 0usize;
    let mut warmup_divergences = 0usize;
    let mut divergences = 0usize;
    let mut reverse_rejections = 0usize;
    let mut zero_density = 0usize;
    let mut steps = Vec::new();
    let mut final_max_error = Vec::new();
    let mut mass_globals = Vec::new();
    let mut energy_errors = Vec::new();
    let mut energy_ranges = Vec::new();
    let mut unrefined_leaves = 0usize;
    let mut built_leaves = 0usize;
    let mut paper_updates = Vec::new();
    for (chain_index, chain) in output.chains().iter().enumerate() {
        steps.push(chain.metadata().qualified_step_size());
        final_max_error.push(chain.metadata().tuning().max_error());
        mass_globals.push(chain.metadata().mass_diagonal()[..6].to_vec());
        total_calls += chain.telemetry().total().target_calls_total();
        retained_calls += chain.telemetry().retained().target_calls_total();
        warmup_divergences += chain.telemetry().discarded().divergences();
        for d in &chain.diagnostics()[c.discarded..] {
            retained_transitions += 1;
            depth_hist[d.depth().min(c.max_depth)] += 1;
            let idx = match d.stop() {
                StopReason::MaximumDepth => 0,
                StopReason::OuterUTurn => 1,
                StopReason::RecursiveUTurn => 2,
                StopReason::RefinementExhausted => 3,
                StopReason::ReverseCoarserAccepted => 4,
                _ => 5,
            };
            counts[idx] += 1;
            reverse_rejections += d.reverse_coarser_rejections();
            zero_density += d.zero_density_evaluations();
            let level = d.selected_refinement_level().unwrap_or(levels).min(levels);
            refinement_hist[level] += 1;
            if level == 0 {
                unrefined_leaves += d.leaves_built();
            }
            built_leaves += d.leaves_built();
            if d.divergent() {
                divergences += 1;
            }
            energy_errors.push(d.maximum_absolute_energy_error());
            energy_ranges.push(d.maximum_hamiltonian() - d.minimum_hamiltonian());
        }
        for u in chain.telemetry().paper_adaptation_updates() {
            paper_updates.push(json!({
                "chain": chain_index,
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
                "outcome": outcome_name(u.outcome()),
                "dual_averaging_restarted": u.dual_averaging_restarted(),
                "transitions_without_statistic": u.transitions_without_statistic(),
            }));
        }
    }
    let mut median_depth = 0usize;
    let mut cumulative = 0usize;
    for (depth, count) in depth_hist.iter().enumerate() {
        cumulative += count;
        if cumulative * 2 >= retained_transitions {
            median_depth = depth;
            break;
        }
    }
    json!({
        "arm": arm.code(),
        "arm_label": arm.label(),
        "backend": "owalnuts",
        "model_revision": if arm.is_v3() { v3::MODEL_REVISION } else { canonical::MODEL_REVISION },
        "fixture": fixture,
        "fixture_sha256": fixture_sha,
        "seed": seed,
        "dimension": output.chains()[0].metadata().dimension(),
        "algorithm_revision": ALGORITHM_REVISION,
        "paper_adaptation_revision": if arm.is_paper() { Some(PAPER_ADAPTATION_REVISION) } else { None },
        "kernel_commit": kernel_commit,
        "settings": {"chains": c.chains, "threads": c.threads, "discarded": c.discarded, "retained": c.retained, "max_depth": c.max_depth,
                     "max_refinement_levels": levels,
                     "adaptation": if arm.is_paper() { "appendix-c" } else { "dual-averaging-0.8" }},
        "preflight": {"worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2},
        "wall_seconds": fmt(wall),
        "target_calls_counter": calls,
        "target_calls_telemetry_total": total_calls,
        "target_calls_retained": retained_calls,
        "retained_transitions": retained_transitions,
        "depth_histogram": depth_hist,
        "median_depth": median_depth,
        "max_depth_rate": fmt(counts[0] as f64 / retained_transitions as f64),
        "stops": {"maximum_depth": counts[0], "outer_uturn": counts[1], "recursive_uturn": counts[2],
                  "refinement_exhausted": counts[3], "reverse_coarser_accepted": counts[4], "other": counts[5]},
        "retained_divergences": divergences,
        "warmup_divergences": warmup_divergences,
        "retained_invalid_evaluations": counts[5],
        "retained_refinement_exhaustions": counts[3],
        "retained_reverse_coarser_rejections": reverse_rejections,
        "retained_zero_density_evaluations": zero_density,
        "selected_refinement_level_histogram": refinement_hist,
        "retained_unrefined_leaf_fraction": fmt(if built_leaves > 0 { unrefined_leaves as f64 / built_leaves as f64 } else { 0.0 }),
        "retained_max_abs_energy_error_quantiles": quantiles(energy_errors),
        "retained_orbit_energy_range_quantiles": quantiles(energy_ranges),
        "final_step_sizes": steps,
        "final_max_error": final_max_error,
        "final_mass_diagonal_globals": mass_globals,
        "paper_adaptation_updates": paper_updates,
    })
}

fn write_functionals(path: &Path, output: &MultiChainOutput, arm: Arm) -> Vec<f64> {
    let mut file = fs::File::create(path).unwrap();
    let mut means = vec![0.0; 8];
    let mut n = 0usize;
    for chain in output.chains() {
        let dim = chain.metadata().dimension();
        let mut bytes = Vec::with_capacity(chain.samples().len() / dim * 64);
        for draw in chain.samples().chunks(dim) {
            let f = functionals(draw, arm);
            for (m, v) in means.iter_mut().zip(f) {
                *m += v;
            }
            n += 1;
            for v in f {
                bytes.extend_from_slice(&v.to_le_bytes());
            }
        }
        file.write_all(&bytes).unwrap();
    }
    means.iter().map(|m| m / n as f64).collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut fixtures = "sspd-10,sspd-11,sspd-05".to_string();
    let mut arms = "V2-I,V3-D,V3-A,V2-A".to_string();
    let mut out = PathBuf::from("artifacts/owalnuts-v1");
    let mut kernel_commit = "unknown".to_string();
    let mut preflight_only = false;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--fixtures" => { fixtures = args[i + 1].clone(); i += 2; }
            "--arms" => { arms = args[i + 1].clone(); i += 2; }
            "--out" => { out = PathBuf::from(&args[i + 1]); i += 2; }
            "--kernel-commit" => { kernel_commit = args[i + 1].clone(); i += 2; }
            "--preflight-only" => { preflight_only = true; i += 1; }
            other => panic!("unknown argument {other}"),
        }
    }
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let protocol: Value = serde_json::from_slice(&fs::read(here.join("protocol.json")).unwrap()).unwrap();
    let c = common(&protocol);
    fs::create_dir_all(out.join("draws")).unwrap();
    let arms: Vec<Arm> = arms.split(',').map(|s| Arm::parse(s).expect("arm")).collect();
    let mut index = Vec::new();
    let mut preflights = Vec::new();
    for key in fixtures.split(',') {
        let entry = &protocol["fixtures"][key];
        let fixture_path = here.join("fixtures").join(entry["file"].as_str().unwrap());
        let bytes = fs::read(&fixture_path).unwrap();
        let sha = sha256_hex(&bytes);
        assert_eq!(sha, entry["sha256"].as_str().unwrap(), "fixture hash mismatch for {key}");
        let fixture: Value = serde_json::from_slice(&bytes).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["s"]),
            &numbers(&fixture["data"]["v"]),
        )
        .unwrap();
        let seed = protocol["seeds"][key].as_u64().unwrap();
        let starts_doc: Value = serde_json::from_slice(&fs::read(here.join("starts").join(format!("{key}.json"))).unwrap()).unwrap();
        assert_eq!(starts_doc["fixture_sha256"].as_str().unwrap(), sha);
        let base = data.initial_innovations();
        let mu_offsets = numbers(&protocol["starts"]["mu_offsets"]);
        let starts_q: Vec<Vec<f64>> = starts_doc["starts"].as_array().unwrap().iter().map(numbers).collect();
        assert_eq!(starts_q.len(), c.chains);
        for (chain, start) in starts_q.iter().enumerate() {
            for (j, value) in start.iter().enumerate() {
                let expected = base[j] + if j == 0 { mu_offsets[chain] } else { 0.0 };
                assert!((value - expected).abs() <= 1e-9 * (1.0 + expected.abs()), "start mismatch {key} chain {chain} coord {j}");
            }
        }
        for arm in &arms {
            let starts: Vec<Vec<f64>> = starts_q
                .iter()
                .map(|q| if arm.is_v3() { v3::from_innovations(q) } else { canonical::from_innovations(q, 1.0) })
                .collect();
            let target = if arm.is_v3() {
                StudyTarget::V3(v3::V3Target { data: data.clone(), calls: AtomicUsize::new(0) })
            } else {
                StudyTarget::V2(CenteredTarget { data: data.clone(), a: 1.0, calls: AtomicUsize::new(0) })
            };
            let dim = data.dim();
            let mass = DiagonalMass::identity(NonZeroUsize::new(dim).unwrap());
            let config = run_config(&c, seed, *arm);
            let control = RunControl::new().with_timeout(Duration::from_secs_f64(c.wall_cap)).unwrap();
            eprintln!("{key} seed={seed} arm={} dim={dim}", arm.code());
            let stem = format!("{key}-{}-{seed}", arm.code());
            let started = Instant::now();
            let (preflight, result): ((usize, usize, usize), Option<Result<MultiChainOutput, Error>>) = if arm.is_paper() {
                let exact = config.worst_case_target_evaluations(NonZeroUsize::new(c.chains).unwrap()).unwrap();
                let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
                let budget = TargetEvaluationBudget::new(NonZeroUsize::new(c.paper_callback_cap.min(exact)).unwrap());
                let report = preflight_chains_with_target_budget(&target, &starts, &mass, &config, admission, &budget).unwrap();
                let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), target.calls());
                assert_eq!(budget.started(), 0, "preflight consumed budget");
                let r = if preflight_only {
                    None
                } else {
                    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
                    Some(sample_chains_with_target_budget_and_control(&target, &starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), admission, &budget, &control))
                };
                (pre, r)
            } else {
                let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), target.calls());
                let r = if preflight_only {
                    None
                } else {
                    Some(sample_chains_with_control(&target, &starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), &control))
                };
                (pre, r)
            };
            assert_eq!(preflight.2, 0, "preflight started target callbacks");
            preflights.push(json!({"fixture": key, "arm": arm.code(), "worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2}));
            let Some(result) = result else { continue };
            let wall = started.elapsed().as_secs_f64();
            let calls = target.calls();
            match result {
                Ok(output) => {
                    let mut summary = summarize(*arm, key, &sha, seed, &c, &kernel_commit, preflight, calls, wall, &output);
                    let means = write_functionals(&out.join("draws").join(format!("{stem}.f64")), &output, *arm);
                    summary["functional_means"] = Value::Object(FUNCTIONALS.iter().zip(means).map(|(n, m)| (n.to_string(), json!(m))).collect());
                    summary["functionals_file"] = json!(format!("draws/{stem}.f64"));
                    eprintln!(
                        "  done {wall:.1}s calls {calls} median depth {} cap rate {} sigma_x mean {}",
                        summary["median_depth"], summary["max_depth_rate"], summary["functional_means"]["sigma_x"]
                    );
                    fs::write(out.join(format!("{stem}.json")), serde_json::to_string_pretty(&summary).unwrap()).unwrap();
                }
                Err(e) => {
                    let failure = json!({
                        "arm": arm.code(), "fixture": key, "seed": seed, "status": "failed",
                        "error_kind": format!("{:?}", e.kind()), "error": e.to_string(),
                        "wall_seconds": fmt(wall), "target_calls_counter": calls,
                        "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit,
                        "preflight": {"worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2},
                    });
                    eprintln!("  FAILED {:?}: {e}", e.kind());
                    fs::write(out.join(format!("{stem}.json")), serde_json::to_string_pretty(&failure).unwrap()).unwrap();
                }
            }
            index.push(stem);
        }
    }
    if preflight_only {
        fs::write(out.join("preflight.json"), serde_json::to_string_pretty(&json!({"algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit, "preflights": preflights})).unwrap()).unwrap();
        return;
    }
    fs::write(
        out.join("index.json"),
        serde_json::to_string_pretty(&json!({"schema": "canonical-v3-scale-noncentered-v1/runs", "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit, "runs": index, "preflights": preflights})).unwrap(),
    )
    .unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_matches_known_vector() {
        assert_eq!(sha256_hex(b"abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    }

    #[test]
    fn functionals_agree_between_v2_and_v3_coordinates() {
        let fixture: Value = serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        let q = data.initial_innovations();
        let f2 = functionals(&canonical::from_innovations(&q, 1.0), Arm::V2I);
        let f3 = functionals(&v3::from_innovations(&q), Arm::V3D);
        for (a, b) in f2.iter().zip(f3) {
            assert!((a - b).abs() < 1e-9 * (1.0 + a.abs()));
        }
    }
}
