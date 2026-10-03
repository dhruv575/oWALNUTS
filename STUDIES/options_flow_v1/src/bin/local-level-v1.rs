//! Normalized local-level Student-t option-log-price application target.
//! The anchor is explicit: anchor=y[0] reproduces the application's data-dependent prior.
#[path = "../bench_eval.rs"]
mod bench_eval;
#[path = "../local_autodiff.rs"]
mod local_autodiff;
use owalnuts::sampler::{
    Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning, WarmupConfig,
};
use owalnuts::walnutpie::KernelOptions;
use serde::Deserialize;
use serde_json::json;
use std::{env, error::Error, fs, time::Instant};
#[derive(Deserialize)]
struct Data {
    y: Vec<f64>,
    anchor: f64,
    nu: f64,
    dt: Vec<f64>,
    anchor_mode: String,
}
impl Data {
    fn validate(&self) -> Result<(), Box<dyn Error>> {
        if self.y.is_empty()
            || !self.anchor.is_finite()
            || !self.nu.is_finite()
            || self.nu != 5.0
            || self.y.iter().any(|v| !v.is_finite())
            || self.dt.len() != self.y.len().saturating_sub(1)
            || self.dt.iter().any(|v| !v.is_finite() || *v <= 0.0)
            || !matches!(
                self.anchor_mode.as_str(),
                "exogenous" | "empirical_bayes_first_observation"
            )
            || (self.anchor_mode == "empirical_bayes_first_observation" && self.anchor != self.y[0])
        {
            return Err(
                "finite nonempty y, anchor, nu=5, positive dt, and valid anchor_mode required"
                    .into(),
            );
        }
        Ok(())
    }
}
struct Model {
    data: Data,
    nc: bool,
}
fn normal(v: f64, m: f64, s: f64) -> (f64, f64) {
    let z = (v - m) / s;
    (
        -0.5 * z * z - s.ln() - 0.5 * (2.0 * std::f64::consts::PI).ln(),
        -z / s,
    )
}
impl Model {
    fn canonical(&self, q: &[f64]) -> Vec<f64> {
        let mut c = q.to_vec();
        if self.nc {
            let n = self.data.y.len();
            c[0] = self.data.anchor + 1.5 * q[0];
            let s = q[n + 1].exp();
            for t in 1..n {
                c[t] = c[t - 1] + s * self.data.dt[t - 1].sqrt() * q[t];
            }
        }
        c
    }
    fn sampling_coordinates(&self, c: &[f64]) -> Vec<f64> {
        let mut q = c.to_vec();
        if self.nc {
            let n = self.data.y.len();
            q[0] = (c[0] - self.data.anchor) / 1.5;
            for t in 1..n {
                q[t] = (c[t] - c[t - 1]) / (c[n + 1].exp() * self.data.dt[t - 1].sqrt());
            }
        }
        q
    }
    fn centered(&self, q: &[f64], g: &mut [f64]) -> f64 {
        g.fill(0.0);
        let n = self.data.y.len();
        let obs = q[n].exp();
        let rw = q[n + 1].exp();
        let (mut lp, d) = normal(q[0], self.data.anchor, 1.5);
        g[0] += d;
        for t in 1..n {
            let (v, d) = normal(q[t], q[t - 1], rw * self.data.dt[t - 1].sqrt());
            lp += v;
            g[t] += d;
            g[t - 1] -= d;
            g[n + 1] += (q[t] - q[t - 1]).powi(2) / (rw * rw * self.data.dt[t - 1]) - 1.0;
        }
        let nu = self.data.nu;
        let norm = statrs::function::gamma::ln_gamma((nu + 1.0) / 2.0)
            - statrs::function::gamma::ln_gamma(nu / 2.0)
            - 0.5 * (nu * std::f64::consts::PI).ln();
        for t in 0..n {
            let r = self.data.y[t] - q[t];
            let den = nu * obs * obs + r * r;
            lp += norm - q[n] - 0.5 * (nu + 1.0) * (r * r / (nu * obs * obs)).ln_1p();
            g[t] += (nu + 1.0) * r / den;
            g[n] += -1.0 + (nu + 1.0) * r * r / den;
        }
        for (j, m) in [(n, 0.08f64.ln()), (n + 1, 0.12f64.ln())] {
            let (v, d) = normal(q[j], m, 1.0);
            lp += v;
            g[j] += d;
        }
        lp
    }
}
impl Target for Model {
    fn dimension(&self) -> usize {
        self.data.y.len() + 2
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        if q.len() != self.dimension() || g.len() != q.len() {
            return Err(TargetError::new("dimension mismatch"));
        }
        let c = self.canonical(q);
        let mut lp = self.centered(&c, g);
        let n = self.data.y.len();
        if self.nc {
            let path = g[..n].to_vec();
            g[n + 1] += path
                .iter()
                .enumerate()
                .map(|(t, d)| d * (c[t] - c[0]))
                .sum::<f64>()
                + (n - 1) as f64;
            let mut adj = 0.0;
            for t in (0..n).rev() {
                adj += path[t];
                g[t] = adj
                    * if t == 0 {
                        1.5
                    } else {
                        q[n + 1].exp() * self.data.dt[t - 1].sqrt()
                    };
            }
            lp += 1.5f64.ln()
                + (n - 1) as f64 * q[n + 1]
                + 0.5 * self.data.dt.iter().map(|v| v.ln()).sum::<f64>();
        }
        if !lp.is_finite() || g.iter().any(|v| !v.is_finite()) {
            return Err(TargetError::recoverable("nonfinite target"));
        }
        Ok(lp)
    }
}
fn main() -> Result<(), Box<dyn Error>> {
    let a: Vec<String> = env::args().skip(1).collect();
    if a.first().map(String::as_str) == Some("--bench-eval") {
        if a.len() < 5 {
            return Err(
                "usage: --bench-eval data.json arm iterations out.json [canonical_positions.json]"
                    .into(),
            );
        }
        let data: Data = serde_json::from_slice(&fs::read(&a[1])?)?;
        data.validate()?;
        let arm = &a[2];
        if !matches!(
            arm.as_str(),
            "diagonal"
                | "dense"
                | "noncentered"
                | "application-settings"
                | "autodiff"
                | "autodiff-dense"
                | "autodiff-noncentered"
        ) {
            return Err("unknown benchmark arm".into());
        }
        let model = Model {
            data,
            nc: arm.ends_with("noncentered"),
        };
        let canonical: Vec<Vec<f64>> = if let Some(path) = a.get(5) {
            serde_json::from_slice(&fs::read(path)?)?
        } else {
            let mut q = model.data.y.clone();
            q.extend([0.08f64.ln(), 0.12f64.ln()]);
            vec![q]
        };
        if canonical.iter().any(|q| q.len() != model.dimension()) {
            return Err("canonical position dimension mismatch".into());
        }
        let positions: Vec<_> = canonical
            .iter()
            .map(|q| model.sampling_coordinates(q))
            .collect();
        let iterations = a[3].parse()?;
        let mut result = if arm.starts_with("autodiff") {
            bench_eval::benchmark(
                &local_autodiff::target(&model),
                &positions,
                iterations,
                true,
            )?
        } else {
            bench_eval::benchmark(&model, &positions, iterations, false)?
        };
        result["arm"] = json!(arm);
        result["model"] = json!("local_level");
        result["position_source"] = json!(
            a.get(5)
                .map(String::as_str)
                .unwrap_or("observed_path_sampler_initialization")
        );
        fs::write(&a[4], serde_json::to_vec_pretty(&result)?)?;
        return Ok(());
    }
    if a.first().map(String::as_str) == Some("--eval") {
        let data: Data = serde_json::from_slice(&fs::read(a.get(1).ok_or("missing data")?)?)?;
        data.validate()?;
        let model = Model {
            data,
            nc: a.get(3).is_some_and(|s| s.ends_with("noncentered")),
        };
        let q: Vec<f64> = serde_json::from_slice(&fs::read(a.get(2).ok_or("missing q")?)?)?;
        let mut g = vec![0.0; model.dimension()];
        let lp = if a.get(3).is_some_and(|s| s.starts_with("autodiff")) {
            local_autodiff::target(&model).log_density_gradient(&q, &mut g)?
        } else {
            model.log_density_gradient(&q, &mut g)?
        };
        println!("{}", json!({"logp":lp,"gradient":g}));
        return Ok(());
    }
    if a.len() < 2 {
        return Err("usage: data out [diagonal|dense|noncentered|application-settings] [seed] [warmup] [draws] [chains]".into());
    }
    let arm = a.get(2).map(String::as_str).unwrap_or("diagonal");
    let metric = match arm {
        "diagonal"
        | "noncentered"
        | "application-settings"
        | "autodiff"
        | "autodiff-noncentered" => Metric::diagonal(),
        "dense" | "autodiff-dense" => Metric::dense(),
        _ => return Err("unknown arm".into()),
    };
    let seed = a
        .get(3)
        .map(|v| v.parse())
        .transpose()?
        .unwrap_or(20261003u64);
    let warmup = a
        .get(4)
        .map(|v| v.parse())
        .transpose()?
        .unwrap_or(1000usize);
    let draws = a
        .get(5)
        .map(|v| v.parse())
        .transpose()?
        .unwrap_or(1000usize);
    let chains = a.get(6).map(|v| v.parse()).transpose()?.unwrap_or(4usize);
    let data: Data = serde_json::from_slice(&fs::read(&a[0])?)?;
    data.validate()?;
    let model = Model {
        data,
        nc: arm.ends_with("noncentered"),
    };
    let n = model.data.y.len();
    let canonical_starts: Vec<Vec<f64>> = (0..chains)
        .map(|chain| {
            let offset = (chain as f64 - (chains as f64 - 1.0) / 2.0) * 0.02;
            let mut q: Vec<_> = model.data.y.iter().map(|v| v + offset).collect();
            q.extend([0.08f64.ln() + offset, 0.12f64.ln() - offset]);
            q
        })
        .collect();
    let starts: Vec<_> = canonical_starts
        .iter()
        .map(|q| model.sampling_coordinates(q))
        .collect();
    let mut sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(chains)
        .threads(1)
        .seed(seed)
        .metric(metric)
        .limits(Limits::new().admit_worst_case());
    if arm == "application-settings" {
        sampler = sampler
            .tuning(
                Tuning::new()
                    .step_size(0.01)
                    .max_depth(6)
                    .min_micro_steps(1)
                    .max_refinement_levels(2)
                    .max_error(1.0)
                    .kernel_options(KernelOptions::default()),
            )
            .adaptation(Adaptation::Custom(WarmupConfig::default()));
    }
    let started = Instant::now();
    let p = if arm.starts_with("autodiff") {
        sampler.run(&local_autodiff::target(&model), &starts)?
    } else {
        sampler.run(&model, &starts)?
    };
    let wall_seconds = started.elapsed().as_secs_f64();
    let output:Vec<_>=p.chains().iter().map(|c|{let t=c.telemetry();let r=t.retained();json!({"draws":(0..draws).map(|i|model.canonical(c.sample(i).unwrap())).collect::<Vec<_>>(),"warmup_calls":t.discarded().target_calls_total(),"retained_calls":r.target_calls_total(),"retained_divergences":r.divergences(),"retained_rc_stops":r.reverse_coarser_stops(),"depths":c.diagnostics().iter().map(|d|d.depth()).collect::<Vec<_>>(),"final_step":c.metadata().tuning().step_size()})}).collect();
    fs::write(
        &a[1],
        serde_json::to_vec(
            &json!({"schema_version":1,"model":"local_level_t","sampler":"owalnuts","threads":1,"arm":arm,"seed":seed,"warmup":warmup,"draws":draws,"wall_seconds":wall_seconds,"coordinates":"centered","initial_positions":canonical_starts,"application_settings_current_kernel":arm=="application-settings","dimension":n+2,"chains":output}),
        )?,
    )?;
    Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    fn model(nc: bool) -> Model {
        Model {
            data: Data {
                y: vec![0.2, 0.5, -0.1, 0.3, 0.1],
                anchor: 0.2,
                nu: 5.0,
                dt: vec![0.5, 2.0, 3.0, 1.0 / 3.0],
                anchor_mode: "exogenous".into(),
            },
            nc,
        }
    }
    #[test]
    fn finite_differences() {
        for nc in [false, true] {
            let m = model(nc);
            for off in [-0.5, 0.0, 0.5] {
                let mut q = vec![0.1 + off; m.dimension()];
                q[5] = -2.0;
                q[6] = -1.5;
                let mut g = vec![0.0; q.len()];
                m.log_density_gradient(&q, &mut g).unwrap();
                for j in 0..q.len() {
                    let mut tmp = vec![0.0; q.len()];
                    q[j] += 1e-5;
                    let p = m.log_density_gradient(&q, &mut tmp).unwrap();
                    q[j] -= 2e-5;
                    let n = m.log_density_gradient(&q, &mut tmp).unwrap();
                    q[j] += 1e-5;
                    let d = (p - n) / 2e-5;
                    assert!(
                        (d - g[j]).abs() < 1e-5 * (1.0 + d.abs()),
                        "nc={nc} j={j}: {d} vs {}",
                        g[j]
                    );
                }
            }
        }
    }
    #[test]
    fn transform_roundtrip_and_jacobian() {
        let m = model(true);
        let q = vec![0.3; m.dimension()];
        let c = m.canonical(&q);
        let r = m.sampling_coordinates(&c);
        for (a, b) in q.iter().zip(r) {
            assert!((a - b).abs() < 1e-10);
        }
        let mut g = vec![0.0; q.len()];
        let a = m.log_density_gradient(&q, &mut g).unwrap();
        let b = model(false).log_density_gradient(&c, &mut g).unwrap();
        assert!((a - b - 1.5f64.ln() - 4.0 * q[6]).abs() < 1e-10);
    }
}
