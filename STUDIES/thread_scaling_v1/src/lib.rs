//! Shared harness code for WP45 (thread scaling): targets, Windows process and
//! system counters, one timed sampler cell, draw fingerprints and ESS.

use std::fmt::Write as _;
use std::path::Path;
use std::time::Instant;

use owalnuts::diagnostics::ess_bulk;
use owalnuts::sampler::{Posterior, Sampler, Target, TargetError, uniform_starts};
use serde_json::{Value, json};

// --------------------------------------------------------------------------- targets

/// (a) 100-D standard Gaussian with a hand-written gradient (the
/// `kernel_efficiency_v1` 100-D target).
pub struct Gauss100;

impl Target for Gauss100 {
    fn dimension(&self) -> usize {
        100
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let mut s = 0.0;
        for (gi, &x) in g.iter_mut().zip(q) {
            *gi = -x;
            s += x * x;
        }
        Ok(-0.5 * s)
    }
}

/// The three study targets.
pub enum StudyTarget {
    Gauss100(Gauss100),
    LocalLevel(owalnuts_autodiff::AutodiffTarget<owalnuts_autodiff::models::LocalLevel>),
    ArK(owalnuts_bridgestan::ReplicatedStanTarget),
}

/// Fixed workload per target (frozen in protocol.json).
pub struct Workload {
    pub name: &'static str,
    pub seed: u64,
    pub warmup: usize,
    pub draws: usize,
}

pub const WORKLOADS: [Workload; 3] = [
    Workload { name: "gauss100", seed: 945101, warmup: 1000, draws: 20000 },
    Workload { name: "ll1000", seed: 945102, warmup: 200, draws: 200 },
    Workload { name: "ark", seed: 945103, warmup: 500, draws: 500 },
];

pub fn workload(name: &str) -> &'static Workload {
    WORKLOADS.iter().find(|w| w.name == name).expect("unknown target")
}

/// Simulation seed of the T = 1000 local-level data (the autodiff benchmark's).
pub const LOCAL_LEVEL_DATA_SEED: u64 = 2026083101;

pub fn load_target(name: &str, study_dir: &Path) -> Result<StudyTarget, Box<dyn std::error::Error>> {
    Ok(match name {
        "gauss100" => StudyTarget::Gauss100(Gauss100),
        "ll1000" => {
            use owalnuts_autodiff::models::{LocalLevel, LocalLevelData};
            let data = LocalLevelData::simulate(1000, LOCAL_LEVEL_DATA_SEED);
            StudyTarget::LocalLevel(owalnuts_autodiff::AutodiffTarget::new(LocalLevel {
                data,
                normalised: false,
            }))
        }
        "ark" => {
            let model = study_dir.join("models").join("arK__arK_model.so");
            let data = std::fs::read_to_string(study_dir.join("models").join("arK__arK.data.json"))?;
            // Requested replicas = 16 (the largest thread count); on Windows the
            // effective count is always one owned worker (integrations-and-platforms).
            StudyTarget::ArK(owalnuts_bridgestan::ReplicatedStanTarget::load(
                &model,
                &owalnuts_bridgestan::default_preload(),
                Some(&data),
                1,
                16,
            )?)
        }
        _ => return Err(format!("unknown target {name}").into()),
    })
}

impl StudyTarget {
    pub fn info(&self) -> Value {
        match self {
            StudyTarget::Gauss100(_) => json!({"kind": "hand-written", "dimension": 100}),
            StudyTarget::LocalLevel(t) => json!({"kind": "owalnuts-autodiff LocalLevel T=1000 normal_lupdf", "dimension": t.dimension()}),
            StudyTarget::ArK(t) => json!({
                "kind": "BridgeStan posteriordb arK-arK",
                "dimension": t.dimension(),
                "requested_replicas": t.requested_replicas(),
                "effective_replicas": t.effective_replicas(),
                "threading": format!("{:?}", t.threading()),
                "execution": format!("{:?}", t.execution()),
                "compiled_threading": format!("{:?}", t.compiled_threading()),
            }),
        }
    }
}

