use sha2::{Digest,Sha256};
use owalnuts::sampler::{Adaptation, Limits, Metric, Sampler, Target, TargetError, Tuning};

use serde_json::{Value, json};
use std::{error::Error, fs, sync::atomic::{AtomicU64, Ordering}, time::Instant};

const DIMENSION:usize=10;
struct Banana{latent:bool}
impl Target for Banana{fn dimension(&self)->usize{24} fn log_density_gradient(&self,q:&[f64],g:&mut[f64])->Result<f64,TargetError>{let lp=banana_value(q,g,self.latent);if lp.is_finite()&&g.iter().all(|x|x.is_finite()){Ok(lp)}else{Err(TargetError::recoverable("nonfinite banana"))}}}
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
        let observe=input["observe"].as_bool().unwrap_or(false);
        if observe {return Err("original-kernel control cannot observe trajectories".into());}
        let compact=input["compact"].as_bool().unwrap_or(false);
        measurement::recycling::reset(observe);measurement::recycling::set_latent_banana(input["target"].as_str()==Some("banana_latent"));
        measurement::recycling::set_compact(compact && observe);
        let before=target.calls.load(Ordering::Relaxed); let clock=Instant::now();
        allocation_probe::start(input["profile_allocations"].as_bool().unwrap_or(false));let result=Sampler::new().warmup(input["warmup"].as_u64().ok_or("warmup required")? as usize)
            .draws(input["draws"].as_u64().ok_or("draws required")? as usize)
            .seed(seed).threads(1).metric(if input["metric"].as_str()==Some("diagonal") { Metric::diagonal() } else { assert_eq!(input["metric"].as_str(),Some("identity"));Metric::Identity })
            .adaptation(Adaptation::DualAveraging{target_accept:input["target_accept"].as_f64().unwrap_or(0.9)}).tuning(Tuning::default().step_size(step).max_refinement_levels(input["levels"].as_u64().unwrap_or(8) as usize).max_error(input["max_error"].as_f64().unwrap_or(1.0)))
            .limits(Limits::new().admit_worst_case()).run(&target,&[start])?;
        let allocation_counts=allocation_probe::finish();let seconds=clock.elapsed().as_secs_f64(); let chain=&result.chains()[0];

        let draws: Vec<_>=(0..chain.retained()).map(|i|chain.sample(i).unwrap().to_vec()).collect();
        let mut hash=Sha256::new();for draw in &draws {for x in draw {hash.update(x.to_bits().to_le_bytes());}}
        let digest=format!("{:x}",hash.finalize());
        let summary=if compact {
            let acc=if observe {measurement::recycling::drain_compact()}else{
                let mut a=measurement::recycling::Accumulator::new(50);
                for draw in &draws {a.push(&measurement::recycling::observables(draw));}a.finish()
            };
            json!({"count":acc.count,"mean":acc.mean(),"block_means":acc.blocks,"block_sizes":acc.sizes})
        }else{Value::Null};
        rows.push(json!({"allocation_counts":allocation_counts,"draw_sha256":digest,"summary":summary,"draws":if compact {Vec::<Vec<f64>>::new()}else{draws},"recycled":measurement::recycling::drain(),"seconds":seconds,"target_calls":target.calls.load(Ordering::Relaxed)-before,
            "step_size":chain.metadata().tuning().step_size(),"mass":chain.metadata().mass_diagonal(),"initial_step":step,"input_mass":mass,"metadata":format!("{:?}",chain.metadata()),"telemetry":format!("{:?}",chain.telemetry()),"discarded":chain.metadata().discarded(),"seed":seed,"retained_divergences":chain.telemetry().retained().divergences(),
            "revision":result.algorithm_revision(),"levels":chain.metadata().tuning().max_refinement_levels(),"max_error":chain.metadata().tuning().max_error(),"work":json!({"target_calls_initial":chain.telemetry().retained().target_calls_initial(),"target_calls_forward":chain.telemetry().retained().target_calls_forward(),"target_calls_reverse":chain.telemetry().retained().target_calls_reverse(),"target_calls_total":chain.telemetry().retained().target_calls_total(),"accepted_forward_micro_steps":chain.telemetry().retained().accepted_forward_micro_steps(),"forward_refinement_attempts":chain.telemetry().retained().forward_refinement_attempts(),"reverse_coarsening_attempts":chain.telemetry().retained().reverse_coarsening_attempts(),"leaves_attempted":chain.telemetry().retained().leaves_attempted(),"leaves_built":chain.telemetry().retained().leaves_built(),"refinement_exhaustion_stops":chain.telemetry().retained().refinement_exhaustion_stops(),"reverse_coarser_stops":chain.telemetry().retained().reverse_coarser_stops(),"maximum_depth_stops":chain.telemetry().retained().maximum_depth_stops(),"zero_density_evaluations":chain.telemetry().retained().zero_density_evaluations(),"nonfinite_position_rejections":chain.telemetry().retained().nonfinite_position_rejections(),"recoverable_target_failures":chain.telemetry().retained().recoverable_target_failures(),"refinement_level_built":chain.telemetry().retained().refinement_level_built(),"all_phase_calls":chain.telemetry().total().target_calls_total()})}));
    }
    Ok(json!({"chains":rows,"target_calls":target.calls.load(Ordering::Relaxed),"scope":"Sequential cold identity/diagonal adaptation; retained-only research observer."}))
}
fn main() -> Result<(), Box<dyn Error>> {
    let args:Vec<_>=std::env::args().collect();let input:Value=serde_json::from_slice(&fs::read(&args[1])?)?;
    let out=if input["target"].as_str()==Some("banana_direct"){run(Banana{latent:false},&input)?}else if input["target"].as_str()==Some("banana_latent"){run(Banana{latent:true},&input)?}else if input["target"].as_str()==Some("analytic_rotated_gaussian") { run(Gaussian,&input)? }
    else if input["target"].as_str()==Some("funnel") { run(Funnel {noncentered:false},&input)? }
    else if input["target"].as_str()==Some("noncentered") {run(Funnel {noncentered:true},&input)?}
    else { return Err("unknown analytic target".into());
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

#[cfg(test)]
mod recycling_tests {
    use measurement::recycling::merge;
    #[test]
    fn enumerated_selection_tree() {
        let old=merge(&[1.],&[3.],0.75_f64.ln());
        let new=merge(&[10.],&[20.],(1.0_f64/3.0).ln());
        for p in [0.75_f64,3.0/7.0,0.0,1.0] {
            let got=merge(&old,&new,p.ln())[0];let mut exact=0.;let mut total=0.;
            for mask in 0..8 {
                let bits=[mask&1!=0,mask&2!=0,mask&4!=0];let probs=[0.75,1.0/3.0,p];
                let probability=(0..3).map(|i|if bits[i]{probs[i]}else{1.-probs[i]}).product::<f64>();
                let selected=if bits[2]{if bits[1]{20.}else{10.}}else{if bits[0]{3.}else{1.}};
                total+=probability;exact+=probability*selected;
            }
            assert!((total-1.).abs()<1e-14);assert!((got-exact).abs()<1e-13);
        }
        assert!((merge(&old,&new,0.75_f64.ln())[0]-merge(&old,&new,(3.0_f64/7.0).ln())[0]).abs()>1.0);
        assert_eq!(merge(&[],&[],f64::NAN),Vec::<f64>::new());
        assert_eq!(merge(&[1.],&[2.],f64::NEG_INFINITY),vec![1.]);
        assert_eq!(merge(&[1.],&[2.],10.0),vec![2.]);
    }
}

#[cfg(test)]
mod coordinate_tests {
    #[test]
    fn exact_dense_restore_before_nonlinear_features() {
        use measurement::recycling::{reset,set_dense_lower,features};
        reset(true);assert!(features(&[0.,-6.]).is_empty());measurement::recycling::set_retained_phase(true);set_dense_lower(&[2.,0.,1.,3.]);
        // z=L^T*x for x=(1,-2), so z=(0,-6).
        assert_eq!(features(&[0.,-6.]),vec![1.,-2.,1.,4.,0.,1.,0.,0.]);
        reset(false);assert!(features(&[0.,-6.]).is_empty());
    }
}

#[cfg(test)] mod compact_tests {
    use measurement::recycling::Accumulator;
    #[test] fn partial_blocks_and_means(){let mut a=Accumulator::new(2);a.push(&[1.,2.]);a.push(&[3.,4.]);a.push(&[8.,9.]);let a=a.finish();assert_eq!(a.count,3);assert_eq!(a.mean(),vec![4.,5.]);assert_eq!(a.blocks,vec![vec![2.,3.],vec![8.,9.]]);assert_eq!(a.sizes,vec![2,1]);}
    #[test] #[should_panic] fn empty_rejected(){Accumulator::new(2).finish();}
    #[test] #[should_panic] fn nonfinite_rejected(){Accumulator::new(2).push(&[f64::NAN]);}
}

include!("../../banana_core.rs");

include!("../../allocation_probe.rs");
