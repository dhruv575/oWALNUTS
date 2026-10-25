//! WP45 phase-1 profiler. Not the timing harness: this binary installs an
//! instrumented global allocator and (in `timeline`) a probing target wrapper.
//!
//!     profile allocs   <target> --out FILE [--cells C:T,...]
//!     profile timeline <target> --out FILE [--cells C:T,...]
//!     profile alloc-ablation <target> --out FILE [--cells C:T,...] [--reps N]
//!     profile cas-bench --out FILE
//!
//! `allocs` counts heap allocations and bytes during `Sampler::run` (per-thread
//! padded counters, so the counting itself does not contend).
//! `timeline` wraps the target in a probe that records, per OS thread, the
//! calls, the TSC cycles spent inside the user target, the logical processor
//! (sampled every 256 calls) and the thread CPU time, so time per gradient is
//! split into "inside the target" and "everything else" (kernel, driver and
//! the sampler's own per-call wrappers, which sit outside the probe).
//! `alloc-ablation` alternates the system allocator with a thread-local
//! size-class cache in front of it, to bound what allocator contention can
//! cost. `cas-bench` measures the shared compare-and-swap counter pattern of
//! `TargetEvaluationBudget::reserve` against a no-counter control.

use std::alloc::{GlobalAlloc, Layout, System};
use std::cell::UnsafeCell;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU8, AtomicU32, AtomicU64, AtomicUsize, Ordering};
use std::time::Instant;

use owalnuts::sampler::{Target, TargetError};
use serde_json::{Value, json};
use thread_scaling_v1::*;

// --------------------------------------------------------------------------- allocator

const MODE_SYSTEM: u8 = 0;
const MODE_COUNT: u8 = 1;
const MODE_CACHE: u8 = 2;
static MODE: AtomicU8 = AtomicU8::new(MODE_SYSTEM);
const SLOTS: usize = 64;
const CLASSES: usize = 9; // 16 .. 4096 bytes
const CACHE_DEPTH: u32 = 256;

#[repr(align(128))]
struct Slot {
    allocs: AtomicU64,
    bytes: AtomicU64,
    calls: AtomicU64,
    target_cycles: AtomicU64,
    first_ns: AtomicU64,
    last_ns: AtomicU64,
    cpu_first_ns: AtomicU64,
    cpu_last_ns: AtomicU64,
    class_samples: [AtomicU64; 3],
    used: AtomicU64,
}

#[allow(clippy::declare_interior_mutable_const)]
const SLOT: Slot = Slot {
    allocs: AtomicU64::new(0),
    bytes: AtomicU64::new(0),
    calls: AtomicU64::new(0),
    target_cycles: AtomicU64::new(0),
    first_ns: AtomicU64::new(0),
    last_ns: AtomicU64::new(0),
    cpu_first_ns: AtomicU64::new(0),
    cpu_last_ns: AtomicU64::new(0),
    class_samples: [AtomicU64::new(0), AtomicU64::new(0), AtomicU64::new(0)],
    used: AtomicU64::new(0),
};
static SLOTS_ARRAY: [Slot; SLOTS] = [SLOT; SLOTS];
// Thread -> slot mapping without `thread_local!` (on windows-gnu its lazy
// keys allocate, which would recurse into this allocator): open addressing on
// the OS thread id. A slot is used by exactly one live thread, so its free
// lists need no synchronisation. When the table is full the thread falls back
// to the shared overflow slot, which counts but never caches.
static TIDS: [AtomicU32; SLOTS] = [const { AtomicU32::new(0) }; SLOTS];
const OVERFLOW: usize = SLOTS;
struct FreeLists(UnsafeCell<[(*mut u8, u32); CLASSES]>);
unsafe impl Sync for FreeLists {}
static FREE: [FreeLists; SLOTS] = [const { FreeLists(UnsafeCell::new([(std::ptr::null_mut(), 0); CLASSES])) }; SLOTS];
static OVERFLOW_SLOT: Slot = SLOT;

#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetCurrentThreadId() -> u32;
}

