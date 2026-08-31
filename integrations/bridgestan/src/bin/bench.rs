//! BridgeStan-vs-hand-written-gradient benchmark.
//!
//! Engineering evidence, not a preregistered study: numerical agreement at
//! random points, per-call gradient cost, and paired sampling runs (same
//! seeds, starts and settings) so the FFI + Stan-Math autodiff overhead is
//! measured end to end.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, PaperAdaptationConfig, RunConfig, Target,
    TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use owalnuts_autodiff_tape::{Backend, LocalLevel, simulate};
use owalnuts_bridgestan::{StanTarget, default_preload};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::{Value, json};
use std::{
    fs,
    num::NonZeroUsize,
    path::PathBuf,
    sync::atomic::{AtomicUsize, Ordering},
    time::Instant,
};

const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];
const EIGHT_SCHOOLS_DATA: &str =
    r#"{"J":8,"y":[28,8,-3,7,-1,1,18,12],"sigma":[15,10,16,11,9,11,10,18]}"#;

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

/// Verbatim copy of the confirmation-v38 unconstrained density.
fn noncentered_log_density_gradient(q: &[f64], gradient: &mut [f64]) -> f64 {
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
        let residual = Y[j] - theta;
        let likelihood_gradient = residual / SE[j].powi(2);
        value += normal_log_density(Y[j], theta, SE[j]) + normal_log_density(z[j], 0., 1.);
        gradient[0] += likelihood_gradient;
        gradient[1] += likelihood_gradient * tau * z[j];
        gradient[j + 2] = -z[j] + likelihood_gradient * tau;
    }
    value
}

struct EightSchools {
    calls: AtomicUsize,
}

impl Target for EightSchools {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let v = noncentered_log_density_gradient(q, g);
        if v.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(v)
        } else {
            Err(TargetError::new("nonfinite"))
        }
    }
}

fn models_dir() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("models")
}

fn ess_batch_means(x: &[f64]) -> f64 {
    let n = x.len();
    let b = (n as f64).sqrt().floor() as usize;
    let k = n / b;
    let mean = x.iter().sum::<f64>() / n as f64;
    let var = x.iter().map(|v| (v - mean).powi(2)).sum::<f64>() / (n as f64 - 1.0);
    let bmeans: Vec<f64> = (0..k)
        .map(|i| x[i * b..(i + 1) * b].iter().sum::<f64>() / b as f64)
        .collect();
    let bvar = bmeans.iter().map(|m| (m - mean).powi(2)).sum::<f64>() / (k as f64 - 1.0);
    n as f64 * var / (b as f64 * bvar)
}

/// Agreement + per-call timing between two targets of equal dimension.
fn compare_targets<A: Target, B: Target>(
    name: &str,
    a: &A,
    b: &B,
    points: &[Vec<f64>],
    reps: usize,
) -> Value {
    let d = a.dimension();
    let mut ga = vec![0.0; d];
    let mut gb = vec![0.0; d];
    let mut max_dv: f64 = 0.0;
    let mut max_dg: f64 = 0.0;
    let mut max_rel_dg: f64 = 0.0;
    for p in points {
        let va = a.log_density_gradient(p, &mut ga).expect("hand");
        let vb = b.log_density_gradient(p, &mut gb).expect("stan");
        max_dv = max_dv.max((va - vb).abs());
        for i in 0..d {
            let diff = (ga[i] - gb[i]).abs();
            max_dg = max_dg.max(diff);
            max_rel_dg = max_rel_dg.max(diff / (1.0 + ga[i].abs()));
        }
    }
    let start = Instant::now();
    let mut sink = 0.0;
    for i in 0..reps {
        sink += a
            .log_density_gradient(&points[i % points.len()], &mut ga)
            .unwrap();
    }
    let a_ns = start.elapsed().as_nanos() as f64 / reps as f64;
    let start = Instant::now();
    for i in 0..reps {
        sink += b
            .log_density_gradient(&points[i % points.len()], &mut gb)
            .unwrap();
    }
    let b_ns = start.elapsed().as_nanos() as f64 / reps as f64;
    std::hint::black_box(sink);
    json!({
        "model": name, "dimension": d, "points": points.len(), "reps": reps,
        "max_abs_value_diff": max_dv, "max_abs_gradient_diff": max_dg,
        "max_rel_gradient_diff": max_rel_dg,
        "hand_ns_per_call": a_ns, "bridgestan_ns_per_call": b_ns,
        "bridgestan_over_hand": b_ns / a_ns
    })
}

