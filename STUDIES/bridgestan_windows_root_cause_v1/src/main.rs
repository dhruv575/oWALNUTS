//! WP50 Windows-GNU BridgeStan heap-corruption root-cause diagnostic.
//!
//! A single child binary with selectable *arms* that each exercise the same
//! BridgeStan FFI (`bs_model_construct`, `bs_log_density_gradient`,
//! `bs_free_error_msg`, `bs_model_destruct`) under a different concurrency,
//! thread-lifetime and library-lifetime discipline. The arms isolate the
//! mechanism of the silent `STATUS_HEAP_CORRUPTION` (`0xC0000374`) exit
//! reproduced by `sblrc_process_stability_v1`, `bridgestan_lifetime_v1` and the
//! `bridgestan_owned_worker_v1` comparator.
//!
//! The prior comparator that reproduced the fault loaded four independent model
//! modules (replicas) and evaluated them concurrently from four short-lived
//! Rayon worker threads, with model/preload DLLs resident. The owned-worker
//! mitigation that cleared the fault moved every native call onto one
//! long-lived owner thread and one effective replica. These arms vary those
//! factors one at a time.
//!
//! This is a process-lifecycle diagnostic. Its draws and timings are not
//! posterior evidence. It links BridgeStan directly and does NOT route through
//! the `owalnuts-bridgestan` owned-worker backend, so that concurrency,
//! thread lifetime and library lifetime are the controlled variables.

use serde_json::json;
use std::{
    env,
    error::Error,
    ffi::{CStr, CString, OsString, c_char, c_int, c_uint},
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::{
        Mutex,
        atomic::{AtomicU64, Ordering},
        mpsc::{Receiver, SyncSender, sync_channel},
    },
    thread::{self, JoinHandle},
    time::{Instant, SystemTime, UNIX_EPOCH},
};

use libloading::{Library, Symbol};

#[repr(C)]
struct BsModel {
    _private: [u8; 0],
}

type ConstructFn = unsafe extern "C" fn(*const c_char, c_uint, *mut *mut c_char) -> *mut BsModel;
type DestructFn = unsafe extern "C" fn(*mut BsModel);
type FreeErrorFn = unsafe extern "C" fn(*mut c_char);
type UncNumFn = unsafe extern "C" fn(*const BsModel) -> c_int;
type LogDensityGradientFn = unsafe extern "C" fn(
    *const BsModel,
    bool,
    bool,
    *const f64,
    *mut f64,
    *mut f64,
    *mut *mut c_char,
) -> c_int;

/// Forbidden evidence seeds (WP35/WP36 posteriordb evidence); never run.
const FORBIDDEN_SEEDS: &[u64] = &[90101, 90102, 90103];

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Arm {
    /// One replica; construct, every evaluation, destruct and unload all on the
    /// main thread. No extra OS thread ever enters native code. Control.
    MainOnly,
    /// R replica copies; short-lived worker threads evaluate distinct replicas
    /// CONCURRENTLY (no serialization); destruct on main; libraries are
    /// `mem::forget`-resident (never unloaded). Mirrors the reproducing
    /// comparator with resident DLLs.
    ConcurrentResident,
    /// Identical to ConcurrentResident but every library IS unloaded
    /// (FreeLibrary) after destruct. Isolates H1 (library unload) from
    /// concurrency/teardown.
    ConcurrentUnload,
    /// R replica copies and short-lived worker threads as in the concurrent
    /// arms, but every native call is serialized through one process-global
    /// mutex (no genuine concurrency); libraries resident. Isolates "multiple
    /// modules + thread churn" from genuine concurrent native execution.
    SerializedResident,
    /// One replica; construct, every evaluation and destruct all on ONE
    /// dedicated long-lived owner thread; main sends work over a channel and
    /// joins the owner at the end; library unloaded on the owner after the
    /// join. The owned-worker mitigation.
    OwnedWorker,
    /// The REAL oWALNUTS `Sampler` (Rayon multi-chain, tree building) over a
    /// target that dispatches each gradient to one of R resident replica
    /// modules CONCURRENTLY (free-list, no global serialization), exactly like
    /// the reproducing `bridgestan_owned_worker_v1` comparator. Libraries
    /// resident (never unloaded). Baseline.
    SamplerConcurrent,
    /// As SamplerConcurrent but every replica library IS unloaded (FreeLibrary)
    /// after the run. Isolates H1 (library unload).
    SamplerConcurrentUnload,
    /// The REAL oWALNUTS `Sampler`, but the target routes every native call to
    /// ONE long-lived owner thread holding ONE replica, serialized (the
    /// owned-worker mitigation). Library unloaded on the owner after join.
    SamplerOwned,
}

