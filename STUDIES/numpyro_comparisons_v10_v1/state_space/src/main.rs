//! WP14 state-space cells (parts 1 and 2): oWALNUTS arms on `sspd-05` and the
//! real-market T=48 fixture, kernel v10. Runner derived from
//! `STUDIES/sspd11_confirmation_v1/primary/src/main.rs` (WP12); arms are now
//! fully described in `protocol.json` (`parts.*.arms`), each arm runs once per
//! evidence seed, and the path-block arm takes its globals mass from the
//! same-seed adapted-diagonal arm of the same part.
//! Usage: `runner --part 1_sspd05_timing --arms T-F,T-I,T-P --out artifacts/state_space --kernel-commit <sha>`

mod canonical;

use std::fs;
use std::io::Write;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

use canonical::{CenteredTarget, Data, from_innovations, latent_path_from_innovations, to_innovations};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, Error, InitialStepSearchConfig, KernelTuning, MultiChainOutput,
    RunConfig, RunControl, StopReason, StructuredBlockMass, StructuredCovarianceBlock, WarmupConfig,
    preflight_chains, preflight_chains_structured, sample_chains_structured_with_control,
    sample_chains_with_control,
};
use serde_json::{Value, json};

const FUNCTIONALS: [&str; 9] = [
    "mu", "sigma_x", "alpha", "beta", "gamma", "nu", "x_terminal", "x_path_mean", "x_initial",
];

#[derive(Clone, Debug)]
struct ArmSpec {
    code: String,
    centeredness: f64,
    metric: String, // identity_adapted | frozen_diagonal | path_block
    frozen_file: Option<String>,
    globals_mass_from: Option<String>,
    initial_step: f64,
    step_search: bool,
    max_depth: usize,
    levels: usize,
    min_micro: usize,
    max_error: f64,
    target_acceptance: f64,
    discarded: usize,
    retained: usize,
    threads: usize,
    chains: usize,
    wall_cap: f64,
}

