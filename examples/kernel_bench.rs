//! Kernel hot-path microbenchmark.
//!
//! Runs three fixed-seed workloads on one thread and reports, per workload,
//! the wall time, the number of fused target calls, the target's own cost
//! (measured separately in a tight loop), the kernel overhead per target call
//! (wall minus target time, divided by calls), and the heap allocations made
//! per target call. It also prints an FNV fingerprint of every retained draw
//! so a run can be compared bit-for-bit against another build.
//!
//! ```text
//! cargo run --release --example kernel_bench [-- --repeat N]
//! ```

use std::alloc::{GlobalAlloc, Layout, System};
use std::error::Error;
use std::hint::black_box;
use std::num::NonZeroUsize;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

use owalnuts::walnutpie::{
    DiagonalMass, KernelTuning, MultiChainOutput, RunConfig, Target, TargetError,
    TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    sample_chains_with_target_budget,
};

struct CountingAllocator;

static ALLOCATIONS: AtomicUsize = AtomicUsize::new(0);
static ALLOCATED_BYTES: AtomicUsize = AtomicUsize::new(0);

// SAFETY: every method forwards to `System` unchanged; the counters are
// side effects only.
unsafe impl GlobalAlloc for CountingAllocator {
    unsafe fn alloc(&self, layout: Layout) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(layout.size(), Ordering::Relaxed);
        unsafe { System.alloc(layout) }
    }

    unsafe fn dealloc(&self, ptr: *mut u8, layout: Layout) {
        unsafe { System.dealloc(ptr, layout) }
    }

    unsafe fn realloc(&self, ptr: *mut u8, layout: Layout, new_size: usize) -> *mut u8 {
        ALLOCATIONS.fetch_add(1, Ordering::Relaxed);
        ALLOCATED_BYTES.fetch_add(new_size, Ordering::Relaxed);
        unsafe { System.realloc(ptr, layout, new_size) }
    }
}

#[global_allocator]
static GLOBAL: CountingAllocator = CountingAllocator;

const FUNNEL_DIMENSION: usize = 10;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

struct Gaussian(usize);

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let mut value = 0.0;
        for (g, x) in gradient.iter_mut().zip(position) {
            *g = -x;
            value += x * x;
        }
        Ok(-0.5 * value)
    }
}

const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const SCHOOL_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SCHOOL_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

struct EightSchools;

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        10
    }

    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        let z = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.);
        gradient[0] = -mu / 25.;
        gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..8 {
            let theta = mu + tau * z[j];
            let residual = SCHOOL_Y[j] - theta;
            let likelihood_gradient = residual / SCHOOL_SE[j].powi(2);
            value += normal_log_density(SCHOOL_Y[j], theta, SCHOOL_SE[j])
                + normal_log_density(z[j], 0., 1.);
            gradient[0] += likelihood_gradient;
            gradient[1] += likelihood_gradient * tau * z[j];
            gradient[j + 2] = -z[j] + likelihood_gradient * tau;
        }
        if value.is_finite() && gradient.iter().all(|x| x.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::new("nonfinite target evaluation"))
        }
    }
}

fn nz(value: usize) -> NonZeroUsize {
    NonZeroUsize::new(value).expect("nonzero")
}

fn fnv(hash: &mut u64, value: u64) {
    *hash ^= value;
    *hash = hash.wrapping_mul(0x100_0000_01b3);
}

fn fingerprint(output: &MultiChainOutput) -> u64 {
    let mut hash = 0xcbf2_9ce4_8422_2325;
    for chain in output.chains() {
        for value in chain.samples() {
            fnv(&mut hash, value.to_bits());
        }
    }
    hash
}

fn target_calls(output: &MultiChainOutput) -> usize {
    output
        .chains()
        .iter()
        .map(|chain| chain.telemetry().total().target_calls_total())
        .sum()
}

/// Cost of one fused call in isolation, in nanoseconds.
fn target_cost_ns<T: Target>(target: &T, position: &[f64]) -> f64 {
    let mut gradient = vec![0.0; target.dimension()];
    let iterations = 2_000_000usize;
    let start = Instant::now();
    for _ in 0..iterations {
        let value = target
            .log_density_gradient(black_box(position), &mut gradient)
            .expect("finite");
        black_box(value);
        black_box(&gradient);
    }
    start.elapsed().as_nanos() as f64 / iterations as f64
}

struct Report {
    name: &'static str,
    wall_ms: f64,
    calls: usize,
    target_ns: f64,
    overhead_ns: f64,
    allocations_per_call: f64,
    bytes_per_call: f64,
    fingerprint: u64,
}