// --------------------------------------------------------------------------- Windows counters

#[repr(C)]
#[derive(Clone, Copy, Default)]
struct FileTime {
    low: u32,
    high: u32,
}

fn seconds(f: FileTime) -> f64 {
    ((((f.high as u64) << 32) | f.low as u64) as f64) * 1e-7
}

#[repr(C)]
#[derive(Default)]
struct ProcessMemoryCounters {
    cb: u32,
    page_fault_count: u32,
    peak_working_set_size: usize,
    working_set_size: usize,
    quota_peak_paged_pool_usage: usize,
    quota_paged_pool_usage: usize,
    quota_peak_non_paged_pool_usage: usize,
    quota_non_paged_pool_usage: usize,
    pagefile_usage: usize,
    peak_pagefile_usage: usize,
}

#[cfg(windows)]
#[link(name = "kernel32")]
unsafe extern "system" {
    fn GetCurrentProcess() -> isize;
    fn GetCurrentThread() -> isize;
    fn GetProcessTimes(h: isize, c: *mut FileTime, e: *mut FileTime, k: *mut FileTime, u: *mut FileTime) -> i32;
    fn GetThreadTimes(h: isize, c: *mut FileTime, e: *mut FileTime, k: *mut FileTime, u: *mut FileTime) -> i32;
    fn GetSystemTimes(idle: *mut FileTime, kernel: *mut FileTime, user: *mut FileTime) -> i32;
    fn GetCurrentProcessorNumber() -> u32;
    fn K32GetProcessMemoryInfo(h: isize, p: *mut ProcessMemoryCounters, cb: u32) -> i32;
    fn GetSystemCpuSetInformation(info: *mut u8, len: u32, ret: *mut u32, process: isize, flags: u32) -> i32;
}

/// Process user/kernel CPU seconds, system busy core-seconds, page faults.
#[derive(Clone, Copy, Debug, Default)]
pub struct Counters {
    pub process_user: f64,
    pub process_kernel: f64,
    pub system_busy: f64,
    pub system_total: f64,
    pub page_faults: u64,
}

pub fn counters() -> Counters {
    unsafe {
        let p = GetCurrentProcess();
        let (mut c, mut e, mut k, mut u) = Default::default();
        GetProcessTimes(p, &mut c, &mut e, &mut k, &mut u);
        let (mut si, mut sk, mut su) = Default::default();
        GetSystemTimes(&mut si, &mut sk, &mut su);
        let mut m = ProcessMemoryCounters { cb: std::mem::size_of::<ProcessMemoryCounters>() as u32, ..Default::default() };
        K32GetProcessMemoryInfo(p, &mut m, m.cb);
        Counters {
            process_user: seconds(u),
            process_kernel: seconds(k),
            // System kernel time includes idle time.
            system_busy: seconds(sk) - seconds(si) + seconds(su),
            system_total: seconds(sk) + seconds(su),
            page_faults: m.page_fault_count as u64,
        }
    }
}

pub fn peak_working_set() -> usize {
    unsafe {
        let mut m = ProcessMemoryCounters { cb: std::mem::size_of::<ProcessMemoryCounters>() as u32, ..Default::default() };
        K32GetProcessMemoryInfo(GetCurrentProcess(), &mut m, m.cb);
        m.peak_working_set_size
    }
}

/// CPU seconds (user + kernel) consumed by the calling thread.
pub fn thread_cpu_seconds() -> f64 {
    unsafe {
        let (mut c, mut e, mut k, mut u) = Default::default();
        GetThreadTimes(GetCurrentThread(), &mut c, &mut e, &mut k, &mut u);
        seconds(k) + seconds(u)
    }
}

pub fn current_processor() -> u32 {
    unsafe { GetCurrentProcessorNumber() }
}

