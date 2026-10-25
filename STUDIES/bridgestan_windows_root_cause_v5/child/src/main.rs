//! WP50E deterministic replay child. One process = one replay of seed
//! 50801734 (the WP50D `static_unserialised` fault) with the WP50D shape:
//! HEAD sampler, sblrc, 4 chains / 4 threads / 4 requested replicas,
//! 1000/1000, diagonal metric, default adaptation and tuning, uniform init,
//! `admit_worst_case`.
//!
//! Dispatch `owned` = HEAD `ReplicatedStanTarget` (owned worker); dispatch
//! `unserialised` = the WP50D study-local target (code copied verbatim).
//! Policy `abort` = shipped default; `reject` = research-only
//! `NonfinitePositionPolicy::RejectLeaf` (descriptive arm).
//!
//! The run goes through `Sampler::run_with_comparison_observers` (research)
//! with passive observers that hash every proposal observation per chain and
//! keep chain 2's proposals and completed transitions 0..=9 in full. A
//! pass-through target wrapper counts what the target layer actually saw.
//! Diagnostic only; not posterior evidence.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::Library;
use owalnuts::sampler::{
    Adaptation, Init, Limits, Metric, NonfinitePositionPolicy, Sampler, Target, Tuning,
    uniform_starts,
};
use owalnuts::walnutpie::{
    ComparisonObserver, ComparisonTransitionObservation, ProposalObservation,
    ProposalObservationControl, ProposalObserver, ProposalTargetOutcome, TargetError,
    TargetErrorKind,
};
use owalnuts_bridgestan::{ReplicatedStanTarget, map_evaluation};
use serde_json::{Value, json};
use std::{
    cell::Cell,
    collections::HashMap,
    env,
    error::Error,
    ffi::{CStr, CString, c_char, c_int, c_uint},
    fs,
    num::NonZeroUsize,
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
const SEED: u64 = 50_801_734;

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


// ------------------------------------------------------------ counting ---

/// Pass-through target that records what the target layer actually saw.
struct Counting<'a, T: Target> {
    inner: &'a T,
    calls: AtomicUsize,
    nonfinite_inputs: AtomicUsize,
    recoverable_errors: AtomicUsize,
    fatal_errors: AtomicUsize,
    nonfinite_values: AtomicUsize,
}

impl<'a, T: Target> Counting<'a, T> {
    fn new(inner: &'a T) -> Self {
        Self {
            inner,
            calls: AtomicUsize::new(0),
            nonfinite_inputs: AtomicUsize::new(0),
            recoverable_errors: AtomicUsize::new(0),
            fatal_errors: AtomicUsize::new(0),
            nonfinite_values: AtomicUsize::new(0),
        }
    }

    fn summary(&self) -> Value {
        json!({
            "calls": self.calls.load(Ordering::Relaxed),
            "nonfinite_inputs": self.nonfinite_inputs.load(Ordering::Relaxed),
            "recoverable_errors": self.recoverable_errors.load(Ordering::Relaxed),
            "fatal_errors": self.fatal_errors.load(Ordering::Relaxed),
            "nonfinite_values_returned": self.nonfinite_values.load(Ordering::Relaxed),
        })
    }
}

impl<T: Target> Target for Counting<'_, T> {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }

    fn log_density_gradient(&self, position: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        if position.iter().any(|x| !x.is_finite()) {
            self.nonfinite_inputs.fetch_add(1, Ordering::Relaxed);
        }
        let out = self.inner.log_density_gradient(position, gradient);
        match &out {
            Ok(v) if !v.is_finite() => {
                self.nonfinite_values.fetch_add(1, Ordering::Relaxed);
            }
            Ok(_) => {}
            Err(e) if e.kind() == TargetErrorKind::Recoverable => {
                self.recoverable_errors.fetch_add(1, Ordering::Relaxed);
            }
            Err(_) => {
                self.fatal_errors.fetch_add(1, Ordering::Relaxed);
            }
        }
        out
    }
}

// ------------------------------------------------------------ observers ---