fn my_index() -> usize {
    let tid = unsafe { GetCurrentThreadId() };
    let mut i = (tid as usize).wrapping_mul(2654435761) % SLOTS;
    for _ in 0..SLOTS {
        let cur = TIDS[i].load(Ordering::Relaxed);
        if cur == tid {
            return i;
        }
        if cur == 0 && TIDS[i].compare_exchange(0, tid, Ordering::AcqRel, Ordering::Relaxed).is_ok() {
            return i;
        }
        i = (i + 1) % SLOTS;
    }
    OVERFLOW
}

fn slot() -> &'static Slot {
    let i = my_index();
    let s = if i == OVERFLOW { &OVERFLOW_SLOT } else { &SLOTS_ARRAY[i] };
    s.used.store(1, Ordering::Relaxed);
    s
}

/// Between runs only (every pool thread of the previous run has been joined).
fn reset_slots() {
    for t in &TIDS {
        t.store(0, Ordering::SeqCst);
    }
    for s in SLOTS_ARRAY.iter().chain(std::iter::once(&OVERFLOW_SLOT)) {
        for a in [&s.allocs, &s.bytes, &s.calls, &s.target_cycles, &s.first_ns, &s.last_ns, &s.cpu_first_ns, &s.cpu_last_ns, &s.used] {
            a.store(0, Ordering::SeqCst);
        }
        for a in &s.class_samples {
            a.store(0, Ordering::SeqCst);
        }
    }
}

fn class_of(layout: Layout) -> Option<usize> {
    if layout.align() > 16 || layout.size() > 4096 {
        return None;
    }
    let size = layout.size().max(16).next_power_of_two();
    Some(size.trailing_zeros() as usize - 4)
}

fn class_layout(class: usize) -> Layout {
    Layout::from_size_align(16usize << class, 16).unwrap()
}

struct Probing;

unsafe impl GlobalAlloc for Probing {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        let mode = MODE.load(Ordering::Relaxed);
        if mode != MODE_SYSTEM {
            let s = slot();
            s.allocs.fetch_add(1, Ordering::Relaxed);
            s.bytes.fetch_add(layout.size() as u64, Ordering::Relaxed);
        }
        match class_of(layout) {
            None => unsafe { System.alloc(layout) },
            Some(class) => {
                if mode == MODE_CACHE {
                    let i = my_index();
                    let hit = if i == OVERFLOW {
                        None
                    } else {
                        let f = unsafe { &mut *FREE[i].0.get() };
                        let (head, n) = f[class];
                        if head.is_null() {
                            None
                        } else {
                            f[class] = (unsafe { *(head as *mut *mut u8) }, n - 1);
                            Some(head)
                        }
                    };
                    if let Some(p) = hit {
                        return p;
                    }
                }
                unsafe { System.alloc(class_layout(class)) }
            }
        }
    }
    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        match class_of(layout) {
            None => unsafe { System.dealloc(ptr, layout) },
            Some(class) => {
                if MODE.load(Ordering::Relaxed) == MODE_CACHE {
                    let i = my_index();
                    let kept = if i == OVERFLOW {
                        false
                    } else {
                        let f = unsafe { &mut *FREE[i].0.get() };
                        let (head, n) = f[class];
                        if n < CACHE_DEPTH {
                            unsafe { *(ptr as *mut *mut u8) = head };
                            f[class] = (ptr, n + 1);
                            true
                        } else {
                            false
                        }
                    };
                    if kept {
                        return;
                    }
                }
                unsafe { System.dealloc(ptr, class_layout(class)) }
            }
        }
    }
    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        let new_layout = unsafe { Layout::from_size_align_unchecked(new_size, layout.align()) };
        if let (Some(a), Some(b)) = (class_of(layout), class_of(new_layout))
            && a == b
        {
            return ptr;
        }
        if class_of(layout).is_none() && class_of(new_layout).is_none() {
            return unsafe { System.realloc(ptr, layout, new_size) };
        }
        let new = unsafe { self.alloc(new_layout) };
        if !new.is_null() {
            unsafe { std::ptr::copy_nonoverlapping(ptr, new, layout.size().min(new_size)) };
            unsafe { self.dealloc(ptr, layout) };
        }
        new
    }
}

#[global_allocator]
static GLOBAL: Probing = Probing;

// --------------------------------------------------------------------------- probe target

