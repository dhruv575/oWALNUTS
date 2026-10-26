//! WP65 part (b): one fault-rate child. One process = one (path, seed).
//!
//! Adapted from the WP50D child (`STUDIES/bridgestan_windows_root_cause_v4/child`):
//! the same run shape (sblrc, 4 chains / 4 threads, 1000/1000,
//! `Init::uniform()`, diagonal metric, default adaptation and tuning,
//! `admit_worst_case`), heartbeats and FNV-1a draw fingerprint. Changes: the
//! three arms are the Linux dispatch paths of the shipped crate, no
//! study-local target; the Windows module probe is replaced by the
//! `/proc/self/maps` model/TBB mappings after load and after drop and by a
//! check that the replica copy directory was removed.
//!
//! Arms:
//! * `serialised`: `StanTarget` on the library built without `STAN_THREADS`
//!   (DirectSerialised; four sampler threads share one module under its mutex);
//! * `replicated`: `ReplicatedStanTarget` with four replicas on the same
//!   library (ReplicatedConcurrent; the off-Windows default of `load`);
//! * `threaded_direct`: `StanTarget` on the `STAN_THREADS=true` library
//!   (DirectConcurrent; four sampler threads call one module concurrently).
#![deny(unsafe_op_in_unsafe_fn)]
#![forbid(unsafe_code)]

use owalnuts::sampler::{Adaptation, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts};
use owalnuts_bridgestan::{ReplicatedStanTarget, StanTarget, default_preload};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{Instant, SystemTime, UNIX_EPOCH},
};

const CHAINS: usize = 4;
const THREADS: usize = 4;
const REPLICAS: usize = 4;
const WARMUP: usize = 1000;
const DRAWS: usize = 1000;
const PROBE_SEED: u64 = 65_299_002;

fn seed_allowed(seed: u64) -> bool {
    (65_201_001..=65_201_500).contains(&seed) || seed == PROBE_SEED
}

fn expected(arm: &str) -> Option<(&'static str, usize)> {
    match arm {
        "serialised" => Some(("DirectSerialised", 1)),
        "replicated" => Some(("ReplicatedConcurrent", REPLICAS)),
        "threaded_direct" => Some(("DirectConcurrent", 1)),
        _ => None,
    }
}

struct Heartbeat {
    dir: PathBuf,
    sequence: usize,
    arm: String,
    seed: u64,
}

impl Heartbeat {
    fn event(&mut self, stage: &str, boundary: &str, detail: Value) -> Result<(), Box<dyn Error>> {
        let path = self.dir.join(format!("{:04}-{stage}-{boundary}.json", self.sequence));
        let payload = json!({
            "schema": "bridgestan-linux-dispatch-v1-heartbeat",
            "sequence": self.sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "arm": self.arm,
            "seed": self.seed,
            "stage": stage,
            "boundary": boundary,
            "detail": detail,
        });
        write_new_atomically(&path, &serde_json::to_vec_pretty(&payload)?)?;
        self.sequence += 1;
        Ok(())
    }
}

fn write_new_atomically(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err(format!("refusing to replace existing file: {}", path.display()).into());
    }
    let parent = path.parent().ok_or("path has no parent")?;
    fs::create_dir_all(parent)?;
    let name = path.file_name().ok_or("path has no file name")?.to_string_lossy();
    let temporary = parent.join(format!(".{name}.tmp-{}", std::process::id()));
    let mut file = OpenOptions::new().write(true).create_new(true).open(&temporary)?;
    file.write_all(bytes)?;
    file.write_all(b"\n")?;
    file.sync_all()?;
    drop(file);
    fs::rename(temporary, path)?;
    Ok(())
}

