//! WP16 runner: arms I (adapted diagonal), P (fixed one-shot path block, WP12
//! verbatim), and R (boundary-refreshed path block) on sspd-11 / sspd-05.
//!
//! One run per `--fixtures/--arms/--retained/--seeds` selection; every arm is
//! preflighted with zero callbacks first. Output schema follows WP12 so the
//! analysis stays comparable.

mod canonical;

use std::fs;
use std::io::Write as _;
use std::num::NonZeroUsize;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

use canonical::{CenteredTarget, Data, from_innovations, latent_path_from_innovations, to_innovations};
use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, Error, InitialStepSearchConfig, KernelTuning,
    MultiChainOutput, RunConfig, RunControl, STRUCTURED_REFRESH_REVISION, StopReason,
    StructuredBlockMass, StructuredCovarianceBlock, StructuredRefreshConfig,
    StructuredRefreshOutcome, WarmupConfig, WindowSummary, preflight_chains,
    preflight_chains_structured, preflight_chains_structured_refresh, sample_chains_structured_refresh,
    sample_chains_structured_with_control, sample_chains_with_control,
};
use serde_json::{Value, json};

const FUNCTIONALS: [&str; 8] = [
    "mu", "sigma_x", "alpha", "beta", "gamma", "nu", "x_terminal", "x_path_mean",
];

#[derive(Clone, Copy, PartialEq, Eq)]
enum Arm {
    I,
    P,
    R,
}

impl Arm {
    fn parse(s: &str) -> Option<Arm> {
        match s {
            "I" => Some(Arm::I),
            "P" => Some(Arm::P),
            "R" => Some(Arm::R),
            _ => None,
        }
    }
    fn code(self) -> &'static str {
        match self {
            Arm::I => "I",
            Arm::P => "P",
            Arm::R => "R",
        }
    }
    fn label(self) -> &'static str {
        match self {
            Arm::I => "a=1 centered, identity initial diagonal, diagonal mass adaptation",
            Arm::P => "a=1 centered, fixed posterior-precision tridiagonal path block + fixed globals diagonal (WP12 arm P)",
            Arm::R => "a=1 centered, boundary-refreshed posterior-precision path block + window-precision globals diagonal",
        }
    }
}

struct Common {
    chains: usize,
    threads: usize,
    discarded: usize,
    retained: usize,
    initial_step: f64,
    max_depth: usize,
    min_micro: usize,
    levels: usize,
    max_error: f64,
    target_acceptance: f64,
    wall_cap: f64,
}

fn common(protocol: &Value) -> Common {
    let c = &protocol["owalnuts_common"];
    Common {
        chains: c["chains"].as_u64().unwrap() as usize,
        threads: c["threads"].as_u64().unwrap() as usize,
        discarded: c["discarded"].as_u64().unwrap() as usize,
        retained: c["retained"].as_u64().unwrap() as usize,
        initial_step: c["initial_step"].as_f64().unwrap(),
        max_depth: c["max_depth"].as_u64().unwrap() as usize,
        min_micro: c["min_micro_steps"].as_u64().unwrap() as usize,
        levels: c["max_refinement_levels"].as_u64().unwrap() as usize,
        max_error: c["max_error"].as_f64().unwrap(),
        target_acceptance: c["target_acceptance"].as_f64().unwrap(),
        wall_cap: c["wall_cap_seconds"].as_f64().unwrap(),
    }
}

fn numbers(value: &Value) -> Vec<f64> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect()
}

