//! Side checks of `STUDIES/freeze_mode_v1`: the candidate kernel rule on the
//! two hand-written targets whose retained draws it could change.
//!
//! Usage: `checks <funnel|eight_centered> <variant> <out.json> [chains] [warmup] [draws]`
//!
//! * `funnel`: Neal's 10-D funnel (`omega ~ N(0, 9)`, `x_i | omega ~ N(0,
//!   e^omega)`), sampler defaults from fixed starts `omega in {-3, -1, 1, 3}`;
//!   reports the tail mass `P(omega < -5)` (exact 0.0478) with a
//!   batch-means standard error, gradients, exhaustions and divergences.
//! * `eight_centered`: the centered Eight Schools (`mu, log tau, theta[8]`),
//!   the one posteriordb-like model whose retained transitions exhaust at
//!   the sampler defaults; reports minimum bulk ESS over coordinates,
//!   gradients, exhaustions and divergences from uniform(-2, 2) starts.
#![forbid(unsafe_code)]

use owalnuts::diagnostics::{ess_bulk, ess_tail, rhat};
use owalnuts::sampler::{Adaptation, Init, Metric, Sampler, Target, Tuning, WarmupConfig};
use owalnuts::walnutpie::{DualAveragingAcceptance, ExhaustionRule, KernelOptions, TargetError};
use serde_json::json;
use std::{env, error::Error, fs, path::Path};

const FUNNEL_DIMENSION: usize = 10;

struct Funnel;

impl Target for Funnel {
    fn dimension(&self) -> usize {
        FUNNEL_DIMENSION
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let omega = q[0];
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = q[1..].iter().map(|x| x * x).sum();
        let tail = (FUNNEL_DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&q[1..]) {
            *g = -inverse_variance * x;
        }
        Ok(-omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares)
    }
}

const LOG_2PI: f64 = 1.837_877_066_409_345_3;
const SCHOOL_Y: [f64; 8] = [28., 8., -3., 7., -1., 1., 18., 12.];
const SCHOOL_SE: [f64; 8] = [15., 10., 16., 11., 9., 11., 10., 18.];

fn normal_log_density(x: f64, mean: f64, sd: f64) -> f64 {
    -0.5 * LOG_2PI - sd.ln() - 0.5 * ((x - mean) / sd).powi(2)
}

/// Centered Eight Schools: `mu ~ N(0, 5)`, `tau ~ half-Cauchy(0, 5)` on
/// `log tau`, `theta_j ~ N(mu, tau)`, `y_j ~ N(theta_j, se_j)`.
struct EightSchoolsCentered;

impl Target for EightSchoolsCentered {
    fn dimension(&self) -> usize {
        10
    }
    fn log_density_gradient(&self, q: &[f64], gradient: &mut [f64]) -> Result<f64, TargetError> {
        let mu = q[0];
        let log_tau = q[1];
        let tau = log_tau.exp();
        if !tau.is_finite() || tau == 0.0 {
            return Err(TargetError::recoverable("tau out of range"));
        }
        let theta = &q[2..];
        let mut value = normal_log_density(mu, 0., 5.)
            + (2. / (std::f64::consts::PI * 5. * (1. + (tau / 5.).powi(2)))).ln()
            + log_tau;
        gradient.fill(0.);
        gradient[0] = -mu / 25.;
        gradient[1] = 1. - 2. * tau * tau / (25. + tau * tau);
        for j in 0..8 {
            let z = (theta[j] - mu) / tau;
            value += normal_log_density(theta[j], mu, tau)
                + normal_log_density(SCHOOL_Y[j], theta[j], SCHOOL_SE[j]);
            let likelihood_gradient = (SCHOOL_Y[j] - theta[j]) / SCHOOL_SE[j].powi(2);
            gradient[j + 2] = -z / tau + likelihood_gradient;
            gradient[0] += z / tau;
            gradient[1] += z * z - 1.0;
        }
        if !value.is_finite() || gradient.iter().any(|g| !g.is_finite()) {
            return Err(TargetError::recoverable("nonfinite log density"));
        }
        Ok(value)
    }
}

struct Variant {
    options: KernelOptions,
    adaptation: Adaptation,
}

fn variant(name: &str) -> Result<Variant, Box<dyn Error>> {
    let mut v = Variant {
        options: KernelOptions::default(),
        adaptation: Adaptation::default(),
    };
    match name {
        "baseline" => {}
        "exhaust-signed" => v.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent,
        "warmup-signed" => {
            v.adaptation = Adaptation::Custom(
                WarmupConfig::new(0.8)?
                    .with_warmup_exhaustion_rule(ExhaustionRule::AcceptUnlessDivergent),
            )
        }
        "exhaust-accept" => v.options.exhaustion = ExhaustionRule::AcceptBelowDivergenceThreshold,
        "exhaust-signed+mean-accept" => {
            v.options.exhaustion = ExhaustionRule::AcceptUnlessDivergent;
            v.adaptation =
                Adaptation::Custom(WarmupConfig::new(0.8)?.with_dual_averaging_acceptance(
                    DualAveragingAcceptance::MeanTrajectoryAcceptance,
                ))
        }
        other => return Err(format!("unknown variant {other:?}").into()),
    }
    Ok(v)
}

fn batch_means_se(values: &[f64], batches: usize) -> f64 {
    let size = values.len() / batches;
    let means: Vec<f64> = (0..batches)
        .map(|b| values[b * size..(b + 1) * size].iter().sum::<f64>() / size as f64)
        .collect();
    let mean = means.iter().sum::<f64>() / batches as f64;
    let var = means.iter().map(|m| (m - mean).powi(2)).sum::<f64>() / (batches - 1) as f64;
    (var / batches as f64).sqrt()
}

