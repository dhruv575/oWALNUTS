//! Process-lifecycle diagnostic for the WP35 silent `sblrc` child exit.
//!
//! This harness deliberately reports only process and lifecycle facts. Its
//! samples and timings are not posterior-performance evidence.
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
    time::{Instant, SystemTime, UNIX_EPOCH},
};

const WARMUP: usize = 1000;
const RETAINED: usize = 1000;
const FORBIDDEN_SEED: u64 = 90101;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Mode {
    LoadDrop,
    Evaluate,
    Sample,
    RepeatLoadDrop,
}

impl Mode {
    fn parse(value: &str) -> Result<Self, Box<dyn Error>> {
        match value {
            "load_drop" => Ok(Self::LoadDrop),
            "evaluate" => Ok(Self::Evaluate),
            "sample" => Ok(Self::Sample),
            "repeat_load_drop" => Ok(Self::RepeatLoadDrop),
            _ => Err(format!("unknown mode {value:?}").into()),
        }
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::LoadDrop => "load_drop",
            Self::Evaluate => "evaluate",
            Self::Sample => "sample",
            Self::RepeatLoadDrop => "repeat_load_drop",
        }
    }

    fn work_stage(self) -> &'static str {
        match self {
            Self::LoadDrop | Self::RepeatLoadDrop => "load_drop_work",
            Self::Evaluate => "evaluation",
            Self::Sample => "sampling",
        }
    }
}

#[derive(Debug)]
struct Config {
    mode: Mode,
    model: PathBuf,
    data: PathBuf,
    seed: u64,
    replicas: usize,
    threads: usize,
    chains: usize,
    heartbeat_dir: PathBuf,
    output: PathBuf,
    work_units: usize,
}

impl Config {
    fn parse(args: impl IntoIterator<Item = OsString>) -> Result<Self, Box<dyn Error>> {
        let args = args
            .into_iter()
            .map(|arg| arg.to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        let [
            mode,
            model,
            data,
            seed,
            replicas,
            threads,
            chains,
            heartbeat,
            output,
            work_units,
        ] = args.as_slice()
        else {
            return Err(
                "usage: <mode> <model.so> <data.json> <seed> <replicas> <threads> \
                 <chains> <heartbeat-dir> <output.json> <work-units>"
                    .into(),
            );
        };
        let cfg = Self {
            mode: Mode::parse(mode)?,
            model: PathBuf::from(model),
            data: PathBuf::from(data),
            seed: seed.parse()?,
            replicas: replicas.parse()?,
            threads: threads.parse()?,
            chains: chains.parse()?,
            heartbeat_dir: PathBuf::from(heartbeat),
            output: PathBuf::from(output),
            work_units: work_units.parse()?,
        };
        cfg.validate()?;
        Ok(cfg)
    }

    fn validate(&self) -> Result<(), Box<dyn Error>> {
        if self.seed == FORBIDDEN_SEED {
            return Err(format!("evidence seed {FORBIDDEN_SEED} is forbidden").into());
        }
        if self.seed > u32::MAX as u64 {
            return Err("seed does not fit BridgeStan's u32 seed".into());
        }
        if self.replicas == 0 || self.threads == 0 {
            return Err("replicas and threads must be positive".into());
        }
        match self.mode {
            Mode::LoadDrop if self.chains != 0 || self.work_units != 0 => {
                Err("load_drop requires chains=0 and work-units=0".into())
            }
            Mode::Evaluate if self.chains != 0 || self.work_units == 0 => {
                Err("evaluate requires chains=0 and positive work-units".into())
            }
            Mode::Sample if self.chains == 0 || self.work_units != 0 => {
                Err("sample requires positive chains and work-units=0".into())
            }
            Mode::RepeatLoadDrop if self.chains != 0 || self.work_units == 0 => {
                Err("repeat_load_drop requires chains=0 and positive work-units".into())
            }
            _ => Ok(()),
        }
    }
}

struct Heartbeat {
    dir: PathBuf,
    seq: usize,
    mode: Mode,
    seed: u64,
    replicas: usize,
    threads: usize,
    chains: usize,
}

impl Heartbeat {
    fn new(cfg: &Config) -> Result<Self, Box<dyn Error>> {
        fs::create_dir_all(&cfg.heartbeat_dir)?;
        Ok(Self {
            dir: cfg.heartbeat_dir.clone(),
            seq: 0,
            mode: cfg.mode,
            seed: cfg.seed,
            replicas: cfg.replicas,
            threads: cfg.threads,
            chains: cfg.chains,
        })
    }