fn fnv_bytes(hash: &mut u64, bytes: &[u8]) {
    for byte in bytes {
        *hash ^= u64::from(*byte);
        *hash = hash.wrapping_mul(0x0000_0100_0000_01b3);
    }
}

fn fnv_f64(hash: &mut u64, value: f64) {
    fnv_bytes(hash, &value.to_bits().to_le_bytes());
}

fn fnv_opt(hash: &mut u64, value: Option<f64>) {
    match value {
        Some(v) => {
            fnv_bytes(hash, &[1]);
            fnv_f64(hash, v);
        }
        None => fnv_bytes(hash, &[0]),
    }
}

fn bits(values: &[f64]) -> Vec<String> {
    values.iter().map(|v| format!("{:016x}", v.to_bits())).collect()
}

fn opt_num(value: Option<f64>) -> Value {
    match value {
        Some(v) if v.is_finite() => json!(v),
        Some(v) => json!(format!("{v}")),
        None => Value::Null,
    }
}

fn nums(values: &[f64]) -> Value {
    Value::Array(values.iter().map(|&v| opt_num(Some(v))).collect())
}

#[derive(Default)]
struct ChainStream {
    observations: usize,
    hash: u64,
    last_transition: Option<usize>,
    last_target_call: usize,
    first_kernel_nonfinite: Option<Value>,
}

#[derive(Default)]
struct Recorder {
    streams: Mutex<HashMap<usize, ChainStream>>,
    proposals: Mutex<Vec<Value>>,
    transitions: Mutex<Vec<Value>>,
}

impl ProposalObserver for Recorder {
    fn observe(&self, o: &ProposalObservation) {
        let mut streams = self.streams.lock().unwrap_or_else(|p| p.into_inner());
        let s = streams.entry(o.chain()).or_insert_with(|| ChainStream {
            hash: 0xcbf2_9ce4_8422_2325,
            ..ChainStream::default()
        });
        s.observations += 1;
        s.last_transition = Some(o.transition());
        s.last_target_call = o.target_call();
        let h = &mut s.hash;
        fnv_bytes(h, &(o.transition() as u64).to_le_bytes());
        fnv_bytes(h, &(o.target_call() as u64).to_le_bytes());
        fnv_bytes(h, format!("{:?}{:?}{:?}{:?}{:?}{:?}", o.phase(), o.direction(),
                             o.refinement_level(), o.leaf_attempt(), o.micro_steps(),
                             o.outcome()).as_bytes());
        fnv_opt(h, o.step());
        for &v in o.coordinates() {
            fnv_f64(h, v);
        }
        for &v in o.gradient() {
            fnv_f64(h, v);
        }
        if let Some(m) = o.mid_step_momentum() {
            for &v in m {
                fnv_f64(h, v);
            }
        }
        fnv_f64(h, o.kinetic());
        fnv_opt(h, o.potential());
        fnv_opt(h, o.current_hamiltonian());
        let record = || json!({
            "chain": o.chain(), "transition": o.transition(), "discarded": o.is_discarded(),
            "phase": format!("{:?}", o.phase()), "direction": format!("{:?}", o.direction()),
            "refinement_level": o.refinement_level(), "evaluation_in_attempt": o.evaluation_in_attempt(),
            "leaf_attempt": o.leaf_attempt(), "micro_steps": o.micro_steps(),
            "step": opt_num(o.step()), "step_bits": o.step().map(|v| format!("{:016x}", v.to_bits())),
            "target_call": o.target_call(), "phase_target_call": o.phase_target_call(),
            "coordinates": nums(o.coordinates()), "coordinates_bits": bits(o.coordinates()),
            "gradient": nums(o.gradient()),
            "mid_step_momentum": o.mid_step_momentum().map(nums),
            "kinetic": opt_num(Some(o.kinetic())), "potential": opt_num(o.potential()),
            "initial_hamiltonian": opt_num(o.initial_hamiltonian()),
            "current_hamiltonian": opt_num(o.current_hamiltonian()),
            "delta_h": opt_num(o.delta_h()), "outcome": format!("{:?}", o.outcome()),
        });
        if o.outcome() == ProposalTargetOutcome::KernelNonfinite && s.first_kernel_nonfinite.is_none() {
            s.first_kernel_nonfinite = Some(record());
        }
        drop(streams);
        if o.chain() == TRACE_CHAIN && o.transition() <= TRACE_LAST_TRANSITION {
            self.proposals.lock().unwrap_or_else(|p| p.into_inner()).push(record());
        }
    }
}

