//! WP50D confirmatory stress-gate child. One process = one (arm, seed) child.
//!
//! HEAD sampler, sblrc, 4 chains / 4 threads / 4 requested replicas, 1000/1000.
//! Arms:
//!
//! * `static_unserialised`: Phase A static-runtime DLLs, [`Unserialised`]
//!   target (4 independently loaded model copies, per-replica mutex,
//!   free-replica dispatch, no owned worker, no process-global lock): the
//!   configuration an opt-in would ship.
//! * `dynamic_unserialised`: the old dynamic DLLs on the same target: the
//!   positive control (it faulted 2/120 in WP50C Phase B).
//! * `dynamic_owned`: the old dynamic DLLs on HEAD's owned-worker
//!   `ReplicatedStanTarget` (the coordinator's literal control).
//!
//! Records which mingw runtime modules are mapped after load and after drop.
//! Diagnostic only; not posterior evidence.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::Library;
use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, Sampler, Target, Tuning, uniform_starts,
};
use owalnuts::walnutpie::TargetError;
use owalnuts_bridgestan::{ReplicatedStanTarget, map_evaluation};
use serde_json::{Value, json};
use std::{
    cell::Cell,
    env,
    error::Error,
    ffi::{CStr, CString, c_char, c_int, c_uint},
    fs::{self, OpenOptions},
    io::Write,
    path::{Path, PathBuf},
    sync::{
        Mutex, TryLockError,
        atomic::{AtomicUsize, Ordering},
    },
    time::{Instant, SystemTime, UNIX_EPOCH},
};

const CHAINS: usize = 4;
const THREADS: usize = 4;
const REPLICAS: usize = 4;
const WARMUP: usize = 1000;
const DRAWS: usize = 1000;
const PROBE_SEED: u32 = 50_800_000;

fn seed_allowed(arm: &str, seed: u64) -> bool {
    match arm {
        "static_unserialised" => (50_801_001..=50_802_000).contains(&seed),
        "dynamic_unserialised" => (50_803_001..=50_803_300).contains(&seed),
        "dynamic_owned" => (50_804_001..=50_804_300).contains(&seed),
        _ => false,
    }
}

// ---------------------------------------------------------------- target ---

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

struct Replica {
    model: *mut BsModel,
    destruct: DestructFn,
    free_error: FreeErrorFn,
    gradient: LogDensityGradientFn,
    serial: Mutex<()>,
}

// SAFETY: a replica's model pointer is used only under its own mutex (or in
// Drop, which has exclusive access); a non-STAN_THREADS module has one global
// autodiff stack, so one thread at a time per module is its contract.
unsafe impl Send for Replica {}
// SAFETY: see `Send`; shared access goes through `serial`.
unsafe impl Sync for Replica {}

thread_local! {
    static PREFERRED: Cell<usize> = const { Cell::new(0) };
}

/// Four independently loaded model modules with free-replica dispatch
/// (identical to the WP50C Phase C `unserialised` arm).
struct Unserialised {
    replicas: Vec<Replica>,
    dimension: usize,
    calls: AtomicUsize,
}

fn take_error(err: *mut c_char, free: FreeErrorFn) -> String {
    if err.is_null() {
        return "(no message)".into();
    }
    // SAFETY: BridgeStan allocated a NUL-terminated string; copied then freed once.
    let message = unsafe { CStr::from_ptr(err) }.to_string_lossy().into_owned();
    // SAFETY: freed exactly once with the library's own deallocator.
    unsafe { free(err) };
    message
}

impl Unserialised {
    fn load(model: &Path, data: &str, seed: u32, replicas: usize) -> Result<Self, Box<dyn Error>> {
        let copies = env::temp_dir().join(format!("wp50d-unserialised-{}", std::process::id()));
        fs::create_dir_all(&copies)?;
        let bytes = fs::read(model)?;
        let name = model.file_name().ok_or("model has no file name")?.to_string_lossy();
        let data = CString::new(data)?;
        let mut out = Vec::with_capacity(replicas);
        let mut dimension = None;
        for index in 0..replicas {
            let path = copies.join(format!("replica{index}-{name}"));
            fs::write(&path, &bytes)?;
            // SAFETY: loading a BridgeStan model DLL; its initialisers are trusted.
            let library = unsafe { Library::new(&path)? };
            // SAFETY: symbol types match the BridgeStan 2.x C API.
            let (construct, destruct, free_error, unc_num, gradient) = unsafe {
                (
                    *library.get::<ConstructFn>(b"bs_model_construct\0")?,
                    *library.get::<DestructFn>(b"bs_model_destruct\0")?,
                    *library.get::<FreeErrorFn>(b"bs_free_error_msg\0")?,
                    *library.get::<UncNumFn>(b"bs_param_unc_num\0")?,
                    *library.get::<LogDensityGradientFn>(b"bs_log_density_gradient\0")?,
                )
            };
            // Resident for the process lifetime (as HEAD does on Windows).
            std::mem::forget(library);
            let mut err: *mut c_char = std::ptr::null_mut();
            // SAFETY: valid NUL-terminated JSON and a writable error slot.
            let model = unsafe { construct(data.as_ptr(), seed, &mut err) };
            if model.is_null() {
                return Err(format!("construct failed: {}", take_error(err, free_error)).into());
            }
            // SAFETY: valid model pointer.
            let dim = unsafe { unc_num(model) } as usize;
            if *dimension.get_or_insert(dim) != dim {
                return Err("replicas disagree on dimension".into());
            }
            out.push(Replica { model, destruct, free_error, gradient, serial: Mutex::new(()) });
        }
        Ok(Self { replicas: out, dimension: dimension.unwrap_or(0), calls: AtomicUsize::new(0) })
    }

