use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, WarmupConfig};
use serde_json::{json, Value};
use std::{env, fs, error::Error, time::Instant};
struct Gaussian { p: Vec<Vec<f64>> }
impl Target for Gaussian {
    fn dimension(&self) -> usize { self.p.len() }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        for i in 0..q.len() { g[i] = -self.p[i].iter().zip(q).map(|(p,x)| p*x).sum::<f64>(); }
        Ok(0.5*q.iter().zip(g).map(|(x,y)| x * *y).sum::<f64>())
    }
}
fn main() -> Result<(), Box<dyn Error>> {
    let args: Vec<_> = env::args().collect();
    let input: Value = serde_json::from_slice(&fs::read(&args[1])?)?;
    let target = Gaussian {p: serde_json::from_value(input["precision"].clone())?};
    let starts: Vec<Vec<f64>> = serde_json::from_value(input["starts"].clone())?;
    let mut sampler = Sampler::new().warmup(input["warmup"].as_u64().unwrap() as usize)
        .draws(input["draws"].as_u64().unwrap() as usize).seed(input["seed"].as_u64().unwrap())
        .threads(4).limits(Limits::new().admit_worst_case());
    match input["arm"].as_str().unwrap() {
        "dense" => sampler = sampler.metric(Metric::dense()),
        "fixed_dense" | "fixed_diag" => {
            let m: Vec<f64> = serde_json::from_value(input["mass"].clone())?;
            sampler = sampler.metric(if input["arm"] == "fixed_dense" { Metric::fixed_dense(m) }
                else { Metric::fixed_diagonal(m) })
                .adaptation(Adaptation::Custom(WarmupConfig::new(0.8)?.with_mass_adaptation(false)));
        },
        "diag" => {},
        _ => return Err("unknown arm".into()),
    }
    let start = Instant::now();
    let result = sampler.run(&target, &starts)?;
    let elapsed = start.elapsed().as_secs_f64();
    let draws: Vec<_> = result.chains().iter().map(|c|
        (0..c.retained()).map(|i| c.sample(i).unwrap().to_vec()).collect::<Vec<_>>()).collect();
    fs::write(&args[2], serde_json::to_vec(&json!({"draws": draws, "seconds": elapsed,
        "target_calls": result.total_target_calls(), "revision": result.algorithm_revision()}))?)?;
    Ok(())
}
