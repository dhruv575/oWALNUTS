use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};
use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};
use serde_json::{Value, json};
use std::{error::Error, fs, sync::atomic::{AtomicU64, Ordering}, time::Instant};

const DIMENSION:usize=10;
struct Funnel { noncentered: bool }

impl Target for Funnel {
    fn dimension(&self) -> usize {
        DIMENSION
    }

    fn log_density_gradient(
        &self,
        position: &[f64],
        gradient: &mut [f64],
    ) -> Result<f64, TargetError> {
        let omega = position[0];
        if self.noncentered {
            gradient[0] = -omega / 9.0;
            for (g,x) in gradient[1..].iter_mut().zip(&position[1..]) { *g = -x; }
            let value = -omega*omega/18.0 - 0.5*position[1..].iter().map(|x|x*x).sum::<f64>();
            return if value.is_finite() && gradient.iter().all(|x|x.is_finite()) { Ok(value) }
                else { Err(TargetError::recoverable("nonfinite Gaussian evaluation")) };
        }
        let inverse_variance = (-omega).exp();
        if !inverse_variance.is_finite() {
            return Err(TargetError::recoverable("exp(-omega) overflowed"));
        }
        let sum_squares: f64 = position[1..].iter().map(|x| x * x).sum();
        let tail = (DIMENSION - 1) as f64;
        gradient[0] = -omega / 9.0 - 0.5 * tail + 0.5 * inverse_variance * sum_squares;
        for (g, x) in gradient[1..].iter_mut().zip(&position[1..]) {
            *g = -inverse_variance * x;
        }
        let value =
            -omega * omega / 18.0 - 0.5 * tail * omega - 0.5 * inverse_variance * sum_squares;
        if value.is_finite() && gradient.iter().all(|g| g.is_finite()) {
            Ok(value)
        } else {
            Err(TargetError::recoverable("nonfinite funnel evaluation"))
        }
    }
}


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
            .seed(seed).threads(1).metric(if input["metric"].as_str()==Some("diagonal") { Metric::fixed_diagonal(mass.clone()) } else { Metric::fixed_dense(mass.clone()) })
            .adaptation(Adaptation::None).tuning(Tuning::default().step_size(step).max_refinement_levels(input["levels"].as_u64().unwrap_or(8) as usize).max_error(input["max_error"].as_f64().unwrap_or(1.0)))
            .limits(Limits::new().admit_worst_case()).run(&target,&[start])?;
        let seconds=clock.elapsed().as_secs_f64(); let chain=&result.chains()[0];
        if chain.metadata().tuning().step_size()!=step { return Err("step size changed".into()); }
        let draws: Vec<_>=(0..chain.retained()).map(|i|chain.sample(i).unwrap().to_vec()).collect();
        rows.push(json!({"draws":draws,"seconds":seconds,"target_calls":target.calls.load(Ordering::Relaxed)-before,
            "step_size":step,"mass":mass,"seed":seed,"retained_divergences":chain.telemetry().retained().divergences(),
            "revision":result.algorithm_revision(),"levels":chain.metadata().tuning().max_refinement_levels(),"max_error":chain.metadata().tuning().max_error(),"work":json!({"target_calls_initial":chain.telemetry().retained().target_calls_initial(),"target_calls_forward":chain.telemetry().retained().target_calls_forward(),"target_calls_reverse":chain.telemetry().retained().target_calls_reverse(),"target_calls_total":chain.telemetry().retained().target_calls_total(),"accepted_forward_micro_steps":chain.telemetry().retained().accepted_forward_micro_steps(),"forward_refinement_attempts":chain.telemetry().retained().forward_refinement_attempts(),"reverse_coarsening_attempts":chain.telemetry().retained().reverse_coarsening_attempts(),"leaves_attempted":chain.telemetry().retained().leaves_attempted(),"leaves_built":chain.telemetry().retained().leaves_built(),"refinement_exhaustion_stops":chain.telemetry().retained().refinement_exhaustion_stops(),"reverse_coarser_stops":chain.telemetry().retained().reverse_coarser_stops(),"maximum_depth_stops":chain.telemetry().retained().maximum_depth_stops(),"zero_density_evaluations":chain.telemetry().retained().zero_density_evaluations(),"nonfinite_position_rejections":chain.telemetry().retained().nonfinite_position_rejections(),"recoverable_target_failures":chain.telemetry().retained().recoverable_target_failures(),"refinement_level_built":chain.telemetry().retained().refinement_level_built(),"all_phase_calls":chain.telemetry().total().target_calls_total()})}));
    }
    Ok(json!({"chains":rows,"target_calls":target.calls.load(Ordering::Relaxed),"scope":"Sequential fixed metric, fixed step, no warmup or adaptation; research only."}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let args:Vec<_>=std::env::args().collect();let input:Value=serde_json::from_slice(&fs::read(&args[1])?)?;
    let out=if input["target"].as_str()==Some("analytic_rotated_gaussian") { run(Gaussian,&input)? }
    else if input["target"].as_str()==Some("funnel") { run(Funnel {noncentered:false},&input)? }
    else if input["target"].as_str()==Some("noncentered") {run(Funnel {noncentered:true},&input)?}
    else {
        let data=fs::read_to_string(input["data"].as_str().ok_or("data required")?)?;
        let target=ReplicatedStanTarget::load(std::path::Path::new(input["model"].as_str().ok_or("model required")?),&default_preload(),Some(&data),1,1)?;
        run(target,&input)?
    };
    fs::write(&args[2],serde_json::to_vec(&out)?)?;Ok(())
}
#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn gradients_and_change_of_variables() {
        for omega in [-6.0, -1.0, 3.0] {
            let z: Vec<f64> = (0..10).map(|i| if i==0 {omega} else {i as f64 / 10.0}).collect();
            let mut x=z.clone(); for v in &mut x[1..] { *v *= (omega/2.0).exp(); }
            let mut g=vec![0.;10];
            let lc=Funnel{noncentered:false}.log_density_gradient(&x,&mut g).unwrap();
            let ln=Funnel{noncentered:true}.log_density_gradient(&z,&mut g).unwrap();
            assert!((lc+4.5*omega-ln).abs()<1e-10);
            for (nc,q) in [(false,x),(true,z)] {
                let target=Funnel{noncentered:nc}; target.log_density_gradient(&q,&mut g).unwrap();
                for i in 0..10 { let mut p=q.clone(); let mut m=q.clone(); p[i]+=1e-6; m[i]-=1e-6;
                    let mut scratch=vec![0.;10];
                    let fd=(target.log_density_gradient(&p,&mut scratch).unwrap()-target.log_density_gradient(&m,&mut scratch).unwrap())/2e-6;
                    assert!((fd-g[i]).abs()<1e-5*(1.0+g[i].abs()));
                }
            }
        }
    }
}