/// Per logical processor: (index, core index, last-level-cache index, efficiency class).
pub fn cpu_sets() -> Vec<(u8, u8, u8, u8)> {
    unsafe {
        let mut len = 0u32;
        GetSystemCpuSetInformation(std::ptr::null_mut(), 0, &mut len, GetCurrentProcess(), 0);
        let mut buf = vec![0u8; len as usize];
        if GetSystemCpuSetInformation(buf.as_mut_ptr(), len, &mut len, GetCurrentProcess(), 0) == 0 {
            return Vec::new();
        }
        let mut out = Vec::new();
        let mut off = 0usize;
        while off + 8 <= len as usize {
            let size = u32::from_le_bytes(buf[off..off + 4].try_into().unwrap()) as usize;
            if size == 0 {
                break;
            }
            // SYSTEM_CPU_SET_INFORMATION: Size, Type, then CpuSet {Id u32, Group u16,
            // LogicalProcessorIndex u8, CoreIndex u8, LastLevelCacheIndex u8,
            // NumaNodeIndex u8, EfficiencyClass u8, ...}.
            let b = &buf[off..off + size];
            out.push((b[14], b[15], b[16], b[18]));
            off += size;
        }
        out
    }
}

/// Logical processor -> class label: "P" (highest efficiency class), "E"
/// (lower class sharing the P cores' last-level cache) or "LPE" (lower class
/// on its own last-level cache).
pub fn processor_classes() -> Vec<&'static str> {
    let sets = cpu_sets();
    let n = sets.iter().map(|s| s.0 as usize + 1).max().unwrap_or(0);
    let max_class = sets.iter().map(|s| s.3).max().unwrap_or(0);
    let p_llc: Vec<u8> = sets.iter().filter(|s| s.3 == max_class).map(|s| s.2).collect();
    let mut out = vec!["?"; n];
    for s in &sets {
        out[s.0 as usize] = if s.3 == max_class {
            "P"
        } else if p_llc.contains(&s.2) {
            "E"
        } else {
            "LPE"
        };
    }
    out
}

// --------------------------------------------------------------------------- fingerprints

/// FNV-1a 64.
#[derive(Clone, Copy)]
pub struct Fnv(u64);

impl Default for Fnv {
    fn default() -> Self {
        Fnv(0xcbf29ce484222325)
    }
}

impl Fnv {
    pub fn bytes(&mut self, b: &[u8]) {
        for &x in b {
            self.0 ^= x as u64;
            self.0 = self.0.wrapping_mul(0x100000001b3);
        }
    }
    pub fn f64s(&mut self, v: &[f64]) {
        for x in v {
            self.bytes(&x.to_bits().to_le_bytes());
        }
    }
    pub fn hex(&self) -> String {
        format!("{:016x}", self.0)
    }
}

/// Per-chain fingerprints: (draws, transition diagnostics + telemetry, metadata).
/// The metadata fingerprint excludes nothing, so it differs across thread
/// counts (it records `thread_count`); draws and work fingerprints must not.
pub fn fingerprints(posterior: &Posterior) -> Vec<(String, String, String)> {
    posterior
        .chains()
        .iter()
        .map(|chain| {
            let mut d = Fnv::default();
            d.f64s(chain.samples());
            let mut w = Fnv::default();
            let mut s = String::new();
            for diag in chain.diagnostics() {
                s.clear();
                let _ = write!(s, "{diag:?}");
                w.bytes(s.as_bytes());
            }
            s.clear();
            let _ = write!(s, "{:?}", chain.telemetry());
            w.bytes(s.as_bytes());
            let mut m = Fnv::default();
            s.clear();
            let _ = write!(s, "{:?}", chain.metadata());
            m.bytes(s.as_bytes());
            (d.hex(), w.hex(), m.hex())
        })
        .collect()
}

/// Combined fingerprint of all chains' draws and work.
pub fn combined(fps: &[(String, String, String)]) -> String {
    let mut h = Fnv::default();
    for (d, w, _) in fps {
        h.bytes(d.as_bytes());
        h.bytes(w.as_bytes());
    }
    h.hex()
}

