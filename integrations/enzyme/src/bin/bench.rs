//! Tape-vs-hand gradient benchmark: per-call cost and a paired sampling run.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, RunConfig, WarmupConfig, preflight_chains,
    sample_chains,
};
use owalnuts_autodiff_tape::{
    Backend, LocalLevel, hand_log_density_gradient, simulate, tape_log_density_gradient,
};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::{Value, json};
use std::{fs, num::NonZeroUsize, path::PathBuf, time::Instant};

fn ess_batch_means(x: &[f64]) -> f64 {
    let n = x.len();
    let b = (n as f64).sqrt().floor() as usize;
    let k = n / b;
    if k < 2 {
        return f64::NAN;
    }
    let mean = x.iter().sum::<f64>() / n as f64;
    let var = x.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n as f64 - 1.0);
    let bmeans: Vec<f64> = (0..k)
        .map(|i| x[i * b..(i + 1) * b].iter().sum::<f64>() / b as f64)
        .collect();
    let bvar = bmeans.iter().map(|m| (m - mean).powi(2)).sum::<f64>() / (k as f64 - 1.0);
    n as f64 * var / (b as f64 * bvar)
}

fn per_call(t: usize, reps: usize) -> Value {
    let data = simulate(t, 2026083101);
    let mut rng = SmallRng::seed_from_u64(99);
    let points: Vec<Vec<f64>> = (0..16)
        .map(|_| (0..t).map(|_| rng.random_range(-2.0..2.0)).collect())
        .collect();
    let mut g = vec![0.0; t];
    let mut max_dv: f64 = 0.0;
    let mut max_dg: f64 = 0.0;
    for p in &points {
        let mut gh = vec![0.0; t];
        let lh = hand_log_density_gradient(p, &mut gh, &data);
        let lt = tape_log_density_gradient(p, &mut g, &data);
        max_dv = max_dv.max((lh - lt).abs());
        for i in 0..t {
            max_dg = max_dg.max((gh[i] - g[i]).abs());
        }
    }
    let mut sink = 0.0;
    let start = Instant::now();
    for i in 0..reps {
        sink += hand_log_density_gradient(&points[i % 16], &mut g, &data);
    }
    let hand_ns = start.elapsed().as_nanos() as f64 / reps as f64;
    let start = Instant::now();
    for i in 0..reps {
        sink += tape_log_density_gradient(&points[i % 16], &mut g, &data);
    }
    let tape_ns = start.elapsed().as_nanos() as f64 / reps as f64;
    json!({
        "T": t, "reps": reps, "max_abs_value_diff": max_dv, "max_abs_gradient_diff": max_dg,
        "hand_ns_per_call": hand_ns, "tape_ns_per_call": tape_ns,
        "tape_over_hand": tape_ns / hand_ns, "sink": sink
    })
}

fn sample_arm(t: usize, backend: Backend, seed: u64) -> Value {
    let data = simulate(t, 2026083101);
    let target = LocalLevel::new(data.clone(), backend);
    let starts: Vec<Vec<f64>> = (0..4)
        .map(|c| data.y.iter().map(|y| y + 0.5 * (c as f64 - 1.5)).collect())
        .collect();
    let tuning = KernelTuning::new(
        0.1,
        NonZeroUsize::new(8).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(3).unwrap(),
        1.0,
    )
    .unwrap();
    let config = RunConfig::new(500, NonZeroUsize::new(2000).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.8).unwrap().with_mass_adaptation(true));
    let mass = DiagonalMass::identity(NonZeroUsize::new(t).unwrap());
    preflight_chains(&target, &starts, &mass, &config).expect("preflight");
    let start = Instant::now();
    let out = sample_chains(
        &target,
        &starts,
        &mass,
        &config,
        NonZeroUsize::new(4).unwrap(),
    )
    .expect("sampling");
    let wall = start.elapsed().as_secs_f64();
    let calls: usize = out
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let last: Vec<f64> = out
        .chains()
        .iter()
        .flat_map(|c| (0..c.retained()).map(|d| c.sample(d).unwrap()[t - 1]))
        .collect();
    let ess = ess_batch_means(&last);
    json!({
        "T": t, "backend": format!("{backend:?}"), "seed": seed, "wall_seconds": wall,
        "target_calls": calls, "target_calls_counted": target.calls(),
        "x_last_mean": last.iter().sum::<f64>() / last.len() as f64,
        "ess_x_last": ess, "ess_per_second": ess / wall, "ess_per_call": ess / calls as f64
    })
}

fn main() {
    let out_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("artifacts");
    fs::create_dir_all(&out_dir).unwrap();
    let per_call_rows: Vec<Value> = vec![
        per_call(10, 200_000),
        per_call(100, 40_000),
        per_call(1000, 4_000),
    ];
    let mut sampling = Vec::new();
    for &t in &[100usize, 1000] {
        for backend in [Backend::Hand, Backend::Tape] {
            let row = sample_arm(t, backend, 84101);
            eprintln!("{row}");
            sampling.push(row);
        }
    }
    let result = json!({
        "algorithm_revision": ALGORITHM_REVISION,
        "tape_crate": "reverse 0.2.2",
        "per_call": per_call_rows,
        "sampling": sampling,
    });
    fs::write(
        out_dir.join("tape-benchmark.json"),
        serde_json::to_string_pretty(&result).unwrap(),
    )
    .unwrap();
    println!("{}", serde_json::to_string_pretty(&result).unwrap());
}
