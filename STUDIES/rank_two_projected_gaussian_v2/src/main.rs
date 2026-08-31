use std::fs;
use std::num::NonZeroUsize;
use std::sync::atomic::{AtomicUsize, Ordering};

use owalnuts::walnutpie::{
    DEFAULT_MAX_ERROR, DEFAULT_MAX_REFINEMENT_LEVELS, DEFAULT_MIN_MICRO_STEPS, DEFAULT_STEP_SIZE,
    DirectOriginalQMass, InitialStepSearchConfig, KernelTuning, LowRankArrowheadMass,
    ProjectedArrowheadWarmup, ProjectedMetricOutcome, RunConfig, RunControl, StopReason,
    StructuredCovarianceBlock, Target, TargetError, WarmupConfig, WarmupWindowConfig,
    preflight_chains_projected_arrowhead, preflight_direct_original_q,
    sample_chains_projected_arrowhead, sample_direct_original_q,
};

struct Gaussian {
    precision: Vec<f64>,
    calls: AtomicUsize,
}
impl Target for Gaussian {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        for i in 0..10 {
            g[i] = -(0..10)
                .map(|j| self.precision[i * 10 + j] * q[j])
                .sum::<f64>();
        }
        Ok(0.5 * q.iter().zip(g.iter()).map(|(q, g)| q * g).sum::<f64>())
    }
}

fn inverse(mut a: Vec<f64>) -> Vec<f64> {
    let mut out = vec![0.0; 100];
    for i in 0..10 {
        out[i * 10 + i] = 1.0;
    }
    for i in 0..10 {
        let p = (i..10)
            .max_by(|&x, &y| a[x * 10 + i].abs().total_cmp(&a[y * 10 + i].abs()))
            .unwrap();
        for j in 0..10 {
            a.swap(i * 10 + j, p * 10 + j);
            out.swap(i * 10 + j, p * 10 + j);
        }
        let s = a[i * 10 + i];
        for j in 0..10 {
            a[i * 10 + j] /= s;
            out[i * 10 + j] /= s;
        }
        for k in 0..10 {
            if k == i {
                continue;
            }
            let f = a[k * 10 + i];
            for j in 0..10 {
                a[k * 10 + j] -= f * a[i * 10 + j];
                out[k * 10 + j] -= f * out[i * 10 + j];
            }
        }
    }
    out
}

fn metrics(samples: &[f64], covariance: &[f64]) -> (f64, f64) {
    let n = samples.len() / 10;
    let esjd = (1..n)
        .flat_map(|t| {
            (0..10).map(move |j| {
                let d = samples[t * 10 + j] - samples[(t - 1) * 10 + j];
                d * d / covariance[j * 10 + j]
            })
        })
        .sum::<f64>()
        / (n - 1) as f64;
    let ineff = (0..10)
        .map(|j| {
            let m = (0..n).map(|t| samples[t * 10 + j]).sum::<f64>() / n as f64;
            let den = (0..n)
                .map(|t| (samples[t * 10 + j] - m).powi(2))
                .sum::<f64>();
            let num = (1..n)
                .map(|t| (samples[t * 10 + j] - m) * (samples[(t - 1) * 10 + j] - m))
                .sum::<f64>();
            let r = (num / den).clamp(-0.99, 0.99);
            (1.0 + r) / (1.0 - r)
        })
        .sum::<f64>()
        / 10.0;
    (esjd, ineff)
}

