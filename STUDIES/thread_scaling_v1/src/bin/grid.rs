//! WP45 grid runner (plain system allocator, no instrumentation).
//!
//!     grid <target> --out <dir> [--reps N] [--rep-start R] [--cells C:T,...|--full|--lower]
//!          [--arm NAME] [--seed S] [--warmup W --draws D]
//!
//! Cells run strictly sequentially, rep-major: for each rep, chains ascending,
//! threads ascending. `--full` is chains x threads in {1,2,4,8,16}^2;
//! `--lower` keeps threads <= chains (the driver clamps threads to chains).
//! Each cell writes `<out>/cells/<arm>-<target>-c<C>-t<T>-r<R>.json` and
//! refuses to overwrite. Draw/work fingerprints must agree across every
//! thread count and repetition at fixed (target, chains, seed); a mismatch is
//! recorded and the process exits with status 3 after the last cell.

use std::collections::BTreeMap;
use std::path::PathBuf;

use serde_json::json;
use thread_scaling_v1::*;

const LEVELS: [usize; 5] = [1, 2, 4, 8, 16];

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let target_name = args.get(1).expect("target").clone();
    let mut out = None;
    let mut reps = 1usize;
    let mut rep_start = 0usize;
    let mut cells: Vec<(usize, usize)> = Vec::new();
    let mut arm = "baseline".to_string();
    let mut seed = None;
    let mut warmup = None;
    let mut draws = None;
    let mut i = 2;
    while i < args.len() {
        let a = args[i].as_str();
        let v = || args.get(i + 1).cloned().expect("value");
        match a {
            "--out" => { out = Some(PathBuf::from(v())); i += 1; }
            "--reps" => { reps = v().parse().unwrap(); i += 1; }
            "--rep-start" => { rep_start = v().parse().unwrap(); i += 1; }
            "--arm" => { arm = v(); i += 1; }
            "--seed" => { seed = Some(v().parse::<u64>().unwrap()); i += 1; }
            "--warmup" => { warmup = Some(v().parse::<usize>().unwrap()); i += 1; }
            "--draws" => { draws = Some(v().parse::<usize>().unwrap()); i += 1; }
            "--full" => { cells = LEVELS.iter().flat_map(|&c| LEVELS.iter().map(move |&t| (c, t))).collect(); }
            "--lower" => { cells = LEVELS.iter().flat_map(|&c| LEVELS.iter().filter(move |&&t| t <= c).map(move |&t| (c, t))).collect(); }
            "--cells" => {
                cells = v().split(',').map(|p| {
                    let (c, t) = p.split_once(':').expect("C:T");
                    (c.parse().unwrap(), t.parse().unwrap())
                }).collect();
                i += 1;
            }
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let out = out.expect("--out");
    std::fs::create_dir_all(out.join("cells")).unwrap();
    let study_dir = std::env::var_os("TS_STUDY_DIR").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    let base = workload(&target_name);
    let wl = Workload {
        name: base.name,
        seed: seed.unwrap_or(base.seed),
        warmup: warmup.unwrap_or(base.warmup),
        draws: draws.unwrap_or(base.draws),
    };
    let target = load_target(&target_name, &study_dir).expect("target load");
    let info = target.info();
    let mut reference: BTreeMap<usize, String> = BTreeMap::new();
    let mut ess_cache: BTreeMap<usize, (f64, usize)> = BTreeMap::new();
    let mut mismatches = 0usize;
    for rep in rep_start..rep_start + reps {
        for &(chains, threads) in &cells {
            let path = out.join("cells").join(format!("{arm}-{}-c{chains}-t{threads}-r{rep}.json", wl.name));
            if path.exists() {
                panic!("refusing to overwrite {}", path.display());
            }
            let started = utc_now();
            let outcome = run_study_cell(&target, &wl, chains, threads);
            let finished = utc_now();
            let mut record = outcome.record;
            if let Some(posterior) = &outcome.posterior {
                let fp = record["fingerprint"].as_str().unwrap().to_string();
                let identical = match reference.get(&chains) {
                    None => {
                        reference.insert(chains, fp.clone());
                        true
                    }
                    Some(r) => *r == fp,
                };
                if !identical {
                    mismatches += 1;
                    eprintln!("FINGERPRINT MISMATCH {} c{chains} t{threads} r{rep}", wl.name);
                }
                let (ess, argmin) = *ess_cache.entry(chains).or_insert_with(|| min_bulk_ess(posterior));
                let wall = record["wall_s"].as_f64().unwrap();
                let grads = record["gradients_total"].as_f64().unwrap();
                record["identical_to_first_in_process"] = json!(identical);
                record["min_bulk_ess"] = json!(ess);
                record["argmin_bulk_ess"] = json!(argmin);
                record["min_bulk_ess_per_second"] = json!(ess / wall);
                record["min_bulk_ess_per_gradient"] = json!(ess / grads);
                record["gradients_per_second"] = json!(grads / wall);
            }
            record["schema"] = json!("thread-scaling-v1-cell");
            record["arm"] = json!(arm);
            record["target"] = json!(wl.name);
            record["target_info"] = info.clone();
            record["chains"] = json!(chains);
            record["threads"] = json!(threads);
            record["rep"] = json!(rep);
            record["seed"] = json!(wl.seed);
            record["warmup"] = json!(wl.warmup);
            record["draws"] = json!(wl.draws);
            record["started_unix"] = json!(started);
            record["finished_unix"] = json!(finished);
            record["peak_working_set_bytes"] = json!(peak_working_set());
            record["timing_estimand"] = json!("wall around Sampler::run (warmup + retained, all chains); uniform start search excluded");
            std::fs::write(&path, serde_json::to_vec_pretty(&record).unwrap()).unwrap();
            println!(
                "[{}] {arm} {} c{chains:>2} t{threads:>2} r{rep}: {} wall {:.3}s cpu {:.2}s sysbusy {:.1}/{:.1} fp {}",
                finished,
                wl.name,
                record["status"].as_str().unwrap_or("?"),
                record["wall_s"].as_f64().unwrap_or(f64::NAN),
                record["counters"]["process_cpu_s"].as_f64().unwrap_or(f64::NAN),
                record["counters"]["system_busy_core_s"].as_f64().unwrap_or(f64::NAN),
                record["counters"]["system_total_core_s"].as_f64().unwrap_or(f64::NAN),
                record["fingerprint"].as_str().unwrap_or("-"),
            );
        }
    }
    if mismatches > 0 {
        eprintln!("{mismatches} fingerprint mismatches");
        std::process::exit(3);
    }
}