impl Arm {
    fn parse(value: &str) -> Result<Self, Box<dyn Error>> {
        Ok(match value {
            "main_only" => Self::MainOnly,
            "concurrent_resident" => Self::ConcurrentResident,
            "concurrent_unload" => Self::ConcurrentUnload,
            "serialized_resident" => Self::SerializedResident,
            "owned_worker" => Self::OwnedWorker,
            "sampler_concurrent" => Self::SamplerConcurrent,
            "sampler_concurrent_unload" => Self::SamplerConcurrentUnload,
            "sampler_owned" => Self::SamplerOwned,
            other => return Err(format!("unknown arm {other:?}").into()),
        })
    }

    fn as_str(self) -> &'static str {
        match self {
            Self::MainOnly => "main_only",
            Self::ConcurrentResident => "concurrent_resident",
            Self::ConcurrentUnload => "concurrent_unload",
            Self::SerializedResident => "serialized_resident",
            Self::OwnedWorker => "owned_worker",
            Self::SamplerConcurrent => "sampler_concurrent",
            Self::SamplerConcurrentUnload => "sampler_concurrent_unload",
            Self::SamplerOwned => "sampler_owned",
        }
    }

    fn is_sampler(self) -> bool {
        matches!(
            self,
            Self::SamplerConcurrent | Self::SamplerConcurrentUnload | Self::SamplerOwned
        )
    }

    fn concurrent(self) -> bool {
        matches!(self, Self::ConcurrentResident | Self::ConcurrentUnload)
    }

    fn resident(self) -> bool {
        matches!(self, Self::ConcurrentResident | Self::SerializedResident)
    }
}

#[derive(Debug)]
struct Config {
    arm: Arm,
    model: PathBuf,
    data: PathBuf,
    preload: Vec<PathBuf>,
    seed: u64,
    replicas: usize,
    threads: usize,
    rounds: usize,
    calls_per_thread: usize,
    radius: f64,
    heartbeat_dir: PathBuf,
    output: PathBuf,
}

impl Config {
    fn parse(args: impl IntoIterator<Item = OsString>) -> Result<Self, Box<dyn Error>> {
        let args: Vec<String> = args
            .into_iter()
            .map(|a| a.to_string_lossy().into_owned())
            .collect();
        let [
            arm,
            model,
            data,
            seed,
            replicas,
            threads,
            rounds,
            calls,
            radius,
            heartbeat,
            output,
            preload,
        ] = args.as_slice()
        else {
            return Err(
                "usage: <arm> <model.so> <data.json> <seed> <replicas> <threads> \
                 <rounds> <calls-per-thread> <radius> <heartbeat-dir> <output.json> \
                 <preload;semicolon-list-or-'none'>"
                    .into(),
            );
        };
        let seed: u64 = seed.parse()?;
        if FORBIDDEN_SEEDS.contains(&seed) {
            return Err(format!("evidence seed {seed} is forbidden").into());
        }
        if seed > u32::MAX as u64 {
            return Err("seed does not fit BridgeStan's u32 seed".into());
        }
        let preload = if preload == "none" {
            Vec::new()
        } else {
            preload.split(';').map(PathBuf::from).collect()
        };
        Ok(Self {
            arm: Arm::parse(arm)?,
            model: PathBuf::from(model),
            data: PathBuf::from(data),
            preload,
            seed,
            replicas: replicas.parse()?,
            threads: threads.parse()?,
            rounds: rounds.parse()?,
            calls_per_thread: calls.parse()?,
            radius: radius.parse()?,
            heartbeat_dir: PathBuf::from(heartbeat),
            output: PathBuf::from(output),
        })
    }
}

/// Immutable atomic heartbeats (temp file flushed, synced, renamed to a
/// previously-absent final name), the WP35A discipline.
struct Heartbeat {
    dir: PathBuf,
    seq: usize,
    arm: Arm,
    seed: u64,
}

impl Heartbeat {
    fn new(cfg: &Config) -> Result<Self, Box<dyn Error>> {
        fs::create_dir_all(&cfg.heartbeat_dir)?;
        Ok(Self {
            dir: cfg.heartbeat_dir.clone(),
            seq: 0,
            arm: cfg.arm,
            seed: cfg.seed,
        })
    }

    fn event(&mut self, stage: &str, boundary: &str) -> Result<(), Box<dyn Error>> {
        let seq = self.seq;
        let path = self.dir.join(format!("{seq:04}-{stage}-{boundary}.json"));
        let payload = json!({
            "schema": "bridgestan-windows-root-cause-v1-heartbeat",
            "sequence": seq,
            "unix_time_ms": SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis(),
            "pid": std::process::id(),
            "arm": self.arm.as_str(),
            "seed": self.seed,
            "stage": stage,
            "boundary": boundary,
        });
        write_new_atomically(&path, &serde_json::to_vec_pretty(&payload)?)?;
        self.seq += 1;
        Ok(())
    }
}

