//! Per-call wall cost of `bs_log_density_gradient` for a built model.
//!
//! Usage: `wallgap <model.so> <data.json> [calls] [threads]`
//!
//! Prints one JSON line: microseconds per call through `StanTarget`, through
//! the raw function pointer (separate library handle, no wrapper, no checks),
//! both single-threaded, and the per-thread cost when `threads` threads call
//! the same `StanTarget` concurrently (wall / calls-per-thread, i.e. what a
//! multi-chain sampler sees), and the same through a `ReplicatedStanTarget`
//! with `threads` replicas.
#![deny(unsafe_op_in_unsafe_fn)]

use libloading::{Library, Symbol};
use owalnuts::walnutpie::Target;
use owalnuts_bridgestan::{ReplicatedStanTarget, StanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use std::{env, ffi::c_char, fs, path::Path, time::Instant};

type Construct = unsafe extern "C" fn(*const c_char, u32, *mut *mut c_char) -> *mut u8;
type Ldg = unsafe extern "C" fn(
    *const u8,
    bool,
    bool,
    *const f64,
    *mut f64,
    *mut f64,
    *mut *mut c_char,
) -> i32;

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

    // SAFETY: same contract as `StanTarget`; a second model instance in a
    // second library handle, evaluated only from this thread.
    let raw_us = unsafe {
        let lib = Library::new(so).expect("lib");
        let construct: Symbol<Construct> = lib.get(b"bs_model_construct\0").unwrap();
        let ldg: Symbol<Ldg> = lib.get(b"bs_log_density_gradient\0").unwrap();
        let cdata = std::ffi::CString::new(data.clone()).unwrap();
        let mut err: *mut c_char = std::ptr::null_mut();
        let m = construct(cdata.as_ptr(), 1, &mut err);
        assert!(!m.is_null());
        let mut v = 0.0;
        for _ in 0..200 {
            ldg(m, false, true, q.as_ptr(), &mut v, g.as_mut_ptr(), &mut err);
        }
        let t = Instant::now();
        for _ in 0..calls {
            let rc = ldg(m, false, true, q.as_ptr(), &mut v, g.as_mut_ptr(), &mut err);
            assert_eq!(rc, 0);
        }
        t.elapsed().as_secs_f64() * 1e6 / calls as f64
    };

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
        "{{\"model\":\"{}\",\"dimension\":{d},\"calls\":{calls},\"threads\":{threads},\"threading\":\"{:?}\",\"stan_target_us\":{wrapped_us:.3},\"raw_fnptr_us\":{raw_us:.3},\"concurrent_per_thread_us\":{concurrent_us:.3},\"replicated_per_thread_us\":{replicated_us:.3}}}",
        so.display().to_string().replace('\\', "/"),
        target.threading()
    );
}