fn run<T: Target>(
    name: &'static str,
    target: &T,
    starts: &[Vec<f64>],
    config: &RunConfig,
    probe: &[f64],
    repeat: usize,
) -> Result<Report, Box<dyn Error>> {
    let mass = DiagonalMass::identity(nz(target.dimension()));
    let target_ns = target_cost_ns(target, probe);
    let mut best_wall = f64::INFINITY;
    let mut best = None;
    for _ in 0..repeat {
        let allocations_before = ALLOCATIONS.load(Ordering::Relaxed);
        let bytes_before = ALLOCATED_BYTES.load(Ordering::Relaxed);
        let start = Instant::now();
        let worst = config.worst_case_target_evaluations(nz(starts.len()))?;
        let output = sample_chains_with_target_budget(
            target,
            starts,
            &mass,
            config,
            nz(1),
            TargetEvaluationAdmissionLimit::new(nz(worst)),
            &TargetEvaluationBudget::new(nz(worst)),
        )?;
        let wall = start.elapsed();
        let allocations = ALLOCATIONS.load(Ordering::Relaxed) - allocations_before;
        let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed) - bytes_before;
        let wall_ms = wall.as_secs_f64() * 1e3;
        if wall_ms < best_wall {
            best_wall = wall_ms;
            let calls = target_calls(&output);
            best = Some(Report {
                name,
                wall_ms,
                calls,
                target_ns,
                overhead_ns: (wall.as_nanos() as f64 - target_ns * calls as f64) / calls as f64,
                allocations_per_call: allocations as f64 / calls as f64,
                bytes_per_call: bytes as f64 / calls as f64,
                fingerprint: fingerprint(&output),
            });
        }
    }
    Ok(best.expect("at least one repeat"))
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut repeat = 3usize;
    let mut args = std::env::args().skip(1);
    while let Some(arg) = args.next() {
        if arg == "--repeat" {
            repeat = args.next().ok_or("--repeat needs a value")?.parse()?;
        }
    }

    let mut reports = Vec::new();

    // (a) Neal's funnel at the paper tuning: delta = 0.21, h = 0.36,
    // depth 10, eight refinement levels. No warmup, four dispersed starts.
    {
        let tuning = KernelTuning::new(0.36, nz(10), nz(1), nz(8), 0.21)?;
        let config = RunConfig::new(0, nz(1_000), 0x5eed_f0f0).with_tuning(tuning);
        let starts: Vec<Vec<f64>> = [-3.0, -1.0, 1.0, 3.0]
            .into_iter()
            .map(|omega| {
                let mut q = vec![0.0; FUNNEL_DIMENSION];
                q[0] = omega;
                q
            })
            .collect();
        let mut probe = vec![0.3; FUNNEL_DIMENSION];
        probe[0] = -1.0;
        reports.push(run(
            "funnel-10d",
            &Funnel,
            &starts,
            &config,
            &probe,
            repeat,
        )?);
    }

    // (b) 100-D standard Gaussian at depth 8.
    {
        let dimension = 100;
        let tuning = KernelTuning::new(0.3, nz(8), nz(1), nz(4), 1.0)?;
        let config = RunConfig::new(0, nz(1_000), 0x5eed_0100).with_tuning(tuning);
        let starts: Vec<Vec<f64>> = (0..4)
            .map(|chain| vec![0.5 * (chain as f64 - 1.5); dimension])
            .collect();
        let probe = vec![0.7; dimension];
        reports.push(run(
            "gaussian-100d",
            &Gaussian(dimension),
            &starts,
            &config,
            &probe,
            repeat,
        )?);
    }

    // (c) Noncentered Eight Schools with the strict matched-track warmup.
    {
        let tuning =
            KernelTuning::new(0.3, nz(8), nz(1), nz(8), 1.0)?.with_divergence_threshold(1000.0)?;
        let warmup = WarmupConfig::new(0.95)?.with_mass_adaptation(true);
        let config = RunConfig::new(1_000, nz(1_000), 0x5eed_0008)
            .with_tuning(tuning)
            .with_warmup(warmup);
        let starts: Vec<Vec<f64>> = [-2., -1., 0., 1.]
            .into_iter()
            .map(|log_tau| {
                let mut q = vec![0.0; 10];
                q[1] = log_tau;
                q
            })
            .collect();
        let probe = vec![0.2; 10];
        reports.push(run(
            "eight-schools",
            &EightSchools,
            &starts,
            &config,
            &probe,
            repeat,
        )?);
    }

    println!(
        "{:<14} {:>10} {:>10} {:>10} {:>12} {:>10} {:>10}  {}",
        "workload",
        "wall ms",
        "calls",
        "target ns",
        "overhead ns",
        "alloc/cl",
        "bytes/cl",
        "fingerprint"
    );
    for report in &reports {
        println!(
            "{:<14} {:>10.1} {:>10} {:>10.1} {:>12.1} {:>10.2} {:>10.1}  {:016x}",
            report.name,
            report.wall_ms,
            report.calls,
            report.target_ns,
            report.overhead_ns,
            report.allocations_per_call,
            report.bytes_per_call,
            report.fingerprint
        );
    }
    Ok(())
}
