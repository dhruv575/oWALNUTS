//! WP48 per-gradient cost decomposition for a quiet-machine wall estimate.
//!
//! `overhead grad <model.so> <data.json> <points.json> <out.json>`: single-replica
//! BridgeStan gradient cost at posterior points (a JSON list of unconstrained
//! vectors); seconds per gradient, minimum over 7 timed passes of at least
//! 0.3 s each, after one warm-up pass.
//!
//! `overhead kernel <dimension> <out.json>`: sampler-side cost per gradient
//! for each arm on an independent standard Gaussian of that dimension (whose
//! own gradient costs O(d) and is timed separately and subtracted): one chain,
//! one thread, 1,000 + 1,000 transitions, minimum over 5 repetitions of wall
//! per target call. Measured on a contended machine; minima are reported
//! because contention only adds time.
#![forbid(unsafe_code)]

use owalnuts::sampler::{
    Adaptation, DEFAULT_METRIC_REGULARIZATION, DEFAULT_WARMUP_EXHAUSTION, Limits, Metric, Sampler,
    Target, TargetError, WarmupConfig,
};
use owalnuts::walnutpie::{DenseMetricRegularization, DenseWarmupSeeding};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::json;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::{env, error::Error, fs, hint::black_box, path::Path, time::Instant};

struct Gaussian {
    dimension: usize,
    calls: AtomicUsize,
}

impl Target for Gaussian {
    fn dimension(&self) -> usize {
        self.dimension
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let mut value = 0.0;
        for (gi, qi) in g.iter_mut().zip(q) {
            *gi = -qi;
            value -= 0.5 * qi * qi;
        }
        Ok(value)
    }
}

fn arm_config(arm: &str) -> Result<(Metric, Adaptation), Box<dyn Error>> {
    let custom = |regularization, seeding| -> Result<Adaptation, Box<dyn Error>> {
        Ok(Adaptation::Custom(
            WarmupConfig::new(0.8)?
                .with_warmup_exhaustion_rule(DEFAULT_WARMUP_EXHAUSTION)
                .with_metric_regularization(DEFAULT_METRIC_REGULARIZATION)
                .with_dense_metric_regularization(regularization)
                .with_dense_warmup_seeding(seeding),
        ))
    };
    match arm {
        "diag" => Ok((Metric::diagonal(), Adaptation::default())),
        "dense" => Ok((Metric::dense(), Adaptation::default())),
        "dense-custom-default" => Ok((
            Metric::dense(),
            custom(
                DenseMetricRegularization::MeanVarianceShrinkage,
                DenseWarmupSeeding::Legacy,
            )?,
        )),
        "dense-seeded" => Ok((
            Metric::dense(),
            custom(
                DenseMetricRegularization::MeanVarianceShrinkage,
                DenseWarmupSeeding::PerTransition,
            )?,
        )),
        "dense-stan" => Ok((
            Metric::dense(),
            custom(DenseMetricRegularization::Stan, DenseWarmupSeeding::PerTransition)?,
        )),
        other => Err(format!("unknown arm {other:?}").into()),
    }
}

fn time_gradients<T: Target>(target: &T, points: &[Vec<f64>]) -> Result<(f64, usize), Box<dyn Error>> {
    let mut gradient = vec![0.0; target.dimension()];
    let mut pass = |reps: usize| -> Result<f64, Box<dyn Error>> {
        let begin = Instant::now();
        for _ in 0..reps {
            for p in points {
                let v = target
                    .log_density_gradient(black_box(p), &mut gradient)
                    .map_err(|e| format!("{e:?}"))?;
                black_box(v);
            }
        }
        Ok(begin.elapsed().as_secs_f64())
    };
    pass(1)?;
    let mut reps = 1;
    while pass(reps)? < 0.3 {
        reps *= 2;
    }
    let mut best = f64::INFINITY;
    for _ in 0..7 {
        best = best.min(pass(reps)? / (reps * points.len()) as f64);
    }
    Ok((best, reps * points.len()))
}

