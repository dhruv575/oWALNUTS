//! WP65 part (a): gradient-call latency of each BridgeStan dispatch path.
//!
//! Usage: `latency <model.so> <data.json> <build-label> <repeat> <out.json>`
//!
//! Derived from `integrations/bridgestan/src/bin/wallgap.rs`. One process
//! measures, in this fixed order, with `CALLERS` = 4 caller threads where a
//! path has four callers:
//!
//! 1. `raw1`: the raw `bs_log_density_gradient` function pointer on a model
//!    constructed here, one caller (Stan's own cost; no wrapper);
//! 2. `direct1`: one `StanTarget`, one caller;
//! 3. `direct4`: the same `StanTarget`, four callers (DirectSerialised for a
//!    library without `STAN_THREADS`, DirectConcurrent with it);
//! 4. `replicated1`: `ReplicatedStanTarget` with four replicas, one caller;
//! 5. `replicated4`: the same, four callers (ReplicatedConcurrent).
//!
//! Every caller performs the same number of calls (`calls`, calibrated once
//! from `raw1` so that a one-caller path takes about one second) over a fixed
//! cycle of 64 positions drawn uniform(-0.5, 0.5) from seed 65299001; caller
//! `k` starts at position `16 k`. Callers are released together by a barrier
//! and the clock runs from release until the last caller finishes.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::{Library, Symbol};
use owalnuts::walnutpie::Target;
use owalnuts_bridgestan::{ReplicatedStanTarget, StanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::{Value, json};
use std::ffi::{CStr, CString, c_char};
use std::sync::Barrier;
use std::{env, fs, path::Path, time::Instant};

const CALLERS: usize = 4;
const REPLICAS: usize = 4;
const POSITIONS: usize = 64;
const POSITION_SEED: u64 = 65_299_001;
const TARGET_SECONDS: f64 = 1.0;
const MIN_CALLS: usize = 2_000;
const MAX_CALLS: usize = 4_000_000;

type Construct = unsafe extern "C" fn(*const c_char, u32, *mut *mut c_char) -> *mut u8;
type Destruct = unsafe extern "C" fn(*mut u8);
type FreeError = unsafe extern "C" fn(*mut c_char);
type Ldg =
    unsafe extern "C" fn(*const u8, bool, bool, *const f64, *mut f64, *mut f64, *mut *mut c_char) -> i32;

fn take_error(error: *mut c_char, free_error: FreeError) -> String {
    if error.is_null() {
        return "(no message)".into();
    }
    // SAFETY: BridgeStan returned a NUL-terminated allocation for this slot.
    let message = unsafe { CStr::from_ptr(error) }.to_string_lossy().into_owned();
    // SAFETY: the error is freed exactly once by its originating library.
    unsafe { free_error(error) };
    message
}

/// One raw model on the calling thread; destructed before the library unloads.
struct Raw {
    _lib: Library,
    ptr: *mut u8,
    destruct: Destruct,
    free_error: FreeError,
    ldg: Ldg,
}

// SAFETY: the raw model is evaluated by exactly one caller thread at a time
// (the `raw1` path has one caller and nothing else uses the model meanwhile).
unsafe impl Sync for Raw {}
// SAFETY: see `Sync`.
unsafe impl Send for Raw {}

impl Raw {
    fn load(so: &Path, data: &str) -> Self {
        // SAFETY: loading a BridgeStan model library; symbol types match the 2.x C API.
        unsafe {
            let lib = Library::new(so).expect("raw library");
            let construct: Symbol<Construct> = lib.get(b"bs_model_construct\0").unwrap();
            let destruct: Symbol<Destruct> = lib.get(b"bs_model_destruct\0").unwrap();
            let free_error: Symbol<FreeError> = lib.get(b"bs_free_error_msg\0").unwrap();
            let ldg: Symbol<Ldg> = lib.get(b"bs_log_density_gradient\0").unwrap();
            let (construct, destruct, free_error, ldg) = (*construct, *destruct, *free_error, *ldg);
            let cdata = CString::new(data).unwrap();
            let mut err: *mut c_char = std::ptr::null_mut();
            let ptr = construct(cdata.as_ptr(), 1, &mut err);
            if ptr.is_null() {
                panic!("raw construct failed: {}", take_error(err, free_error));
            }
            if !err.is_null() {
                let _ = take_error(err, free_error);
            }
            Self { _lib: lib, ptr, destruct, free_error, ldg }
        }
    }

    /// Returns (log density or NaN on a Stan exception, ok).
    fn eval(&self, q: &[f64], g: &mut [f64]) -> (f64, bool) {
        let mut v = f64::NAN;
        let mut error: *mut c_char = std::ptr::null_mut();
        // SAFETY: q and g have the model's dimension, the model is valid and
        // used from this one thread only.
        let rc = unsafe { (self.ldg)(self.ptr, false, true, q.as_ptr(), &mut v, g.as_mut_ptr(), &mut error) };
        if rc != 0 {
            let _ = take_error(error, self.free_error);
            (f64::NAN, false)
        } else {
            if !error.is_null() {
                let _ = take_error(error, self.free_error);
            }
            (v, true)
        }
    }
}

impl Drop for Raw {
    fn drop(&mut self) {
        // SAFETY: constructed by this library; destructed once, before unload.
        unsafe { (self.destruct)(self.ptr) };
    }
}

struct Measured {
    elapsed: f64,
    recoverable: usize,
    value_checksum: f64,
}

/// `callers` threads each make `calls` calls of `f` over the position cycle.
fn measure<F>(callers: usize, calls: usize, d: usize, positions: &[Vec<f64>], f: F) -> Measured
where
    F: Fn(&[f64], &mut [f64]) -> (f64, bool) + Sync,
{
    let barrier = Barrier::new(callers + 1);
    let mut started = None;
    let results: Vec<(usize, f64)> = std::thread::scope(|s| {
        let handles: Vec<_> = (0..callers)
            .map(|k| {
                let (barrier, f) = (&barrier, &f);
                s.spawn(move || {
                    let mut g = vec![0.0; d];
                    let mut bad = 0usize;
                    let mut sum = 0.0f64;
                    barrier.wait();
                    for i in 0..calls {
                        let q = &positions[(16 * k + i) % POSITIONS];
                        let (v, ok) = f(q, &mut g);
                        if ok {
                            sum += v;
                        } else {
                            bad += 1;
                        }
                    }
                    (bad, sum)
                })
            })
            .collect();
        barrier.wait();
        started = Some(Instant::now());
        handles.into_iter().map(|h| h.join().expect("caller")).collect()
    });
    let elapsed = started.expect("started").elapsed().as_secs_f64();
    Measured {
        elapsed,
        recoverable: results.iter().map(|r| r.0).sum(),
        value_checksum: results.iter().map(|r| r.1).sum(),
    }
}

fn path_json(name: &str, callers: usize, calls: usize, m: &Measured, execution: Value) -> Value {
    let total = (callers * calls) as f64;
    json!({
        "path": name,
        "callers": callers,
        "calls_per_caller": calls,
        "elapsed_seconds": m.elapsed,
        "us_per_call_per_caller": m.elapsed * 1e6 / calls as f64,
        "aggregate_us_per_gradient": m.elapsed * 1e6 / total,
        "gradients_per_second": total / m.elapsed,
        "recoverable_failures": m.recoverable,
        "value_checksum": m.value_checksum,
        "execution": execution,
    })
}

fn cpus_allowed() -> Option<String> {
    fs::read_to_string("/proc/self/status").ok()?.lines().find_map(|l| {
        l.strip_prefix("Cpus_allowed_list:").map(|v| v.trim().to_string())
    })
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    let [so, data, build, repeat, out] = args.as_slice() else {
        eprintln!("usage: latency <model.so> <data.json> <build-label> <repeat> <out.json>");
        std::process::exit(2);
    };
    let out = Path::new(out);
    if out.exists() {
        eprintln!("output exists: {}", out.display());
        std::process::exit(2);
    }
    let so = Path::new(so);
    let data = fs::read_to_string(data).expect("data");

    let raw = Raw::load(so, &data);
    let direct = StanTarget::load(so, &default_preload(), Some(&data), 1).expect("direct load");
    let d = direct.dimension();
    let mut rng = SmallRng::seed_from_u64(POSITION_SEED);
    let positions: Vec<Vec<f64>> =
        (0..POSITIONS).map(|_| (0..d).map(|_| rng.random_range(-0.5..0.5)).collect()).collect();

    // Warm-up and calibration on the raw path (one caller).
    let mut g = vec![0.0; d];
    for i in 0..400 {
        raw.eval(&positions[i % POSITIONS], &mut g);
    }
    let t = Instant::now();
    let probe = 400;
    for i in 0..probe {
        raw.eval(&positions[i % POSITIONS], &mut g);
    }
    let per_call = t.elapsed().as_secs_f64() / probe as f64;
    let calls = ((TARGET_SECONDS / per_call).ceil() as usize).clamp(MIN_CALLS, MAX_CALLS);

    let mut paths = Vec::new();
    // 1. raw, one caller (on this model's own thread: the raw model is only
    //    ever used by one thread at a time, as its contract requires).
    let m = measure(1, calls, d, &positions, |q, g| raw.eval(q, g));
    paths.push(path_json("raw1", 1, calls, &m, json!("raw_function_pointer")));
    drop(raw);

    let ldg = |t: &dyn Target, q: &[f64], g: &mut [f64]| match t.log_density_gradient(q, g) {
        Ok(v) => (v, true),
        Err(_) => (f64::NAN, false),
    };
    let direct_exec = json!(format!("{:?}", direct.execution()));
    for _ in 0..200 {
        let _ = direct.log_density_gradient(&positions[0], &mut g);
    }
    let m = measure(1, calls, d, &positions, |q, g| ldg(&direct, q, g));
    paths.push(path_json("direct1", 1, calls, &m, direct_exec.clone()));
    let m = measure(CALLERS, calls, d, &positions, |q, g| ldg(&direct, q, g));
    paths.push(path_json("direct4", CALLERS, calls, &m, direct_exec.clone()));
    let direct_info = json!({
        "compiled_threading": format!("{:?}", direct.compiled_threading()),
        "threading": format!("{:?}", direct.threading()),
        "execution": direct_exec,
        "model_info": direct.info(),
    });
    drop(direct);

    let pool = ReplicatedStanTarget::load(so, &default_preload(), Some(&data), 1, REPLICAS)
        .expect("replicated load");
    let pool_exec = json!(format!("{:?}", pool.execution()));
    for _ in 0..200 {
        let _ = pool.log_density_gradient(&positions[0], &mut g);
    }
    let m = measure(1, calls, d, &positions, |q, g| ldg(&pool, q, g));
    paths.push(path_json("replicated1", 1, calls, &m, pool_exec.clone()));
    let m = measure(CALLERS, calls, d, &positions, |q, g| ldg(&pool, q, g));
    paths.push(path_json("replicated4", CALLERS, calls, &m, pool_exec.clone()));
    let pool_info = json!({
        "requested_replicas": pool.requested_replicas(),
        "effective_replicas": pool.effective_replicas(),
        "threading": format!("{:?}", pool.threading()),
        "execution": pool_exec,
    });
    drop(pool);

    let payload = json!({
        "schema": "bridgestan-linux-dispatch-v1-latency",
        "model_library": so.display().to_string(),
        "build": build,
        "repeat": repeat,
        "dimension": d,
        "calls_per_caller": calls,
        "calibration_raw_us_per_call": per_call * 1e6,
        "callers": CALLERS,
        "position_seed": POSITION_SEED,
        "positions": POSITIONS,
        "direct": direct_info,
        "replicated": pool_info,
        "cpus_allowed_list": cpus_allowed(),
        "paths": paths,
    });
    fs::write(out, serde_json::to_vec_pretty(&payload).unwrap()).expect("write");
    println!("{}", serde_json::to_string(&payload["paths"]).unwrap());
}