fn sha256_hex(bytes: &[u8]) -> String {
    // Minimal SHA-256 (FIPS 180-4) to avoid an extra dependency.
    const K: [u32; 64] = [
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
        0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
        0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
        0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
        0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
        0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
        0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
        0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
        0xc67178f2,
    ];
    let mut h: [u32; 8] = [
        0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
        0x5be0cd19,
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
            w[i] = u32::from_be_bytes([
                chunk[4 * i],
                chunk[4 * i + 1],
                chunk[4 * i + 2],
                chunk[4 * i + 3],
            ]);
        }
        for i in 16..64 {
            let s0 = w[i - 15].rotate_right(7) ^ w[i - 15].rotate_right(18) ^ (w[i - 15] >> 3);
            let s1 = w[i - 2].rotate_right(17) ^ w[i - 2].rotate_right(19) ^ (w[i - 2] >> 10);
            w[i] = w[i - 16]
                .wrapping_add(s0)
                .wrapping_add(w[i - 7])
                .wrapping_add(s1);
        }
        let mut a = h;
        for i in 0..64 {
            let s1 = a[4].rotate_right(6) ^ a[4].rotate_right(11) ^ a[4].rotate_right(25);
            let ch = (a[4] & a[5]) ^ (!a[4] & a[6]);
            let t1 = a[7]
                .wrapping_add(s1)
                .wrapping_add(ch)
                .wrapping_add(K[i])
                .wrapping_add(w[i]);
            let s0 = a[0].rotate_right(2) ^ a[0].rotate_right(13) ^ a[0].rotate_right(22);
            let maj = (a[0] & a[1]) ^ (a[0] & a[2]) ^ (a[1] & a[2]);
            let t2 = s0.wrapping_add(maj);
            a = [
                t1.wrapping_add(t2),
                a[0],
                a[1],
                a[2],
                a[3].wrapping_add(t1),
                a[4],
                a[5],
                a[6],
            ];
        }
        for i in 0..8 {
            h[i] = h[i].wrapping_add(a[i]);
        }
    }
    h.iter().map(|x| format!("{x:08x}")).collect()
}

/// Lower-bidiagonal Cholesky factor of the tridiagonal precision; fails
/// closed instead of panicking so it is usable inside a refresh.
fn tridiagonal_cholesky(diag: &[f64], off: &[f64]) -> Result<(Vec<f64>, Vec<f64>), Error> {
    let n = diag.len();
    let mut d = vec![0.0; n];
    let mut l = vec![0.0; n.saturating_sub(1)];
    if !(diag[0].is_finite() && diag[0] > 0.0) {
        return Err(Error::metric_candidate("path precision is not positive"));
    }
    d[0] = diag[0].sqrt();
    for i in 1..n {
        l[i - 1] = off[i - 1] / d[i - 1];
        let value = diag[i] - l[i - 1] * l[i - 1];
        if !(value.is_finite() && value > 0.0) {
            return Err(Error::metric_candidate(
                "tridiagonal precision is not positive definite",
            ));
        }
        d[i] = value.sqrt();
    }
    Ok((d, l))
}

/// Posterior-precision path block `H = [1/tau^2 at x_1] + Q_rw(sigma_x) + diag(c_t)`.
fn path_precision(data: &Data, q_globals: &[f64]) -> Result<(Vec<f64>, Vec<f64>), Error> {
    let t = data.t();
    let sigma_x = q_globals[1].exp();
    if !(sigma_x.is_finite() && sigma_x > 0.0) {
        return Err(Error::metric_candidate("sigma_x is not representable"));
    }
    let s2 = 1.0 / (sigma_x * sigma_x);
    if !s2.is_finite() {
        return Err(Error::metric_candidate("sigma_x precision overflowed"));
    }
    let curvature = data.observation_curvature(q_globals);
    if curvature.iter().any(|c| !c.is_finite() || *c < 0.0) {
        return Err(Error::metric_candidate(
            "observation curvature is not representable",
        ));
    }
    let mut diag = vec![0.0; t];
    let off = vec![-s2; t - 1];
    diag[0] += 1.0 / (data.tau * data.tau);
    for (i, value) in diag.iter_mut().enumerate() {
        if i + 1 < t {
            *value += s2;
        }
        if i > 0 {
            *value += s2;
        }
        *value += curvature[i];
    }
    Ok((diag, off))
}

fn functionals(y: &[f64], a: f64) -> [f64; 8] {
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
    ]
}