fn rdtsc() -> u64 {
    #[cfg(target_arch = "x86_64")]
    unsafe {
        core::arch::x86_64::_rdtsc()
    }
}

static EPOCH: std::sync::OnceLock<Instant> = std::sync::OnceLock::new();
fn now_ns() -> u64 {
    EPOCH.get_or_init(Instant::now).elapsed().as_nanos() as u64 + 1
}

struct Probe<'a, T> {
    inner: &'a T,
    classes: &'a [&'static str],
}

impl<T: Target> Target for Probe<'_, T> {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }
    fn parameter_names(&self) -> Option<Vec<String>> {
        self.inner.parameter_names()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let s = slot();
        let n = s.calls.load(Ordering::Relaxed);
        if n == 0 {
            s.first_ns.store(now_ns(), Ordering::Relaxed);
            s.cpu_first_ns.store((thread_cpu_seconds() * 1e9) as u64, Ordering::Relaxed);
        }
        if n % 256 == 0 {
            let p = current_processor() as usize;
            let c = match self.classes.get(p).copied().unwrap_or("?") {
                "P" => 0,
                "E" => 1,
                _ => 2,
            };
            s.class_samples[c].fetch_add(1, Ordering::Relaxed);
            s.last_ns.store(now_ns(), Ordering::Relaxed);
            s.cpu_last_ns.store((thread_cpu_seconds() * 1e9) as u64, Ordering::Relaxed);
        }
        let t0 = rdtsc();
        let r = self.inner.log_density_gradient(q, g);
        let t1 = rdtsc();
        s.target_cycles.fetch_add(t1.wrapping_sub(t0), Ordering::Relaxed);
        s.calls.store(n + 1, Ordering::Relaxed);
        r
    }
}

fn tsc_ghz() -> f64 {
    let t = Instant::now();
    let c = rdtsc();
    while t.elapsed().as_millis() < 200 {}
    (rdtsc() - c) as f64 / t.elapsed().as_nanos() as f64
}

// --------------------------------------------------------------------------- modes

fn parse_cells(s: &str) -> Vec<(usize, usize)> {
    s.split(',')
        .map(|p| {
            let (c, t) = p.split_once(':').unwrap();
            (c.parse().unwrap(), t.parse().unwrap())
        })
        .collect()
}

fn slot_report(tsc: f64) -> Vec<Value> {
    SLOTS_ARRAY
        .iter()
        .enumerate()
        .filter(|(_, s)| s.used.load(Ordering::SeqCst) == 1)
        .map(|(i, s)| {
            let calls = s.calls.load(Ordering::SeqCst);
            let span = (s.last_ns.load(Ordering::SeqCst).saturating_sub(s.first_ns.load(Ordering::SeqCst))) as f64 * 1e-9;
            let cpu = (s.cpu_last_ns.load(Ordering::SeqCst).saturating_sub(s.cpu_first_ns.load(Ordering::SeqCst))) as f64 * 1e-9;
            let target_s = s.target_cycles.load(Ordering::SeqCst) as f64 / tsc * 1e-9;
            json!({
                "slot": i,
                "allocs": s.allocs.load(Ordering::SeqCst),
                "alloc_bytes": s.bytes.load(Ordering::SeqCst),
                "calls": calls,
                "active_span_s": span,
                "thread_cpu_over_span_s": cpu,
                "cpu_fraction_of_span": if span > 0.0 { cpu / span } else { f64::NAN },
                "inside_target_s": target_s,
                "ns_per_call_span": if calls > 0 { span * 1e9 / calls as f64 } else { f64::NAN },
                "ns_per_call_inside_target": if calls > 0 { target_s * 1e9 / calls as f64 } else { f64::NAN },
                "ns_per_call_outside_target_cpu": if calls > 0 { (cpu - target_s) * 1e9 / calls as f64 } else { f64::NAN },
                "processor_class_samples": {"P": s.class_samples[0].load(Ordering::SeqCst), "E": s.class_samples[1].load(Ordering::SeqCst), "LPE": s.class_samples[2].load(Ordering::SeqCst)},
            })
        })
        .collect()
}