    fn event(
        &mut self,
        stage: &str,
        boundary: &str,
        cycle: Option<usize>,
        detail: Option<&str>,
    ) -> Result<(), Box<dyn Error>> {
        let sequence = self.seq;
        let name = format!("{sequence:04}-{stage}-{boundary}.json");
        let final_path = self.dir.join(&name);
        if final_path.exists() {
            return Err(format!("heartbeat event already exists: {}", final_path.display()).into());
        }
        let payload = json!({
            "schema": "sblrc-process-stability-v1-heartbeat",
            "sequence": sequence,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "mode": self.mode.as_str(),
            "seed": self.seed,
            "replicas": self.replicas,
            "threads": self.threads,
            "chains": self.chains,
            "stage": stage,
            "boundary": boundary,
            "cycle": cycle,
            "detail": detail,
        });
        write_new_atomically(&final_path, &serde_json::to_vec_pretty(&payload)?)?;
        self.seq += 1;
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
    let temp = parent.join(format!(".{file_name}.tmp-{}", std::process::id()));
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(&temp)?;
    file.write_all(bytes)?;
    if !bytes.ends_with(b"\n") {
        file.write_all(b"\n")?;
    }
    file.sync_all()?;
    drop(file);
    fs::rename(&temp, path)?;
    Ok(())
}

fn init_settings() -> (f64, usize) {
    match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must return Init::Uniform"),
    }
}

fn initialize(
    target: &ReplicatedStanTarget,
    count: usize,
    seed: u64,
) -> Result<Vec<Vec<f64>>, Box<dyn Error>> {
    let (radius, max_attempts) = init_settings();
    Ok(uniform_starts(target, count, seed, radius, max_attempts)?)
}

fn evaluate(
    target: &ReplicatedStanTarget,
    starts: &[Vec<f64>],
    threads: usize,
    iterations: usize,
) -> Result<Value, Box<dyn Error>> {
    let checksums = std::thread::scope(|scope| {
        let mut handles = Vec::with_capacity(threads);
        for worker in 0..threads {
            let position = starts[worker].clone();
            handles.push(scope.spawn(move || -> Result<f64, String> {
                let mut gradient = vec![0.0; position.len()];
                let mut checksum = 0.0;
                for _ in 0..iterations {
                    let value = target
                        .log_density_gradient(&position, &mut gradient)
                        .map_err(|error| error.to_string())?;
                    checksum += value + gradient.iter().sum::<f64>() * f64::EPSILON;
                }
                Ok(checksum)
            }));
        }
        handles
            .into_iter()
            .map(|handle| {
                handle
                    .join()
                    .map_err(|_| "evaluation worker panicked".to_string())?
            })
            .collect::<Result<Vec<_>, String>>()
    })
    .map_err(|error| -> Box<dyn Error> { error.into() })?;
    Ok(json!({
        "workers": threads,
        "evaluations_per_worker": iterations,
        "evaluations_requested": threads * iterations,
        "checksums": checksums,
    }))
}

fn sample(
    target: &ReplicatedStanTarget,
    starts: &[Vec<f64>],
    cfg: &Config,
) -> Result<Value, Box<dyn Error>> {
    let sampler = Sampler::new()
        .warmup(WARMUP)
        .draws(RETAINED)
        .chains(cfg.chains)
        .seed(cfg.seed)
        .threads(cfg.threads)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case());
    let posterior = sampler.run(target, starts)?;
    let mut finite = true;
    let mut checksum = 0.0;
    let mut samples_observed = 0usize;
    for chain in posterior.chains() {
        for index in 0..RETAINED {
            let draw = chain
                .sample(index)
                .ok_or_else(|| format!("missing retained draw {index}"))?;
            samples_observed += 1;
            for value in draw {
                finite &= value.is_finite();
                checksum += value;
            }
        }
    }
    Ok(json!({
        "warmup_per_chain": WARMUP,
        "retained_per_chain": RETAINED,
        "chains": cfg.chains,
        "samples_observed": samples_observed,
        "all_retained_values_finite": finite,
        "diagnostic_checksum": checksum,
        "algorithm_revision": posterior.algorithm_revision(),
    }))
}

