//! WP50B process-lifetime diagnostic child, built against the integration's
//! original reproducing code path (commit 9edcbac: four resident replica
//! modules evaluated concurrently from the sampler's worker threads). Derived
//! from the `bridgestan_owned_worker_v1` comparator child. Additionally records
//! the full path and size of every mingw runtime module actually loaded
//! (`libwinpthread-1.dll`, `libgcc_s_seh-1.dll`, `libstdc++-6.dll`, `tbb.dll`).
//! This produces no posterior evidence.
#![deny(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{
    env,
    error::Error,
    ffi::OsString,
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    time::{Instant, SystemTime, UNIX_EPOCH},
};

const CHAINS: usize = 4;
const THREADS: usize = 4;
const REQUESTED_REPLICAS: usize = 4;
const WARMUP: usize = 4;
const RETAINED: usize = 4;

#[derive(Debug)]
struct Config {
    shape: String,
    model: PathBuf,
    data: PathBuf,
    seed: u64,
    heartbeat_dir: PathBuf,
    output: PathBuf,
}

impl Config {
    fn parse(args: impl IntoIterator<Item = OsString>) -> Result<Self, Box<dyn Error>> {
        let args = args
            .into_iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        let [shape, model, data, seed, heartbeat_dir, output] = args.as_slice() else {
            return Err(
                "usage: <shape> <model.so> <data.json> <seed> <heartbeats> <output.json>".into(),
            );
        };
        let seed: u64 = seed.parse()?;
        let allowed = shape == "sblrc" && (50_600_001..=50_600_060).contains(&seed);
        if !allowed {
            return Err("shape/seed pair is outside the frozen diagnostic matrix".into());
        }
        Ok(Self {
            shape: shape.clone(),
            model: model.into(),
            data: data.into(),
            seed,
            heartbeat_dir: heartbeat_dir.into(),
            output: output.into(),
        })
    }
}

struct Heartbeat {
    dir: PathBuf,
    sequence: usize,
    shape: String,
    seed: u64,
}

impl Heartbeat {
    fn new(config: &Config) -> Result<Self, Box<dyn Error>> {
        fs::create_dir_all(&config.heartbeat_dir)?;
        Ok(Self {
            dir: config.heartbeat_dir.clone(),
            sequence: 0,
            shape: config.shape.clone(),
            seed: config.seed,
        })
    }

    fn event(&mut self, stage: &str, boundary: &str) -> Result<(), Box<dyn Error>> {
        self.event_with(stage, boundary, Value::Null)
    }