fn write_new_atomically(path: &Path, bytes: &[u8]) -> Result<(), Box<dyn Error>> {
    if path.exists() {
        return Err(format!("refusing to replace existing file: {}", path.display()).into());
    }
    let parent = path.parent().ok_or("path has no parent")?;
    fs::create_dir_all(parent)?;
    let file_name = path
        .file_name()
        .ok_or("path has no file name")?
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

/// Deterministic xorshift64* stream so evaluation positions (and any Stan
/// exceptions they provoke) are reproducible per seed.
struct Rng(u64);
impl Rng {
    fn new(seed: u64) -> Self {
        Self(seed.wrapping_mul(0x9e37_79b9_7f4a_7c15).wrapping_add(1) | 1)
    }
    fn next_f64(&mut self) -> f64 {
        let mut x = self.0;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.0 = x;
        let v = x.wrapping_mul(0x2545_f491_4f6c_dd1d);
        (v >> 11) as f64 / (1u64 << 53) as f64
    }
}

/// The native model handle and the entry points it needs. The library handle
/// is held separately so lifetime is an explicit arm choice.
struct Model {
    ptr: *mut BsModel,
    destruct: DestructFn,
    free_error: FreeErrorFn,
    ldg: LogDensityGradientFn,
    dim: usize,
}

// SAFETY: a BridgeStan model built from a non-STAN_THREADS DLL copy is
// immutable after construction and owns a module-private global autodiff
// stack; each replica is evaluated by at most one thread at a time.
unsafe impl Send for Model {}
unsafe impl Sync for Model {}

/// One loaded replica: its library handle(s) and constructed model.
struct Replica {
    model: Model,
    libraries: Vec<Library>,
    copy_path: Option<PathBuf>,
}

/// Process-global native-call serialization used by the serialized/owned arms.
static NATIVE_LOCK: Mutex<()> = Mutex::new(());
static TOTAL_CALLS: AtomicU64 = AtomicU64::new(0);
static TOTAL_EXCEPTIONS: AtomicU64 = AtomicU64::new(0);
static NONCE: AtomicU64 = AtomicU64::new(0);

/// Load one replica. `index` 0 loads the caller's path directly; index > 0
/// loads a distinct file copy so Windows maps an independent module (its own
/// global autodiff stack), mirroring `ReplicatedStanTarget`.
fn load_replica(cfg: &Config, index: usize) -> Result<Replica, Box<dyn Error>> {
    let (load_path, copy_path) = if index == 0 {
        (cfg.model.clone(), None)
    } else {
        let stem = cfg
            .model
            .file_name()
            .map(|n| n.to_string_lossy().into_owned())
            .unwrap_or_else(|| "model.so".into());
        let nonce = NONCE.fetch_add(1, Ordering::Relaxed);
        let dir =
            std::env::temp_dir().join(format!("wp50-replicas-{}-{}", std::process::id(), cfg.seed));
        fs::create_dir_all(&dir)?;
        let copy = dir.join(format!("r{index}-{nonce}-{stem}"));
        fs::copy(&cfg.model, &copy)?;
        (copy.clone(), Some(copy))
    };

    let mut libraries = Vec::new();
    for dep in &cfg.preload {
        // SAFETY: caller supplies BridgeStan's native dependencies (tbb.dll).
        libraries.push(unsafe { Library::new(dep)? });
    }
    // SAFETY: loading the model DLL runs its initialisers.
    let library = unsafe { Library::new(&load_path)? };
    // SAFETY: symbol types match bridgestan.h 2.x.
    let (construct, destruct, free_error, unc_num, ldg) = unsafe {
        let construct: Symbol<ConstructFn> = library.get(b"bs_model_construct\0")?;
        let destruct: Symbol<DestructFn> = library.get(b"bs_model_destruct\0")?;
        let free_error: Symbol<FreeErrorFn> = library.get(b"bs_free_error_msg\0")?;
        let unc_num: Symbol<UncNumFn> = library.get(b"bs_param_unc_num\0")?;
        let ldg: Symbol<LogDensityGradientFn> = library.get(b"bs_log_density_gradient\0")?;
        (*construct, *destruct, *free_error, *unc_num, *ldg)
    };
    let data = fs::read_to_string(&cfg.data)?;
    let data_c = CString::new(data)?;
    let mut err: *mut c_char = std::ptr::null_mut();
    // SAFETY: valid C string and writable error slot.
    let ptr = unsafe { construct(data_c.as_ptr(), cfg.seed as c_uint, &mut err) };
    if ptr.is_null() {
        let msg = take_error(err, free_error);
        return Err(format!("bs_model_construct failed: {msg}").into());
    }
    // SAFETY: model pointer valid.
    let dim = unsafe { unc_num(ptr) };
    if dim <= 0 {
        return Err(format!("bs_param_unc_num returned {dim}").into());
    }
    libraries.push(library);
    Ok(Replica {
        model: Model {
            ptr,
            destruct,
            free_error,
            ldg,
            dim: dim as usize,
        },
        libraries,
        copy_path,
    })
}

fn take_error(err: *mut c_char, free: FreeErrorFn) -> String {
    if err.is_null() {
        return String::from("(no message)");
    }
    // SAFETY: BridgeStan allocated a NUL-terminated string; we copy then free it
    // with the library's own deallocator (same CRT).
    let msg = unsafe { CStr::from_ptr(err) }
        .to_string_lossy()
        .into_owned();
    unsafe { free(err) };
    msg
}

/// One fused evaluation at a random position. Extreme positions provoke Stan
/// exceptions, exercising the error alloc/free (`bs_free_error_msg`) path.
fn evaluate(model: &Model, rng: &mut Rng, radius: f64) -> bool {
    let mut position = vec![0.0; model.dim];
    for p in &mut position {
        *p = (rng.next_f64() * 2.0 - 1.0) * radius;
    }
    let mut grad = vec![0.0; model.dim];
    let mut value = f64::NAN;
    let mut err: *mut c_char = std::ptr::null_mut();
    // SAFETY: position/gradient have `dim` elements; model pointer valid; err is
    // a writable slot freed below if set.
    let rc = unsafe {
        (model.ldg)(
            model.ptr,
            false,
            true,
            position.as_ptr(),
            &mut value,
            grad.as_mut_ptr(),
            &mut err,
        )
    };
    let exception = rc != 0;
    if !err.is_null() {
        let _ = take_error(err, model.free_error);
    }
    exception
}

fn evaluate_burst(model: &Model, seed: u64, calls: usize, radius: f64, serialized: bool) {
    let mut rng = Rng::new(seed);
    let mut exceptions = 0u64;
    for _ in 0..calls {
        if serialized {
            let _guard = NATIVE_LOCK.lock().unwrap_or_else(|p| p.into_inner());
            if evaluate(model, &mut rng, radius) {
                exceptions += 1;
            }
        } else if evaluate(model, &mut rng, radius) {
            exceptions += 1;
        }
    }
    TOTAL_CALLS.fetch_add(calls as u64, Ordering::Relaxed);
    TOTAL_EXCEPTIONS.fetch_add(exceptions, Ordering::Relaxed);
}

fn destruct(model: &Model) {
    let _guard = NATIVE_LOCK.lock().unwrap_or_else(|p| p.into_inner());
    if !model.ptr.is_null() {
        // SAFETY: ptr came from bs_model_construct and is destructed once.
        unsafe { (model.destruct)(model.ptr) };
    }
}

fn run(cfg: &Config) -> Result<(), Box<dyn Error>> {
    if cfg.output.exists() {
        return Err(format!("output already exists: {}", cfg.output.display()).into());
    }
    let started = Instant::now();
    let mut hb = Heartbeat::new(cfg)?;
    hb.event("process", "start")?;

    if cfg.arm.is_sampler() {
        run_sampler(cfg, &mut hb)?;
    } else {
        match cfg.arm {
            Arm::OwnedWorker => run_owned(cfg, &mut hb)?,
            Arm::MainOnly => run_main_only(cfg, &mut hb)?,
            _ => run_replicated(cfg, &mut hb)?,
        }
    }

    let payload = json!({
        "schema": "bridgestan-windows-root-cause-v1-raw",
        "status": "ok",
        "diagnostic_only": true,
        "evidence_use": "forbidden; process diagnostic only",
        "arm": cfg.arm.as_str(),
        "seed": cfg.seed,
        "replicas": cfg.replicas,
        "threads": cfg.threads,
        "rounds": cfg.rounds,
        "calls_per_thread": cfg.calls_per_thread,
        "radius": cfg.radius,
        "worker_threads_spawned": match cfg.arm {
            Arm::MainOnly => 0,
            Arm::OwnedWorker => 1,
            _ => cfg.threads * cfg.rounds,
        },
        "total_calls": TOTAL_CALLS.load(Ordering::Relaxed),
        "total_exceptions": TOTAL_EXCEPTIONS.load(Ordering::Relaxed),
        "elapsed_seconds": started.elapsed().as_secs_f64(),
        "model": cfg.model.display().to_string(),
    });
    hb.event("result_write", "before")?;
    write_new_atomically(&cfg.output, &serde_json::to_vec_pretty(&payload)?)?;
    hb.event("result_write", "after")?;
    hb.event("process", "complete")?;
    Ok(())
}

fn run_main_only(cfg: &Config, hb: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    hb.event("load", "before")?;
    let replica = load_replica(cfg, 0)?;
    hb.event("load", "after")?;
    hb.event("evaluate", "before")?;
    evaluate_burst(
        &replica.model,
        cfg.seed,
        cfg.threads * cfg.rounds * cfg.calls_per_thread,
        cfg.radius,
        false,
    );
    hb.event("evaluate", "after")?;
    hb.event("destruct", "before")?;
    destruct(&replica.model);
    hb.event("destruct", "after")?;
    hb.event("library_drop", "before")?;
    let Replica {
        libraries,
        copy_path,
        ..
    } = replica;
    drop(libraries);
    if let Some(p) = copy_path {
        let _ = fs::remove_file(p);
    }
    hb.event("library_drop", "after")?;
    Ok(())
}

/// ConcurrentResident / ConcurrentUnload / SerializedResident.
fn run_replicated(cfg: &Config, hb: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    hb.event("load", "before")?;
    let mut replicas = Vec::with_capacity(cfg.replicas);
    for index in 0..cfg.replicas {
        replicas.push(load_replica(cfg, index)?);
    }
    hb.event("load", "after")?;

    let serialized = !cfg.arm.concurrent();
    // Continuous staggered spawning: keep up to `threads` short-lived workers in
    // flight at once and join the oldest only when at capacity. A worker OS
    // thread therefore EXITS (running its winpthread/emutls TLS destructors)
    // while the other in-flight workers are still executing native code. Total
    // workers spawned is `threads * rounds`; each worker binds to one replica so
    // concurrent arms run distinct module-private autodiff stacks in parallel.
    hb.event("worker_rounds", "before")?;
    let total = cfg.threads.saturating_mul(cfg.rounds);
    let mut in_flight: std::collections::VecDeque<JoinHandle<()>> =
        std::collections::VecDeque::with_capacity(cfg.threads + 1);
    for w in 0..total {
        let model = &replicas[w % cfg.replicas].model;
        let seed = cfg.seed ^ ((w as u64) << 20);
        let calls = cfg.calls_per_thread;
        let radius = cfg.radius;
        // SAFETY: Model is Send+Sync; each replica is touched by one worker at a
        // time, and serialized arms additionally take NATIVE_LOCK per call.
        let model_ref: &'static Model = unsafe { std::mem::transmute(model) };
        in_flight.push_back(thread::spawn(move || {
            evaluate_burst(model_ref, seed, calls, radius, serialized);
        }));
        if in_flight.len() >= cfg.threads {
            if let Some(h) = in_flight.pop_front() {
                let _ = h.join();
            }
        }
    }
    for h in in_flight {
        let _ = h.join();
    }
    hb.event("worker_rounds", "after")?;

    hb.event("destruct", "before")?;
    for replica in &replicas {
        destruct(&replica.model);
    }
    hb.event("destruct", "after")?;

    hb.event("library_drop", "before")?;
    for replica in replicas {
        let Replica {
            libraries,
            copy_path,
            ..
        } = replica;
        if cfg.arm.resident() {
            // Never unload: FreeLibrary is never called (H1 never-unload).
            for lib in libraries {
                std::mem::forget(lib);
            }
            // Keep the resident copy file on disk; orchestrator cleans the dir.
            let _ = copy_path;
        } else {
            drop(libraries);
            if let Some(p) = copy_path {
                let _ = fs::remove_file(p);
            }
        }
    }
    hb.event("library_drop", "after")?;
    Ok(())
}

enum Msg {
    Burst {
        seed: u64,
        calls: usize,
        radius: f64,
    },
    Shutdown,
}

/// OwnedWorker: construct, every evaluation, and destruct happen on ONE
/// long-lived owner thread. No short-lived thread ever enters native code.
fn run_owned(cfg: &Config, hb: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    hb.event("load", "before")?;
    let (req_tx, req_rx): (SyncSender<Msg>, Receiver<Msg>) = sync_channel(1);
    let (init_tx, init_rx) = sync_channel(0);
    let model_path = cfg.model.clone();
    let data_path = cfg.data.clone();
    let preload = cfg.preload.clone();
    let seed = cfg.seed;

    let owner = thread::Builder::new()
        .name("wp50-owner".into())
        .spawn(move || {
            let child_cfg = Config {
                arm: Arm::OwnedWorker,
                model: model_path,
                data: data_path,
                preload,
                seed,
                replicas: 1,
                threads: 0,
                rounds: 0,
                calls_per_thread: 0,
                radius: 0.0,
                heartbeat_dir: PathBuf::new(),
                output: PathBuf::new(),
            };
            match load_replica(&child_cfg, 0) {
                Ok(replica) => {
                    if init_tx.send(Ok(())).is_err() {
                        return;
                    }
                    while let Ok(msg) = req_rx.recv() {
                        match msg {
                            Msg::Burst {
                                seed,
                                calls,
                                radius,
                            } => {
                                evaluate_burst(&replica.model, seed, calls, radius, true);
                            }
                            Msg::Shutdown => break,
                        }
                    }
                    destruct(&replica.model);
                    // Model DLL unloaded on this owner thread after destruct,
                    // before the thread exits and its TLS is torn down.
                    let Replica { libraries, .. } = replica;
                    drop(libraries);
                }
                Err(error) => {
                    let _ = init_tx.send(Err(error.to_string()));
                }
            }
        })?;

    match init_rx.recv() {
        Ok(Ok(())) => {}
        Ok(Err(e)) => {
            let _ = owner.join();
            return Err(e.into());
        }
        Err(_) => {
            let _ = owner.join();
            return Err("owner thread panicked during load".into());
        }
    }
    hb.event("load", "after")?;

    hb.event("worker_rounds", "before")?;
    for round in 0..cfg.rounds {
        for t in 0..cfg.threads {
            req_tx
                .send(Msg::Burst {
                    seed: cfg.seed ^ ((round as u64) << 32) ^ (t as u64),
                    calls: cfg.calls_per_thread,
                    radius: cfg.radius,
                })
                .map_err(|_| "owner disconnected")?;
        }
    }
    hb.event("worker_rounds", "after")?;

    hb.event("destruct", "before")?;
    let _ = req_tx.send(Msg::Shutdown);
    // Join the owner: destruct and library unload complete on the owner, then
    // that single thread's TLS is torn down exactly once, before join returns.
    let _ = owner.join();
    hb.event("destruct", "after")?;
    hb.event("library_drop", "before")?;
    hb.event("library_drop", "after")?;
    Ok(())
}

// ---------------------------------------------------------------------------
// Sampler-driven arms: the real oWALNUTS Sampler over a BridgeStan target.
// ---------------------------------------------------------------------------

use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, Sampler, Target, TargetError, Tuning, uniform_starts,
};