fn fnv(hash: &mut u64, value: f64) {
    for byte in value.to_bits().to_le_bytes() {
        *hash ^= u64::from(byte);
        *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
}

/// Distinct mapped files of this process whose name contains `_model.so` or
/// `libtbb` (Linux `/proc/self/maps`).
fn mapped_modules() -> Value {
    let Ok(maps) = fs::read_to_string("/proc/self/maps") else {
        return Value::Null;
    };
    let mut paths: Vec<String> = maps
        .lines()
        .filter_map(|l| l.split_whitespace().nth(5).map(str::to_string))
        .filter(|p| p.contains("_model.so") || p.contains("libtbb"))
        .collect();
    paths.sort();
    paths.dedup();
    json!(paths)
}

/// Replica copy directories `owalnuts-bridgestan-<pid>-*` left in the temp dir.
fn leftover_copy_dirs() -> Value {
    let prefix = format!("owalnuts-bridgestan-{}-", std::process::id());
    let Ok(entries) = fs::read_dir(env::temp_dir()) else {
        return Value::Null;
    };
    json!(
        entries
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().into_owned())
            .filter(|n| n.starts_with(&prefix))
            .collect::<Vec<_>>()
    )
}

fn cpus_allowed() -> Option<String> {
    fs::read_to_string("/proc/self/status").ok()?.lines().find_map(|l| {
        l.strip_prefix("Cpus_allowed_list:").map(|v| v.trim().to_string())
    })
}

fn sample<T: Target>(target: &T, seed: u64, hb: &mut Heartbeat) -> Result<Value, Box<dyn Error>> {
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform { radius, max_attempts } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    hb.event("initialization", "before", Value::Null)?;
    let starts = uniform_starts(target, CHAINS, seed, radius, max_attempts)?;
    hb.event("initialization", "after", Value::Null)?;
    hb.event("sampling", "before", Value::Null)?;
    let started = Instant::now();
    let posterior = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .chains(CHAINS)
        .seed(seed)
        .threads(THREADS)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case())
        .run(target, &starts)?;
    let wall = started.elapsed().as_secs_f64();
    hb.event("sampling", "after", Value::Null)?;
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut observed = 0;
    let mut finite = true;
    for chain in posterior.chains() {
        for index in 0..DRAWS {
            for &value in chain.sample(index).ok_or("missing retained draw")? {
                finite &= value.is_finite();
                fnv(&mut hash, value);
            }
            observed += 1;
        }
    }
    Ok(json!({
        "draws_fingerprint_fnv1a64": format!("{hash:016x}"),
        "draws_observed": observed,
        "all_retained_values_finite": finite,
        "algorithm_revision": posterior.algorithm_revision(),
        "sampling_wall_seconds_pinned_cotenanted": wall,
    }))
}

