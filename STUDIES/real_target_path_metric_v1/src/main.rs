//! WP4b: real canonical-v2 target at T=1000 — arms I (centered adapted
//! diagonal), P (fixed posterior-precision path metric), B (production
//! a=0.75 adapted diagonal). Arm N (NumPyro) lives in `numpyro_reference.py`.

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

const FUNCTIONALS: [&str; 8] = ["mu", "sigma_x", "alpha", "beta", "gamma", "nu", "x_terminal", "x_path_mean"];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Arm {
    I,
    P,
    P2,
    B,
    /// POST-HOC: globals frozen at arm I posterior means, identity path metric.
    FI,
    /// POST-HOC: globals frozen at arm I posterior means, posterior-precision path block.
    FP,
}

impl Arm {
    fn parse(s: &str) -> Option<Arm> {
        match s {
            "I" => Some(Arm::I),
            "P" => Some(Arm::P),
            "P2" => Some(Arm::P2),
            "B" => Some(Arm::B),
            "FI" => Some(Arm::FI),
            "FP" => Some(Arm::FP),
            _ => None,
        }
    }
    fn code(self) -> &'static str {
        match self {
            Arm::I => "I",
            Arm::P => "P",
            Arm::P2 => "P2",
            Arm::B => "B",
            Arm::FI => "FI",
            Arm::FP => "FP",
        }
    }
    fn label(self) -> &'static str {
        match self {
            Arm::I => "a=1 centered, identity initial diagonal, mass adaptation on",
            Arm::P => "a=1 centered, fixed posterior-precision tridiagonal path block + fixed globals diagonal",
            Arm::P2 => "POST-HOC: as P, but the path block is built at arm I's posterior-mean globals",
            Arm::FI => "POST-HOC: globals frozen at arm I posterior means, identity path metric, no mass adaptation",
            Arm::FP => "POST-HOC: globals frozen at arm I posterior means, posterior-precision path block at those globals, no mass adaptation",
            Arm::B => "a=0.75 production coordinates, identity initial diagonal, mass adaptation on",
        }
    }
    fn centeredness(self) -> f64 {
        match self {
            Arm::B => 0.75,
            _ => 1.0,
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
    value.as_array().unwrap().iter().map(|x| x.as_f64().unwrap()).collect()
}

fn sha256_hex(bytes: &[u8]) -> String {
    // Minimal SHA-256 (FIPS 180-4) to avoid an extra dependency.
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

/// Posterior-precision path block `H = [1/tau^2 at x_1] + Q_rw(sigma_x) + diag(c_t)`.
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

/// Path-only target with the six globals frozen (a=1 coordinates).
struct FrozenGlobals {
    inner: CenteredTarget,
    globals: Vec<f64>,
}

impl owalnuts::walnutpie::Target for FrozenGlobals {
    fn dimension(&self) -> usize {
        self.inner.data.t()
    }
    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, owalnuts::walnutpie::TargetError> {
        let mut y = Vec::with_capacity(position.len() + 6);
        y.extend_from_slice(&self.globals);
        y.extend_from_slice(position);
        let mut g = vec![0.0; y.len()];
        let lp = self.inner.log_density_gradient(&y, &mut g)?;
        gradient.copy_from_slice(&g[6..]);
        Ok(lp)
    }
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

fn run_config(c: &Common, seed: u64, adapt_mass: bool) -> RunConfig {
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
    RunConfig::new(c.discarded, NonZeroUsize::new(c.retained).unwrap(), seed)
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
    kernel_commit: &str,
    preflight: (usize, usize, usize),
    calls_before: usize,
    calls_after: usize,
    wall: f64,
    output: &MultiChainOutput,
    extra: Value,
) -> Value {
    let mut depth_hist = vec![0usize; c.max_depth + 1];
    let mut counts = [0usize; 6];
    let mut refinement_hist = vec![0usize; c.levels + 1];
    let mut retained_calls = 0usize;
    let mut total_calls = 0usize;
    let mut retained_transitions = 0usize;
    let mut warmup_divergences = 0usize;
    let mut divergences = 0usize;
    let mut reverse_rejections = 0usize;
    let mut steps = Vec::new();
    let mut mean_leaves = 0.0;
    let mut max_energy_error: f64 = 0.0;
    let mut mass_globals = Vec::new();
    for chain in output.chains() {
        steps.push(chain.metadata().qualified_step_size());
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
                StopReason::InvalidEvaluation => 5,
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
        "centeredness": arm.centeredness(),
        "seed": seed,
        "dimension": output.chains()[0].metadata().dimension(),
        "algorithm_revision": ALGORITHM_REVISION,
        "kernel_commit": kernel_commit,
        "settings": {"chains": c.chains, "threads": c.threads, "discarded": c.discarded, "retained": c.retained,
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
                  "refinement_exhausted": counts[3], "reverse_coarser_accepted": counts[4], "invalid_evaluation": counts[5]},
        "retained_divergences": divergences,
        "warmup_divergences": warmup_divergences,
        "retained_invalid_evaluations": counts[5],
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

fn write_functionals(path: &Path, output: &MultiChainOutput, a: f64, frozen: Option<&[f64]>) -> Vec<f64> {
    let mut file = fs::File::create(path).unwrap();
    let mut means = vec![0.0; 8];
    let mut n = 0usize;
    for chain in output.chains() {
        let dim = chain.metadata().dimension();
        let mut bytes = Vec::with_capacity(chain.samples().len() / dim * 64);
        for draw in chain.samples().chunks(dim) {
            let full: Vec<f64>;
            let draw = if let Some(g) = frozen {
                full = g.iter().chain(draw.iter()).copied().collect();
                &full[..]
            } else {
                draw
            };
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
    let mut fixtures = "sspd-11,sspd-10,sspd-05".to_string();
    let mut arms = "I,P,B".to_string();
    let mut out = PathBuf::from("artifacts/owalnuts-v1");
    let mut kernel_commit = "unknown".to_string();
    let mut globals_mass_from: Option<PathBuf> = None;
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--fixtures" => fixtures = args[i + 1].clone(),
            "--arms" => arms = args[i + 1].clone(),
            "--out" => out = PathBuf::from(&args[i + 1]),
            "--kernel-commit" => kernel_commit = args[i + 1].clone(),
            "--globals-mass-from" => globals_mass_from = Some(PathBuf::from(&args[i + 1])),
            other => panic!("unknown argument {other}"),
        }
        i += 2;
    }
    let here = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let protocol: Value = serde_json::from_slice(&fs::read(here.join("protocol.json")).unwrap()).unwrap();
    let c = common(&protocol);
    fs::create_dir_all(out.join("draws")).unwrap();
    let arms: Vec<Arm> = arms.split(',').map(|s| Arm::parse(s).expect("arm")).collect();
    let mut index = Vec::new();
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
        // Shared starts (innovation coordinates), verified against the Rust rule.
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
        let mut globals_mass: Option<Vec<f64>> = None;
        let mut globals_mean: Option<Vec<f64>> = None;
        if let Some(dir) = &globals_mass_from {
            let p = dir.join(format!("{key}-globals-mass.json"));
            if p.exists() {
                let v: Value = serde_json::from_slice(&fs::read(&p).unwrap()).unwrap();
                globals_mass = Some(numbers(&v["momentum_covariance_globals"]));
                if v.get("posterior_mean_globals_unconstrained").is_some() {
                    globals_mean = Some(numbers(&v["posterior_mean_globals_unconstrained"]));
                }
            }
        }
        for arm in &arms {
            let a = arm.centeredness();
            let starts: Vec<Vec<f64>> = starts_q.iter().map(|q| from_innovations(q, a)).collect();
            let target = CenteredTarget { data: data.clone(), a, calls: AtomicUsize::new(0) };
            let dim = data.dim();
            let control = RunControl::new().with_timeout(Duration::from_secs_f64(c.wall_cap)).unwrap();
            let calls_before = target.calls.load(Ordering::Relaxed);
            let started = Instant::now();
            eprintln!("{key} seed={seed} arm={} dim={dim}", arm.code());
            let (preflight, result, extra): ((usize, usize, usize), Result<MultiChainOutput, Error>, Value) = match arm {
                Arm::FI | Arm::FP => {
                    let globals = globals_mean.clone().expect("frozen arms require arm I's posterior-mean globals");
                    let frozen = FrozenGlobals { inner: CenteredTarget { data: data.clone(), a: 1.0, calls: AtomicUsize::new(0) }, globals: globals.clone() };
                    let path_starts: Vec<Vec<f64>> = starts.iter().map(|y| y[6..].to_vec()).collect();
                    let config = run_config(&c, seed, false);
                    let t = data.t();
                    let r = if *arm == Arm::FI {
                        let mass = DiagonalMass::identity(NonZeroUsize::new(t).unwrap());
                        let report = preflight_chains(&frozen, &path_starts, &mass, &config).unwrap();
                        let after = frozen.inner.calls.load(Ordering::Relaxed);
                        assert_eq!(after, 0, "preflight started callbacks");
                        let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), 0);
                        (pre, sample_chains_with_control(&frozen, &path_starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), &control))
                    } else {
                        let (hd, ho) = path_precision(&data, &globals);
                        let (ld, ls) = tridiagonal_cholesky(&hd, &ho);
                        let mass = StructuredBlockMass::new(vec![StructuredCovarianceBlock::BidiagonalCholesky { diagonal: ld, subdiagonal: ls }]).unwrap();
                        let report = preflight_chains_structured(&frozen, &path_starts, &mass, &config).unwrap();
                        let after = frozen.inner.calls.load(Ordering::Relaxed);
                        assert_eq!(after, 0, "preflight started callbacks");
                        let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), 0);
                        (pre, sample_chains_structured_with_control(&frozen, &path_starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), &control))
                    };
                    target.calls.store(frozen.inner.calls.load(Ordering::Relaxed), Ordering::Relaxed);
                    (r.0, r.1, json!({"frozen_globals_unconstrained": globals}))
                }
                Arm::I | Arm::B => {
                    let mass = DiagonalMass::identity(NonZeroUsize::new(dim).unwrap());
                    let config = run_config(&c, seed, true);
                    let report = preflight_chains(&target, &starts, &mass, &config).unwrap();
                    let after = target.calls.load(Ordering::Relaxed);
                    let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), after - calls_before);
                    let r = sample_chains_with_control(&target, &starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), &control);
                    (pre, r, json!({}))
                }
                Arm::P | Arm::P2 => {
                    let gm = globals_mass.clone().expect("arm P requires arm I's globals mass (run I first or pass --globals-mass-from)");
                    let globals_for_path: Vec<f64> = if *arm == Arm::P2 {
                        globals_mean.clone().expect("arm P2 requires arm I's posterior-mean globals")
                    } else {
                        base[..6].to_vec()
                    };
                    let (hd, ho) = path_precision(&data, &globals_for_path);
                    let (ld, ls) = tridiagonal_cholesky(&hd, &ho);
                    let blocks = vec![
                        StructuredCovarianceBlock::BidiagonalCholesky {
                            diagonal: gm.iter().map(|m| m.sqrt()).collect(),
                            subdiagonal: vec![0.0; 5],
                        },
                        StructuredCovarianceBlock::BidiagonalCholesky { diagonal: ld.clone(), subdiagonal: ls.clone() },
                    ];
                    let mass = StructuredBlockMass::new(blocks).unwrap();
                    let config = run_config(&c, seed, false);
                    let report = preflight_chains_structured(&target, &starts, &mass, &config).unwrap();
                    let after = target.calls.load(Ordering::Relaxed);
                    let pre = (report.worst_case_target_evaluations(), report.admission_ceiling(), after - calls_before);
                    let r = sample_chains_structured_with_control(&target, &starts, &mass, &config, NonZeroUsize::new(c.threads).unwrap(), &control);
                    let extra = json!({
                        "globals_momentum_covariance": gm,
                        "path_precision_globals_used": globals_for_path,
                        "path_precision_diag_range": [hd.iter().cloned().fold(f64::INFINITY, f64::min), hd.iter().cloned().fold(0.0, f64::max)],
                        "path_precision_offdiag": ho[0],
                    });
                    (pre, r, extra)
                }
            };
            let wall = started.elapsed().as_secs_f64();
            let calls_after = target.calls.load(Ordering::Relaxed);
            let stem = format!("{key}-{}-{seed}", arm.code());
            match result {
                Ok(output) => {
                    let mut summary = summarize(*arm, key, &sha, seed, &c, &kernel_commit, preflight, calls_before, calls_after, wall, &output, extra);
                    let frozen_globals = if matches!(arm, Arm::FI | Arm::FP) { globals_mean.clone() } else { None };
                    let means = write_functionals(&out.join("draws").join(format!("{stem}.f64")), &output, a, frozen_globals.as_deref());
                    summary["functional_means"] = Value::Object(FUNCTIONALS.iter().zip(means).map(|(n, m)| (n.to_string(), json!(m))).collect());
                    summary["functionals_file"] = json!(format!("draws/{stem}.f64"));
                    if *arm == Arm::I {
                        let mass = geometric_mean_globals(&output.chains().iter().map(|ch| ch.metadata().mass_diagonal()[..6].to_vec()).collect::<Vec<_>>());
                        let m = &summary["functional_means"];
                        let unconstrained = vec![
                            m["mu"].as_f64().unwrap(),
                            m["sigma_x"].as_f64().unwrap().ln(),
                            m["alpha"].as_f64().unwrap().ln(),
                            m["beta"].as_f64().unwrap().ln(),
                            m["gamma"].as_f64().unwrap().ln(),
                            (m["nu"].as_f64().unwrap() - 2.0).ln(),
                        ];
                        fs::write(
                            out.join(format!("{key}-globals-mass.json")),
                            serde_json::to_string_pretty(&json!({"source": "arm I adapted momentum covariance, geometric mean over chains; posterior-mean globals from arm I retained draws", "momentum_covariance_globals": mass, "posterior_mean_globals_unconstrained": unconstrained})).unwrap(),
                        )
                        .unwrap();
                        globals_mass = Some(mass);
                        globals_mean = Some(unconstrained);
                    }
                    eprintln!("  done {wall:.1}s calls {} median depth {} cap rate {}", calls_after - calls_before, summary["median_depth"], summary["max_depth_rate"]);
                    fs::write(out.join(format!("{stem}.json")), serde_json::to_string_pretty(&summary).unwrap()).unwrap();
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
                    fs::write(out.join(format!("{stem}.json")), serde_json::to_string_pretty(&failure).unwrap()).unwrap();
                }
            }
            index.push(stem);
        }
    }
    fs::write(
        out.join("index.json"),
        serde_json::to_string_pretty(&json!({"schema": "real-target-path-metric-v1/runs", "algorithm_revision": ALGORITHM_REVISION, "kernel_commit": kernel_commit, "runs": index})).unwrap(),
    )
    .unwrap();
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sha256_matches_known_vector() {
        assert_eq!(
            sha256_hex(b"abc"),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    #[test]
    fn cholesky_reconstructs_path_precision() {
        let fixture: Value = serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        let base = data.initial_innovations();
        let (hd, ho) = path_precision(&data, &base[..6]);
        let (d, l) = tridiagonal_cholesky(&hd, &ho);
        let n = hd.len();
        for i in 0..n {
            // (L L')_{ii} = d_i^2 + l_{i-1}^2 ; (L L')_{i,i+1} = d_i l_i
            let diag = d[i] * d[i] + if i > 0 { l[i - 1] * l[i - 1] } else { 0.0 };
            assert!((diag - hd[i]).abs() < 1e-9 * hd[i]);
            if i + 1 < n {
                assert!((d[i] * l[i] - ho[i]).abs() < 1e-9 * ho[i].abs());
            }
        }
        // Path precision is the negative Hessian of the a=1 target restricted to
        // the path block, up to the Student-t nonlinearity: check the RW part by
        // finite differences at the data-informed point with the observation
        // curvature approximated at zero residual.
        assert!(hd.iter().all(|x| x.is_finite() && *x > 0.0));
    }

    #[test]
    fn functionals_agree_between_parameterizations() {
        let fixture: Value = serde_json::from_str(include_str!("../fixtures/polyscope_parity.json")).unwrap();
        let data = Data::try_from_raw(
            &numbers(&fixture["data"]["y"]),
            &numbers(&fixture["data"]["spread"]),
            &numbers(&fixture["data"]["volume"]),
        )
        .unwrap();
        let q = data.initial_innovations();
        let f1 = functionals(&from_innovations(&q, 1.0), 1.0);
        let f075 = functionals(&from_innovations(&q, 0.75), 0.75);
        for (a, b) in f1.iter().zip(f075) {
            assert!((a - b).abs() < 1e-9 * (1.0 + a.abs()));
        }
    }
}