/// A free-list guard so at most one Rayon worker evaluates a given replica at
/// once (each non-STAN_THREADS module has one global autodiff stack).
struct Gated {
    model: Model,
    gate: Mutex<()>,
}

/// Concurrent replicated target: dispatches each gradient to a free replica and
/// calls the DLL directly, with NO process-global serialization. This is the
/// reproducing comparator's native-execution model.
struct ConcurrentReplicated {
    replicas: Vec<Gated>,
    dim: usize,
}

// SAFETY: each replica is evaluated under its own gate; Model is Send+Sync.
unsafe impl Send for ConcurrentReplicated {}
unsafe impl Sync for ConcurrentReplicated {}

impl Target for ConcurrentReplicated {
    fn dimension(&self) -> usize {
        self.dim
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        loop {
            for replica in &self.replicas {
                if let Ok(_guard) = replica.gate.try_lock() {
                    return native_ldg(&replica.model, position, gradient);
                }
            }
            std::hint::spin_loop();
        }
    }
}

impl Drop for ConcurrentReplicated {
    fn drop(&mut self) {
        for replica in &self.replicas {
            destruct(&replica.model);
        }
    }
}

/// Owned-worker target: one long-lived owner thread holds one replica and
/// performs every native call, serialized. The mitigation.
struct OwnedTarget {
    requests: SyncSender<OwnedMsg>,
    join: Mutex<Option<JoinHandle<()>>>,
    dim: usize,
}