fn run_config(c: &Common, seed: u64, retained: usize, adapt_mass: bool) -> RunConfig {
    let tuning = KernelTuning::new(
        c.initial_step,
        NonZeroUsize::new(c.max_depth).unwrap(),
        NonZeroUsize::new(c.min_micro).unwrap(),
        NonZeroUsize::new(c.levels).unwrap(),
        c.max_error,
    )
    .unwrap();
    let warmup = WarmupConfig::new(c.target_acceptance)
        .unwrap()
        .with_mass_adaptation(adapt_mass)
        .with_step_size_adaptation(true)
        .with_initial_step_search(InitialStepSearchConfig::default());
    RunConfig::new(c.discarded, NonZeroUsize::new(retained).unwrap(), seed)
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
    arm: Arm,
    fixture: &str,
    fixture_sha: &str,
    seed: u64,
    c: &Common,
    retained: usize,
    kernel_commit: &str,
    preflight: (usize, usize, usize),
    calls_before: usize,
    calls_after: usize,
    wall: f64,
    output: &MultiChainOutput,
    extra: Value,
) -> Value {
    let mut counts = [0usize; 6];
    let mut depth_hist = vec![0usize; c.max_depth + 1];
    let mut refinement_hist = vec![0usize; c.levels + 1];
    let mut divergences = 0usize;
    let mut warmup_divergences = 0usize;
    let mut reverse_rejections = 0usize;
    let mut retained_transitions = 0usize;
    let mut retained_calls = 0usize;
    let mut total_calls = 0usize;
    let mut mean_leaves = 0.0f64;
    let mut max_energy_error = 0.0f64;
    let mut steps = Vec::new();
    let mut mass_globals = Vec::new();
    for chain in output.chains() {
        steps.push(chain.metadata().qualified_step_size());
        mass_globals.push(chain.metadata().mass_diagonal()[..6].to_vec());
        total_calls += chain.telemetry().total().target_calls_total();
        retained_calls += chain.telemetry().retained().target_calls_total();
        for d in &chain.diagnostics()[..c.discarded] {
            if d.divergent() {
                warmup_divergences += 1;
            }
        }
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
            refinement_hist[d.selected_refinement_level().unwrap_or(c.levels).min(c.levels)] += 1;
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
        "arm": arm.code(),
        "arm_label": arm.label(),
        "backend": "owalnuts",
        "fixture": fixture,
        "fixture_sha256": fixture_sha,
        "centeredness": 1.0,
        "seed": seed,
        "dimension": output.chains()[0].metadata().dimension(),
        "algorithm_revision": ALGORITHM_REVISION,
        "driver_revision": if arm == Arm::R { STRUCTURED_REFRESH_REVISION } else { "fixed" },
        "kernel_commit": kernel_commit,
        "settings": {"chains": c.chains, "threads": c.threads, "discarded": c.discarded, "retained": retained,
                      "initial_step": c.initial_step, "max_depth": c.max_depth, "min_micro_steps": c.min_micro,
                      "max_refinement_levels": c.levels, "max_error": c.max_error, "target_acceptance": c.target_acceptance},
        "preflight": {"worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2},
        "wall_seconds": fmt(wall),
        "target_calls_counter": calls_after - calls_before,
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
        "retained_refinement_exhaustions": counts[3],
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
    let mut means = vec![0.0; 8];
    let mut n = 0usize;
    for chain in output.chains() {
        let dim = chain.metadata().dimension();
        let mut bytes = Vec::with_capacity(chain.samples().len() / dim * 64);
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
    let mut fixtures = "sspd-11".to_string();
    let mut arms = "I,P,R".to_string();
    let mut retained_override: Option<usize> = None;
    let mut seeds_override: Option<Vec<u64>> = None;
    let mut out = PathBuf::from("artifacts/run-2000");
    let mut kernel_commit = "unknown".to_string();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--fixtures" => fixtures = args[i + 1].clone(),
            "--arms" => arms = args[i + 1].clone(),
            "--retained" => retained_override = Some(args[i + 1].parse().unwrap()),
            "--seeds" => {
                seeds_override =
                    Some(args[i + 1].split(',').map(|s| s.parse().unwrap()).collect())
            }
            "--out" => out = PathBuf::from(&args[i + 1]),
            "--kernel-commit" => kernel_commit = args[i + 1].clone(),
            other => panic!("unknown argument {other}"),
        }
        i += 2;
    }
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let protocol: Value =
        serde_json::from_slice(&fs::read(here.join("protocol.json")).unwrap()).unwrap();
    let c = common(&protocol);
    let retained = retained_override.unwrap_or(c.retained);
    fs::create_dir_all(out.join("draws")).unwrap();
    let arms: Vec<Arm> = arms.split(',').map(|s| Arm::parse(s).expect("arm")).collect();
    let mut index = Vec::new();
    for key in fixtures.split(',') {
        let entry = &protocol["fixtures"][key];
        let fixture_path = here.join("fixtures").join(entry["file"].as_str().unwrap());
        let bytes = fs::read(&fixture_path).unwrap();
        let sha = sha256_hex(&bytes);
        assert_eq!(
            sha,
            entry["sha256"].as_str().unwrap(),
            "fixture hash mismatch for {key}"
        );
        let fixture: Value = serde_json::from_slice(&bytes).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["s"]),
            &numbers(&fixture["data"]["v"]),
        )
        .unwrap();
        let seeds: Vec<u64> = seeds_override.clone().unwrap_or_else(|| {
            numbers(&protocol["seeds"][key])
                .iter()
                .map(|s| *s as u64)
                .collect()
        });
        // Starts by the frozen rule: initial innovations plus mu offsets.
        let base = data.initial_innovations();
        let mu_offsets = numbers(&protocol["starts"]["mu_offsets"]);
        assert_eq!(mu_offsets.len(), c.chains);
        let starts_q: Vec<Vec<f64>> = mu_offsets
            .iter()
            .map(|offset| {
                let mut q = base.clone();
                q[0] += offset;
                q
            })
            .collect();
        for &seed in &seeds {
            let mut globals_mass: Option<Vec<f64>> = None;
            for arm in &arms {
                let a = 1.0;
                let starts: Vec<Vec<f64>> =
                    starts_q.iter().map(|q| from_innovations(q, a)).collect();
                let target = CenteredTarget {
                    data: data.clone(),
                    a,
                    calls: AtomicUsize::new(0),
                };
                let dim = data.dim();
                let control = RunControl::new()
                    .with_timeout(Duration::from_secs_f64(c.wall_cap))
                    .unwrap();
                let calls_before = target.calls.load(Ordering::Relaxed);
                let started = Instant::now();
                eprintln!("{key} seed={seed} retained={retained} arm={}", arm.code());
                let threads = NonZeroUsize::new(c.threads).unwrap();
                let (preflight, result, extra): (
                    (usize, usize, usize),
                    Result<MultiChainOutput, Error>,
                    Value,
                ) = match arm {
                    Arm::I => {
                        let mass = DiagonalMass::identity(NonZeroUsize::new(dim).unwrap());
                        let config = run_config(&c, seed, retained, true);
                        let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                        let after = target.calls.load(Ordering::Relaxed);
                        let pre = (
                            report.worst_case_target_evaluations(),
                            report.admission_ceiling(),
                            after - calls_before,
                        );
                        let r = sample_chains_with_control(
                            &target, &starts, &mass, &config, threads, &control,
                        );
                        (pre, r, json!({}))
                    }
                    Arm::P => {
                        let gm = globals_mass
                            .clone()
                            .expect("arm P requires arm I's globals mass (run I first)");
                        let (hd, ho) = path_precision(&data, &base[..6]).unwrap();
                        let (ld, ls) = tridiagonal_cholesky(&hd, &ho).unwrap();
                        let blocks = vec![
                            StructuredCovarianceBlock::BidiagonalCholesky {
                                diagonal: gm.iter().map(|m| m.sqrt()).collect(),
                                subdiagonal: vec![0.0; 5],
                            },
                            StructuredCovarianceBlock::BidiagonalCholesky {
                                diagonal: ld.clone(),
                                subdiagonal: ls.clone(),
                            },
                        ];
                        let mass = StructuredBlockMass::new(blocks).unwrap();
                        let config = run_config(&c, seed, retained, false);
                        let report =
                            preflight_chains_structured(&target, &starts, &mass, &config).unwrap();
                        let after = target.calls.load(Ordering::Relaxed);
                        let pre = (
                            report.worst_case_target_evaluations(),
                            report.admission_ceiling(),
                            after - calls_before,
                        );
                        let r = sample_chains_structured_with_control(
                            &target, &starts, &mass, &config, threads, &control,
                        );
                        let extra = json!({
                            "globals_momentum_covariance": gm,
                            "path_precision_globals_used": base[..6].to_vec(),
                            "path_precision_diag_range": [hd.iter().cloned().fold(f64::INFINITY, f64::min), hd.iter().cloned().fold(0.0, f64::max)],
                            "path_precision_offdiag": ho[0],
                        });
                        (pre, r, extra)
                    }
                    Arm::R => {
                        let (hd, ho) = path_precision(&data, &base[..6]).unwrap();
                        let (ld, ls) = tridiagonal_cholesky(&hd, &ho).unwrap();
                        let initial = StructuredBlockMass::new(vec![
                            StructuredCovarianceBlock::BidiagonalCholesky {
                                diagonal: vec![1.0; 6],
                                subdiagonal: vec![0.0; 5],
                            },
                            StructuredCovarianceBlock::BidiagonalCholesky {
                                diagonal: ld,
                                subdiagonal: ls,
                            },
                        ])
                        .unwrap();
                        let refresh_data = data.clone();
                        let refresh = move |summary: &WindowSummary,
                                            _: &StructuredBlockMass|
                              -> Result<StructuredBlockMass, Error> {
                            let precision =
                                summary.regularized_precision(&[0, 1, 2, 3, 4, 5])?;
                            let globals = &summary.mean()[..6];
                            let (hd, ho) = path_precision(&refresh_data, globals)?;
                            let (ld, ls) = tridiagonal_cholesky(&hd, &ho)?;
                            StructuredBlockMass::new(vec![
                                StructuredCovarianceBlock::BidiagonalCholesky {
                                    diagonal: precision.iter().map(|p| p.sqrt()).collect(),
                                    subdiagonal: vec![0.0; 5],
                                },
                                StructuredCovarianceBlock::BidiagonalCholesky {
                                    diagonal: ld,
                                    subdiagonal: ls,
                                },
                            ])
                        };
                        let refresh_config = StructuredRefreshConfig::default();
                        let config = run_config(&c, seed, retained, true);
                        let report = preflight_chains_structured_refresh(
                            &target, &starts, &initial, &config,
                        )
                        .unwrap();
                        let after = target.calls.load(Ordering::Relaxed);
                        let pre = (
                            report.worst_case_target_evaluations(),
                            report.admission_ceiling(),
                            after - calls_before,
                        );
                        match sample_chains_structured_refresh(
                            &target,
                            &starts,
                            &initial,
                            &refresh,
                            &refresh_config,
                            &config,
                            threads,
                            &control,
                        ) {
                            Ok(refreshed) => {
                                let mut installed = 0usize;
                                let mut failed = 0usize;
                                let mut skipped = 0usize;
                                let mut failures = Vec::new();
                                let boundaries: Vec<Value> = refreshed
                                    .metric_updates()
                                    .iter()
                                    .enumerate()
                                    .map(|(chain, updates)| {
                                        json!({
                                            "chain": chain,
                                            "updates": updates.iter().map(|u| {
                                                match u.outcome() {
                                                    StructuredRefreshOutcome::Installed => installed += 1,
                                                    StructuredRefreshOutcome::InsufficientSamples => skipped += 1,
                                                    _ => {
                                                        failed += 1;
                                                        if let Some(message) = u.failure() {
                                                            failures.push(message.to_string());
                                                        }
                                                    }
                                                }
                                                json!({
                                                    "window": u.window_index(),
                                                    "outcome": format!("{:?}", u.outcome()),
                                                    "generation": u.generation(),
                                                    "samples": u.sample_count(),
                                                    "step_before": u.step_before(),
                                                    "step_after_search": u.step_after_search(),
                                                    "covariance_diagonal_range": u.covariance_diagonal_range(),
                                                })
                                            }).collect::<Vec<_>>(),
                                        })
                                    })
                                    .collect();
                                let extra = json!({
                                    "driver": "sample_chains_structured_refresh",
                                    "installed": installed,
                                    "refresh_failures": failed,
                                    "insufficient_samples": skipped,
                                    "failure_messages": failures,
                                    "boundaries": boundaries,
                                });
                                (pre, Ok(refreshed.chains().clone()), extra)
                            }
                            Err(e) => (pre, Err(e), json!({})),
                        }
                    }
                };
                let wall = started.elapsed().as_secs_f64();
                let calls_after = target.calls.load(Ordering::Relaxed);
                let stem = format!("{key}-{}-{seed}", arm.code());
                match result {
                    Ok(output) => {
                        let mut summary = summarize(
                            *arm,
                            key,
                            &sha,
                            seed,
                            &c,
                            retained,
                            &kernel_commit,
                            preflight,
                            calls_before,
                            calls_after,
                            wall,
                            &output,
                            extra,
                        );
                        let means = write_functionals(
                            &out.join("draws").join(format!("{stem}.f64")),
                            &output,
                            a,
                        );
                        summary["functional_means"] = Value::Object(
                            FUNCTIONALS
                                .iter()
                                .zip(means)
                                .map(|(n, m)| (n.to_string(), json!(m)))
                                .collect(),
                        );
                        summary["functionals_file"] = json!(format!("draws/{stem}.f64"));
                        if *arm == Arm::I {
                            let mass = geometric_mean_globals(
                                &output
                                    .chains()
                                    .iter()
                                    .map(|ch| ch.metadata().mass_diagonal()[..6].to_vec())
                                    .collect::<Vec<_>>(),
                            );
                            globals_mass = Some(mass);
                        }
                        eprintln!(
                            "  done {wall:.1}s calls {} median depth {} cap rate {}",
                            calls_after - calls_before,
                            summary["median_depth"],
                            summary["max_depth_rate"]
                        );
                        fs::write(
                            out.join(format!("{stem}.json")),
                            serde_json::to_string_pretty(&summary).unwrap(),
                        )
                        .unwrap();
                    }
                    Err(e) => {
                        let failure = json!({
                            "arm": arm.code(), "fixture": key, "seed": seed, "status": "failed",
                            "error_kind": format!("{:?}", e.kind()), "error": e.to_string(),
                            "wall_seconds": fmt(wall), "target_calls_counter": calls_after - calls_before,
                            "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit,
                            "preflight": {"worst_case_target_evaluations": preflight.0, "admission_ceiling": preflight.1, "callbacks_started": preflight.2},
                        });
                        eprintln!("  FAILED {:?}: {e}", e.kind());
                        fs::write(
                            out.join(format!("{stem}.json")),
                            serde_json::to_string_pretty(&failure).unwrap(),
                        )
                        .unwrap();
                    }
                }
                index.push(stem);
            }
        }
    }
    fs::write(
        out.join("index.json"),
        serde_json::to_string_pretty(&json!({"schema": "sspd11-refreshed-block-v1/runs", "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit, "retained": retained, "runs": index})).unwrap(),
    )
    .unwrap();
}
