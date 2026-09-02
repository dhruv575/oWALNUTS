//! Autodiff-vs-hand-written benchmark.
//!
//! Per-call cost (hand gradient, value-only `f64`, tape gradient) on Eight
//! Schools, Neal's funnel and the local-level state space at T=100/1000, then
//! paired sampling runs (same seeds, starts and settings) on Eight Schools
//! and the state space so the end-to-end ESS/s cost is measured and the
//! draws compared bit for bit. Writes `artifacts/bench.json`.
#![forbid(unsafe_code)]

use owalnuts::walnutpie::{
    ALGORITHM_REVISION, DiagonalMass, KernelTuning, MultiChainOutput, RunConfig, Target,
    TargetError, TargetEvaluationAdmissionLimit, TargetEvaluationBudget, WarmupConfig,
    preflight_chains_with_target_budget, sample_chains_with_target_budget,
};
use owalnuts_autodiff::models::{
    EightSchools, EightSchoolsVectorised, Funnel, LocalLevel, LocalLevelData,
    LocalLevelNoncentered, eight_schools_hand_gradient_const,
};
use owalnuts_autodiff::{AutodiffTarget, Model, last_tape_stats};
use rand::{Rng, SeedableRng, rngs::SmallRng};
use serde_json::{Value, json};
use std::{fs, num::NonZeroUsize, path::PathBuf, time::Instant};

/// A hand-written gradient wrapped as a `Target`.
struct Hand<F: Fn(&[f64], &mut [f64]) -> f64 + Send + Sync> {
    dim: usize,
    f: F,
}

impl<F: Fn(&[f64], &mut [f64]) -> f64 + Send + Sync> Target for Hand<F> {
    fn dimension(&self) -> usize {
        self.dim
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        let v = (self.f)(q, g);
        if v.is_finite() && g.iter().all(|x| x.is_finite()) {
            Ok(v)
        } else {
            Err(TargetError::recoverable("nonfinite"))
        }
    }
}

fn time_ns(reps: usize, mut f: impl FnMut(usize) -> f64) -> f64 {
    let mut sink = 0.0;
    let start = Instant::now();
    for i in 0..reps {
        sink += f(i);
    }
    let ns = start.elapsed().as_nanos() as f64 / reps as f64;
    std::hint::black_box(sink);
    ns
}

/// Repeat a timing and keep the minimum (robust to other load on the box).
fn best_of(rounds: usize, reps: usize, mut f: impl FnMut(usize) -> f64) -> f64 {
    (0..rounds)
        .map(|_| time_ns(reps, &mut f))
        .fold(f64::INFINITY, f64::min)
}

fn per_call<M: Model>(
    name: &str,
    model: M,
    hand: &dyn Fn(&[f64], &mut [f64]) -> f64,
    points: &[Vec<f64>],
    reps: usize,
) -> Value {
    let dim = model.dimension();
    let target = AutodiffTarget::new(model);
    let mut gh = vec![0.0; dim];
    let mut ga = vec![0.0; dim];
    let mut max_dv: f64 = 0.0;
    let mut max_rel_dg: f64 = 0.0;
    let mut bit_identical = true;
    let mut offsets: Vec<f64> = Vec::new();
    for p in points {
        let vh = hand(p, &mut gh);
        let va = target.log_density_gradient(p, &mut ga).unwrap();
        bit_identical &= vh.to_bits() == va.to_bits();
        // Value differences are reported after removing any constant offset
        // (an unnormalised density differs from the hand one by a constant).
        max_dv = max_dv.max((vh - va).abs());
        offsets.push(vh - va);
        for i in 0..dim {
            max_rel_dg = max_rel_dg.max((gh[i] - ga[i]).abs() / (1.0 + gh[i].abs()));
        }
    }
    let stats = last_tape_stats();
    let offset_spread = offsets.iter().cloned().fold(f64::NEG_INFINITY, f64::max)
        - offsets.iter().cloned().fold(f64::INFINITY, f64::min);
    let n = points.len();
    let hand_ns = best_of(5, reps, |i| hand(&points[i % n], &mut gh));
    let value_ns = best_of(5, reps, |i| target.value(&points[i % n]));
    let ad_ns = best_of(5, reps, |i| {
        target
            .log_density_gradient(&points[i % n], &mut ga)
            .unwrap()
    });
    let row = json!({
        "model": name, "dimension": dim, "points": n, "reps": reps,
        "values_bit_identical": bit_identical, "max_abs_value_diff": max_dv,
        "value_offset_spread": offset_spread,
        "max_rel_gradient_diff": max_rel_dg,
        "tape_nodes": stats.nodes, "tape_partials": stats.partials, "tape_indices": stats.indices,
        "hand_ns_per_call": hand_ns, "value_only_ns_per_call": value_ns,
        "autodiff_ns_per_call": ad_ns, "autodiff_over_hand": ad_ns / hand_ns,
        "autodiff_over_value_only": ad_ns / value_ns,
    });
    eprintln!(
        "{name:<40} hand {hand_ns:8.1} ns  value {value_ns:8.1} ns  autodiff {ad_ns:8.1} ns  ratio {:.2}x  bit-identical {bit_identical}  tape {} nodes / {} partials / {} indices",
        ad_ns / hand_ns,
        stats.nodes,
        stats.partials,
        stats.indices
    );
    row
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

fn eight_schools_config(seed: u64) -> RunConfig {
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
    RunConfig::new(1000, NonZeroUsize::new(1000).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.95).unwrap().with_mass_adaptation(true))
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

fn local_level_config(seed: u64, warmup: usize, retained: usize) -> RunConfig {
    let tuning = KernelTuning::new(
        0.1,
        NonZeroUsize::new(8).unwrap(),
        NonZeroUsize::new(1).unwrap(),
        NonZeroUsize::new(3).unwrap(),
        1.0,
    )
    .unwrap();
    RunConfig::new(warmup, NonZeroUsize::new(retained).unwrap(), seed)
        .with_tuning(tuning)
        .with_warmup(WarmupConfig::new(0.8).unwrap().with_mass_adaptation(true))
}

fn run_sampling<T: Target>(
    target: &T,
    starts: &[Vec<f64>],
    config: &RunConfig,
    threads: usize,
) -> (MultiChainOutput, f64) {
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
    (out, start.elapsed().as_secs_f64())
}

fn summarise(
    label: &str,
    out: &MultiChainOutput,
    wall: f64,
    functional: &dyn Fn(&[f64]) -> f64,
) -> Value {
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
    })
}