fn with_target<R>(target: &StudyTarget, f: &mut dyn FnMut(&dyn ErasedRun) -> R) -> R {
    match target {
        StudyTarget::Gauss100(t) => f(&Runner(t)),
        StudyTarget::LocalLevel(t) => f(&Runner(t)),
        StudyTarget::ArK(t) => f(&Runner(t)),
    }
}

trait ErasedRun {
    fn run(&self, wl: &Workload, chains: usize, threads: usize, probe: Option<&[&'static str]>) -> CellOutcome;
}
struct Runner<'a, T>(&'a T);
impl<T: Target> ErasedRun for Runner<'_, T> {
    fn run(&self, wl: &Workload, chains: usize, threads: usize, probe: Option<&[&'static str]>) -> CellOutcome {
        match probe {
            None => run_cell(self.0, wl, chains, threads),
            Some(classes) => run_cell(&Probe { inner: self.0, classes }, wl, chains, threads),
        }
    }
}

fn cell_summary(rec: &Value) -> Value {
    json!({
        "status": rec["status"], "wall_s": rec["wall_s"], "counters": rec["counters"],
        "gradients_total": rec["gradients_total"], "gradients_per_chain": rec["gradients_per_chain"],
        "fingerprint": rec["fingerprint"], "metadata_thread_count": rec["metadata_thread_count"],
    })
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let mode = args[1].clone();
    let mut out = None;
    let mut cells = vec![(1, 1), (8, 8), (16, 16)];
    let mut reps = 3usize;
    let mut target_name = None;
    let mut overrides: (Option<u64>, Option<usize>, Option<usize>) = (None, None, None);
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--out" => { out = Some(PathBuf::from(&args[i + 1])); i += 1; }
            "--cells" => { cells = parse_cells(&args[i + 1]); i += 1; }
            "--reps" => { reps = args[i + 1].parse().unwrap(); i += 1; }
            "--seed" => { overrides.0 = Some(args[i + 1].parse().unwrap()); i += 1; }
            "--warmup" => { overrides.1 = Some(args[i + 1].parse().unwrap()); i += 1; }
            "--draws" => { overrides.2 = Some(args[i + 1].parse().unwrap()); i += 1; }
            other if !other.starts_with("--") && target_name.is_none() => target_name = Some(other.to_string()),
            other => panic!("unknown argument {other}"),
        }
        i += 1;
    }
    let out = out.expect("--out");
    if out.exists() {
        panic!("refusing to overwrite {}", out.display());
    }
    let study_dir = std::env::var_os("TS_STUDY_DIR").map(PathBuf::from).unwrap_or_else(|| PathBuf::from(env!("CARGO_MANIFEST_DIR")));
    let classes = processor_classes();
    let tsc = tsc_ghz();
    let mut results = Vec::new();
    match mode.as_str() {
        "cas-bench" => results = cas_bench(),
        "allocs" | "timeline" | "alloc-ablation" => {
            let name = target_name.expect("target");
            let target = load_target(&name, &study_dir).expect("load");
            let base = workload(&name);
            let wl = &Workload {
                name: base.name,
                seed: overrides.0.unwrap_or(base.seed),
                warmup: overrides.1.unwrap_or(base.warmup),
                draws: overrides.2.unwrap_or(base.draws),
            };
            let arms: Vec<u8> = match mode.as_str() {
                "allocs" | "timeline" => vec![MODE_COUNT],
                _ => vec![MODE_SYSTEM, MODE_CACHE],
            };
            let reps = if mode == "alloc-ablation" { reps } else { 1 };
            for rep in 0..reps {
                for &(c, t) in &cells {
                    // Alternate arm order by repetition (ABBA-style) to spread drift.
                    let order: Vec<u8> = if rep % 2 == 0 { arms.clone() } else { arms.iter().rev().copied().collect() };
                    for &m in &order {
                        reset_slots();
                        MODE.store(m, Ordering::SeqCst);
                        let probe = (mode == "timeline").then_some(classes.as_slice());
                        let outcome = with_target(&target, &mut |r| r.run(wl, c, t, probe));
                        MODE.store(MODE_SYSTEM, Ordering::SeqCst);
                        let slots = slot_report(tsc);
                        let allocs: u64 = slots.iter().map(|s| s["allocs"].as_u64().unwrap()).sum();
                        let bytes: u64 = slots.iter().map(|s| s["alloc_bytes"].as_u64().unwrap()).sum();
                        let grads = outcome.record["gradients_total"].as_f64().unwrap_or(f64::NAN);
                        let rec = json!({
                            "mode": mode, "target": name, "seed": wl.seed, "warmup": wl.warmup, "draws": wl.draws, "chains": c, "threads": t, "rep": rep,
                            "allocator": match m { MODE_SYSTEM => "system", MODE_COUNT => "system+count", _ => "thread-cache" },
                            "cell": cell_summary(&outcome.record),
                            "allocs_total": allocs, "alloc_bytes_total": bytes,
                            "allocs_per_gradient": allocs as f64 / grads,
                            "allocs_per_transition_per_chain": allocs as f64 / (c * (wl.warmup + wl.draws)) as f64,
                            "threads_report": if mode == "timeline" { Value::Array(slots) } else { Value::Null },
                        });
                        println!(
                            "{mode} {name} c{c} t{t} r{rep} {}: wall {:.3}s allocs/grad {:.3} fp {}",
                            rec["allocator"], outcome.record["wall_s"].as_f64().unwrap_or(f64::NAN),
                            rec["allocs_per_gradient"].as_f64().unwrap_or(f64::NAN),
                            outcome.record["fingerprint"].as_str().unwrap_or("-")
                        );
                        results.push(rec);
                    }
                }
            }
        }
        other => panic!("unknown mode {other}"),
    }
    let payload = json!({
        "schema": "thread-scaling-v1-profile",
        "mode": mode,
        "tsc_ghz": tsc,
        "processor_classes": classes,
        "cpu_sets": cpu_sets().iter().map(|s| json!({"lp": s.0, "core": s.1, "llc": s.2, "efficiency_class": s.3})).collect::<Vec<_>>(),
        "results": results,
    });
    std::fs::create_dir_all(out.parent().unwrap()).unwrap();
    std::fs::write(&out, serde_json::to_vec_pretty(&payload).unwrap()).unwrap();
}