    fn event_with(
        &mut self,
        stage: &str,
        boundary: &str,
        detail: Value,
    ) -> Result<(), Box<dyn Error>> {
        let path = self
            .dir
            .join(format!("{:04}-{stage}-{boundary}.json", self.sequence));
        let payload = json!({
            "schema": "bridgestan-windows-root-cause-v2-heartbeat",
            "sequence": self.sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "shape": self.shape,
            "seed": self.seed,
            "requested_replicas": REQUESTED_REPLICAS,
            "threads": THREADS,
            "chains": CHAINS,
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
    let parent = path
        .parent()
        .ok_or_else(|| format!("path has no parent: {}", path.display()))?;
    fs::create_dir_all(parent)?;
    let file_name = path
        .file_name()
        .ok_or_else(|| format!("path has no file name: {}", path.display()))?
        .to_string_lossy();
    let temporary = parent.join(format!(".{file_name}.tmp-{}", std::process::id()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temporary)?;
    file.write_all(bytes)?;
    if !bytes.ends_with(b"\n") {
        file.write_all(b"\n")?;
    }
    file.sync_all()?;
    drop(file);
    fs::rename(temporary, path)?;
    Ok(())
}

fn initialize(target: &ReplicatedStanTarget, seed: u64) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    Ok(uniform_starts(target, CHAINS, seed, radius, max_attempts)?)
}

fn fingerprint(posterior: &owalnuts::sampler::Posterior) -> (String, usize, bool, f64) {
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut observed = 0;
    let mut finite = true;
    let mut checksum = 0.0;
    for chain in posterior.chains() {
        for index in 0..RETAINED {
            let draw = chain.sample(index).expect("retained draw count is fixed");
            observed += 1;
            for value in draw {
                finite &= value.is_finite();
                checksum += value;
                for byte in value.to_bits().to_le_bytes() {
                    hash ^= u64::from(byte);
                    hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
                }
            }
        }
    }
    (format!("{hash:016x}"), observed, finite, checksum)
}

/// Full path and size of each mingw runtime module currently mapped in this
/// process, via `GetModuleHandleW` + `GetModuleFileNameW` (no load is caused:
/// a module that is not already mapped reports `null`).
#[allow(unsafe_code)]
fn loaded_runtime_modules() -> Value {
    use std::ffi::c_void;
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetModuleHandleW(name: *const u16) -> *mut c_void;
        fn GetModuleFileNameW(module: *mut c_void, buffer: *mut u16, size: u32) -> u32;
    }
    let mut out = serde_json::Map::new();
    for name in [
        "libwinpthread-1.dll",
        "libgcc_s_seh-1.dll",
        "libstdc++-6.dll",
        "tbb.dll",
    ] {
        let wide: Vec<u16> = name.encode_utf16().chain(std::iter::once(0)).collect();
        // SAFETY: NUL-terminated UTF-16 name; GetModuleHandleW does not load or
        // add a reference, it only looks up an already-mapped module.
        let handle = unsafe { GetModuleHandleW(wide.as_ptr()) };
        if handle.is_null() {
            out.insert(name.into(), Value::Null);
            continue;
        }
        let mut buffer = vec![0u16; 32_768];
        // SAFETY: valid module handle and a writable buffer of the stated size.
        let len = unsafe { GetModuleFileNameW(handle, buffer.as_mut_ptr(), buffer.len() as u32) };
        let path = String::from_utf16_lossy(&buffer[..len as usize]);
        let bytes = fs::metadata(&path).map(|m| m.len()).ok();
        out.insert(name.into(), json!({"path": path, "bytes": bytes}));
    }
    Value::Object(out)
}

fn run(config: &Config) -> Result<(), Box<dyn Error>> {
    if config.output.exists() {
        return Err(format!("output already exists: {}", config.output.display()).into());
    }
    let process_started = Instant::now();
    let data = fs::read_to_string(&config.data)?;
    let mut heartbeat = Heartbeat::new(config)?;
    heartbeat.event("process", "start")?;
    heartbeat.event("load", "before")?;
    let load_started = Instant::now();
    let target = ReplicatedStanTarget::load(
        &config.model,
        &default_preload(),
        Some(&data),
        config.seed as u32,
        REQUESTED_REPLICAS,
    )?;
    let load_seconds = load_started.elapsed().as_secs_f64();
    let modules = loaded_runtime_modules();
    heartbeat.event_with("load", "after", modules.clone())?;
    heartbeat.event("initialization", "before")?;
    let starts = initialize(&target, config.seed)?;
    heartbeat.event("initialization", "after")?;
    heartbeat.event("sampling", "before")?;
    let sample_started = Instant::now();
    let posterior = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(CHAINS)
        .seed(config.seed)
        .threads(THREADS)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts)?;
    let sample_seconds = sample_started.elapsed().as_secs_f64();
    heartbeat.event("sampling", "after")?;

    let (fingerprint, samples_observed, all_finite, diagnostic_checksum) = fingerprint(&posterior);
    let payload: Value = json!({
        "schema": "bridgestan-windows-root-cause-v2-child",
        "status": "ok",
        "diagnostic_only": true,
        "shape": config.shape,
        "seed": config.seed,
        "requested_replicas": REQUESTED_REPLICAS,
        "effective_replicas": target.replicas(),
        "threads": THREADS,
        "chains": CHAINS,
        "warmup_per_chain": WARMUP,
        "retained_per_chain": RETAINED,
        "samples_observed": samples_observed,
        "all_retained_values_finite": all_finite,
        "sample_fingerprint_fnv1a64": fingerprint,
        "diagnostic_checksum": diagnostic_checksum,
        "algorithm_revision": posterior.algorithm_revision(),
        "target_calls": target.calls(),
        "recoverable_failures": target.recoverable_failures(),
        "dimension": target.dimension(),
        "threading": format!("{:?}", target.threading()),
        "load_seconds": load_seconds,
        "sample_seconds": sample_seconds,
        "elapsed_before_drop_seconds": process_started.elapsed().as_secs_f64(),
        "loaded_runtime_modules": modules,
        "path_env": env::var("PATH").unwrap_or_default(),
        "model": config.model.display().to_string(),
        "data": config.data.display().to_string(),
    });
    heartbeat.event("result_write", "before")?;
    write_new_atomically(&config.output, &serde_json::to_vec_pretty(&payload)?)?;
    heartbeat.event("result_write", "after")?;
    heartbeat.event("drop", "before")?;
    drop(target);
    heartbeat.event("drop", "after")?;
    heartbeat.event("process", "complete")?;
    Ok(())
}

/// Pre-launch manipulation check only: load ONE replica (no sampling, no
/// evidence seed), report which runtime modules bound, drop, exit.
fn probe(model: &str, data: &str) -> Result<(), Box<dyn Error>> {
    let data = fs::read_to_string(data)?;
    let target =
        ReplicatedStanTarget::load(Path::new(model), &default_preload(), Some(&data), 50_600_000, 1)?;
    let report = json!({
        "schema": "bridgestan-windows-root-cause-v2-probe",
        "loaded_runtime_modules": loaded_runtime_modules(),
        "replicas": target.replicas(),
        "path_env": env::var("PATH").unwrap_or_default(),
    });
    drop(target);
    println!("{}", serde_json::to_string(&report)?);
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.first().map(String::as_str) == Some("probe") && args.len() == 3 {
        if let Err(error) = probe(&args[1], &args[2]) {
            eprintln!("error: {error}");
            std::process::exit(1);
        }
        return;
    }
    let result = Config::parse(env::args_os().skip(1)).and_then(|config| run(&config));
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn args(shape: &str, seed: u64) -> [OsString; 6] {
        [
            shape.into(),
            "model.so".into(),
            "data.json".into(),
            seed.to_string().into(),
            "heartbeats".into(),
            "output.json".into(),
        ]
    }

    #[test]
    fn accepts_only_frozen_shape_seed_pairs() {
        assert!(Config::parse(args("sblrc", 50_600_001)).is_ok());
        assert!(Config::parse(args("sblrc", 50_600_060)).is_ok());
        assert!(Config::parse(args("sblrc", 50_600_061)).is_err());
        assert!(Config::parse(args("sblrc", 90_101)).is_err());
        assert!(Config::parse(args("diamonds", 50_600_001)).is_err());
    }

    #[test]
    fn module_probe_reports_kernel_free_names_without_loading() {
        let modules = loaded_runtime_modules();
        let object = modules.as_object().expect("object");
        assert_eq!(object.len(), 4);
        // The test binary does not map BridgeStan's mingw runtime itself.
        assert!(object["tbb.dll"].is_null());
    }
}