impl ComparisonObserver for Recorder {
    fn observe(&self, o: &ComparisonTransitionObservation) {
        if o.chain != TRACE_CHAIN || o.transition > TRACE_LAST_TRANSITION {
            return;
        }
        let adaptation = o.adaptation.as_ref().map(|a| json!({
            "stage": format!("{:?}", a.stage),
            "active_step_before": opt_num(Some(a.active_step_before)),
            "active_step_after": opt_num(Some(a.active_step_after)),
            "input_acceptance": opt_num(a.input_acceptance),
            "debug": format!("{a:?}"),
        }));
        self.transitions.lock().unwrap_or_else(|p| p.into_inner()).push(json!({
            "chain": o.chain, "transition": o.transition,
            "selected_theta": nums(&o.selected_theta), "selected_theta_bits": bits(&o.selected_theta),
            "selected_rho": nums(&o.selected_rho),
            "selected_log_density": opt_num(Some(o.selected_log_density)),
            "selected_gradient": nums(&o.selected_gradient),
            "diagnostics": format!("{:?}", o.diagnostics),
            "work": format!("{:?}", o.work),
            "leaf_outcomes": format!("{:?}", o.leaf_outcomes),
            "adaptation": adaptation,
        }));
    }
}

const TRACE_CHAIN: usize = 2;
const TRACE_LAST_TRANSITION: usize = 9;

fn sample<T: Target>(target: &T, policy: &str) -> Result<Value, Box<dyn Error>> {
    let counting = Counting::new(target);
    let (radius, max_attempts) = match Init::uniform() {
        Init::Uniform { radius, max_attempts } => (radius, max_attempts),
        _ => unreachable!("Init::uniform() must remain uniform"),
    };
    let starts = uniform_starts(&counting, CHAINS, SEED, radius, max_attempts)?;
    let tuning = match policy {
        "abort" => Tuning::default(),
        "reject" => Tuning::default().nonfinite_position(NonfinitePositionPolicy::RejectLeaf),
        _ => return Err("policy must be abort or reject".into()),
    };
    let recorder = Recorder::default();
    let proposals = ProposalObservationControl::new(
        &recorder,
        NonZeroUsize::new(usize::MAX).expect("nonzero"),
        64,
    );
    let started = Instant::now();
    let outcome = Sampler::new()
        .warmup(WARMUP)
        .draws(DRAWS)
        .chains(CHAINS)
        .seed(SEED)
        .threads(THREADS)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(tuning)
        .limits(Limits::new().admit_worst_case())
        .run_with_comparison_observers(&counting, &starts, &proposals, &recorder);
    let wall = started.elapsed().as_secs_f64();
    let mut streams: Vec<(usize, Value)> = recorder
        .streams
        .lock()
        .unwrap_or_else(|p| p.into_inner())
        .iter()
        .map(|(chain, s)| {
            (*chain, json!({
                "chain": chain, "observations": s.observations,
                "hash_fnv1a64": format!("{:016x}", s.hash),
                "last_transition": s.last_transition, "last_target_call": s.last_target_call,
                "first_kernel_nonfinite": s.first_kernel_nonfinite,
            }))
        })
        .collect();
    streams.sort_by_key(|(chain, _)| *chain);
    let mut result = json!({
        "starts": starts.iter().map(|s| nums(s)).collect::<Vec<_>>(),
        "starts_bits": starts.iter().map(|s| bits(s)).collect::<Vec<_>>(),
        "chain_streams": streams.into_iter().map(|(_, v)| v).collect::<Vec<_>>(),
        "trace_chain": TRACE_CHAIN,
        "trace_proposals": *recorder.proposals.lock().unwrap_or_else(|p| p.into_inner()),
        "trace_transitions": *recorder.transitions.lock().unwrap_or_else(|p| p.into_inner()),
        "sampling_wall_seconds_contended": wall,
    });
    match outcome {
        Ok(posterior) => {
            let mut hash = 0xcbf2_9ce4_8422_2325_u64;
            for chain in posterior.chains() {
                for index in 0..DRAWS {
                    for &value in chain.sample(index).ok_or("missing retained draw")? {
                        fnv_f64(&mut hash, value);
                    }
                }
            }
            result["status"] = json!("ok");
            result["draws_fingerprint_fnv1a64"] = json!(format!("{hash:016x}"));
            result["nonfinite_position_rejections_per_chain"] = json!(posterior
                .telemetry()
                .map(|t| t.total().nonfinite_position_rejections())
                .collect::<Vec<_>>());
        }
        Err(error) => {
            result["status"] = json!("sampler_error");
            result["error"] = json!({
                "kind": format!("{:?}", error.kind()),
                "display": error.to_string(),
                "chain": error.chain(),
                "transition": error.transition(),
                "has_target_source": error.target_source().is_some(),
                "target_source": error.target_source().map(|s| format!("{s:?}")),
            });
        }
    }
    result["target_layer"] = counting.summary();
    Ok(result)
}