/// Compare every retained draw of two runs.
fn draws_identical(a: &MultiChainOutput, b: &MultiChainOutput) -> (bool, usize, f64) {
    let mut identical = true;
    let mut first_diverging_draw = usize::MAX;
    let mut max_abs = 0.0f64;
    for (ca, cb) in a.chains().iter().zip(b.chains()) {
        for d in 0..ca.retained().min(cb.retained()) {
            let (sa, sb) = (ca.sample(d).unwrap(), cb.sample(d).unwrap());
            if sa != sb {
                identical = false;
                first_diverging_draw = first_diverging_draw.min(d);
                for (x, y) in sa.iter().zip(sb) {
                    max_abs = max_abs.max((x - y).abs());
                }
            }
        }
    }
    (identical, first_diverging_draw, max_abs)
}

fn paired<A: Target, B: Target>(
    name: &str,
    hand: &A,
    autodiff: &B,
    starts: &[Vec<f64>],
    config: &RunConfig,
    threads: usize,
    functional: &dyn Fn(&[f64]) -> f64,
) -> Value {
    let (out_h, wall_h) = run_sampling(hand, starts, config, threads);
    let (out_a, wall_a) = run_sampling(autodiff, starts, config, threads);
    let h = summarise("hand", &out_h, wall_h, functional);
    let a = summarise("autodiff", &out_a, wall_a, functional);
    let (identical, first, max_abs) = draws_identical(&out_h, &out_a);
    eprintln!(
        "{name} seed {} threads {threads}: hand {:.0} ESS/s ({} calls), autodiff {:.0} ESS/s ({} calls), ratio {:.2}x, draws bit-identical: {identical}{}",
        config.seed(),
        h["ess_per_second"].as_f64().unwrap(),
        h["target_calls"],
        a["ess_per_second"].as_f64().unwrap(),
        a["target_calls"],
        h["ess_per_second"].as_f64().unwrap() / a["ess_per_second"].as_f64().unwrap(),
        if identical {
            String::new()
        } else {
            format!(" (first differing retained draw {first}, max |diff| {max_abs:.3e})")
        }
    );
    json!({
        "model": name, "seed": config.seed(), "threads": threads,
        "hand": h, "autodiff": a,
        "hand_over_autodiff_ess_per_second":
            h["ess_per_second"].as_f64().unwrap() / a["ess_per_second"].as_f64().unwrap(),
        "draws_bit_identical": identical,
        "first_differing_retained_draw": if identical { Value::Null } else { json!(first) },
        "max_abs_draw_diff": max_abs,
    })
}

