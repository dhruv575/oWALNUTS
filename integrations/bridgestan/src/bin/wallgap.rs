//! Per-call wall cost of `bs_log_density_gradient` for a built model.
//!
//! Usage: `wallgap <model.so> <data.json> [calls] [threads]`
//!
//! Prints one JSON line with wrapped, shared-call, and replicated timings. The
//! raw function-pointer arm runs only off Windows. Windows reports it disabled
//! because direct FFI would bypass the owned-worker lifetime backend.
#![deny(unsafe_op_in_unsafe_fn)]

#[cfg(not(windows))]
use libloading::{Library, Symbol};
use owalnuts::walnutpie::Target;
use owalnuts_bridgestan::{ReplicatedStanTarget, StanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::json;
#[cfg(not(windows))]
use std::ffi::{CStr, c_char};
use std::{env, fs, path::Path, time::Instant};

#[cfg(not(windows))]
type Construct = unsafe extern "C" fn(*const c_char, u32, *mut *mut c_char) -> *mut u8;
#[cfg(not(windows))]
type Destruct = unsafe extern "C" fn(*mut u8);
#[cfg(not(windows))]
type FreeError = unsafe extern "C" fn(*mut c_char);
#[cfg(not(windows))]
type Ldg = unsafe extern "C" fn(
    *const u8,
    bool,
    bool,
    *const f64,
    *mut f64,
    *mut f64,
    *mut *mut c_char,
) -> i32;

#[cfg(not(windows))]
struct RawModel {
    ptr: *mut u8,
    destruct: Destruct,
}

#[cfg(not(windows))]
impl Drop for RawModel {
    fn drop(&mut self) {
        if !self.ptr.is_null() {
            // SAFETY: `ptr` came from this library's constructor and is dropped once.
            unsafe { (self.destruct)(self.ptr) };
            self.ptr = std::ptr::null_mut();
        }
    }
}

#[cfg(not(windows))]
fn take_error(error: *mut c_char, free_error: FreeError) -> String {
    if error.is_null() {
        return "(no message)".into();
    }
    // SAFETY: BridgeStan returned a NUL-terminated allocation for this slot.
    let message = unsafe { CStr::from_ptr(error) }
        .to_string_lossy()
        .into_owned();
    // SAFETY: the error is freed exactly once by its originating library.
    unsafe { free_error(error) };
    message
}

fn main() {
    let args: Vec<String> = env::args().skip(1).collect();
    if args.len() < 2 {
        eprintln!("usage: wallgap <model.so> <data.json> [calls] [threads]");
        std::process::exit(2);
    }
    let so = Path::new(&args[0]);
    let data = fs::read_to_string(&args[1]).expect("data");
    let calls: usize = args.get(2).map_or(2000, |s| s.parse().expect("calls"));
    let threads: usize = args.get(3).map_or(4, |s| s.parse().expect("threads"));
    let target = StanTarget::load(so, &default_preload(), Some(&data), 1).expect("load");
    let d = target.dimension();
    let mut rng = SmallRng::seed_from_u64(7);
    let q: Vec<f64> = (0..d).map(|_| rng.random_range(-0.5..0.5)).collect();
    let mut g = vec![0.0; d];
    for _ in 0..200 {
        target.log_density_gradient(&q, &mut g).expect("eval");
    }
    let t = Instant::now();
    for _ in 0..calls {
        target.log_density_gradient(&q, &mut g).expect("eval");
    }
    let wrapped_us = t.elapsed().as_secs_f64() * 1e6 / calls as f64;

    #[cfg(not(windows))]
    // SAFETY: this arm is deliberately unavailable on Windows. Off Windows it
    // uses one model on this thread and pairs every allocation with the
    // originating library's destructor/deallocator before library unload.
    let raw_us = Some(unsafe {
        let lib = Library::new(so).expect("lib");
        let construct: Symbol<Construct> = lib.get(b"bs_model_construct\0").unwrap();
        let destruct: Symbol<Destruct> = lib.get(b"bs_model_destruct\0").unwrap();
        let free_error: Symbol<FreeError> = lib.get(b"bs_free_error_msg\0").unwrap();
        let ldg: Symbol<Ldg> = lib.get(b"bs_log_density_gradient\0").unwrap();
        let (construct, destruct, free_error, ldg) = (*construct, *destruct, *free_error, *ldg);
        let cdata = std::ffi::CString::new(data.clone()).unwrap();
        let mut err: *mut c_char = std::ptr::null_mut();
        let m = construct(cdata.as_ptr(), 1, &mut err);
        if m.is_null() {
            panic!("raw construct failed: {}", take_error(err, free_error));
        }
        if !err.is_null() {
            let _ = take_error(err, free_error);
        }
        let _model = RawModel { ptr: m, destruct };
        let mut v = 0.0;
        let mut evaluate = || {
            let mut error: *mut c_char = std::ptr::null_mut();
            let rc = ldg(
                m,
                false,
                true,
                q.as_ptr(),
                &mut v,
                g.as_mut_ptr(),
                &mut error,
            );
            if rc != 0 {
                panic!("raw evaluation failed: {}", take_error(error, free_error));
            }
        };
        for _ in 0..200 {
            evaluate();
        }
        let t = Instant::now();
        for _ in 0..calls {
            evaluate();
        }
        t.elapsed().as_secs_f64() * 1e6 / calls as f64
    });
    #[cfg(windows)]
    let raw_us: Option<f64> = None;
    #[cfg(not(windows))]
    let raw_status = "enabled_non_windows_only";
    #[cfg(windows)]
    let raw_status = "disabled_windows_owned_worker_required";

    let t = Instant::now();
    std::thread::scope(|s| {
        for _ in 0..threads {
            s.spawn(|| {
                let mut g = vec![0.0; d];
                for _ in 0..calls {
                    target.log_density_gradient(&q, &mut g).expect("eval");
                }
            });
        }
    });
    let concurrent_us = t.elapsed().as_secs_f64() * 1e6 / calls as f64;

    // Replicated: `threads` copies of the library, one per thread.
    let pool =
        ReplicatedStanTarget::load(so, &default_preload(), Some(&data), 1, threads).expect("pool");
    let t = Instant::now();
    std::thread::scope(|s| {
        for _ in 0..threads {
            s.spawn(|| {
                let mut g = vec![0.0; d];
                for _ in 0..calls {
                    pool.log_density_gradient(&q, &mut g).expect("eval");
                }
            });
        }
    });
    let replicated_us = t.elapsed().as_secs_f64() * 1e6 / calls as f64;
    println!(
        "{}",
        json!({
            "model": so.display().to_string().replace('\\', "/"),
            "dimension": d,
            "calls": calls,
            "threads": threads,
            "compiled_threading": format!("{:?}", target.compiled_threading()),
            "threading": format!("{:?}", target.threading()),
            "execution": format!("{:?}", target.execution()),
            "requested_replicas": pool.requested_replicas(),
            "effective_replicas": pool.effective_replicas(),
            "stan_target_us": wrapped_us,
            "raw_fnptr_us": raw_us,
            "raw_fnptr_status": raw_status,
            "concurrent_per_thread_us": concurrent_us,
            "replicated_per_thread_us": replicated_us,
        })
    );
}