fn eight_schools_config(seed: u64, paper: bool) -> RunConfig {
    let tuning = KernelTuning::new(
        0.3,
        NonZeroUsize::new(8).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(8).unwrap(),
        1.,
    )
    .unwrap()
    .with_divergence_threshold(1000.)
    .unwrap();
    let warmup = if paper {
        WarmupConfig::new(0.8)
            .unwrap()
            .with_mass_adaptation(true)
            .with_paper_adaptation(PaperAdaptationConfig::default())
    } else {
        WarmupConfig::new(0.95).unwrap().with_mass_adaptation(true)
    };
    RunConfig::new(1000, NonZeroUsize::new(1000).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(warmup)
}

fn eight_schools_starts() -> Vec<Vec<f64>> {
    [-2., -1., 0., 1.]
        .map(|x| {
            let mut q = vec![0.; 10];
            q[1] = x;
            q
        })
        .to_vec()
}

fn run_sampling<T: Target>(
    label: &str,
    target: &T,
    starts: &[Vec<f64>],
    config: &RunConfig,
    threads: usize,
    functional: &dyn Fn(&[f64]) -> f64,
) -> Value {
    let dim = target.dimension();
    let mass = DiagonalMass::identity(NonZeroUsize::new(dim).unwrap());
    let exact = config
        .worst_case_target_evaluations(NonZeroUsize::new(starts.len()).unwrap())
        .expect("worst-case bound");
    let admission = TargetEvaluationAdmissionLimit::new(NonZeroUsize::new(exact).unwrap());
    let budget = TargetEvaluationBudget::new(NonZeroUsize::new(exact).unwrap());
    preflight_chains_with_target_budget(target, starts, &mass, config, admission, &budget)
        .expect("preflight");
    let start = Instant::now();
    let out = sample_chains_with_target_budget(
        target,
        starts,
        &mass,
        config,
        NonZeroUsize::new(threads).unwrap(),
        admission,
        &budget,
    )
    .expect("sampling");
    let wall = start.elapsed().as_secs_f64();
    let calls: usize = out
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let values: Vec<f64> = out
        .chains()
        .iter()
        .flat_map(|c| (0..c.retained()).map(|d| functional(c.sample(d).unwrap())))
        .collect();
    let ess = ess_batch_means(&values);
    let mean = values.iter().sum::<f64>() / values.len() as f64;
    let divergent = out
        .chains()
        .iter()
        .flat_map(|c| c.diagnostics())
        .filter(|d| d.divergent())
        .count();
    json!({
        "label": label, "wall_seconds": wall, "target_calls": calls,
        "functional_mean": mean, "ess": ess, "ess_per_second": ess / wall,
        "ess_per_call": ess / calls as f64, "divergent_transitions": divergent,
        "final_step": out.chains()[0].metadata().tuning().step_size(),
    })
}

fn main() {
    let out_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("artifacts");
    fs::create_dir_all(&out_dir).unwrap();
    let preload = default_preload();
    let mut rng = SmallRng::seed_from_u64(2026083102);

    // Eight Schools.
    let stan_es = StanTarget::load(
        &models_dir().join("eight_schools_model.so"),
        &preload,
        Some(EIGHT_SCHOOLS_DATA),
        1,
    )
    .expect("load eight schools");
    eprintln!("eight schools info:\n{}", stan_es.info());
    let hand_es = EightSchools {
        calls: AtomicUsize::new(0),
    };
    let es_points: Vec<Vec<f64>> = (0..20)
        .map(|_| {
            let mut q: Vec<f64> = (0..10).map(|_| rng.random_range(-2.0..2.0)).collect();
            q[1] = rng.random_range(-2.0..1.0);
            q
        })
        .collect();
    let es_compare = compare_targets("eight_schools", &hand_es, &stan_es, &es_points, 200_000);
    eprintln!("{es_compare}");

    let mut es_sampling = Vec::new();
    for seed in [82001u64, 82002, 82003] {
        for paper in [false, true] {
            let config = eight_schools_config(seed, paper);
            let mode = if paper { "paper" } else { "v38" };
            let functional = |q: &[f64]| q[1];
            let row = run_sampling(
                &format!("es-{mode}-hand-{seed}"),
                &hand_es,
                &eight_schools_starts(),
                &config,
                1,
                &functional,
            );
            eprintln!("{row}");
            es_sampling.push(row);
            let row = run_sampling(
                &format!("es-{mode}-bridgestan-{seed}"),
                &stan_es,
                &eight_schools_starts(),
                &config,
                1,
                &functional,
            );
            eprintln!("{row}");
            es_sampling.push(row);
        }
    }

    // Local level, T = 100 and 1000.
    let stan_ll_so = models_dir().join("local_level_model.so");
    let mut ll_compare = Vec::new();
    let mut ll_sampling = Vec::new();
    for (t, reps) in [(100usize, 40_000usize), (1000, 4_000)] {
        let data = simulate(t, 2026083101);
        let data_json = json!({
            "T": t, "y": data.y, "r": data.r, "m0": data.m0, "tau0": data.tau0,
            "mu": data.mu, "sigma_x": data.sigma_x
        })
        .to_string();
        let stan_ll =
            StanTarget::load(&stan_ll_so, &preload, Some(&data_json), 1).expect("load local level");
        let hand_ll = LocalLevel::new(data.clone(), Backend::Hand);
        let points: Vec<Vec<f64>> = (0..20)
            .map(|_| (0..t).map(|_| rng.random_range(-2.0..2.0)).collect())
            .collect();
        let cmp = compare_targets(
            &format!("local_level_T{t}"),
            &hand_ll,
            &stan_ll,
            &points,
            reps,
        );
        eprintln!("{cmp}");
        ll_compare.push(cmp);
        let starts: Vec<Vec<f64>> = (0..4)
            .map(|c| data.y.iter().map(|y| y + 0.5 * (c as f64 - 1.5)).collect())
            .collect();
        let tuning = KernelTuning::new(
            0.1,
            NonZeroUsize::new(8).unwrap(),
            NonZeroUsize::new(1).unwrap(),
            NonZeroUsize::new(3).unwrap(),
            1.0,
        )
        .unwrap();
        let config = RunConfig::new(500, NonZeroUsize::new(2000).unwrap(), 84201)
            .with_tuning(tuning)
            .with_warmup(WarmupConfig::new(0.8).unwrap().with_mass_adaptation(true));
        let functional = |q: &[f64]| q[t - 1];
        for threads in [1usize, 4] {
            let row = run_sampling(
                &format!("ll-T{t}-hand-threads{threads}"),
                &hand_ll,
                &starts,
                &config,
                threads,
                &functional,
            );
            eprintln!("{row}");
            ll_sampling.push(row);
            let row = run_sampling(
                &format!("ll-T{t}-bridgestan-threads{threads}"),
                &stan_ll,
                &starts,
                &config,
                threads,
                &functional,
            );
            eprintln!("{row}");
            ll_sampling.push(row);
        }
        eprintln!(
            "T={t}: stan recoverable failures {} of {} calls",
            stan_ll.recoverable_failures(),
            stan_ll.calls()
        );
    }

    let result = json!({
        "algorithm_revision": ALGORITHM_REVISION,
        "bridgestan": "2.9.0 (STAN_THREADS=true, mingw g++ 16.1.0)",
        "eight_schools": {"threading": format!("{:?}", stan_es.threading()), "agreement": es_compare, "sampling": es_sampling},
        "local_level": {"agreement": ll_compare, "sampling": ll_sampling},
    });
    fs::write(
        out_dir.join("bridgestan-benchmark.json"),
        serde_json::to_string_pretty(&result).unwrap(),
    )
    .unwrap();
    println!("{}", serde_json::to_string_pretty(&result).unwrap());
}