enum OwnedMsg {
    Eval {
        position: Vec<f64>,
        reply: SyncSender<Result<(f64, Vec<f64>), String>>,
    },
    Shutdown,
}

// SAFETY: all native state lives on the owner thread; only Send messages cross.
unsafe impl Send for OwnedTarget {}
unsafe impl Sync for OwnedTarget {}

impl Target for OwnedTarget {
    fn dimension(&self) -> usize {
        self.dim
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let (reply_tx, reply_rx) = sync_channel(0);
        self.requests
            .send(OwnedMsg::Eval {
                position: position.to_vec(),
                reply: reply_tx,
            })
            .map_err(|_| TargetError::new("owner disconnected"))?;
        match reply_rx.recv() {
            Ok(Ok((value, grad))) => {
                gradient.copy_from_slice(&grad);
                Ok(value)
            }
            Ok(Err(message)) => Err(TargetError::recoverable(message)),
            Err(_) => Err(TargetError::new("owner panicked")),
        }
    }
}

impl Drop for OwnedTarget {
    fn drop(&mut self) {
        let _ = self.requests.send(OwnedMsg::Shutdown);
        if let Some(join) = self.join.lock().unwrap().take() {
            let _ = join.join();
        }
    }
}

/// Direct native gradient, mapping Stan exceptions / nonfinite to recoverable.
fn native_ldg(model: &Model, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
    let mut value = f64::NAN;
    let mut err: *mut c_char = std::ptr::null_mut();
    // SAFETY: slices have `dim` elements; model valid; err freed if set.
    let rc = unsafe {
        (model.ldg)(
            model.ptr,
            false,
            true,
            position.as_ptr(),
            &mut value,
            gradient.as_mut_ptr(),
            &mut err,
        )
    };
    TOTAL_CALLS.fetch_add(1, Ordering::Relaxed);
    if rc != 0 {
        let msg = take_error(err, model.free_error);
        TOTAL_EXCEPTIONS.fetch_add(1, Ordering::Relaxed);
        return Err(TargetError::recoverable(format!("stan exception: {msg}")));
    }
    if !err.is_null() {
        let _ = take_error(err, model.free_error);
    }
    if !value.is_finite() || gradient.iter().any(|g| !g.is_finite()) {
        TOTAL_EXCEPTIONS.fetch_add(1, Ordering::Relaxed);
        return Err(TargetError::recoverable("nonfinite density/gradient"));
    }
    Ok(value)
}

