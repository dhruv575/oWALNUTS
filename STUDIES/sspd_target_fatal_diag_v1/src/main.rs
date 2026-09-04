//! Diagnostic only (no evidence seeds): why did the WP37B state-space cell die
//! at chain 1, transition 1? Wraps the frozen polyscope-canonical-v2 target,
//! counts finite / recoverable / fatal-classified evaluations, and optionally
//! reclassifies the target's fatal "not representable as finite" results as
//! recoverable. Usage: sspd-target-fatal-diag-v1 <seed> <none|repair> <warmup> <draws> [initial_step]
#[path = "../../sspd11_confirmation_v1/primary/src/canonical.rs"]
mod canonical;
use canonical::{CenteredTarget, Data, from_innovations};
use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Tuning};
use owalnuts::walnutpie::{Target, TargetError};
use serde_json::Value;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

fn numbers(v: &Value) -> Vec<f64> {
    v.as_array()
        .unwrap()
        .iter()
        .map(|x| x.as_f64().unwrap())
        .collect()
}

struct Diag {
    inner: CenteredTarget,
    repair: bool,
    fatal: AtomicUsize,
    recoverable: AtomicUsize,
    finite: AtomicUsize,
}
impl Target for Diag {
    fn dimension(&self) -> usize {
        self.inner.dimension()
    }
    fn log_density_gradient(&self, p: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        match self.inner.log_density_gradient(p, g) {
            Ok(lp) => {
                self.finite.fetch_add(1, Ordering::Relaxed);
                Ok(lp)
            }
            Err(e) if e.kind() == owalnuts::walnutpie::TargetErrorKind::Recoverable => {
                self.recoverable.fetch_add(1, Ordering::Relaxed);
                Err(e)
            }
            Err(e) => {
                self.fatal.fetch_add(1, Ordering::Relaxed);
                if self.repair {
                    Err(TargetError::recoverable(e.message().to_owned()))
                } else {
                    Err(e)
                }
            }
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let seed: u64 = args[1].parse().unwrap();
    let repair = args[2] == "repair";
    let warmup: usize = args[3].parse().unwrap();
    let draws: usize = args[4].parse().unwrap();
    let step: f64 = args.get(5).map(|x| x.parse().unwrap()).unwrap_or(0.5);
    let fixture: Value = serde_json::from_slice(
        &std::fs::read(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../reverse_coarsening_order_v1/config/sspd-target-fixture.json"
        ))
        .unwrap(),
    )
    .unwrap();
    let data = Data::try_from_raw(
        &numbers(&fixture["data"]["y"]),
        &numbers(&fixture["data"]["s"]),
        &numbers(&fixture["data"]["v"]),
    )
    .unwrap();
    let starts_doc: Value = serde_json::from_slice(
        &std::fs::read(concat!(
            env!("CARGO_MANIFEST_DIR"),
            "/../sspd11_confirmation_v1/primary/starts/sspd-11.json"
        ))
        .unwrap(),
    )
    .unwrap();
    let starts: Vec<Vec<f64>> = starts_doc["starts"]
        .as_array()
        .unwrap()
        .iter()
        .map(|s| from_innovations(&numbers(s), 1.0))
        .collect();
    let target = Diag {
        inner: CenteredTarget {
            data,
            a: 1.0,
            calls: AtomicUsize::new(0),
        },
        repair,
        fatal: AtomicUsize::new(0),
        recoverable: AtomicUsize::new(0),
        finite: AtomicUsize::new(0),
    };
    let tuning = Tuning::new()
        .step_size(step)
        .max_depth(10)
        .min_micro_steps(1)
        .max_refinement_levels(8)
        .max_error(1.0)
        .divergence_threshold(1000.0);
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(4)
        .seed(seed)
        .threads(4)
        .metric(Metric::diagonal())
        .adaptation(Adaptation::default())
        .tuning(tuning)
        .limits(
            Limits::new()
                .admit_worst_case()
                .timeout(Duration::from_secs(900)),
        );
    let t0 = Instant::now();
    let result = sampler.run(&target, &starts);
    let secs = t0.elapsed().as_secs_f64();
    let (fatal, rec, fin) = (
        target.fatal.load(Ordering::Relaxed),
        target.recoverable.load(Ordering::Relaxed),
        target.finite.load(Ordering::Relaxed),
    );
    match result {
        Ok(post) => println!(
            "step={step} seed={seed} repair={repair} OK secs={secs:.1} calls={} finite={fin} recoverable={rec} fatal_class={fatal} draws={}",
            post.total_target_calls(),
            post.draws_per_chain()
        ),
        Err(e) => println!(
            "step={step} seed={seed} repair={repair} ERR secs={secs:.1} finite={fin} recoverable={rec} fatal_class={fatal} err={e:?}"
        ),
    }
}