// --------------------------------------------------------------------------- CAS micro-benchmark

/// `work` dependent floating-point steps, then (arm) a budget-style reservation.
fn cas_bench() -> Vec<Value> {
    #[repr(align(128))]
    struct Padded(AtomicUsize);
    let ops = 2_000_000usize;
    let mut rows = Vec::new();
    for &work in &[0usize, 64, 256, 1024] {
        for &arm in &["none", "shared-cas", "per-thread-add"] {
            for &n in &[1usize, 2, 4, 8, 16] {
                let shared = Padded(AtomicUsize::new(0));
                let own: Vec<Padded> = (0..n).map(|_| Padded(AtomicUsize::new(0))).collect();
                let maximum = usize::MAX;
                let per_thread = ops / n.max(1);
                let begin = Instant::now();
                std::thread::scope(|scope| {
                    for k in 0..n {
                        let shared = &shared;
                        let own = &own[k];
                        scope.spawn(move || {
                            let mut x = 1.000_000_1f64 + k as f64 * 1e-9;
                            for _ in 0..per_thread {
                                for _ in 0..work {
                                    x = x * 1.000_000_01 + 1e-12;
                                }
                                match arm {
                                    "shared-cas" => {
                                        let _ = shared.0.fetch_update(Ordering::AcqRel, Ordering::Acquire, |c| (c < maximum).then_some(c + 1));
                                    }
                                    "per-thread-add" => {
                                        own.0.fetch_add(1, Ordering::Relaxed);
                                    }
                                    _ => {}
                                }
                            }
                            std::hint::black_box(x);
                        });
                    }
                });
                let wall = begin.elapsed().as_secs_f64();
                let ns_per_op_per_thread = wall * 1e9 / per_thread as f64;
                println!("cas-bench work {work:>4} {arm:>14} n{n:>2}: {ns_per_op_per_thread:8.1} ns/op/thread");
                rows.push(json!({"work_steps": work, "arm": arm, "threads": n, "ops_per_thread": per_thread,
                                 "wall_s": wall, "ns_per_op_per_thread": ns_per_op_per_thread}));
            }
        }
    }
    rows
}