fn init_settings() -> (f64, usize) {
    match Init::uniform() {
        Init::Uniform {
            radius,
            max_attempts,
        } => (radius, max_attempts),
        _ => unreachable!(),
    }
}

/// `rounds` is warmup, `calls_per_thread` is retained draws, `threads` is both
/// chains and sampler threads, `replicas` is the concurrent replica count.
fn run_sampler(cfg: &Config, hb: &mut Heartbeat) -> Result<(), Box<dyn Error>> {
    let warmup = cfg.rounds;
    let draws = cfg.calls_per_thread;
    let chains = cfg.threads;

    hb.event("load", "before")?;
    let (target_box, teardown): (Box<dyn Target>, Teardown) = match cfg.arm {
        Arm::SamplerOwned => build_owned_target(cfg)?,
        _ => build_concurrent_target(cfg)?,
    };
    hb.event("load", "after")?;

    let dim = target_box.dimension();
    hb.event("initialization", "before")?;
    let (radius, max_attempts) = init_settings();
    let starts = uniform_starts(target_box.as_ref(), chains, cfg.seed, radius, max_attempts)?;
    let _ = dim;
    hb.event("initialization", "after")?;

    hb.event("sampling", "before")?;
    let posterior = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(chains)
        .seed(cfg.seed)
        .threads(chains)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(Tuning::default())
        .limits(Limits::new().admit_worst_case())
        .run(&target_box.as_ref(), &starts)?;
    let mut observed = 0usize;
    let mut finite = true;
    for chain in posterior.chains() {
        for i in 0..draws {
            if let Some(draw) = chain.sample(i) {
                observed += 1;
                finite &= draw.iter().all(|v| v.is_finite());
            }
        }
    }
    hb.event("sampling", "after")?;
    let _ = (observed, finite);

    hb.event("result_write_inner", "before")?;
    hb.event("result_write_inner", "after")?;

    hb.event("drop", "before")?;
    drop(target_box);
    teardown.finish();
    hb.event("drop", "after")?;
    Ok(())
}