fn target_metadata(target: &ReplicatedStanTarget) -> Value {
    json!({
        "dimension": target.dimension(),
        "replicas_loaded": target.replicas(),
        "threading": format!("{:?}", target.threading()),
        "model_info": target.info(),
        "target_calls": target.calls(),
        "recoverable_failures": target.recoverable_failures(),
    })
}

fn run_single(cfg: &Config, data: &str, heartbeat: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    heartbeat.event("load", "before", None, None)?;
    let target = ReplicatedStanTarget::load(
        &cfg.model,
        &default_preload(),
        Some(data),
        cfg.seed as u32,
        cfg.replicas,
    )?;
    heartbeat.event("load", "after", None, None)?;

    heartbeat.event("initialization", "before", None, None)?;
    let starts = match cfg.mode {
        Mode::LoadDrop => Vec::new(),
        Mode::Evaluate => initialize(&target, cfg.threads, cfg.seed)?,
        Mode::Sample => initialize(&target, cfg.chains, cfg.seed)?,
        Mode::RepeatLoadDrop => unreachable!(),
    };
    heartbeat.event(
        "initialization",
        "after",
        None,
        (cfg.mode == Mode::LoadDrop).then_some("not applicable to load-only mode"),
    )?;

    let work_stage = cfg.mode.work_stage();
    heartbeat.event(work_stage, "before", None, None)?;
    let work_begin = Instant::now();
    let work = match cfg.mode {
        Mode::LoadDrop => json!({"kind": "load_only"}),
        Mode::Evaluate => evaluate(&target, &starts, cfg.threads, cfg.work_units)?,
        Mode::Sample => sample(&target, &starts, cfg)?,
        Mode::RepeatLoadDrop => unreachable!(),
    };
    let work_seconds = work_begin.elapsed().as_secs_f64();
    heartbeat.event(work_stage, "after", None, None)?;

    let payload = json!({
        "schema": "sblrc-process-stability-v1-raw",
        "status": "ok",
        "mode": cfg.mode.as_str(),
        "seed": cfg.seed,
        "replicas": cfg.replicas,
        "threads": cfg.threads,
        "chains": cfg.chains,
        "warmup": (cfg.mode == Mode::Sample).then_some(WARMUP),
        "retained": (cfg.mode == Mode::Sample).then_some(RETAINED),
        "work_units": cfg.work_units,
        "work_seconds": work_seconds,
        "model": cfg.model.display().to_string(),
        "data": cfg.data.display().to_string(),
        "target": target_metadata(&target),
        "work": work,
        "raw_written_before_explicit_drop": true,
        "evidence_use": "forbidden; process diagnostic only",
    });
    heartbeat.event("result_write", "before", None, None)?;
    write_new_atomically(&cfg.output, &serde_json::to_vec_pretty(&payload)?)?;
    heartbeat.event("result_write", "after", None, None)?;

    heartbeat.event("drop", "before", None, None)?;
    drop(target);
    heartbeat.event("drop", "after", None, None)?;
    heartbeat.event("process", "complete", None, None)?;
    Ok(())
}