    fn evaluate(r: &Replica, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mut value = f64::NAN;
        let mut err: *mut c_char = std::ptr::null_mut();
        // SAFETY: arrays have `dimension` elements (checked), the model is
        // valid, the caller holds this replica's mutex.
        let rc = unsafe {
            (r.gradient)(r.model, false, true, position.as_ptr(), &mut value,
                         gradient.as_mut_ptr(), &mut err)
        };
        if rc != 0 {
            let message = take_error(err, r.free_error);
            Err(TargetError::recoverable(format!("stan exception: {message}")))
        } else {
            if !err.is_null() {
                let _ = take_error(err, r.free_error);
            }
            map_evaluation(value, gradient)
        }
    }
}

impl Target for Unserialised {
    fn dimension(&self) -> usize {
        self.dimension
    }

    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        if position.len() != self.dimension || gradient.len() != self.dimension {
            return Err(TargetError::new("position/gradient dimension mismatch"));
        }
        self.calls.fetch_add(1, Ordering::Relaxed);
        let n = self.replicas.len();
        let start = PREFERRED.with(Cell::get) % n;
        for k in 0..n {
            let i = (start + k) % n;
            let guard = match self.replicas[i].serial.try_lock() {
                Ok(g) => g,
                Err(TryLockError::Poisoned(p)) => p.into_inner(),
                Err(TryLockError::WouldBlock) => continue,
            };
            PREFERRED.with(|p| p.set(i));
            let out = Self::evaluate(&self.replicas[i], position, gradient);
            drop(guard);
            return out;
        }
        let _guard = self.replicas[start].serial.lock().unwrap_or_else(|p| p.into_inner());
        Self::evaluate(&self.replicas[start], position, gradient)
    }
}

impl Drop for Unserialised {
    fn drop(&mut self) {
        for r in &self.replicas {
            // SAFETY: exclusive access in Drop; each model destructed once.
            unsafe { (r.destruct)(r.model) };
        }
    }
}

// ------------------------------------------------------------- recording ---

/// Full path and size of each mingw runtime module currently mapped in this
/// process (GetModuleHandleW + GetModuleFileNameW; no load is caused).
#[allow(unsafe_code)]
fn loaded_runtime_modules() -> Value {
    use std::ffi::c_void;
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetModuleHandleW(name: *const u16) -> *mut c_void;
        fn GetModuleFileNameW(module: *mut c_void, buffer: *mut u16, size: u32) -> u32;
    }
    let mut out = serde_json::Map::new();
    for name in ["libwinpthread-1.dll", "libgcc_s_seh-1.dll", "libstdc++-6.dll", "tbb.dll"] {
        let wide: Vec<u16> = name.encode_utf16().chain(std::iter::once(0)).collect();
        // SAFETY: NUL-terminated UTF-16 name; lookup only, no reference added.
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
            "schema": "bridgestan-windows-root-cause-v4-heartbeat",
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
        "sampling_wall_seconds_contended": wall,
    }))
}