/// Carries resident library handles / replica copies so the arm's library
/// lifetime policy is applied after the target is dropped.
struct Teardown {
    resident_libraries: Vec<Library>,
    copies: Vec<PathBuf>,
    unload: bool,
}

impl Teardown {
    fn finish(self) {
        if self.unload {
            drop(self.resident_libraries);
            for p in self.copies {
                let _ = fs::remove_file(p);
            }
        } else {
            for lib in self.resident_libraries {
                std::mem::forget(lib);
            }
            // Resident: leave copies; orchestrator cleans the dir.
        }
    }
}

fn build_concurrent_target(cfg: &Config) -> Result<(Box<dyn Target>, Teardown), Box<dyn Error>> {
    let mut gated = Vec::with_capacity(cfg.replicas);
    let mut resident = Vec::new();
    let mut copies = Vec::new();
    let mut dim = 0usize;
    for index in 0..cfg.replicas {
        let replica = load_replica(cfg, index)?;
        dim = replica.model.dim;
        let Replica {
            model,
            mut libraries,
            copy_path,
        } = replica;
        resident.append(&mut libraries);
        if let Some(p) = copy_path {
            copies.push(p);
        }
        gated.push(Gated {
            model,
            gate: Mutex::new(()),
        });
    }
    let target = ConcurrentReplicated {
        replicas: gated,
        dim,
    };
    let unload = cfg.arm == Arm::SamplerConcurrentUnload;
    Ok((
        Box::new(target),
        Teardown {
            resident_libraries: resident,
            copies,
            unload,
        },
    ))
}

