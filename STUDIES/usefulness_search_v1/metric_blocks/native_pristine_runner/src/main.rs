use nuts_rs::{Chain,Settings,CpuLogpFunc,CpuMath,CpuMathError,LogpError,HasDims,DiagNutsSettings,LowRankNutsSettings};
use nuts_rs::rand::{Rng,SeedableRng,rngs::ChaCha8Rng};
use std::{collections::HashMap,fs,sync::{Arc,atomic::{AtomicU64,Ordering}},time::Instant};
use serde_json::{Value,json};
#[cfg(feature="observe")] use nuts_rs::research_recycling as observer;
#[cfg(not(feature="observe"))] mod observer {pub fn reset(value:bool){assert!(!value);}pub fn drain()->Vec<Vec<f64>>{vec![]}}
#[derive(Debug,thiserror::Error)] #[error("nonfinite analytic target")] struct EvalError;
impl LogpError for EvalError {fn is_recoverable(&self)->bool{true}}
#[derive(Clone)] struct Target{kind:String,dim:usize,calls:Arc<AtomicU64>}
impl HasDims for Target {fn dim_sizes(&self)->HashMap<String,u64>{HashMap::from([("unconstrained_parameter".into(),self.dim as u64)])}}
impl CpuLogpFunc for Target {
    type LogpError=EvalError;type FlowParameters=();type ExpandedVector=Vec<f64>;
    fn dim(&self)->usize{self.dim}
    fn logp(&mut self,q:&[f64],g:&mut[f64])->Result<f64,EvalError>{
        self.calls.fetch_add(1,Ordering::Relaxed);
        let value=if self.kind=="analytic_rotated_gaussian" {
            g[0]=-(2.*q[0]-q[1])/3.;g[1]=-(-q[0]+2.*q[1])/3.;0.5*(q[0]*g[0]+q[1]*g[1])
        }else if self.kind=="noncentered"{
            g[0]=-q[0]/9.;for i in 1..self.dim{g[i]=-q[i];}-q[0]*q[0]/18.-0.5*q[1..].iter().map(|x|x*x).sum::<f64>()
        }else{
            let iv=(-q[0]).exp();let ss=q[1..].iter().map(|x|x*x).sum::<f64>();g[0]=-q[0]/9.-4.5+0.5*iv*ss;for i in 1..self.dim{g[i]=-iv*q[i];}-q[0]*q[0]/18.-4.5*q[0]-0.5*iv*ss
        };
        if value.is_finite()&&g.iter().all(|x|x.is_finite()){Ok(value)}else{Err(EvalError)}
    }
    fn expand_vector<R:Rng+?Sized>(&mut self,_rng:&mut R,q:&[f64])->Result<Vec<f64>,CpuMathError>{Ok(q.to_vec())}
}
fn one<S:Settings>(settings:S,target:Target,c:&Value,warmup:usize,draws:usize,observe:bool)->anyhow::Result<Value>{
    observer::reset(observe);let calls=target.calls.clone();let mut rng=ChaCha8Rng::seed_from_u64(c["seed"].as_u64().unwrap());let math=CpuMath::new(target);let start:Vec<f64>=serde_json::from_value(c["start"].clone())?;
    let clock=Instant::now();let mut chain=settings.new_chain(0,math,&mut rng);chain.set_position(&start)?;
    let mut positions=Vec::new();let mut progress=Vec::new();let mut warmup_calls=0;
    for i in 0..warmup+draws{let (q,p)=chain.draw()?;positions.push(q.to_vec());progress.push(json!({"draw":p.draw,"chain":p.chain,"diverging":p.diverging,"tuning":p.tuning,"step_size":p.step_size,"num_steps":p.num_steps}));if i+1==warmup{warmup_calls=calls.load(Ordering::Relaxed);}}
    let seconds=clock.elapsed().as_secs_f64();let recycled=observer::drain();if observe{assert_eq!(recycled.len(),warmup+draws);}
    Ok(json!({"all_draws":positions,"all_progress":progress,"recycled":recycled,"warmup":warmup,"draws":draws,"target_calls":calls.load(Ordering::Relaxed),"warmup_calls":warmup_calls,"seconds":seconds}))
}
fn main()->anyhow::Result<()>{
    let args:Vec<_>=std::env::args().collect();let spec:Value=serde_json::from_slice(&fs::read(&args[1])?)?;let kind=spec["target"].as_str().unwrap();assert!(["analytic_rotated_gaussian","noncentered","funnel"].contains(&kind));let dim=if kind=="analytic_rotated_gaussian"{2}else{10};let warmup=spec["warmup"].as_u64().unwrap() as usize;assert!(warmup>0);let draws=spec["draws"].as_u64().unwrap() as usize;let observe=spec["observe"].as_bool().unwrap_or(false);let mut rows=Vec::new();
    for c in spec["chains"].as_array().unwrap(){let target=Target{kind:kind.into(),dim,calls:Arc::new(AtomicU64::new(0))};let row=if spec["adaptation"].as_str()==Some("low_rank"){
        let mut s=LowRankNutsSettings::default();s.num_tune=warmup as u64;s.num_draws=draws as u64;s.maxdepth=10;s.adapt_options.step_size_settings.jitter=None;one(s,target,c,warmup,draws,observe)?
    }else{let mut s=DiagNutsSettings::default();s.num_tune=warmup as u64;s.num_draws=draws as u64;s.maxdepth=10;s.adapt_options.step_size_settings.jitter=None;one(s,target,c,warmup,draws,observe)?};rows.push(row);}
    fs::write(&args[2],serde_json::to_vec(&json!({"chains":rows,"target":kind,"adaptation":spec["adaptation"],"scope":"Native source qualification, not Python-wheel binary identity or performance comparison"}))?)?;Ok(())
}
#[cfg(test)] mod tests{
    use super::*;
    #[test] fn finite_difference_targets(){for kind in ["analytic_rotated_gaussian","noncentered","funnel"]{let dim=if kind=="analytic_rotated_gaussian"{2}else{10};let mut t=Target{kind:kind.into(),dim,calls:Arc::new(AtomicU64::new(0))};let q=vec![0.3;dim];let mut g=vec![0.;dim];t.logp(&q,&mut g).unwrap();for i in 0..dim{let mut a=q.clone();let mut b=q.clone();a[i]+=1e-6;b[i]-=1e-6;let mut scratch=vec![0.;dim];let fd=(t.logp(&a,&mut scratch).unwrap()-t.logp(&b,&mut scratch).unwrap())/2e-6;assert!((fd-g[i]).abs()<1e-6);}}}
    #[cfg(feature="observe")] #[test] fn merge_probabilities(){let a=[1.,2.];let b=[5.,8.];assert_eq!(observer::merge(&a,&b,f64::NEG_INFINITY),a);assert_eq!(observer::merge(&a,&b,10.),b);assert_eq!(observer::merge(&a,&b,0.5_f64.ln()),vec![3.,5.]);assert!(observer::merge(&[],&[],f64::NAN).is_empty());}
}