fn run(args: &[String]) -> Result<(), Box<dyn Error>> {
    let [arm, model, data, preload, seed, heartbeats, output] = args else {
        return Err("usage: <arm> <model.so> <data.json> <preload tbb.dll> <seed> <heartbeats> <output.json>".into());
    };
    let seed: u64 = seed.parse()?;
    if !seed_allowed(arm, seed) {
        return Err("arm/seed pair is outside the frozen gate matrix".into());
    }
    let output = PathBuf::from(output);
    if output.exists() {
        return Err("output exists".into());
    }
    let data = fs::read_to_string(data)?;
    let mut hb = Heartbeat { dir: PathBuf::from(heartbeats), sequence: 0, arm: arm.clone(), seed };
    fs::create_dir_all(&hb.dir)?;
    hb.event("process", "start", Value::Null)?;
    hb.event("load", "before", Value::Null)?;
    // SAFETY: preloading tbb.dll by full path; resident for the process lifetime.
    std::mem::forget(unsafe { Library::new(preload)? });
    let model = Path::new(model);
    let mut result;
    let modules_after_load;
    if arm == "dynamic_owned" {
        let target = ReplicatedStanTarget::load(model, &[PathBuf::from(preload)], Some(&data),
                                                seed as u32, REPLICAS)?;
        modules_after_load = loaded_runtime_modules();
        hb.event("load", "after", modules_after_load.clone())?;
        result = sample(&target, seed, &mut hb)?;
        result["effective_replicas"] = json!(target.effective_replicas());
        result["target_calls"] = json!(target.calls());
        result["execution"] = json!(format!("{:?}", target.execution()));
        hb.event("drop", "before", Value::Null)?;
        drop(target);
    } else {
        let target = Unserialised::load(model, &data, seed as u32, REPLICAS)?;
        modules_after_load = loaded_runtime_modules();
        hb.event("load", "after", modules_after_load.clone())?;
        result = sample(&target, seed, &mut hb)?;
        result["effective_replicas"] = json!(target.replicas.len());
        result["target_calls"] = json!(target.calls.load(Ordering::Relaxed));
        result["execution"] = json!("study-local unserialised free-replica dispatch");
        hb.event("drop", "before", Value::Null)?;
        drop(target);
    }
    let modules_after_drop = loaded_runtime_modules();
    hb.event("drop", "after", modules_after_drop.clone())?;
    result["schema"] = json!("bridgestan-windows-root-cause-v4-child");
    result["status"] = json!("ok");
    result["arm"] = json!(arm);
    result["seed"] = json!(seed);
    result["chains"] = json!(CHAINS);
    result["threads"] = json!(THREADS);
    result["requested_replicas"] = json!(REPLICAS);
    result["warmup"] = json!(WARMUP);
    result["draws"] = json!(DRAWS);
    result["model"] = json!(model.display().to_string());
    result["preload"] = json!(preload);
    result["loaded_runtime_modules_after_load"] = modules_after_load;
    result["loaded_runtime_modules_after_drop"] = modules_after_drop;
    hb.event("result_write", "before", Value::Null)?;
    write_new_atomically(&output, &serde_json::to_vec_pretty(&result)?)?;
    hb.event("result_write", "after", Value::Null)?;
    hb.event("process", "complete", Value::Null)?;
    Ok(())
}

/// Pre-launch manipulation check: load the arm's target (probe seed, no
/// sampling), report mapped runtime modules, drop, exit.
fn probe(arm: &str, model: &str, data: &str, preload: &str) -> Result<(), Box<dyn Error>> {
    let data = fs::read_to_string(data)?;
    // SAFETY: preloading tbb.dll by full path; resident.
    std::mem::forget(unsafe { Library::new(preload)? });
    let modules = match arm {
        "dynamic_owned" => {
            let t = ReplicatedStanTarget::load(Path::new(model), &[PathBuf::from(preload)],
                                               Some(&data), PROBE_SEED, REPLICAS)?;
            let m = loaded_runtime_modules();
            drop(t);
            m
        }
        "static_unserialised" | "dynamic_unserialised" => {
            let t = Unserialised::load(Path::new(model), &data, PROBE_SEED, REPLICAS)?;
            let m = loaded_runtime_modules();
            drop(t);
            m
        }
        _ => return Err("unknown arm".into()),
    };
    println!("{}", serde_json::to_string(&json!({
        "schema": "bridgestan-windows-root-cause-v4-probe", "arm": arm,
        "loaded_runtime_modules": modules,
    }))?);
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let result = if args.first().map(String::as_str) == Some("probe") && args.len() == 5 {
        probe(&args[1], &args[2], &args[3], &args[4])
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
    fn seeds_are_frozen_per_arm() {
        assert!(seed_allowed("static_unserialised", 50_801_001));
        assert!(seed_allowed("static_unserialised", 50_802_000));
        assert!(!seed_allowed("static_unserialised", 50_802_001));
        assert!(seed_allowed("dynamic_unserialised", 50_803_300));
        assert!(!seed_allowed("dynamic_unserialised", 50_801_001));
        assert!(seed_allowed("dynamic_owned", 50_804_001));
        assert!(!seed_allowed("dynamic_owned", 90_101));
        assert!(!seed_allowed("other", 50_801_001));
    }

    #[test]
    fn module_probe_reports_four_names_without_loading() {
        let modules = loaded_runtime_modules();
        let object = modules.as_object().expect("object");
        assert_eq!(object.len(), 4);
        assert!(object["tbb.dll"].is_null());
    }
}