fn run(args: &[String]) -> Result<(), Box<dyn Error>> {
    let [arm, model, data, seed, heartbeats, output] = args else {
        return Err("usage: <serialised|replicated|threaded_direct> <model.so> <data.json> <seed> <heartbeats> <output.json>".into());
    };
    let (want_execution, want_replicas) = expected(arm).ok_or("unknown arm")?;
    let seed: u64 = seed.parse()?;
    if !seed_allowed(seed) {
        return Err("seed is outside the frozen matrix".into());
    }
    let output = PathBuf::from(output);
    if output.exists() {
        return Err("output exists".into());
    }
    let data = fs::read_to_string(data)?;
    let mut hb = Heartbeat { dir: PathBuf::from(heartbeats), sequence: 0, arm: arm.clone(), seed };
    fs::create_dir_all(&hb.dir)?;
    hb.event("process", "start", json!({"cpus_allowed_list": cpus_allowed()}))?;
    hb.event("load", "before", Value::Null)?;
    let model = Path::new(model);
    let mut result;
    let after_load;
    let (execution, replicas, calls, recoverable);
    if arm == "replicated" {
        let target = ReplicatedStanTarget::load(model, &default_preload(), Some(&data), seed as u32, REPLICAS)?;
        after_load = mapped_modules();
        hb.event("load", "after", after_load.clone())?;
        result = sample(&target, seed, &mut hb)?;
        execution = format!("{:?}", target.execution());
        replicas = target.effective_replicas();
        calls = target.calls();
        recoverable = target.recoverable_failures();
        hb.event("drop", "before", Value::Null)?;
        drop(target);
    } else {
        let target = StanTarget::load(model, &default_preload(), Some(&data), seed as u32)?;
        after_load = mapped_modules();
        hb.event("load", "after", after_load.clone())?;
        result = sample(&target, seed, &mut hb)?;
        execution = format!("{:?}", target.execution());
        replicas = 1;
        calls = target.calls();
        recoverable = target.recoverable_failures();
        hb.event("drop", "before", Value::Null)?;
        drop(target);
    }
    let after_drop = mapped_modules();
    let leftovers = leftover_copy_dirs();
    hb.event("drop", "after", json!({"mapped": after_drop, "leftover_copy_dirs": leftovers}))?;
    result["schema"] = json!("bridgestan-linux-dispatch-v1-child");
    result["status"] = json!("ok");
    result["arm"] = json!(arm);
    result["seed"] = json!(seed);
    result["chains"] = json!(CHAINS);
    result["threads"] = json!(THREADS);
    result["warmup"] = json!(WARMUP);
    result["draws"] = json!(DRAWS);
    result["model"] = json!(model.display().to_string());
    result["execution"] = json!(execution);
    result["effective_replicas"] = json!(replicas);
    result["execution_as_expected"] = json!(execution == want_execution && replicas == want_replicas);
    result["target_calls"] = json!(calls);
    result["recoverable_failures"] = json!(recoverable);
    result["mapped_after_load"] = after_load;
    result["mapped_after_drop"] = after_drop;
    result["leftover_copy_dirs"] = leftovers;
    result["cpus_allowed_list"] = json!(cpus_allowed());
    hb.event("result_write", "before", Value::Null)?;
    write_new_atomically(&output, &serde_json::to_vec_pretty(&result)?)?;
    hb.event("result_write", "after", Value::Null)?;
    hb.event("process", "complete", Value::Null)?;
    Ok(())
}

/// Pre-launch manipulation check: load the arm's target at the probe seed,
/// report its execution and replica count, drop, exit. No sampling.
fn probe(arm: &str, model: &str, data: &str) -> Result<(), Box<dyn Error>> {
    let (want_execution, want_replicas) = expected(arm).ok_or("unknown arm")?;
    let data = fs::read_to_string(data)?;
    let (execution, replicas, info) = if arm == "replicated" {
        let t = ReplicatedStanTarget::load(Path::new(model), &default_preload(), Some(&data), PROBE_SEED as u32, REPLICAS)?;
        (format!("{:?}", t.execution()), t.effective_replicas(), t.info().to_string())
    } else {
        let t = StanTarget::load(Path::new(model), &default_preload(), Some(&data), PROBE_SEED as u32)?;
        (format!("{:?}", t.execution()), 1, t.info().to_string())
    };
    println!(
        "{}",
        serde_json::to_string(&json!({
            "schema": "bridgestan-linux-dispatch-v1-probe", "arm": arm,
            "execution": execution, "effective_replicas": replicas,
            "execution_as_expected": execution == want_execution && replicas == want_replicas,
            "model_info": info, "leftover_copy_dirs_after_drop": leftover_copy_dirs(),
            "cpus_allowed_list": cpus_allowed(),
        }))?
    );
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = if args.first().map(String::as_str) == Some("probe") && args.len() == 4 {
        probe(&args[1], &args[2], &args[3])
    } else {
        run(&args)
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn seeds_are_frozen() {
        assert!(seed_allowed(65_201_001));
        assert!(seed_allowed(65_201_500));
        assert!(!seed_allowed(65_201_501));
        assert!(!seed_allowed(50_801_734));
        assert!(seed_allowed(PROBE_SEED));
    }

    #[test]
    fn arms_have_expected_backends() {
        assert_eq!(expected("serialised"), Some(("DirectSerialised", 1)));
        assert_eq!(expected("replicated"), Some(("ReplicatedConcurrent", 4)));
        assert_eq!(expected("threaded_direct"), Some(("DirectConcurrent", 1)));
        assert_eq!(expected("owned"), None);
    }
}
