//! WP50C Phase C payoff child. One process = one (arm, model, seed) cell.
//!
//! Both arms use this worktree's HEAD sampler with identical settings and the
//! Phase A static-runtime DLLs. They differ only in the BridgeStan target:
//!
//! * `serialised`: HEAD `ReplicatedStanTarget::load(.., 4)`, which on Windows
//!   is one owned worker behind the process-global native-call lock (the
//!   current default);
//! * `unserialised`: [`Unserialised`], a study-local target with 4
//!   independently loaded copies of the model DLL (own autodiff stacks), each
//!   behind its own mutex, with free-replica dispatch. This is the 9edcbac /
//!   off-Windows dispatch, with resident (never unloaded) libraries.
//!
//! Outputs draws fingerprint, start-gradient hash, wall and process CPU time.
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
    fs,
    path::{Path, PathBuf},
    sync::{
        Mutex, TryLockError,
        atomic::{AtomicUsize, Ordering},
    },
    time::Instant,
};

const CHAINS: usize = 4;
const THREADS: usize = 4;
const REPLICAS: usize = 4;
const WARMUP: usize = 1000;
const DRAWS: usize = 1000;
const SEEDS: [(&str, [u64; 3]); 2] = [
    ("sblrc", [50_700_701, 50_700_702, 50_700_703]),
    ("arK", [50_700_711, 50_700_712, 50_700_713]),
];

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

// SAFETY: a replica's model pointer is only used under its own mutex (or in
// Drop, which has exclusive access); a non-STAN_THREADS module has one global
// autodiff stack, so one-thread-at-a-time per module is its contract.
unsafe impl Send for Replica {}
// SAFETY: see `Send`; shared access goes through `serial`.
unsafe impl Sync for Replica {}

thread_local! {
    static PREFERRED: Cell<usize> = const { Cell::new(0) };
}

/// Four independently loaded model modules with free-replica dispatch.
struct Unserialised {
    replicas: Vec<Replica>,
    dimension: usize,
    calls: AtomicUsize,
    copies: PathBuf,
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
    fn load(model: &Path, data: &str, seed: u32) -> Result<Self, Box<dyn Error>> {
        let copies = env::temp_dir().join(format!("wp50c-unserialised-{}", std::process::id()));
        fs::create_dir_all(&copies)?;
        let bytes = fs::read(model)?;
        let name = model.file_name().ok_or("model has no file name")?.to_string_lossy();
        let data = CString::new(data)?;
        let mut replicas = Vec::with_capacity(REPLICAS);
        let mut dimension = None;
        for index in 0..REPLICAS {
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
            // Resident for the process lifetime (as at 9edcbac and HEAD on Windows).
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
            replicas.push(Replica { model, destruct, free_error, gradient, serial: Mutex::new(()) });
        }
        Ok(Self { replicas, dimension: dimension.unwrap_or(0), calls: AtomicUsize::new(0), copies })
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
        let _ = &self.copies; // copies stay mapped (resident); removed by the orchestrator
    }
}

/// (kernel + user) CPU seconds of this process so far, via GetProcessTimes.
#[allow(unsafe_code)]
fn process_cpu_seconds() -> (f64, f64) {
    use std::ffi::c_void;
    #[repr(C)]
    #[derive(Default, Clone, Copy)]
    struct FileTime {
        low: u32,
        high: u32,
    }
    #[link(name = "kernel32")]
    unsafe extern "system" {
        fn GetCurrentProcess() -> *mut c_void;
        fn GetProcessTimes(
            process: *mut c_void,
            creation: *mut FileTime,
            exit: *mut FileTime,
            kernel: *mut FileTime,
            user: *mut FileTime,
        ) -> i32;
    }
    let (mut c, mut e, mut k, mut u) = Default::default();
    // SAFETY: pseudo-handle of the current process and four writable FILETIMEs.
    let ok = unsafe { GetProcessTimes(GetCurrentProcess(), &mut c, &mut e, &mut k, &mut u) };
    if ok == 0 {
        return (f64::NAN, f64::NAN);
    }
    let secs = |t: FileTime| ((u64::from(t.high) << 32) | u64::from(t.low)) as f64 * 1e-7;
    (secs(k), secs(u))
}