fn run<T: Target>(
    target: &T,
    name: &str,
    which: &str,
    init: Init,
    chains: usize,
    warmup: usize,
    draws: usize,
    out: &Path,
) -> Result<(), Box<dyn Error>> {
    let v = variant(name)?;
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(chains)
        .seed(0x0f0f_2026)
        .threads(chains)
        .metric(Metric::diagonal())
        .adaptation(v.adaptation)
        .tuning(Tuning::default().kernel_options(v.options));
    let posterior = sampler.run_with_init(target, &init)?;
    let dimension = target.dimension();
    let gradients: usize = posterior
        .chains()
        .iter()
        .map(|c| c.telemetry().total().target_calls_total())
        .sum();
    let (exhaustions, divergences, depth_caps, warmup_exhaustions): (usize, usize, usize, usize) =
        posterior.chains().iter().fold((0, 0, 0, 0), |acc, c| {
            let r = c.telemetry().retained();
            (
                acc.0 + r.refinement_exhaustion_stops(),
                acc.1 + r.divergences(),
                acc.2 + r.maximum_depth_stops(),
                acc.3 + c.telemetry().discarded().refinement_exhaustion_stops(),
            )
        });
    let mut per_coordinate = Vec::new();
    let mut min_bulk = f64::INFINITY;
    let mut max_rhat: f64 = 0.0;
    for k in 0..dimension {
        let columns: Vec<Vec<f64>> = (0..chains)
            .map(|c| {
                posterior
                    .chain_draws(c)
                    .unwrap()
                    .chunks(dimension)
                    .map(|row| row[k])
                    .collect()
            })
            .collect();
        let refs: Vec<&[f64]> = columns.iter().map(Vec::as_slice).collect();
        let (b, t, r) = (ess_bulk(&refs), ess_tail(&refs), rhat(&refs));
        min_bulk = min_bulk.min(b);
        max_rhat = max_rhat.max(r);
        per_coordinate.push(json!({"bulk_ess": b, "tail_ess": t, "rhat": r}));
    }
    let mut payload = json!({
        "schema": "freeze-mode-v1-check",
        "target": which, "variant": name, "chains": chains, "warmup": warmup, "draws": draws,
        "gradients_total": gradients,
        "retained_exhaustions": exhaustions, "warmup_exhaustions": warmup_exhaustions,
        "retained_divergences": divergences, "retained_depth_caps": depth_caps,
        "min_bulk_ess": min_bulk, "max_rhat": max_rhat,
        "min_bulk_ess_per_gradient": min_bulk / gradients as f64,
        "final_step_sizes": posterior.chains().iter().map(|c| c.metadata().tuning().step_size()).collect::<Vec<_>>(),
        "per_coordinate": per_coordinate,
    });
    if which == "funnel" {
        let omega: Vec<f64> = posterior.draws().map(|d| d[0]).collect();
        let indicator: Vec<f64> = omega.iter().map(|w| f64::from(*w < -5.0)).collect();
        let estimate = indicator.iter().sum::<f64>() / indicator.len() as f64;
        let se = batch_means_se(&indicator, 40);
        let exact = 0.047_790_352_272_814_7;
        payload["tail_mass"] = json!({"estimate": estimate, "batch_means_se": se, "exact": exact,
                                      "z": (estimate - exact) / se});
    }
    if let Some(parent) = out.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(out, serde_json::to_vec_pretty(&payload)?)?;
    eprintln!(
        "{which} {name}: grads {gradients} exhaustions {exhaustions} (warmup {warmup_exhaustions}) div {divergences} min bulk ESS {min_bulk:.1} max rhat {max_rhat:.3} {}",
        payload.get("tail_mass").map_or(String::new(), |t| format!(
            "tail {:.4} +- {:.4} z {:.2}",
            t["estimate"], t["batch_means_se"], t["z"]
        ))
    );
    Ok(())
}

fn main() {
    let args = env::args().skip(1).collect::<Vec<_>>();
    let result: Result<(), Box<dyn Error>> = match args.as_slice() {
        [which, name, out, rest @ ..] => {
            let chains = rest.first().map_or(4, |t| t.parse().unwrap_or(4));
            let warmup = rest.get(1).map_or(2000, |t| t.parse().unwrap_or(2000));
            let draws = rest.get(2).map_or(20000, |t| t.parse().unwrap_or(20000));
            match which.as_str() {
                "funnel" => {
                    let starts = [-3.0, -1.0, 1.0, 3.0]
                        .iter()
                        .take(chains)
                        .map(|omega| {
                            let mut q = vec![0.0; FUNNEL_DIMENSION];
                            q[0] = *omega;
                            q
                        })
                        .collect();
                    run(
                        &Funnel,
                        name,
                        which,
                        Init::Given(starts),
                        chains,
                        warmup,
                        draws,
                        Path::new(out),
                    )
                }
                "eight_centered" => run(
                    &EightSchoolsCentered,
                    name,
                    which,
                    Init::uniform(),
                    chains,
                    warmup,
                    draws,
                    Path::new(out),
                ),
                other => Err(format!("unknown target {other:?}").into()),
            }
        }
        _ => Err(
            "usage: <funnel|eight_centered> <variant> <out.json> [chains] [warmup] [draws]".into(),
        ),
    };
    if let Err(error) = result {
        eprintln!("error: {error}");
        std::process::exit(1);
    }
}