fn grad(model: &Path, data: &Path, points: &Path, out: &Path) -> Result<(), Box<dyn Error>> {
    let data_json = fs::read_to_string(data)?;
    let target = ReplicatedStanTarget::load(model, &default_preload(), Some(&data_json), 1, 1)?;
    let points: Vec<Vec<f64>> = serde_json::from_str(&fs::read_to_string(points)?)?;
    let (seconds, evaluations) = time_gradients(&target, &points)?;
    let payload = json!({"schema": "dense-metric-posteriordb-v1-grad-cost",
        "dimension": target.dimension(), "points": points.len(),
        "seconds_per_gradient_min_of_7": seconds, "evaluations_per_pass": evaluations,
        "note": "single replica, single thread, contended shared machine; minimum over passes"});
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!("grad: {:.3} us per gradient", seconds * 1e6);
    Ok(())
}

fn kernel(dimension: usize, out: &Path) -> Result<(), Box<dyn Error>> {
    let target = Gaussian {
        dimension,
        calls: AtomicUsize::new(0),
    };
    let points: Vec<Vec<f64>> = (0..16)
        .map(|k| (0..dimension).map(|i| ((k * 31 + i * 7) % 13) as f64 / 6.0 - 1.0).collect())
        .collect();
    let (gaussian_gradient, _) = time_gradients(&target, &points)?;
    let mut arms = serde_json::Map::new();
    for arm in ["diag", "dense", "dense-seeded", "dense-stan"] {
        let mut best = f64::INFINITY;
        let mut calls_seen = 0;
        let mut failure = None;
        for rep in 0..5u64 {
            let (metric, adaptation) = arm_config(arm)?;
            let before = target.calls.load(Ordering::Relaxed);
            let begin = Instant::now();
            let posterior = match Sampler::new()
                .warmup(1000)
                .draws(1000)
                .chains(1)
                .threads(1)
                .seed(0x0e48_0000 + rep)
                .metric(metric)
                .adaptation(adaptation)
                .limits(Limits::new().admit_worst_case())
                .run(&target, &[vec![0.5; dimension]])
            {
                Ok(posterior) => posterior,
                Err(error) => {
                    failure = Some(format!("repetition {rep}: {error}"));
                    continue;
                }
            };
            let wall = begin.elapsed().as_secs_f64();
            black_box(posterior.total_target_calls());
            let calls = target.calls.load(Ordering::Relaxed) - before;
            calls_seen = calls;
            best = best.min(wall / calls as f64);
        }
        let ok = best.is_finite();
        arms.insert(arm.to_string(), json!({
            "wall_per_target_call_min_of_5": if ok { Some(best) } else { None },
            "kernel_overhead_per_gradient": if ok { Some(best - gaussian_gradient) } else { None },
            "target_calls_last_rep": calls_seen,
            "failure": failure,
        }));
        eprintln!("kernel d={dimension} {arm}: {:.3} us per call", best * 1e6);
    }
    let payload = json!({"schema": "dense-metric-posteriordb-v1-kernel-cost",
        "dimension": dimension, "gaussian_gradient_seconds": gaussian_gradient,
        "arms": arms,
        "note": "one chain, one thread, iid standard Gaussian target, 1,000 + 1,000; contended shared machine; minimum over repetitions"});
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [cmd, model, data, points, out] if cmd == "grad" => {
            grad(Path::new(model), Path::new(data), Path::new(points), Path::new(out))
        }
        [cmd, dimension, out] if cmd == "kernel" => match dimension.parse::<usize>() {
            Ok(d) => kernel(d, Path::new(out)),
            Err(_) => Err("dimension must be an integer".into()),
        },
        _ => Err("usage: grad <model.so> <data.json> <points.json> <out.json> | kernel <d> <out.json>".into()),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
