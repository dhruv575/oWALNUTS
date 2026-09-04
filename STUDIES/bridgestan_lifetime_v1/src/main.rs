//! Fast process-lifetime diagnostic child. This produces no posterior evidence.
#![forbid(unsafe_code)]

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
    time::{SystemTime, UNIX_EPOCH},
};

const WARMUP: usize = 4;
const RETAINED: usize = 4;
const FIRST_DIAGNOSTIC_SEED: u64 = 991_001;
const LAST_DIAGNOSTIC_SEED: u64 = 991_180;

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
        if !matches!(shape.as_str(), "sblrc" | "diamonds" | "mesquite") {
            return Err(format!("unknown diagnostic shape {shape:?}").into());
        }
        let seed = seed.parse()?;
        if !(FIRST_DIAGNOSTIC_SEED..=LAST_DIAGNOSTIC_SEED).contains(&seed) {
            return Err(format!(
                "seed must be in diagnostic range {FIRST_DIAGNOSTIC_SEED}..={LAST_DIAGNOSTIC_SEED}"
            )
            .into());
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
        let path = self
            .dir
            .join(format!("{:04}-{stage}-{boundary}.json", self.sequence));
        let payload = json!({
            "schema": "bridgestan-lifetime-v1-heartbeat",
            "sequence": self.sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "shape": self.shape,
            "seed": self.seed,
            "replicas": 4,
            "threads": 4,
            "chains": 4,
            "stage": stage,
            "boundary": boundary,
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
    Ok(uniform_starts(target, 4, seed, radius, max_attempts)?)
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

fn run(config: &Config) -> Result<(), Box<dyn Error>> {
    if config.output.exists() {
        return Err(format!("output already exists: {}", config.output.display()).into());
    }
    let data = fs::read_to_string(&config.data)?;
    let mut heartbeat = Heartbeat::new(config)?;
    heartbeat.event("process", "start")?;
    heartbeat.event("load", "before")?;
    let target = ReplicatedStanTarget::load(
        &config.model,
        &default_preload(),
        Some(&data),
        config.seed as u32,
        4,
    )?;
    heartbeat.event("load", "after")?;
    heartbeat.event("initialization", "before")?;
    let starts = initialize(&target, config.seed)?;
    heartbeat.event("initialization", "after")?;
    heartbeat.event("sampling", "before")?;
    let posterior = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(4)
        .seed(config.seed)
        .threads(4)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case())
        .run(&target, &starts)?;
    heartbeat.event("sampling", "after")?;

    let (fingerprint, samples_observed, all_finite, diagnostic_checksum) = fingerprint(&posterior);
    let payload: Value = json!({
        "schema": "bridgestan-lifetime-v1-child",
        "status": "ok",
        "diagnostic_only": true,
        "shape": config.shape,
        "seed": config.seed,
        "replicas": 4,
        "threads": 4,
        "chains": 4,
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
        "replicas_loaded": target.replicas(),
        "threading": format!("{:?}", target.threading()),
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

fn main() {
    let result = Config::parse(env::args_os().skip(1)).and_then(|config| run(&config));
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn accepts_only_the_frozen_diagnostic_seed_range() {
        let args = |seed: u64| {
            [
                "sblrc".into(),
                "model.so".into(),
                "data.json".into(),
                seed.to_string().into(),
                "heartbeats".into(),
                "output.json".into(),
            ]
        };
        assert!(Config::parse(args(FIRST_DIAGNOSTIC_SEED)).is_ok());
        assert!(Config::parse(args(LAST_DIAGNOSTIC_SEED)).is_ok());
        assert!(Config::parse(args(90101)).is_err());
        assert!(Config::parse(args(FIRST_DIAGNOSTIC_SEED - 1)).is_err());
    }
}