fn run_repeated(cfg: &Config, data: &str, heartbeat: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    let begin = Instant::now();
    let mut dimensions = Vec::with_capacity(cfg.work_units);
    for cycle in 0..cfg.work_units {
        heartbeat.event("load", "before", Some(cycle), None)?;
        let target = ReplicatedStanTarget::load(
            &cfg.model,
            &default_preload(),
            Some(data),
            cfg.seed as u32,
            cfg.replicas,
        )?;
        heartbeat.event("load", "after", Some(cycle), None)?;
        heartbeat.event(
            "initialization",
            "before",
            Some(cycle),
            Some("not applicable to load-only mode"),
        )?;
        heartbeat.event(
            "initialization",
            "after",
            Some(cycle),
            Some("not applicable to load-only mode"),
        )?;
        heartbeat.event("load_drop_work", "before", Some(cycle), None)?;
        dimensions.push(target.dimension());
        heartbeat.event("load_drop_work", "after", Some(cycle), None)?;
        heartbeat.event("drop", "before", Some(cycle), None)?;
        drop(target);
        heartbeat.event("drop", "after", Some(cycle), None)?;
    }
    let payload = json!({
        "schema": "sblrc-process-stability-v1-raw",
        "status": "ok",
        "mode": cfg.mode.as_str(),
        "seed": cfg.seed,
        "replicas": cfg.replicas,
        "threads": cfg.threads,
        "chains": cfg.chains,
        "load_drop_cycles": cfg.work_units,
        "dimensions": dimensions,
        "work_seconds": begin.elapsed().as_secs_f64(),
        "model": cfg.model.display().to_string(),
        "data": cfg.data.display().to_string(),
        "evidence_use": "forbidden; process diagnostic only",
    });
    heartbeat.event("result_write", "before", None, None)?;
    write_new_atomically(&cfg.output, &serde_json::to_vec_pretty(&payload)?)?;
    heartbeat.event("result_write", "after", None, None)?;
    heartbeat.event("process", "complete", None, None)?;
    Ok(())
}

fn run(cfg: &Config) -> Result<(), Box<dyn Error>> {
    if cfg.output.exists() {
        return Err(format!("output already exists: {}", cfg.output.display()).into());
    }
    let data = fs::read_to_string(&cfg.data)?;
    let mut heartbeat = Heartbeat::new(cfg)?;
    heartbeat.event("process", "start", None, None)?;
    match cfg.mode {
        Mode::RepeatLoadDrop => run_repeated(cfg, &data, &mut heartbeat),
        _ => run_single(cfg, &data, &mut heartbeat),
    }
}

fn main() {
    let result = Config::parse(env::args_os().skip(1)).and_then(|cfg| run(&cfg));
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_dir(name: &str) -> PathBuf {
        env::temp_dir().join(format!(
            "sblrc-process-stability-test-{name}-{}",
            std::process::id()
        ))
    }

    #[test]
    fn forbidden_evidence_seed_is_rejected() {
        let args = [
            "load_drop",
            "model.so",
            "data.json",
            "90101",
            "1",
            "1",
            "0",
            "heartbeats",
            "out.json",
            "0",
        ]
        .into_iter()
        .map(OsString::from);
        let error = Config::parse(args).unwrap_err().to_string();
        assert!(error.contains("forbidden"));
    }

    #[test]
    fn heartbeat_events_are_immutable_and_sequenced() {
        let root = test_dir("heartbeat");
        let _ = fs::remove_dir_all(&root);
        let cfg = Config {
            mode: Mode::LoadDrop,
            model: "model.so".into(),
            data: "data.json".into(),
            seed: 990101,
            replicas: 1,
            threads: 1,
            chains: 0,
            heartbeat_dir: root.clone(),
            output: root.join("out.json"),
            work_units: 0,
        };
        let mut heartbeat = Heartbeat::new(&cfg).unwrap();
        heartbeat.event("load", "before", None, None).unwrap();
        heartbeat.event("load", "after", None, None).unwrap();
        let files = fs::read_dir(&root)
            .unwrap()
            .map(|entry| entry.unwrap().file_name().to_string_lossy().into_owned())
            .collect::<Vec<_>>();
        assert_eq!(files, ["0000-load-before.json", "0001-load-after.json"]);
        let first: Value =
            serde_json::from_slice(&fs::read(root.join(&files[0])).unwrap()).unwrap();
        assert_eq!(first["sequence"], 0);
        assert_eq!(first["seed"], 990101);
        fs::remove_dir_all(root).unwrap();
    }

    #[test]
    fn atomic_writer_refuses_replacement() {
        let root = test_dir("atomic");
        let _ = fs::remove_dir_all(&root);
        fs::create_dir_all(&root).unwrap();
        let path = root.join("value.json");
        write_new_atomically(&path, b"{}").unwrap();
        assert!(write_new_atomically(&path, b"{\"changed\":true}").is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "{}\n");
        fs::remove_dir_all(root).unwrap();
    }
}