fn arm_spec(code: &str, a: &Value) -> ArmSpec {
    let u = |k: &str| a[k].as_u64().unwrap_or_else(|| panic!("arm {code}: {k}")) as usize;
    let f = |k: &str| a[k].as_f64().unwrap_or_else(|| panic!("arm {code}: {k}"));
    ArmSpec {
        code: code.to_string(),
        centeredness: f("centeredness"),
        metric: a["metric"].as_str().unwrap().to_string(),
        frozen_file: a["frozen_diagonal_file"].as_str().map(str::to_string),
        globals_mass_from: a["globals_mass_from"].as_str().map(str::to_string),
        initial_step: f("initial_step"),
        step_search: a["initial_step_search"].as_bool().unwrap(),
        max_depth: u("max_depth"),
        levels: u("max_refinement_levels"),
        min_micro: u("min_micro_steps"),
        max_error: f("max_error"),
        target_acceptance: f("target_acceptance"),
        discarded: u("discarded"),
        retained: u("retained"),
        threads: u("threads"),
        chains: u("chains"),
        wall_cap: f("wall_cap_seconds"),
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

/// Lower-bidiagonal Cholesky factor of the tridiagonal precision.
fn tridiagonal_cholesky(diag: &[f64], off: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let n = diag.len();
    let mut d = vec![0.0; n];
    let mut l = vec![0.0; n.saturating_sub(1)];
    d[0] = diag[0].sqrt();
    for i in 1..n {
        l[i - 1] = off[i - 1] / d[i - 1];
        let value = diag[i] - l[i - 1] * l[i - 1];
        assert!(value > 0.0, "tridiagonal precision is not positive definite at {i}");
        d[i] = value.sqrt();
    }
    (d, l)
}

/// Posterior-precision path block `H = [1/tau^2 at x_1] + Q_rw(sigma_x) + diag(c_t)` (WP4b/WP12).
fn path_precision(data: &Data, q_globals: &[f64]) -> (Vec<f64>, Vec<f64>) {
    let t = data.t();
    let sigma_x = q_globals[1].exp();
    let s2 = 1.0 / (sigma_x * sigma_x);
    let curvature = data.observation_curvature(q_globals);
    let mut diag = vec![0.0; t];
    let off = vec![-s2; t - 1];
    diag[0] += 1.0 / (data.tau * data.tau);
    for i in 0..t {
        if i + 1 < t {
            diag[i] += s2;
        }
        if i > 0 {
            diag[i] += s2;
        }
        diag[i] += curvature[i];
    }
    (diag, off)
}

fn functionals(y: &[f64], a: f64) -> [f64; 9] {
    let q = to_innovations(y, a);
    let path = latent_path_from_innovations(&q);
    let mean = path.iter().sum::<f64>() / path.len() as f64;
    [
        q[0],
        q[1].exp(),
        q[2].exp(),
        q[3].exp(),
        q[4].exp(),
        2.0 + q[5].exp(),
        *path.last().unwrap(),
        mean,
        q[6],
    ]
}

fn run_config(s: &ArmSpec, seed: u64, adapt_mass: bool) -> RunConfig {
    let tuning = KernelTuning::new(
        s.initial_step,
        NonZeroUsize::new(s.max_depth).unwrap(),
        NonZeroUsize::new(s.min_micro).unwrap(),
        NonZeroUsize::new(s.levels).unwrap(),
        s.max_error,
    )
    .unwrap();
    let mut warmup = WarmupConfig::new(s.target_acceptance)
        .unwrap()
        .with_mass_adaptation(adapt_mass)
        .with_step_size_adaptation(true);
    if s.step_search {
        warmup = warmup.with_initial_step_search(InitialStepSearchConfig::default());
    }
    RunConfig::new(s.discarded, NonZeroUsize::new(s.retained).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(warmup)
        .with_maximum_depth_stop_limit(usize::MAX)
}

fn fmt(x: f64) -> Value {
    assert!(x.is_finite(), "non-finite value in JSON output");
    json!(x)
}

#[allow(clippy::too_many_arguments)]
fn summarize(
    s: &ArmSpec,
    fixture: &str,
    fixture_sha: &str,
    seed: u64,
    kernel_commit: &str,
    preflight: (usize, usize, usize),
    calls_before: usize,
    calls_after: usize,
    wall: f64,
    output: &MultiChainOutput,
    extra: Value,
) -> Value {
    let mut depth_hist = vec![0usize; s.max_depth + 1];
    let mut counts = [0usize; 6];
    let mut refinement_hist = vec![0usize; s.levels + 1];
    let mut retained_calls = 0usize;
    let mut discarded_calls = 0usize;
    let mut total_calls = 0usize;
    let mut retained_transitions = 0usize;
    let mut warmup_divergences = 0usize;
    let mut divergences = 0usize;
    let mut reverse_rejections = 0usize;
    let mut zero_density = 0usize;
    let mut steps = Vec::new();
    let mut mean_leaves = 0.0;
    let mut max_energy_error: f64 = 0.0;
    let mut mass_globals = Vec::new();
    for chain in output.chains() {
        steps.push(chain.metadata().qualified_step_size());
        mass_globals.push(chain.metadata().mass_diagonal()[..6].to_vec());
        total_calls += chain.telemetry().total().target_calls_total();
        retained_calls += chain.telemetry().retained().target_calls_total();
        discarded_calls += chain.telemetry().discarded().target_calls_total();
        warmup_divergences += chain.telemetry().discarded().divergences();
        zero_density += chain.telemetry().retained().recoverable_target_failures();
        for d in &chain.diagnostics()[s.discarded..] {
            retained_transitions += 1;
            depth_hist[d.depth().min(s.max_depth)] += 1;
            let idx = match d.stop() {
                StopReason::MaximumDepth => 0,
                StopReason::OuterUTurn => 1,
                StopReason::RecursiveUTurn => 2,
                StopReason::RefinementExhausted => 3,
                StopReason::ReverseCoarserAccepted => 4,
                StopReason::InvalidEvaluation => 5,
                _ => 5,
            };
            counts[idx] += 1;
            reverse_rejections += d.reverse_coarser_rejections();
            refinement_hist[d.selected_refinement_level().unwrap_or(s.levels).min(s.levels)] += 1;
            if d.divergent() {
                divergences += 1;
            }
            mean_leaves += d.leaves_built() as f64;
            max_energy_error = max_energy_error.max(d.maximum_absolute_energy_error());
        }
    }
    mean_leaves /= retained_transitions as f64;
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
        "arm": s.code,
        "backend": "owalnuts",
        "fixture": fixture,
        "fixture_sha256": fixture_sha,
        "centeredness": s.centeredness,
        "metric": s.metric,
        "seed": seed,
        "dimension": output.chains()[0].metadata().dimension(),
        "algorithm_revision": ALGORITHM_REVISION,
        "kernel_commit": kernel_commit,
        "settings": {"chains": s.chains, "threads": s.threads, "discarded": s.discarded, "retained": s.retained,
                      "initial_step": s.initial_step, "initial_step_search": s.step_search, "max_depth": s.max_depth,
                      "min_micro_steps": s.min_micro, "max_refinement_levels": s.levels, "max_error": s.max_error,
                      "target_acceptance": s.target_acceptance},
        "preflight": {"worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2},
        "wall_seconds_total_sampler_call": fmt(wall),
        "timing_note": "one sampler call covering warmup and retained phases; compilation excluded (release binary built beforehand)",
        "target_calls_counter": calls_after - calls_before,
        "target_calls_telemetry_total": total_calls,
        "target_calls_retained": retained_calls,
        "target_calls_discarded": discarded_calls,
        "retained_transitions": retained_transitions,
        "depth_histogram": depth_hist,
        "median_depth": median_depth,
        "max_depth_rate": fmt(counts[0] as f64 / retained_transitions as f64),
        "stops": {"maximum_depth": counts[0], "outer_uturn": counts[1], "recursive_uturn": counts[2],
                  "refinement_exhausted": counts[3], "reverse_coarser_accepted": counts[4], "invalid_evaluation": counts[5]},
        "retained_divergences": divergences,
        "warmup_divergences": warmup_divergences,
        "retained_invalid_evaluations": counts[5],
        "retained_refinement_exhaustions": counts[3],
        "retained_zero_density_evaluations": zero_density,
        "retained_reverse_coarser_rejections": reverse_rejections,
        "selected_refinement_level_histogram": refinement_hist,
        "mean_leaves_built": fmt(mean_leaves),
        "max_abs_energy_error": fmt(max_energy_error),
        "final_step_sizes": steps,
        "final_mass_diagonal_globals": mass_globals,
        "extra": extra,
    })
}

fn write_functionals(path: &Path, output: &MultiChainOutput, a: f64) -> Vec<f64> {
    let mut file = fs::File::create(path).unwrap();
    let mut means = vec![0.0; FUNCTIONALS.len()];
    let mut n = 0usize;
    for chain in output.chains() {
        let dim = chain.metadata().dimension();
        let mut bytes = Vec::with_capacity(chain.samples().len() / dim * 72);
        for draw in chain.samples().chunks(dim) {
            let f = functionals(draw, a);
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

fn geometric_mean_globals(mass: &[Vec<f64>]) -> Vec<f64> {
    (0..6)
        .map(|i| (mass.iter().map(|m| m[i].ln()).sum::<f64>() / mass.len() as f64).exp())
        .collect()
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mut part = String::new();
    let mut arms = String::new();
    let mut out = PathBuf::from("artifacts/state_space");
    let mut kernel_commit = "unknown".to_string();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--part" => part = args[i + 1].clone(),
            "--arms" => arms = args[i + 1].clone(),
            "--out" => out = PathBuf::from(&args[i + 1]),
            "--kernel-commit" => kernel_commit = args[i + 1].clone(),
            other => panic!("unknown argument {other}"),
        }
        i += 2;
    }
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let study = here.parent().unwrap().to_path_buf();
    let protocol: Value = serde_json::from_slice(&fs::read(study.join("protocol.json")).unwrap()).unwrap();
    assert_eq!(
        protocol["kernel"]["expected_algorithm_revision"].as_str().unwrap(),
        ALGORITHM_REVISION,
        "kernel revision mismatch"
    );
    let part_doc = &protocol["parts"][&part];
    assert!(part_doc.is_object(), "unknown part {part}");
    let key = part_doc["fixture"].as_str().unwrap();
    let entry = &protocol["fixtures"][key];
    let fixture_path = study.join("fixtures").join(entry["file"].as_str().unwrap());
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
    let seeds: Vec<u64> = protocol["seeds"]["evidence"].as_array().unwrap().iter().map(|v| v.as_u64().unwrap()).collect();
    let starts_doc: Value = serde_json::from_slice(&fs::read(study.join("starts").join(format!("{key}.json"))).unwrap()).unwrap();
    assert_eq!(starts_doc["fixture_sha256"].as_str().unwrap(), sha);
    let base = data.initial_innovations();
    let mu_offsets = numbers(&protocol["starts"]["mu_offsets"]);
    let starts_q: Vec<Vec<f64>> = starts_doc["starts"].as_array().unwrap().iter().map(numbers).collect();
    for (chain, start) in starts_q.iter().enumerate() {
        for (j, value) in start.iter().enumerate() {
            let expected = base[j] + if j == 0 { mu_offsets[chain] } else { 0.0 };
            assert!((value - expected).abs() <= 1e-9 * (1.0 + expected.abs()), "start mismatch {key} chain {chain} coord {j}");
        }
    }
    fs::create_dir_all(out.join("draws")).unwrap();
    let arm_codes: Vec<String> = if arms.is_empty() {
        part_doc["arm_order"].as_array().unwrap().iter().map(|v| v.as_str().unwrap().to_string()).collect()
    } else {
        arms.split(',').map(str::to_string).collect()
    };
    let specs: Vec<ArmSpec> = arm_codes
        .iter()
        .filter(|c| part_doc["arms"][c.as_str()]["backend"] == "owalnuts")
        .map(|c| arm_spec(c, &part_doc["arms"][c.as_str()]))
        .collect();
    let mut index = Vec::new();
    for &seed in &seeds {
        let mut globals_mass: std::collections::BTreeMap<String, Vec<f64>> = Default::default();
        for s in &specs {
            let a = s.centeredness;
            assert_eq!(starts_q.len(), s.chains);
            let starts: Vec<Vec<f64>> = starts_q.iter().map(|q| from_innovations(q, a)).collect();
            let target = CenteredTarget { data: data.clone(), a, calls: AtomicUsize::new(0) };
            let dim = data.dim();
            let control = RunControl::new().with_timeout(Duration::from_secs_f64(s.wall_cap)).unwrap();
            let calls_before = target.calls.load(Ordering::Relaxed);
            eprintln!("{part} {key} seed={seed} arm={} dim={dim}", s.code);
            let started = Instant::now();
            let threads = NonZeroUsize::new(s.threads).unwrap();
            let (preflight, result, extra): ((usize, usize, usize), Result<MultiChainOutput, Error>, Value) = match s.metric.as_str() {
                "identity_adapted" => {
                    let mass = DiagonalMass::identity(NonZeroUsize::new(dim).unwrap());
                    let config = run_config(s, seed, true);
                    let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                    let after = target.calls.load(Ordering::Relaxed);
                    let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), after - calls_before);
                    let r = sample_chains_with_control(&target, &starts, &mass, &config, threads, &control);
                    (pre, r, json!({}))
                }
                "frozen_diagonal" => {
                    let file = study.join("fixtures").join(s.frozen_file.as_ref().unwrap());
                    let fb = fs::read(&file).unwrap();
                    let cov = numbers(&serde_json::from_slice::<Value>(&fb).unwrap());
                    assert_eq!(cov.len(), dim, "frozen diagonal dimension");
                    let mass = DiagonalMass::from_diagonal(cov.clone()).unwrap();
                    let config = run_config(s, seed, false);
                    let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                    let after = target.calls.load(Ordering::Relaxed);
                    let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), after - calls_before);
                    let r = sample_chains_with_control(&target, &starts, &mass, &config, threads, &control);
                    (pre, r, json!({"frozen_diagonal_file": s.frozen_file, "frozen_diagonal_sha256": sha256_hex(&fb), "frozen_diagonal_is_momentum_covariance": true}))
                }
                "path_block" => {
                    let from = s.globals_mass_from.as_ref().expect("path_block needs globals_mass_from");
                    let gm = globals_mass.get(from).cloned().unwrap_or_else(|| panic!("arm {from} must run before {}", s.code));
                    let globals_for_path: Vec<f64> = base[..6].to_vec();
                    let (hd, ho) = path_precision(&data, &globals_for_path);
                    let (ld, ls) = tridiagonal_cholesky(&hd, &ho);
                    let blocks = vec![
                        StructuredCovarianceBlock::BidiagonalCholesky { diagonal: gm.iter().map(|m| m.sqrt()).collect(), subdiagonal: vec![0.0; 5] },
                        StructuredCovarianceBlock::BidiagonalCholesky { diagonal: ld, subdiagonal: ls },
                    ];
                    let mass = StructuredBlockMass::new(blocks).unwrap();
                    let config = run_config(s, seed, false);
                    let report = preflight_chains_structured(&target, &starts, &mass, &config).unwrap();
                    let after = target.calls.load(Ordering::Relaxed);
                    let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), after - calls_before);
                    let r = sample_chains_structured_with_control(&target, &starts, &mass, &config, threads, &control);
                    (pre, r, json!({"globals_momentum_covariance": gm, "path_precision_globals_used": globals_for_path,
                                    "path_precision_diag_range": [hd.iter().cloned().fold(f64::INFINITY, f64::min), hd.iter().cloned().fold(0.0, f64::max)],
                                    "path_precision_offdiag": ho[0]}))
                }
                other => panic!("unknown metric {other}"),
            };
            let wall = started.elapsed().as_secs_f64();
            let calls_after = target.calls.load(Ordering::Relaxed);
            let stem = format!("{key}-{}-{seed}", s.code);
            match result {
                Ok(output) => {
                    let mut summary = summarize(s, key, &sha, seed, &kernel_commit, preflight, calls_before, calls_after, wall, &output, extra);
                    let means = write_functionals(&out.join("draws").join(format!("{stem}.f64")), &output, a);
                    summary["functional_names"] = json!(FUNCTIONALS);
                    summary["functional_means"] = Value::Object(FUNCTIONALS.iter().zip(means).map(|(n, m)| (n.to_string(), json!(m))).collect());
                    summary["functionals_file"] = json!(format!("draws/{stem}.f64"));
                    if s.metric == "identity_adapted" {
                        let mass = geometric_mean_globals(&output.chains().iter().map(|ch| ch.metadata().mass_diagonal()[..6].to_vec()).collect::<Vec<_>>());
                        summary["globals_momentum_covariance_geomean"] = json!(mass);
                        globals_mass.insert(s.code.clone(), mass);
                    }
                    eprintln!("  done {wall:.1}s calls {} median depth {} cap rate {}", calls_after - calls_before, summary["median_depth"], summary["max_depth_rate"]);
                    fs::write(out.join(format!("{stem}.json")), serde_json::to_string_pretty(&summary).unwrap()).unwrap();
                }
                Err(e) => {
                    let failure = json!({
                        "arm": s.code, "fixture": key, "seed": seed, "status": "failed",
                        "error_kind": format!("{:?}", e.kind()), "error": e.to_string(),
                        "wall_seconds_total_sampler_call": fmt(wall), "target_calls_counter": calls_after - calls_before,
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
    let index_path = out.join(format!("index-{part}.json"));
    fs::write(
        &index_path,
        serde_json::to_string_pretty(&json!({"schema": "numpyro-comparisons-v10/state-space-runs", "part": part, "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit, "runs": index})).unwrap(),
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
    fn cholesky_reconstructs_path_precision() {
        let fixture: Value = serde_json::from_str(include_str!("../../fixtures/polyscope_parity.json")).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        let base = data.initial_innovations();
        let (hd, ho) = path_precision(&data, &base[..6]);
        let (d, l) = tridiagonal_cholesky(&hd, &ho);
        for i in 0..hd.len() {
            let diag = d[i] * d[i] + if i > 0 { l[i - 1] * l[i - 1] } else { 0.0 };
            assert!((diag - hd[i]).abs() < 1e-9 * hd[i]);
            if i + 1 < hd.len() {
                assert!((d[i] * l[i] - ho[i]).abs() < 1e-9 * ho[i].abs());
            }
        }
    }
}