fn run(args: &[String]) -> Result<(), Box<dyn Error>> {
    let [dispatch, policy, model, data, preload, output] = args else {
        return Err("usage: <owned|unserialised> <abort|reject> <model.so> <data.json> <preload tbb.dll> <output.json>".into());
    };
    let output = PathBuf::from(output);
    if output.exists() {
        return Err("output exists".into());
    }
    let data = fs::read_to_string(data)?;
    // SAFETY: preloading tbb.dll by full path; resident for the process lifetime.
    std::mem::forget(unsafe { Library::new(preload)? });
    let model = Path::new(model);
    let mut result = match dispatch.as_str() {
        "owned" => {
            let target = ReplicatedStanTarget::load(model, &[PathBuf::from(preload)], Some(&data),
                                                    SEED as u32, REPLICAS)?;
            let modules = loaded_runtime_modules();
            let mut r = sample(&target, policy)?;
            r["effective_replicas"] = json!(target.effective_replicas());
            r["execution"] = json!(format!("{:?}", target.execution()));
            r["loaded_runtime_modules_after_load"] = modules;
            r
        }
        "unserialised" => {
            let target = Unserialised::load(model, &data, SEED as u32, REPLICAS)?;
            let modules = loaded_runtime_modules();
            let mut r = sample(&target, policy)?;
            r["effective_replicas"] = json!(target.replicas.len());
            r["execution"] = json!("study-local unserialised free-replica dispatch (WP50D)");
            r["loaded_runtime_modules_after_load"] = modules;
            r
        }
        _ => return Err("dispatch must be owned or unserialised".into()),
    };
    result["schema"] = json!("bridgestan-windows-root-cause-v5-child");
    result["pid"] = json!(std::process::id());
    result["dispatch"] = json!(dispatch);
    result["policy"] = json!(policy);
    result["seed"] = json!(SEED);
    result["chains"] = json!(CHAINS);
    result["threads"] = json!(THREADS);
    result["requested_replicas"] = json!(REPLICAS);
    result["warmup"] = json!(WARMUP);
    result["draws"] = json!(DRAWS);
    result["model"] = json!(model.display().to_string());
    result["preload"] = json!(preload);
    fs::write(&output, serde_json::to_vec_pretty(&result)?)?;
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if let Err(error) = run(&args) {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn replay_seed_is_the_wp50d_fault() {
        assert_eq!(SEED, 50_801_734);
        assert_eq!((WARMUP, DRAWS, CHAINS, THREADS, REPLICAS), (1000, 1000, 4, 4, 4));
    }

    #[test]
    fn rejects_unknown_dispatch() {
        let args = ["other", "abort", "m", "d", "p", "o"].map(String::from);
        assert!(run(&args).is_err());
    }
}
