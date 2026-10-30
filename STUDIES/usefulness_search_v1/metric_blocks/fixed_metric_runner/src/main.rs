use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{error::Error, fs, sync::atomic::{AtomicU64, Ordering}, time::Instant};

struct Gaussian;
impl Target for Gaussian {
    fn dimension(&self) -> usize { 2 }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        g[0] = -(2.0*q[0]-q[1])/3.0;
        g[1] = -(-q[0]+2.0*q[1])/3.0;
        Ok(0.5*(q[0]*g[0]+q[1]*g[1]))
    }
}
struct Counted<T> { inner: T, calls: AtomicU64 }
impl<T: Target> Target for Counted<T> {
    fn dimension(&self) -> usize { self.inner.dimension() }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        self.inner.log_density_gradient(q,g)
    }
}
fn run<T: Target>(target: T, input: &Value) -> Result<Value, Box<dyn Error>> {
    let target = Counted { inner: target, calls: AtomicU64::new(0) };
    let mut rows = Vec::new();
    for config in input["chains"].as_array().ok_or("chains required")? {
        let start: Vec<f64> = serde_json::from_value(config["start"].clone())?;
        let mass: Vec<f64> = serde_json::from_value(config["mass"].clone())?;
        let step = config["step_size"].as_f64().ok_or("step size required")?;
        let seed = config["seed"].as_u64().ok_or("seed required")?;
        if start.len()!=target.dimension() { return Err("start dimension mismatch".into()); }
        let before=target.calls.load(Ordering::Relaxed); let clock=Instant::now();
        let result=Sampler::new().warmup(0)
            .draws(input["draws"].as_u64().ok_or("draws required")? as usize)
            .seed(seed).threads(1).metric(Metric::fixed_dense(mass.clone()))
            .adaptation(Adaptation::None).tuning(Tuning::default().step_size(step))
            .limits(Limits::new().admit_worst_case()).run(&target,&[start])?;
        let seconds=clock.elapsed().as_secs_f64(); let chain=&result.chains()[0];
        if chain.metadata().tuning().step_size()!=step { return Err("step size changed".into()); }
        let draws: Vec<_>=(0..chain.retained()).map(|i|chain.sample(i).unwrap().to_vec()).collect();
        rows.push(json!({"draws":draws,"seconds":seconds,"target_calls":target.calls.load(Ordering::Relaxed)-before,
            "step_size":step,"mass":mass,"seed":seed,"retained_divergences":chain.telemetry().retained().divergences(),
            "revision":result.algorithm_revision()}));
    }
    Ok(json!({"chains":rows,"target_calls":target.calls.load(Ordering::Relaxed),"scope":"Sequential fixed metric, fixed step, no warmup or adaptation; research only."}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let args:Vec<_>=std::env::args().collect();let input:Value=serde_json::from_slice(&fs::read(&args[1])?)?;
    let out=if input["target"].as_str()==Some("analytic_rotated_gaussian") { run(Gaussian,&input)? }
    else {
        let data=fs::read_to_string(input["data"].as_str().ok_or("data required")?)?;
        let target=ReplicatedStanTarget::load(std::path::Path::new(input["model"].as_str().ok_or("model required")?),&default_preload(),Some(&data),1,1)?;
        run(target,&input)?
    };
    fs::write(&args[2],serde_json::to_vec(&out)?)?;Ok(())
}
