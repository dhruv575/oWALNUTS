//! One-shot child for `FINAL-QUALIFICATION.md`. Diagnostic only.
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
    sync::{Arc, Barrier},
    thread,
    time::{Instant, SystemTime, UNIX_EPOCH},
};

const CHAINS: usize = 4;
const THREADS: usize = 4;
const REQUESTED_REPLICAS: usize = 4;
const WARMUP: usize = 4;
const RETAINED: usize = 4;
const PROBES: usize = 16;
const INSTANCES: usize = 4;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    Ordinary,
    Concurrent,
}

impl Mode {
    fn name(self) -> &'static str {
        match self {
            Self::Ordinary => "ordinary",
            Self::Concurrent => "concurrent",
        }
    }
}

#[derive(Debug)]
struct Config {
    mode: Mode,
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
        let [mode, shape, model, data, seed, heartbeat_dir, output] = args.as_slice() else {
            return Err(
                "usage: <ordinary|concurrent> <shape> <model.so> <data.json> \
                 <seed> <heartbeats> <output.json>"
                    .into(),
            );
        };
        let mode = match mode.as_str() {
            "ordinary" => Mode::Ordinary,
            "concurrent" => Mode::Concurrent,
            _ => return Err("mode is outside the frozen final matrix".into()),
        };
        let seed: u64 = seed.parse()?;
        let allowed = match (mode, shape.as_str()) {
            (Mode::Ordinary, "sblrc") => (4_940_001..=4_940_180).contains(&seed),
            (Mode::Ordinary, "diamonds") => (4_940_201..=4_940_380).contains(&seed),
            (Mode::Ordinary, "mesquite") => (4_940_401..=4_940_580).contains(&seed),
            (Mode::Concurrent, "sblrc") => (4_940_601..=4_940_660).contains(&seed),
            (Mode::Concurrent, "diamonds") => (4_940_701..=4_940_760).contains(&seed),
            (Mode::Concurrent, "mesquite") => (4_940_801..=4_940_860).contains(&seed),
            _ => false,
        };
        if !allowed {
            return Err("shape/seed pair is outside the frozen final matrix".into());
        }
        Ok(Self {
            mode,
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
    mode: Mode,
    shape: String,
    seed: u64,
}

impl Heartbeat {
    fn new(config: &Config) -> Result<Self, Box<dyn Error>> {
        fs::create_dir_all(&config.heartbeat_dir)?;
        Ok(Self {
            dir: config.heartbeat_dir.clone(),
            sequence: 0,
            mode: config.mode,
            shape: config.shape.clone(),
            seed: config.seed,
        })
    }

    fn event(&mut self, stage: &str, boundary: &str) -> Result<(), Box<dyn Error>> {
        let path = self
            .dir
            .join(format!("{:04}-{stage}-{boundary}.json", self.sequence));
        let payload = json!({
            "schema": "bridgestan-owned-worker-final-qualification-heartbeat",
            "sequence": self.sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "mode": self.mode.name(),
            "shape": self.shape,
            "seed": self.seed,
            "requested_replicas": REQUESTED_REPLICAS,
            "threads": THREADS,
            "chains": CHAINS,
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

fn update_hash(hash: &mut u64, value: f64) {
    for byte in value.to_bits().to_le_bytes() {
        *hash ^= u64::from(byte);
        *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
}

fn sample_fingerprint(posterior: &owalnuts::sampler::Posterior) -> (String, usize, bool, f64) {
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
                update_hash(&mut hash, *value);
            }
        }
    }
    (format!("{hash:016x}"), observed, finite, checksum)
}

fn settings(config: &Config) -> Value {
    json!({
        "shape": config.shape,
        "seed": config.seed,
        "requested_replicas": REQUESTED_REPLICAS,
        "threads": THREADS,
        "chains": CHAINS,
        "warmup_per_chain": WARMUP,
        "retained_per_chain": RETAINED,
        "metric": "diagonal",
        "adaptation": "default",
        "tuning": "default",
        "limits": "admit_worst_case",
        "model": config.model.display().to_string(),
        "data": config.data.display().to_string(),
    })
}

fn sample_once(
    config: &Config,
    data: &str,
    label: &str,
    heartbeat: &mut Heartbeat,
) -> Result<(Value, Value), Box<dyn Error>> {
    let load_stage = format!("{label}-load");
    heartbeat.event(&load_stage, "before")?;
    let load_started = Instant::now();
    let target = ReplicatedStanTarget::load(
        &config.model,
        &default_preload(),
        Some(data),
        config.seed as u32,
        REQUESTED_REPLICAS,
    )?;
    let load_seconds = load_started.elapsed().as_secs_f64();
    heartbeat.event(&load_stage, "after")?;

    let initialization_stage = format!("{label}-initialization");
    heartbeat.event(&initialization_stage, "before")?;
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    let starts = uniform_starts(&target, CHAINS, config.seed, radius, max_attempts)?;
    heartbeat.event(&initialization_stage, "after")?;

    let sampling_stage = format!("{label}-sampling");
    heartbeat.event(&sampling_stage, "before")?;
    let sampling_started = Instant::now();
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
    let sample_seconds = sampling_started.elapsed().as_secs_f64();
    heartbeat.event(&sampling_stage, "after")?;

    let (fingerprint, samples_observed, all_finite, diagnostic_checksum) =
        sample_fingerprint(&posterior);
    let comparison = json!({
        "settings": settings(config),
        "sample_fingerprint_fnv1a64": fingerprint,
        "diagnostic_checksum": diagnostic_checksum,
        "samples_observed": samples_observed,
        "all_retained_values_finite": all_finite,
        "algorithm_revision": posterior.algorithm_revision(),
        "target_calls": target.calls(),
        "recoverable_failures": target.recoverable_failures(),
        "dimension": target.dimension(),
        "parameter_names": target.param_unc_names(),
        "model_info": target.info(),
        "compiled_threading": format!("{:?}", target.compiled_threading()),
        "threading": format!("{:?}", target.threading()),
        "execution": format!("{:?}", target.execution()),
        "requested_replicas": target.requested_replicas(),
        "effective_replicas": target.effective_replicas(),
    });
    let timing = json!({
        "load_seconds": load_seconds,
        "sample_seconds": sample_seconds,
    });

    let drop_stage = format!("{label}-drop");
    heartbeat.event(&drop_stage, "before")?;
    drop(target);
    heartbeat.event(&drop_stage, "after")?;
    Ok((comparison, timing))
}

fn run_ordinary(
    config: &Config,
    data: &str,
    heartbeat: &mut Heartbeat,
) -> Result<Value, Box<dyn Error>> {
    let (run_a, timing_a) = sample_once(config, data, "ordinary-a", heartbeat)?;
    let (run_b, timing_b) = sample_once(config, data, "ordinary-b", heartbeat)?;
    heartbeat.event("parity-check", "before")?;
    let parity_exact = run_a == run_b;
    heartbeat.event("parity-check", "after")?;
    Ok(json!({
        "schema": "bridgestan-owned-worker-final-qualification-child",
        "status": if parity_exact { "ok" } else { "parity_mismatch" },
        "diagnostic_only": true,
        "mode": config.mode.name(),
        "shape": config.shape,
        "seed": config.seed,
        "requested_replicas": REQUESTED_REPLICAS,
        "effective_replicas": 1,
        "threads": THREADS,
        "chains": CHAINS,
        "warmup_per_chain": WARMUP,
        "retained_per_chain": RETAINED,
        "expected_samples_per_run": CHAINS * RETAINED,
        "parity_exact": parity_exact,
        "run_a": run_a,
        "run_b": run_b,
        "timing_a": timing_a,
        "timing_b": timing_b,
    }))
}

fn splitmix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9E37_79B9_7F4A_7C15);
    value = (value ^ (value >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
    value ^ (value >> 31)
}

fn probe_positions(seed: u64, dimension: usize) -> Vec<Vec<f64>> {
    (0..PROBES)
        .map(|probe| {
            (0..dimension)
                .map(|coordinate| {
                    let word = splitmix64(
                        seed.wrapping_add((probe as u64) << 32)
                            .wrapping_add(coordinate as u64),
                    );
                    let integer = (word % 1001) as i64 - 500;
                    integer as f64 / 2000.0
                })
                .collect()
        })
        .collect()
}

fn evaluate_instance(target: &ReplicatedStanTarget, config: &Config) -> Result<Value, String> {
    let positions = probe_positions(config.seed, target.dimension());
    let mut output_hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut position_hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut checksum = 0.0;
    let mut all_finite = true;
    for position in &positions {
        for coordinate in position {
            update_hash(&mut position_hash, *coordinate);
        }
        let mut gradient = vec![0.0; target.dimension()];
        let value = target
            .log_density_gradient(position, &mut gradient)
            .map_err(|error| error.to_string())?;
        all_finite &= value.is_finite() && gradient.iter().all(|entry| entry.is_finite());
        checksum += value + gradient.iter().sum::<f64>();
        update_hash(&mut output_hash, value);
        for entry in gradient {
            update_hash(&mut output_hash, entry);
        }
    }
    Ok(json!({
        "settings": settings(config),
        "probe_count": PROBES,
        "position_fingerprint_fnv1a64": format!("{position_hash:016x}"),
        "value_gradient_fingerprint_fnv1a64": format!("{output_hash:016x}"),
        "diagnostic_checksum": checksum,
        "all_values_finite": all_finite,
        "target_calls": target.calls(),
        "recoverable_failures": target.recoverable_failures(),
        "dimension": target.dimension(),
        "parameter_names": target.param_unc_names(),
        "model_info": target.info(),
        "compiled_threading": format!("{:?}", target.compiled_threading()),
        "threading": format!("{:?}", target.threading()),
        "execution": format!("{:?}", target.execution()),
        "requested_replicas": target.requested_replicas(),
        "effective_replicas": target.effective_replicas(),
    }))
}

fn run_concurrent(
    config: &Config,
    data: &str,
    heartbeat: &mut Heartbeat,
) -> Result<Value, Box<dyn Error>> {
    heartbeat.event("multi-target", "before")?;
    let start = Arc::new(Barrier::new(INSTANCES));
    let after_load = Arc::new(Barrier::new(INSTANCES));
    let before_drop = Arc::new(Barrier::new(INSTANCES));
    let observations = thread::scope(|scope| {
        let handles = (0..INSTANCES)
            .map(|_| {
                let start = Arc::clone(&start);
                let after_load = Arc::clone(&after_load);
                let before_drop = Arc::clone(&before_drop);
                scope.spawn(move || {
                    start.wait();
                    let loaded = ReplicatedStanTarget::load(
                        &config.model,
                        &default_preload(),
                        Some(data),
                        config.seed as u32,
                        REQUESTED_REPLICAS,
                    )
                    .map_err(|error| error.to_string());
                    after_load.wait();
                    match loaded {
                        Ok(target) => {
                            let result = evaluate_instance(&target, config);
                            before_drop.wait();
                            drop(target);
                            result
                        }
                        Err(error) => {
                            before_drop.wait();
                            Err(error)
                        }
                    }
                })
            })
            .collect::<Vec<_>>();
        handles
            .into_iter()
            .map(|handle| {
                handle
                    .join()
                    .map_err(|_| "concurrent caller panicked".to_owned())?
            })
            .collect::<Result<Vec<_>, String>>()
    })
    .map_err(|error| -> Box<dyn Error> { error.into() })?;
    heartbeat.event("multi-target", "after")?;

    heartbeat.event("parity-check", "before")?;
    let parity_exact = observations[1..]
        .iter()
        .all(|observation| observation == &observations[0]);
    let calls = observations
        .iter()
        .map(|observation| observation["target_calls"].as_u64().unwrap_or(0))
        .collect::<Vec<_>>();
    let effective = observations
        .iter()
        .map(|observation| observation["effective_replicas"].as_u64().unwrap_or(0))
        .collect::<Vec<_>>();
    heartbeat.event("parity-check", "after")?;
    Ok(json!({
        "schema": "bridgestan-owned-worker-final-qualification-child",
        "status": if parity_exact { "ok" } else { "parity_mismatch" },
        "diagnostic_only": true,
        "mode": config.mode.name(),
        "shape": config.shape,
        "seed": config.seed,
        "requested_replicas": REQUESTED_REPLICAS,
        "effective_replicas": effective,
        "threads": THREADS,
        "target_instances": INSTANCES,
        "probes_per_instance": PROBES,
        "expected_calls_per_instance": PROBES,
        "expected_calls_total": PROBES * INSTANCES,
        "calls_per_instance": calls,
        "calls_total": calls.iter().sum::<u64>(),
        "parity_exact": parity_exact,
        "instances": observations,
    }))
}

fn run(config: &Config) -> Result<(), Box<dyn Error>> {
    if config.output.exists() {
        return Err(format!("output already exists: {}", config.output.display()).into());
    }
    let data = fs::read_to_string(&config.data)?;
    let mut heartbeat = Heartbeat::new(config)?;
    heartbeat.event("process", "start")?;
    let payload = match config.mode {
        Mode::Ordinary => run_ordinary(config, &data, &mut heartbeat)?,
        Mode::Concurrent => run_concurrent(config, &data, &mut heartbeat)?,
    };
    heartbeat.event("result-write", "before")?;
    write_new_atomically(&config.output, &serde_json::to_vec_pretty(&payload)?)?;
    heartbeat.event("result-write", "after")?;
    if payload["status"] != "ok" {
        return Err("exact parity check failed".into());
    }
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

    fn args(mode: &str, shape: &str, seed: u64) -> [OsString; 7] {
        [
            mode.into(),
            shape.into(),
            "model.so".into(),
            "data.json".into(),
            seed.to_string().into(),
            "heartbeats".into(),
            "output.json".into(),
        ]
    }

    #[test]
    fn accepts_only_final_registered_shape_seed_pairs() {
        for (mode, shape, first, last) in [
            ("ordinary", "sblrc", 4_940_001, 4_940_180),
            ("ordinary", "diamonds", 4_940_201, 4_940_380),
            ("ordinary", "mesquite", 4_940_401, 4_940_580),
            ("concurrent", "sblrc", 4_940_601, 4_940_660),
            ("concurrent", "diamonds", 4_940_701, 4_940_760),
            ("concurrent", "mesquite", 4_940_801, 4_940_860),
        ] {
            assert!(Config::parse(args(mode, shape, first)).is_ok());
            assert!(Config::parse(args(mode, shape, last)).is_ok());
        }
        assert!(Config::parse(args("ordinary", "sblrc", 993_001)).is_err());
        assert!(Config::parse(args("concurrent", "sblrc", 4_940_001)).is_err());
        assert!(Config::parse(args("unknown", "sblrc", 4_940_001)).is_err());
    }

    #[test]
    fn deterministic_probe_positions_are_seeded_and_bounded() {
        let first = probe_positions(4_940_601, 7);
        assert_eq!(first, probe_positions(4_940_601, 7));
        assert_ne!(first, probe_positions(4_940_602, 7));
        assert_eq!(first.len(), PROBES);
        assert!(
            first
                .iter()
                .flatten()
                .all(|coordinate| (-0.25..=0.25).contains(coordinate))
        );
    }
}
