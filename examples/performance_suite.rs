use std::alloc::{GlobalAlloc, Layout, System};
use std::hint::black_box;
use std::num::NonZeroUsize;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Instant;

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

use owalnuts::diagnostics::ParameterSummary;
use owalnuts::walnutpie::*;
fn nz(n: usize) -> NonZeroUsize {
    NonZeroUsize::new(n).unwrap()
}
struct Gaussian(usize);
impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.0
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        for (g, q) in g.iter_mut().zip(q) {
            *g = -*q;
        }
        Ok(-0.5 * q.iter().map(|x| x * x).sum::<f64>())
    }
}
fn measure(name: &str, mut f: impl FnMut() -> u64) {
    f(); // warm reusable storage
    for _ in 0..5 {
        let a = ALLOCATIONS.load(Ordering::Relaxed);
        let b = ALLOCATED_BYTES.load(Ordering::Relaxed);
        let start = Instant::now();
        let fingerprint = black_box(f());
        let elapsed = start.elapsed();
        let allocations = ALLOCATIONS.load(Ordering::Relaxed) - a;
        let bytes = ALLOCATED_BYTES.load(Ordering::Relaxed) - b;
        println!(
            "{name} ms={:.6} allocations={allocations} bytes={bytes} fingerprint={fingerprint:016x}",
            elapsed.as_secs_f64() * 1000.
        );
    }
}
fn main() {
    let n = 32;
    let starts = vec![vec![0.2; n], vec![-0.2; n]];
    let config = RunConfig::new(0, nz(500), 71)
        .with_tuning(KernelTuning::new(0.3, nz(8), nz(1), nz(8), 0.21).unwrap());
    let mass = DenseMass::identity(nz(n)).unwrap();
    measure("dense-32", || {
        let output = sample_chains_dense(&Gaussian(n), &starts, &mass, &config, nz(1)).unwrap();
        output
            .chains()
            .iter()
            .flat_map(|c| c.samples())
            .fold(0xcbf29ce484222325, |h, x| {
                (h ^ x.to_bits()).wrapping_mul(0x100000001b3)
            })
    });
    #[cfg(feature = "research")]
    {
        let direct = DirectOriginalQMass::Dense(mass.clone());
        measure("direct-dense-32", || {
            let output =
                sample_chains_direct_original_q(&Gaussian(n), &starts, &direct, &config, nz(1))
                    .unwrap();
            output
                .chains()
                .iter()
                .flat_map(|c| c.samples())
                .fold(0xcbf29ce484222325, |h, x| {
                    (h ^ x.to_bits()).wrapping_mul(0x100000001b3)
                })
        });
        let direct = DirectOriginalQMass::StructuredPath(
            StructuredBlockMass::new(vec![StructuredCovarianceBlock::ScaledAr1 {
                scale: vec![1.0; n],
                rho: 0.4,
            }])
            .unwrap(),
        );
        measure("direct-structured-32", || {
            let output =
                sample_chains_direct_original_q(&Gaussian(n), &starts, &direct, &config, nz(1))
                    .unwrap();
            output
                .chains()
                .iter()
                .flat_map(|c| c.samples())
                .fold(0xcbf29ce484222325, |h, x| {
                    (h ^ x.to_bits()).wrapping_mul(0x100000001b3)
                })
        });
    }
    let columns: Vec<Vec<f64>> = (0..4)
        .map(|c| {
            (0..4096)
                .map(|i| {
                    ((i + c * 13) as f64 * 0.005).sin() + 0.1 * ((i * 17 + c * 7) as f64).sin()
                })
                .collect()
        })
        .collect();
    let views: Vec<_> = columns.iter().map(Vec::as_slice).collect();
    measure("summary-correlated", || {
        let s = ParameterSummary::compute("x", &views);
        [
            s.mean,
            s.sd,
            s.mcse_mean,
            s.ess_bulk,
            s.ess_tail,
            s.rhat,
            s.quantiles[0],
            s.quantiles[1],
            s.quantiles[2],
        ]
        .iter()
        .fold(0xcbf29ce484222325, |h, x| {
            (h ^ x.to_bits()).wrapping_mul(0x100000001b3)
        })
    });
}