/// Minimum over coordinates of bulk ESS across all chains, and its argmin.
pub fn min_bulk_ess(posterior: &Posterior) -> (f64, usize) {
    let chains = posterior.chains();
    let dim = chains[0].dimension();
    let n = chains[0].retained();
    let mut best = (f64::INFINITY, 0);
    let mut cols: Vec<Vec<f64>> = vec![vec![0.0; n]; chains.len()];
    for j in 0..dim {
        for (c, chain) in chains.iter().enumerate() {
            let s = chain.samples();
            for i in 0..n {
                cols[c][i] = s[i * dim + j];
            }
        }
        let refs: Vec<&[f64]> = cols.iter().map(Vec::as_slice).collect();
        let e = ess_bulk(&refs);
        if e < best.0 {
            best = (e, j);
        }
    }
    best
}

// --------------------------------------------------------------------------- one cell

pub struct CellOutcome {
    pub record: Value,
    pub posterior: Option<Posterior>,
}

/// One timed `Sampler::run` at the library defaults with `chains` chains and
/// `threads` threads. The uniform starts are drawn before the clock starts.
pub fn run_cell<T: Target>(target: &T, wl: &Workload, chains: usize, threads: usize) -> CellOutcome {
    let sampler = Sampler::new()
        .warmup(wl.warmup)
        .draws(wl.draws)
        .chains(chains)
        .seed(wl.seed)
        .threads(threads);
    let starts = match uniform_starts(target, chains, wl.seed, 2.0, 100) {
        Ok(s) => s,
        Err(e) => {
            return CellOutcome {
                record: json!({"status": "error", "stage": "init", "error": e.to_string()}),
                posterior: None,
            };
        }
    };
    let before = counters();
    let begin = Instant::now();
    let result = sampler.run(target, &starts);
    let wall = begin.elapsed().as_secs_f64();
    let after = counters();
    let cpu = json!({
        "process_user_s": after.process_user - before.process_user,
        "process_kernel_s": after.process_kernel - before.process_kernel,
        "process_cpu_s": (after.process_user + after.process_kernel) - (before.process_user + before.process_kernel),
        "system_busy_core_s": after.system_busy - before.system_busy,
        "system_total_core_s": after.system_total - before.system_total,
        "page_faults": after.page_faults - before.page_faults,
    });
    match result {
        Err(e) => CellOutcome {
            record: json!({"status": "error", "stage": "sample", "error": e.to_string(), "wall_s": wall, "counters": cpu}),
            posterior: None,
        },
        Ok(posterior) => {
            let per_chain: Vec<usize> = posterior
                .chains()
                .iter()
                .map(|c| c.telemetry().total().target_calls_total())
                .collect();
            let divergences: usize = posterior
                .chains()
                .iter()
                .map(|c| c.telemetry().retained().divergences())
                .sum();
            let fps = fingerprints(&posterior);
            let record = json!({
                "status": "ok",
                "wall_s": wall,
                "counters": cpu,
                "gradients_total": per_chain.iter().sum::<usize>(),
                "gradients_per_chain": per_chain,
                "gradients_max_chain": per_chain.iter().copied().max().unwrap_or(0),
                "retained_divergences": divergences,
                "metadata_thread_count": posterior.chains()[0].metadata().thread_count(),
                "effective_max_target_evaluations": posterior.chains()[0].metadata().effective_max_target_evaluations(),
                "limit_provenance": format!("{:?}", posterior.chains()[0].metadata().target_evaluation_limit_provenance()),
                "fingerprint": combined(&fps),
                "chain_fingerprints": fps.iter().map(|(d, w, m)| json!({"draws": d, "work": w, "metadata": m})).collect::<Vec<_>>(),
            });
            CellOutcome { record, posterior: Some(posterior) }
        }
    }
}

pub fn run_study_cell(target: &StudyTarget, wl: &Workload, chains: usize, threads: usize) -> CellOutcome {
    match target {
        StudyTarget::Gauss100(t) => run_cell(t, wl, chains, threads),
        StudyTarget::LocalLevel(t) => run_cell(t, wl, chains, threads),
        StudyTarget::ArK(t) => run_cell(t, wl, chains, threads),
    }
}

pub fn utc_now() -> String {
    // Seconds since the Unix epoch; the Python driver converts.
    let d = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap();
    format!("{:.3}", d.as_secs_f64())
}
