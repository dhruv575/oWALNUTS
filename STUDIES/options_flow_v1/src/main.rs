//! Exact normalized hierarchical Student-t stochastic-volatility target.
mod bench_eval;
mod flow_autodiff;
mod flow_geometry;
use owalnuts::sampler::{Limits, Metric, Sampler, Target, TargetError};
use serde::Deserialize;
use serde_json::json;
use std::{env, error::Error, fs, time::Instant};

#[derive(Deserialize)]
struct Data {
    y: Vec<Vec<f64>>,
    x: Vec<Vec<f64>>,
    nu: f64,
    rho: f64,
    #[serde(default)]
    initial_positions: Option<Vec<Vec<f64>>>,
}
impl Data {
    fn validate(&self) -> Result<(), Box<dyn Error>> {
        let g = self.y.first().map_or(0, Vec::len);
        if g == 0
            || self.y.len() != self.x.len()
            || self
                .y
                .iter()
                .chain(&self.x)
                .any(|r| r.len() != g || r.iter().any(|v| !v.is_finite()))
            || !self.nu.is_finite()
            || self.nu <= 2.0
            || !self.rho.is_finite()
            || self.rho.abs() >= 1.0
        {
            return Err("invalid rectangular finite data, nu>2 and |rho|<1 required".into());
        }
        if self.initial_positions.as_ref().is_some_and(|starts| {
            starts.is_empty()
                || starts.iter().any(|q| {
                    q.len() != 4 + 2 * g + self.y.len() || q.iter().any(|v| !v.is_finite())
                })
        }) {
            return Err(
                "initial_positions must be a nonempty finite canonical chain-by-dimension matrix"
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
    fn initial_positions(&self, chains: usize) -> Result<Vec<Vec<f64>>, TargetError> {
        if chains == 0 {
            return Err(TargetError::new("positive chain count required"));
        }
        if let Some(starts) = &self.data.initial_positions {
            if starts.len() != chains {
                return Err(TargetError::new(
                    "initial_positions row count must match chains",
                ));
            }
            return Ok(starts.clone());
        }
        let k = 4 + 2 * self.data.y[0].len();
        let mut q = vec![0.0; self.dimension()];
        q[1] = -1.0;
        q[2] = -1.0;
        q[3] = -1.5;
        q[k..].fill(-1.0);
        Ok(vec![q; chains])
    }
    fn sampling_coordinates(&self, c: &[f64]) -> Vec<f64> {
        let mut q = c.to_vec();
        if self.nc {
            let k = 4 + 2 * self.data.y[0].len();
            let rho = self.data.rho;
            let sigma = c[3].exp();
            q[k] = (c[k] - c[2]) * (1.0 - rho * rho).sqrt() / sigma;
            for t in 1..self.data.y.len() {
                q[k + t] = (c[k + t] - c[2] - rho * (c[k + t - 1] - c[2])) / sigma;
            }
        }
        q
    }
    fn canonical(&self, q: &[f64]) -> Vec<f64> {
        let mut c = q.to_vec();
        if self.nc {
            let k = 4 + 2 * self.data.y[0].len();
            let s = q[3].exp();
            let rho = self.data.rho;
            c[k] = q[2] + s * q[k] / (1.0 - rho * rho).sqrt();
            for t in 1..self.data.y.len() {
                c[k + t] = q[2] + rho * (c[k + t - 1] - q[2]) + s * q[k + t];
            }
        }
        c
    }
    fn centered(&self, q: &[f64], grad: &mut [f64]) -> f64 {
        grad.fill(0.0);
        let g = self.data.y[0].len();
        let n = self.data.y.len();
        let k = 4 + 2 * g;
        let mut lp = 0.0;
        for (i, (m, s)) in [(0.0, 0.5), (-1.0, 0.5), (-1.0, 1.0), (-1.5, 0.5)]
            .iter()
            .enumerate()
        {
            let (v, d) = normal(q[i], *m, *s);
            lp += v;
            grad[i] += d;
        }
        for i in 4..k {
            let (v, d) = normal(q[i], 0.0, 1.0);
            lp += v;
            grad[i] += d;
        }
        let rho = self.data.rho;
        let sigma = q[3].exp();
        let tau = q[1].exp();
        for t in 0..n {
            let m = if t == 0 {
                q[2]
            } else {
                q[2] + rho * (q[k + t - 1] - q[2])
            };
            let s = if t == 0 {
                sigma / (1.0 - rho * rho).sqrt()
            } else {
                sigma
            };
            let (v, d) = normal(q[k + t], m, s);
            lp += v;
            grad[k + t] += d;
            grad[2] -= d * if t == 0 { 1.0 } else { 1.0 - rho };
            if t > 0 {
                grad[k + t - 1] -= rho * d;
            }
            grad[3] += (q[k + t] - m).powi(2) / (s * s) - 1.0;
        }
        let nu = self.data.nu;
        let norm = statrs::function::gamma::ln_gamma((nu + 1.0) / 2.0)
            - statrs::function::gamma::ln_gamma(nu / 2.0)
            - 0.5 * (nu * std::f64::consts::PI).ln();
        for t in 0..n {
            for j in 0..g {
                let x = self.data.x[t][j];
                let r = self.data.y[t][j] - (0.3 * q[4 + j] + (q[0] + tau * q[4 + g + j]) * x);
                let inv_var = (-q[k + t]).exp();
                let u = r * r * inv_var / nu;
                lp += norm - 0.5 * q[k + t] - 0.5 * (nu + 1.0) * u.ln_1p();
                let dm = (nu + 1.0) * r * inv_var / (nu * (1.0 + u));
                grad[4 + j] += 0.3 * dm;
                grad[0] += x * dm;
                grad[1] += tau * q[4 + g + j] * x * dm;
                grad[4 + g + j] += tau * x * dm;
                grad[k + t] += -0.5 + 0.5 * (nu + 1.0) * u / (1.0 + u);
            }
        }
        lp
    }
}
impl Target for Model {
    fn dimension(&self) -> usize {
        4 + 2 * self.data.y[0].len() + self.data.y.len()
    }
    fn log_density_gradient(&self, q: &[f64], grad: &mut [f64]) -> Result<f64, TargetError> {
        if q.len() != self.dimension() || grad.len() != q.len() {
            return Err(TargetError::new("dimension mismatch"));
        }
        let c = self.canonical(q);
        let mut lp = self.centered(&c, grad);
        if self.nc {
            let k = 4 + 2 * self.data.y[0].len();
            let n = self.data.y.len();
            let s = q[3].exp();
            let rho = self.data.rho;
            let path_grad = grad[k..].to_vec();
            grad[2] += path_grad.iter().sum::<f64>();
            grad[3] += path_grad
                .iter()
                .enumerate()
                .map(|(t, d)| d * (c[k + t] - q[2]))
                .sum::<f64>()
                + n as f64;
            let mut adj = 0.0;
            for t in (0..n).rev() {
                adj = path_grad[t] + rho * adj;
                grad[k + t] = adj * s
                    / if t == 0 {
                        (1.0 - rho * rho).sqrt()
                    } else {
                        1.0
                    };
            }
            lp += n as f64 * q[3] - 0.5 * (1.0 - rho * rho).ln();
        }
        if !lp.is_finite() || grad.iter().any(|v| !v.is_finite()) {
            return Err(TargetError::recoverable("nonfinite target"));
        }
        Ok(lp)
    }
}
enum Backend<'a> {
    Hand(&'a Model),
    Autodiff(owalnuts_autodiff::AutodiffTarget<flow_autodiff::Density<'a>>),
}
impl Target for Backend<'_> {
    fn dimension(&self) -> usize {
        match self {
            Self::Hand(m) => m.dimension(),
            Self::Autodiff(m) => m.dimension(),
        }
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        match self {
            Self::Hand(m) => m.log_density_gradient(q, g),
            Self::Autodiff(m) => m.log_density_gradient(q, g),
        }
    }
}
struct FlowTarget<'a> {
    model: &'a Model,
    backend: Backend<'a>,
    geometry: Option<flow_geometry::FixedGeometry>,
}
impl<'a> FlowTarget<'a> {
    fn new(model: &'a Model, arm: &str) -> Result<Self, TargetError> {
        if !matches!(
            arm,
            "diagonal"
                | "dense"
                | "noncentered"
                | "autodiff"
                | "autodiff-dense"
                | "autodiff-noncentered"
                | "fisher"
                | "fisher-shear"
                | "autodiff-fisher"
                | "autodiff-fisher-shear"
        ) {
            return Err(TargetError::new("unknown flow arm"));
        }
        let geometry = if arm.contains("fisher") {
            Some(flow_geometry::FixedGeometry::new(
                model.data.y.len(),
                model.data.y[0].len(),
                model.data.rho,
                model.data.nu,
                arm.ends_with("shear"),
            )?)
        } else {
            None
        };
        if geometry.is_some() && model.nc {
            return Err(TargetError::new(
                "Fisher transform requires centered base model",
            ));
        }
        let backend = if arm.starts_with("autodiff") {
            Backend::Autodiff(flow_autodiff::target(model))
        } else {
            Backend::Hand(model)
        };
        Ok(Self {
            model,
            backend,
            geometry,
        })
    }
    fn canonical(&self, q: &[f64]) -> Vec<f64> {
        match &self.geometry {
            Some(g) => g.canonical(q),
            None => self.model.canonical(q),
        }
    }
    fn sampling_coordinates(&self, q: &[f64]) -> Vec<f64> {
        match &self.geometry {
            Some(g) => g.transformed(q),
            None => self.model.sampling_coordinates(q),
        }
    }
    fn geometry_metadata(&self) -> serde_json::Value {
        self.geometry
            .as_ref()
            .map(|g| g.metadata())
            .unwrap_or(serde_json::Value::Null)
    }
}
impl Target for FlowTarget<'_> {
    fn dimension(&self) -> usize {
        self.model.dimension()
    }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        match &self.geometry {
            Some(geometry) => flow_geometry::AffineTarget {
                base: &self.backend,
                geometry,
            }
            .log_density_gradient(q, g),
            None => self.backend.log_density_gradient(q, g),
        }
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
        let model = Model {
            data,
            nc: arm.ends_with("noncentered"),
        };
        let target = FlowTarget::new(&model, arm)?;
        let k = 4 + 2 * model.data.y[0].len();
        let canonical: Vec<Vec<f64>> = if let Some(path) = a.get(5) {
            serde_json::from_slice(&fs::read(path)?)?
        } else {
            let mut q = vec![0.0; model.dimension()];
            q[1] = -1.0;
            q[2] = -1.0;
            q[3] = -1.5;
            q[k..].fill(-1.0);
            vec![q]
        };
        if canonical.iter().any(|q| q.len() != model.dimension()) {
            return Err("canonical position dimension mismatch".into());
        }
        let positions: Vec<_> = canonical
            .iter()
            .map(|q| target.sampling_coordinates(q))
            .collect();
        let iterations = a[3].parse()?;
        let mut result =
            bench_eval::benchmark(&target, &positions, iterations, arm.starts_with("autodiff"))?;
        result["geometry"] = target.geometry_metadata();
        result["arm"] = json!(arm);
        result["model"] = json!("options_flow");
        result["position_source"] = json!(
            a.get(5)
                .map(String::as_str)
                .unwrap_or("deterministic_sampler_initialization")
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
        let mut grad = vec![0.0; model.dimension()];
        let target = FlowTarget::new(&model, a.get(3).map(String::as_str).unwrap_or("diagonal"))?;
        let lp = target.log_density_gradient(&q, &mut grad)?;
        println!(
            "{}",
            json!({"logp":lp,"gradient":grad,"geometry":target.geometry_metadata()})
        );
        return Ok(());
    }
    if a.len() < 2 {
        return Err("usage: data.json out.json [diagonal|dense|noncentered] [seed] [warmup] [draws] [chains]".into());
    }
    let arm = a.get(2).map(String::as_str).unwrap_or("diagonal");
    let metric = match arm {
        "diagonal"
        | "noncentered"
        | "autodiff"
        | "autodiff-noncentered"
        | "fisher"
        | "fisher-shear"
        | "autodiff-fisher"
        | "autodiff-fisher-shear" => Metric::diagonal(),
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
    let setup_started = Instant::now();
    let target = FlowTarget::new(&model, arm)?;
    let target_setup_seconds = setup_started.elapsed().as_secs_f64();
    let canonical_starts = model.initial_positions(chains)?;
    let starts: Vec<_> = canonical_starts
        .iter()
        .map(|q| target.sampling_coordinates(q))
        .collect();
    let start = Instant::now();
    let sampler = Sampler::new()
        .warmup(warmup)
        .draws(draws)
        .chains(chains)
        .threads(1)
        .seed(seed)
        .metric(metric)
        .limits(Limits::new().admit_worst_case());
    let p = sampler.run(&target, &starts)?;
    let wall_seconds = start.elapsed().as_secs_f64();
    let output:Vec<_>=p.chains().iter().map(|c| {
        let t=c.telemetry();let r=t.retained();
        json!({"draws":(0..draws).map(|i|target.canonical(c.sample(i).unwrap())).collect::<Vec<_>>(),"warmup_calls":t.discarded().target_calls_total(),"retained_calls":r.target_calls_total(),"retained_divergences":r.divergences(),"retained_rc_stops":r.reverse_coarser_stops(),"depths":c.diagnostics().iter().map(|d|d.depth()).collect::<Vec<_>>(),"final_step":c.metadata().tuning().step_size()})
    }).collect();
    fs::write(
        &a[1],
        serde_json::to_vec(
            &json!({"schema_version":1,"sampler":"owalnuts","threads":1,"arm":arm,"seed":seed,"warmup":warmup,"draws":draws,"wall_seconds":wall_seconds,"target_setup_seconds":target_setup_seconds,"geometry":target.geometry_metadata(),"coordinates":"centered","initial_positions":canonical_starts,"chains":output}),
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
                y: vec![vec![0.2, -0.4]; 7],
                x: vec![vec![0.8, -0.2]; 7],
                nu: 5.0,
                rho: 0.95,
                initial_positions: None,
            },
            nc,
        }
    }
    #[test]
    fn finite_difference_gradients() {
        for nc in [false, true] {
            let m = model(nc);
            for offset in [-0.7, 0.0, 0.8] {
                let mut q: Vec<_> = (0..m.dimension())
                    .map(|i| offset + (i as f64 * 0.7).sin() * 0.3)
                    .collect();
                q[1] = -1.2 + offset * 0.2;
                q[3] = -1.3 + offset * 0.2;
                let mut grad = vec![0.0; q.len()];
                m.log_density_gradient(&q, &mut grad).unwrap();
                for i in 0..q.len() {
                    let mut tmp = vec![0.0; q.len()];
                    let h = 1e-5;
                    q[i] += h;
                    let plus = m.log_density_gradient(&q, &mut tmp).unwrap();
                    q[i] -= 2.0 * h;
                    let minus = m.log_density_gradient(&q, &mut tmp).unwrap();
                    q[i] += h;
                    let fd = (plus - minus) / (2.0 * h);
                    assert!(
                        (fd - grad[i]).abs() < 2e-5 * (1.0 + fd.abs()),
                        "nc={nc} i={i}: {fd} != {}",
                        grad[i]
                    );
                }
            }
        }
    }
    #[test]
    fn noncentered_change_of_variables() {
        let m = model(true);
        let q = vec![0.1; m.dimension()];
        let c = m.canonical(&q);
        let mut grad = vec![0.0; q.len()];
        let lp = m.log_density_gradient(&q, &mut grad).unwrap();
        let centered = model(false).log_density_gradient(&c, &mut grad).unwrap();
        let expected = centered + 7.0 * q[3] - 0.5 * (1.0 - 0.95f64.powi(2)).ln();
        assert!((lp - expected).abs() < 1e-10);
    }
    #[test]
    fn rejects_invalid_data() {
        let mut m = model(false);
        m.data.x.pop();
        assert!(m.data.validate().is_err());
    }
    #[test]
    fn supplied_canonical_starts_survive_every_transform() {
        for arm in [
            "diagonal",
            "dense",
            "noncentered",
            "autodiff",
            "autodiff-dense",
            "autodiff-noncentered",
            "fisher",
            "fisher-shear",
            "autodiff-fisher",
            "autodiff-fisher-shear",
        ] {
            let mut m = model(arm.ends_with("noncentered"));
            let starts: Vec<Vec<f64>> = (0..3)
                .map(|chain| {
                    (0..m.dimension())
                        .map(|i| -0.7 + ((i + chain * 3) as f64 * 0.21).sin())
                        .collect()
                })
                .collect();
            m.data.initial_positions = Some(starts.clone());
            m.data.validate().unwrap();
            assert_eq!(m.initial_positions(3).unwrap(), starts);
            assert!(m.initial_positions(4).is_err());
            let target = FlowTarget::new(&m, arm).unwrap();
            for q in &starts {
                let restored = target.canonical(&target.sampling_coordinates(q));
                for (a, b) in q.iter().zip(restored) {
                    assert!((a - b).abs() < 1e-12, "arm {arm}");
                }
            }
        }
    }
    #[test]
    fn rejects_invalid_initial_matrix() {
        let mut m = model(false);
        for starts in [vec![], vec![vec![0.0]], vec![vec![f64::NAN; m.dimension()]]] {
            m.data.initial_positions = Some(starts);
            assert!(m.data.validate().is_err());
        }
        m.data.initial_positions = None;
        let starts = m.initial_positions(4).unwrap();
        assert_eq!(starts.len(), 4);
        assert_eq!(starts[0][..4], [0.0, -1.0, -1.0, -1.5]);
        assert!(m.initial_positions(0).is_err());
    }
}