fn build_owned_target(cfg: &Config) -> Result<(Box<dyn Target>, Teardown), Box<dyn Error>> {
    let (req_tx, req_rx): (SyncSender<OwnedMsg>, Receiver<OwnedMsg>) = sync_channel(1);
    let (init_tx, init_rx) = sync_channel(0);
    let model_path = cfg.model.clone();
    let data_path = cfg.data.clone();
    let preload = cfg.preload.clone();
    let seed = cfg.seed;
    let owner = thread::Builder::new()
        .name("wp50-sampler-owner".into())
        .spawn(move || {
            let child_cfg = Config {
                arm: Arm::SamplerOwned,
                model: model_path,
                data: data_path,
                preload,
                seed,
                replicas: 1,
                threads: 0,
                rounds: 0,
                calls_per_thread: 0,
                radius: 0.0,
                heartbeat_dir: PathBuf::new(),
                output: PathBuf::new(),
            };
            match load_replica(&child_cfg, 0) {
                Ok(replica) => {
                    if init_tx.send(Ok(replica.model.dim)).is_err() {
                        return;
                    }
                    while let Ok(msg) = req_rx.recv() {
                        match msg {
                            OwnedMsg::Eval { position, reply } => {
                                let mut grad = vec![0.0; replica.model.dim];
                                let out = native_ldg(&replica.model, &position, &mut grad);
                                let payload = match out {
                                    Ok(v) => Ok((v, grad)),
                                    Err(e) => Err(e.message().to_owned()),
                                };
                                let _ = reply.send(payload);
                            }
                            OwnedMsg::Shutdown => break,
                        }
                    }
                    destruct(&replica.model);
                    let Replica { libraries, .. } = replica;
                    drop(libraries);
                }
                Err(error) => {
                    let _ = init_tx.send(Err(error.to_string()));
                }
            }
        })?;
    let dim = match init_rx.recv() {
        Ok(Ok(dim)) => dim,
        Ok(Err(e)) => {
            let _ = owner.join();
            return Err(e.into());
        }
        Err(_) => {
            let _ = owner.join();
            return Err("owner panicked during load".into());
        }
    };
    let target = OwnedTarget {
        requests: req_tx,
        join: Mutex::new(Some(owner)),
        dim,
    };
    Ok((
        Box::new(target),
        Teardown {
            resident_libraries: Vec::new(),
            copies: Vec::new(),
            unload: true,
        },
    ))
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

    #[test]
    fn forbidden_seeds_rejected() {
        for &s in FORBIDDEN_SEEDS {
            let seed = s.to_string();
            let args = [
                "main_only",
                "m.so",
                "d.json",
                &seed,
                "1",
                "4",
                "4",
                "10",
                "8.0",
                "hb",
                "out.json",
                "none",
            ]
            .into_iter()
            .map(OsString::from);
            let err = Config::parse(args).unwrap_err().to_string();
            assert!(err.contains("forbidden"));
        }
    }

    #[test]
    fn arm_roundtrip_and_properties() {
        for a in [
            "main_only",
            "concurrent_resident",
            "concurrent_unload",
            "serialized_resident",
            "owned_worker",
        ] {
            assert_eq!(Arm::parse(a).unwrap().as_str(), a);
        }
        assert!(Arm::parse("nope").is_err());
        assert!(Arm::ConcurrentResident.concurrent());
        assert!(!Arm::SerializedResident.concurrent());
        assert!(Arm::ConcurrentResident.resident());
        assert!(!Arm::ConcurrentUnload.resident());
    }

    #[test]
    fn rng_is_deterministic() {
        let mut a = Rng::new(123);
        let mut b = Rng::new(123);
        for _ in 0..1000 {
            assert_eq!(a.next_f64().to_bits(), b.next_f64().to_bits());
        }
    }
}