fn main() {
    let out_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("artifacts");
    fs::create_dir_all(&out_dir).unwrap();
    let mut rng = SmallRng::seed_from_u64(2026090101);
    let quick = std::env::args().any(|a| a == "--quick");

    // ---- per-call ----------------------------------------------------------
    eprintln!("== per-call cost (best of 5 rounds) ==");
    let es_points: Vec<Vec<f64>> = (0..16)
        .map(|_| {
            let mut q: Vec<f64> = (0..10).map(|_| rng.random_range(-2.0..2.0)).collect();
            q[1] = rng.random_range(-2.0..1.0);
            q
        })
        .collect();
    let es = EightSchools::default();
    let es_hand = es.clone();
    let mut per_call_rows = vec![
        per_call(
            "eight_schools (vs const-data hand)",
            es.clone(),
            &eight_schools_hand_gradient_const,
            &es_points,
            200_000,
        ),
        per_call(
            "eight_schools (vs struct-data hand)",
            es.clone(),
            &|q, g| es_hand.hand_gradient(q, g),
            &es_points,
            200_000,
        ),
        per_call(
            "eight_schools_vectorised",
            EightSchoolsVectorised(es.clone()),
            &eight_schools_hand_gradient_const,
            &es_points,
            200_000,
        ),
    ];
    let funnel = Funnel { dimension: 10 };
    let funnel_points: Vec<Vec<f64>> = (0..16)
        .map(|_| (0..10).map(|_| rng.random_range(-3.0..3.0)).collect())
        .collect();
    let f_hand = funnel.clone();
    per_call_rows.push(per_call(
        "funnel_10",
        funnel.clone(),
        &|q, g| f_hand.hand_gradient(q, g),
        &funnel_points,
        200_000,
    ));
    for &t in &[100usize, 1000] {
        let data = LocalLevelData::simulate(t, 2026083101);
        let points: Vec<Vec<f64>> = (0..16)
            .map(|_| (0..t).map(|_| rng.random_range(-2.0..2.0)).collect())
            .collect();
        let reps = if t == 100 { 40_000 } else { 4_000 };
        let model = LocalLevel {
            data: data.clone(),
            normalised: true,
        };
        let fast = LocalLevel {
            data: data.clone(),
            normalised: false,
        };
        let m1 = model.clone();
        per_call_rows.push(per_call(
            &format!("local_level_T{t} lupdf (vs WP4 hand)"),
            fast.clone(),
            &|q, g| m1.hand_gradient_wp4(q, g),
            &points,
            reps,
        ));
        let m2 = model.clone();
        per_call_rows.push(per_call(
            &format!("local_level_T{t} lpdf (vs full hand)"),
            model.clone(),
            &|q, g| m2.hand_gradient(q, g),
            &points,
            reps,
        ));
        let nc = LocalLevelNoncentered { data: data.clone() };
        let m3 = nc.clone();
        per_call_rows.push(per_call(
            &format!("local_level_noncentered_T{t}"),
            nc.clone(),
            &|q, g| m3.hand_gradient(q, g),
            &points,
            reps,
        ));
    }

    // ---- paired sampling -----------------------------------------------------
    eprintln!("== paired sampling ==");
    let mut sampling = Vec::new();
    let es_hand_target = Hand {
        dim: 10,
        f: eight_schools_hand_gradient_const,
    };
    let es_ad = AutodiffTarget::new(EightSchools::default());
    let es_vec_ad = AutodiffTarget::new(EightSchoolsVectorised::default());
    let seeds: &[u64] = if quick {
        &[82001]
    } else {
        &[82001, 82002, 82003]
    };
    let log_tau = |q: &[f64]| q[1];
    for &seed in seeds {
        let config = eight_schools_config(seed);
        for threads in [1usize, 4] {
            sampling.push(paired(
                "eight_schools",
                &es_hand_target,
                &es_ad,
                &eight_schools_starts(),
                &config,
                threads,
                &log_tau,
            ));
        }
        sampling.push(paired(
            "eight_schools_vectorised",
            &es_hand_target,
            &es_vec_ad,
            &eight_schools_starts(),
            &config,
            1,
            &log_tau,
        ));
    }
    for &t in &[100usize, 1000] {
        let data = LocalLevelData::simulate(t, 2026083101);
        let model = LocalLevel {
            data: data.clone(),
            normalised: false,
        };
        let hand_model = model.clone();
        let hand = Hand {
            dim: t,
            f: move |q: &[f64], g: &mut [f64]| hand_model.hand_gradient_wp4(q, g),
        };
        let ad = AutodiffTarget::new(model);
        let starts: Vec<Vec<f64>> = (0..4)
            .map(|c| data.y.iter().map(|y| y + 0.5 * (c as f64 - 1.5)).collect())
            .collect();
        let (warmup, retained) = if quick { (200, 500) } else { (500, 2000) };
        let config = local_level_config(84101, warmup, retained);
        let last = move |q: &[f64]| q[t - 1];
        for threads in [1usize, 4] {
            sampling.push(paired(
                &format!("local_level_T{t}"),
                &hand,
                &ad,
                &starts,
                &config,
                threads,
                &last,
            ));
        }
    }

    let result = json!({
        "algorithm_revision": ALGORITHM_REVISION,
        "per_call": per_call_rows,
        "sampling": sampling,
    });
    fs::write(
        out_dir.join("bench.json"),
        serde_json::to_string_pretty(&result).unwrap(),
    )
    .unwrap();
    println!("{}", serde_json::to_string_pretty(&result).unwrap());
}