fn fnv(hash: &mut u64, value: f64) {
    for byte in value.to_bits().to_le_bytes() {
        *hash ^= u64::from(byte);
        *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
}

fn start_gradient_hash<T: Target>(target: &T, starts: &[Vec<f64>]) -> Result<String, Box<dyn Error>> {
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    for start in starts {
        let mut gradient = vec![0.0; target.dimension()];
        let value = target.log_density_gradient(start, &mut gradient)?;
        fnv(&mut hash, value);
        for g in gradient {
            fnv(&mut hash, g);
        }
    }
    Ok(format!("{hash:016x}"))
}

fn sample<T: Target>(target: &T, seed: u64) -> Result<Value, Box<dyn Error>> {
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform { radius, max_attempts } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    let starts = uniform_starts(target, CHAINS, seed, radius, max_attempts)?;
    let gradient_hash = start_gradient_hash(target, &starts)?;
    let (k0, u0) = process_cpu_seconds();
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
    let (k1, u1) = process_cpu_seconds();
    let mut hash = 0xcbf2_9ce4_8422_2325_u64;
    let mut observed = 0;
    for chain in posterior.chains() {
        for index in 0..DRAWS {
            for &value in chain.sample(index).ok_or("missing retained draw")? {
                fnv(&mut hash, value);
            }
            observed += 1;
        }
    }
    Ok(json!({
        "start_gradient_hash_fnv1a64": gradient_hash,
        "draws_fingerprint_fnv1a64": format!("{hash:016x}"),
        "draws_observed": observed,
        "algorithm_revision": posterior.algorithm_revision(),
        "sampling_wall_seconds_contended": wall,
        "sampling_cpu_kernel_seconds": k1 - k0,
        "sampling_cpu_user_seconds": u1 - u0,
    }))
}

fn run(args: &[String]) -> Result<Value, Box<dyn Error>> {
    let [arm, shape, model, data, preload, seed, output] = args else {
        return Err("usage: <serialised|unserialised> <sblrc|arK> <model.so> <data.json> <preload tbb.dll> <seed> <output.json>".into());
    };
    let seed: u64 = seed.parse()?;
    if !SEEDS.iter().any(|(s, seeds)| s == shape && seeds.contains(&seed)) {
        return Err("shape/seed pair is outside the frozen payoff matrix".into());
    }
    let output = PathBuf::from(output);
    if output.exists() {
        return Err("output exists".into());
    }
    let data = fs::read_to_string(data)?;
    let process = Instant::now();
    // SAFETY: preloading the (private, static-runtime) tbb.dll by full path; resident.
    std::mem::forget(unsafe { Library::new(preload)? });
    let mut result = match arm.as_str() {
        "serialised" => {
            let target = ReplicatedStanTarget::load(Path::new(model), &[PathBuf::from(preload)],
                                                    Some(&data), seed as u32, REPLICAS)?;
            let mut r = sample(&target, seed)?;
            r["effective_replicas"] = json!(target.effective_replicas());
            r["requested_replicas"] = json!(target.requested_replicas());
            r["target_calls"] = json!(target.calls());
            r["execution"] = json!(format!("{:?}", target.execution()));
            r
        }
        "unserialised" => {
            let target = Unserialised::load(Path::new(model), &data, seed as u32)?;
            let mut r = sample(&target, seed)?;
            r["effective_replicas"] = json!(target.replicas.len());
            r["requested_replicas"] = json!(REPLICAS);
            r["target_calls"] = json!(target.calls.load(Ordering::Relaxed));
            r["execution"] = json!("study-local unserialised free-replica dispatch");
            r
        }
        _ => return Err("arm must be serialised or unserialised".into()),
    };
    let (k, u) = process_cpu_seconds();
    result["schema"] = json!("bridgestan-windows-payoff-v3-child");
    result["status"] = json!("ok");
    result["arm"] = json!(arm);
    result["shape"] = json!(shape);
    result["seed"] = json!(seed);
    result["chains"] = json!(CHAINS);
    result["threads"] = json!(THREADS);
    result["warmup"] = json!(WARMUP);
    result["draws"] = json!(DRAWS);
    result["model"] = json!(model);
    result["preload"] = json!(preload);
    result["process_wall_seconds_contended"] = json!(process.elapsed().as_secs_f64());
    result["process_cpu_kernel_seconds"] = json!(k);
    result["process_cpu_user_seconds"] = json!(u);
    fs::write(&output, serde_json::to_vec_pretty(&result)?)?;
    Ok(result)
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    match run(&args) {
        Ok(_) => {}
        Err(error) => {
            eprintln!("error: {error}");
            std::process::exit(1);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_seeds_outside_matrix() {
        let args = |seed: &str| -> Vec<String> {
            ["serialised", "sblrc", "m", "d", "p", seed, "o"].map(String::from).to_vec()
        };
        for seed in ["90101", "50700711", "50700704"] {
            assert!(run(&args(seed)).unwrap_err().to_string().contains("frozen payoff matrix"));
        }
    }

    #[test]
    fn cpu_times_are_finite() {
        let (k, u) = process_cpu_seconds();
        assert!(k.is_finite() && u.is_finite());
    }
}
