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
#[derive(Default)]
struct Audit {
    values: std::collections::HashMap<Vec<u64>, (Vec<u64>, u64)>,
    observed: u64, duplicates: u64, mismatches: u64, dropped: u64,
    nonfinite: u64, errors: u64, lag_bins: [u64; 6],
}
impl Audit {
    fn observe(&mut self, q: &[f64], lp: f64, g: &[f64]) {
        self.observed += 1;
        if !lp.is_finite() || q.iter().chain(g).any(|v| !v.is_finite()) {
            self.nonfinite += 1; return;
        }
        let key: Vec<_> = q.iter().map(|v|v.to_bits()).collect();
        let value: Vec<_> = std::iter::once(lp.to_bits()).chain(g.iter().map(|v|v.to_bits())).collect();
        if let Some((prior, last)) = self.values.get_mut(&key) {
            self.duplicates += 1;
            if *prior != value { self.mismatches += 1; }
            let lag = self.observed-*last;
            let bin = [1,4,16,64,256].iter().position(|&v|lag<=v).unwrap_or(5);
            self.lag_bins[bin] += 1; *last=self.observed;
        } else if self.values.len()<32768 {
            self.values.insert(key,(value,self.observed));
        } else { self.dropped += 1; }
    }
    fn summary(&self) -> Value {
        json!({"observed_successful_calls":self.observed,"error_calls":self.errors,
            "duplicate_successful_calls":self.duplicates,"output_bit_mismatches":self.mismatches,
            "stored_unique_positions":self.values.len(),"capacity_dropped_calls":self.dropped,
            "nonfinite_calls":self.nonfinite,"reuse_lag_bins_1_4_16_64_256_larger":self.lag_bins,
            "scope":"Observation only; first32768 unique finite positions per chain. Duplicates are a lower bound when capacity drops occur."})
    }
}
#[cfg(test)]
mod audit_tests {
    use super::*;
    #[test]
    fn exact_keys_output_mismatch_and_signed_zero() {
        let mut a=Audit::default();a.observe(&[0.0],1.0,&[2.0]);a.observe(&[0.0],1.0,&[2.0]);
        a.observe(&[-0.0],1.0,&[2.0]);a.observe(&[0.0],1.0,&[3.0]);
        assert_eq!(a.duplicates,2);assert_eq!(a.mismatches,1);assert_eq!(a.values.len(),2);
    }
    #[test]
    fn capacity_and_nonfinite_are_reported() {
        let mut a=Audit::default();for i in 0..32769 {a.observe(&[i as f64],0.0,&[0.0]);}
        a.observe(&[f64::NAN],0.0,&[0.0]);a.observe(&[0.0],0.0,&[0.0]);
        assert_eq!(a.values.len(),32768);assert_eq!(a.dropped,1);assert_eq!(a.nonfinite,1);assert_eq!(a.duplicates,1);
    }
}

struct Counted<T> { inner: T, calls: AtomicU64, enabled: bool, audit: std::sync::Mutex<Audit> }
impl<T: Target> Target for Counted<T> {
    fn dimension(&self) -> usize { self.inner.dimension() }
    fn log_density_gradient(&self, q: &[f64], g: &mut [f64]) -> Result<f64, TargetError> {
        self.calls.fetch_add(1, Ordering::Relaxed);
        let result=self.inner.log_density_gradient(q,g);
        if self.enabled {
            let mut audit=self.audit.lock().unwrap();
            match &result { Ok(lp)=>audit.observe(q,*lp,g), Err(_)=>audit.errors+=1 }
        }
        result
    }
}
fn run<T: Target>(target: T, input: &Value) -> Result<Value, Box<dyn Error>> {
    let target = Counted { inner: target, calls: AtomicU64::new(0), enabled: input["audit"].as_bool().unwrap_or(false), audit: std::sync::Mutex::new(Audit::default()) };
    let mut rows = Vec::new();
    for config in input["chains"].as_array().ok_or("chains required")? {
        let start: Vec<f64> = serde_json::from_value(config["start"].clone())?;
        let mass: Vec<f64> = serde_json::from_value(config["mass"].clone())?;
        let step = config["step_size"].as_f64().ok_or("step size required")?;
        let seed = config["seed"].as_u64().ok_or("seed required")?;
        if start.len()!=target.dimension() { return Err("start dimension mismatch".into()); }
        *target.audit.lock().unwrap()=Audit::default();
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
            "revision":result.algorithm_revision(),"duplicate_audit":target.audit.lock().unwrap().summary()}));
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