fn main() {
    let mut covariance = vec![0.0; 100];
    for i in 0..10 {
        covariance[i * 10 + i] = 1.0;
    }
    covariance[0] = 9.0;
    covariance[11] = 4.0;
    covariance[66] = 5.0;
    covariance[77] = 3.0;
    for (i, j, v) in [(0, 6, 4.8), (1, 7, -2.4), (2, 6, 0.8), (3, 7, 0.6)] {
        covariance[i * 10 + j] = v;
        covariance[j * 10 + i] = v;
    }
    let target = Gaussian {
        precision: inverse(covariance.clone()),
        calls: AtomicUsize::new(0),
    };
    let basis = vec![
        vec![1.0, 0.0],
        vec![0.0, 1.0],
        vec![0.0, 0.0],
        vec![0.0, 0.0],
    ];
    let mass = LowRankArrowheadMass::new(
        (0..6)
            .map(|i| (0..6).map(|j| f64::from(i == j)).collect())
            .collect(),
        StructuredCovarianceBlock::ScaledAr1 {
            scale: vec![1.0; 4],
            rho: 0.0,
        },
        basis.clone(),
        vec![vec![0.0; 2]; 6],
    )
    .unwrap();
    let projected =
        ProjectedArrowheadWarmup::new(basis, NonZeroUsize::new(30).unwrap(), 0.08, 1e-6, 1e8)
            .unwrap();
    let windows = WarmupWindowConfig::new(30, NonZeroUsize::new(50).unwrap(), 30).unwrap();
    let seeds = [79001_u64, 79002, 79003, 79004];
    let depth4 = KernelTuning::new(
        DEFAULT_STEP_SIZE,
        NonZeroUsize::new(5).unwrap(),
        NonZeroUsize::new(DEFAULT_MIN_MICRO_STEPS).unwrap(),
        NonZeroUsize::new(DEFAULT_MAX_REFINEMENT_LEVELS).unwrap(),
        DEFAULT_MAX_ERROR,
    )
    .unwrap();
    let pooled = RunConfig::new(180, NonZeroUsize::new(300).unwrap(), seeds[0])
        .with_warmup(
            WarmupConfig::new(0.8)
                .unwrap()
                .with_windows(windows.clone())
                .with_initial_step_search(InitialStepSearchConfig::default()),
        )
        .with_tuning(depth4);
    let starts = vec![vec![0.0; 10]; 4];
    let preflight =
        preflight_chains_projected_arrowhead(&target, &starts, &mass, &projected, &pooled).unwrap();
    assert_eq!(preflight.dimension(), 10);
    assert_eq!(target.calls.load(Ordering::Relaxed), 0);
    let adaptive = sample_chains_projected_arrowhead(
        &target,
        &starts,
        &mass,
        &projected,
        &pooled,
        NonZeroUsize::new(4).unwrap(),
        &RunControl::new(),
    )
    .unwrap();
    let mut log_esjd = 0.0;
    let mut log_ineff = 0.0;
    let mut all_healthy = true;
    let mut moments_ok = true;
    let mut truncation_ok = true;
    let mut adaptive_calls = 0usize;
    let mut baseline_calls = 0usize;
    let mut adaptive_leaves = 0usize;
    let mut baseline_leaves = 0usize;
    let mut adaptive_divergences = 0usize;
    let mut baseline_divergences = 0usize;
    let mut divergence_traces = Vec::new();
    let mut retained_health = true;
    let mut warmup_health = true;
    println!("{{\"rows\":[");
    for (chain, seed) in seeds.into_iter().enumerate() {
        let baseline_config = RunConfig::new(180, NonZeroUsize::new(300).unwrap(), seed)
            .with_tuning(depth4)
            .with_warmup(
                WarmupConfig::new(0.8)
                    .unwrap()
                    .with_mass_adaptation(false)
                    .with_windows(windows.clone()),
            );
        let calls_before = target.calls.load(Ordering::Relaxed);
        preflight_direct_original_q(
            &target,
            &[vec![0.0; 10]],
            &DirectOriginalQMass::LowRankArrowhead(mass.clone()),
            &baseline_config,
        )
        .unwrap();
        assert_eq!(target.calls.load(Ordering::Relaxed), calls_before);
        let baseline = sample_direct_original_q(
            &target,
            &[0.0; 10],
            &DirectOriginalQMass::LowRankArrowhead(mass.clone()),
            &baseline_config,
        )
        .unwrap();
        let a = &adaptive.chains().chains()[chain];
        let (ae, ai) = metrics(a.samples(), &covariance);
        let (be, bi) = metrics(baseline.samples(), &covariance);
        let a_depth = a
            .diagnostics()
            .iter()
            .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
            .count();
        let b_depth = baseline
            .diagnostics()
            .iter()
            .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
            .count();
        let healthy = a
            .diagnostics()
            .iter()
            .chain(baseline.diagnostics())
            .all(|d| !d.divergent());
        for diagnostics in [a.diagnostics(), baseline.diagnostics()] {
            let warmup_failures = diagnostics[..180]
                .iter()
                .filter(|d| d.divergent() || matches!(d.stop(), StopReason::RefinementExhausted))
                .count();
            warmup_health &= warmup_failures <= 1
                && diagnostics[75..180].iter().all(|d| {
                    !d.divergent() && !matches!(d.stop(), StopReason::RefinementExhausted)
                });
            retained_health &= diagnostics[180..].iter().all(|d| {
                !d.divergent()
                    && !matches!(
                        d.stop(),
                        StopReason::InvalidEvaluation | StopReason::RefinementExhausted
                    )
            });
            let retained_depth = diagnostics[180..]
                .iter()
                .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
                .count();
            retained_health &= retained_depth * 100 <= diagnostics[180..].len();
        }
        for (owner, diagnostics) in [
            ("adaptive", a.diagnostics()),
            ("baseline", baseline.diagnostics()),
        ] {
            for (transition, diagnostic) in diagnostics.iter().enumerate() {
                if !diagnostic.divergent() {
                    continue;
                }
                if owner == "adaptive" {
                    adaptive_divergences += 1;
                } else {
                    baseline_divergences += 1;
                }
                let step =
                    diagnostic.trajectory_macro_length() / diagnostic.leaves_built().max(1) as f64;
                let window = match transition {
                    75..=99 => 0,
                    100..=149 => 1,
                    _ => -1,
                };
                divergence_traces.push(format!(
                    "{{\"owner\":\"{owner}\",\"seed\":{seed},\"chain\":{chain},\"transition\":{transition},\"phase\":\"{}\",\"initial_h\":{},\"minimum_h\":{},\"maximum_h\":{},\"maximum_delta_h\":{},\"step\":{step},\"window\":{window},\"refinement_level\":{},\"refinement_attempts\":{},\"depth\":{},\"trajectory_length\":{},\"stop\":\"{:?}\",\"target_calls\":{}}}",
                    if transition < 180 { "warmup" } else { "retained" },
                    diagnostic.initial_hamiltonian(),
                    diagnostic.minimum_hamiltonian(),
                    diagnostic.maximum_hamiltonian(),
                    diagnostic.maximum_absolute_energy_error(),
                    diagnostic.selected_refinement_level().map_or(-1, |x| x as i32),
                    diagnostic.refinement_attempts(),
                    diagnostic.depth(),
                    diagnostic.trajectory_macro_length(),
                    diagnostic.stop(),
                    diagnostic.target_evaluations(),
                ));
            }
        }
        truncation_ok &= a_depth * 100 <= a.diagnostics().len();
        for j in 0..10 {
            let values = a
                .samples()
                .chunks_exact(10)
                .map(|draw| draw[j])
                .collect::<Vec<_>>();
            let mean = values.iter().sum::<f64>() / values.len() as f64;
            let variance =
                values.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / (values.len() - 1) as f64;
            moments_ok &= mean.abs() <= 0.75
                && variance >= 0.35 * covariance[j * 10 + j]
                && variance <= 1.65 * covariance[j * 10 + j];
        }
        adaptive_calls += a.telemetry().total().target_calls_total();
        baseline_calls += baseline.telemetry().total().target_calls_total();
        adaptive_leaves += a.telemetry().total().leaves_built();
        baseline_leaves += baseline.telemetry().total().leaves_built();
        let supported = a
            .diagnostics()
            .iter()
            .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
            .filter(|d| {
                !d.divergent()
                    && d.maximum_absolute_energy_error().is_finite()
                    && d.maximum_absolute_energy_error() <= 0.1
                    && d.final_uturn_margin().is_some_and(|margin| margin > 0.0)
            })
            .count();
        let capped = a
            .diagnostics()
            .iter()
            .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
            .collect::<Vec<_>>();
        let nonturning = capped
            .iter()
            .filter(|d| d.final_uturn_margin().is_some_and(|margin| margin >= 0.0))
            .count();
        let finite_nondivergent = capped
            .iter()
            .filter(|d| {
                !d.divergent()
                    && d.maximum_absolute_energy_error().is_finite()
                    && d.initial_hamiltonian().is_finite()
                    && d.minimum_hamiltonian().is_finite()
                    && d.maximum_hamiltonian().is_finite()
            })
            .count();
        all_healthy &= healthy;
        log_esjd += (ae / be).ln();
        log_ineff += (bi / ai).ln();
        println!(
            "{}{{\"chain\":{chain},\"seed\":{seed},\"healthy\":{healthy},\"adaptive_max_depth\":{a_depth},\"baseline_max_depth\":{b_depth},\"nonturning_capped\":{nonturning},\"finite_nondivergent_capped\":{finite_nondivergent},\"energy_tight_capped\":{supported},\"final_step\":{},\"adaptive_esjd\":{ae},\"baseline_esjd\":{be},\"adaptive_ineff\":{ai},\"baseline_ineff\":{bi}}}",
            if chain == 0 { "" } else { "," },
            adaptive.final_steps()[chain]
        );
    }
    let er = (log_esjd / 4.0).exp();
    let ir = (log_ineff / 4.0).exp();
    let installed = adaptive
        .metric_updates()
        .iter()
        .all(|u| u.outcome() == ProjectedMetricOutcome::Installed);
    let aggregate_depth = adaptive
        .chains()
        .chains()
        .iter()
        .flat_map(|chain| chain.diagnostics())
        .filter(|d| matches!(d.stop(), StopReason::MaximumDepth))
        .count();
    truncation_ok &= aggregate_depth * 100
        <= adaptive
            .chains()
            .chains()
            .iter()
            .map(|c| c.diagnostics().len())
            .sum::<usize>();
    let passed = retained_health
        && warmup_health
        && moments_ok
        && truncation_ok
        && installed
        && er >= 1.05
        && ir >= 1.05;
    println!(
        "],\"passed\":{passed},\"all_phase_healthy\":{all_healthy},\"retained_health\":{retained_health},\"warmup_health\":{warmup_health},\"adaptive_divergences\":{adaptive_divergences},\"baseline_divergences\":{baseline_divergences},\"moments_ok\":{moments_ok},\"truncation_ok\":{truncation_ok},\"aggregate_max_depth\":{aggregate_depth},\"adaptive_calls\":{adaptive_calls},\"baseline_calls\":{baseline_calls},\"adaptive_leaves\":{adaptive_leaves},\"baseline_leaves\":{baseline_leaves},\"installed\":{installed},\"esjd_ratio\":{er},\"inefficiency_improvement\":{ir}}}"
    );
    fs::write(
        "STUDIES/rank_two_projected_gaussian_v2/artifacts/depth5-trace-replay.json",
        format!(
            "{{\"seeds\":[79001,79002,79003,79004],\"adaptive_divergences\":{adaptive_divergences},\"baseline_divergences\":{baseline_divergences},\"traces\":[{}]}}",
            divergence_traces.join(",")
        ),
    )
    .unwrap();
    if !passed {
        std::process::exit(2);
    }
}
