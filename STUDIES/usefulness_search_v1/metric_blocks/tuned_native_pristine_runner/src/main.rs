use nuts_rs::{Chain,Settings,CpuLogpFunc,CpuMath,CpuMathError,LogpError,HasDims,DiagNutsSettings,LowRankNutsSettings};
use nuts_rs::rand::{Rng,SeedableRng,rngs::ChaCha8Rng};
use std::{collections::HashMap,fs,sync::{Arc,atomic::{AtomicU64,Ordering}},time::Instant};
use serde_json::{Value,json};
#[cfg(feature="observe")] use nuts_rs::research_recycling as observer;
#[cfg(not(feature="observe"))] mod observer {pub fn reset(value:bool){assert!(!value);}pub fn drain()->Vec<Vec<f64>>{vec![]}pub fn set_latent_banana(_value:bool){}}
#[derive(Debug,thiserror::Error)] #[error("nonfinite analytic target")] struct EvalError;
impl LogpError for EvalError {fn is_recoverable(&self)->bool{true}}
#[derive(Clone)] struct Target{kind:String,dim:usize,calls:Arc<AtomicU64>}
impl HasDims for Target {fn dim_sizes(&self)->HashMap<String,u64>{HashMap::from([("unconstrained_parameter".into(),self.dim as u64)])}}
impl CpuLogpFunc for Target {
    type LogpError=EvalError;type FlowParameters=();type ExpandedVector=Vec<f64>;
    fn dim(&self)->usize{self.dim}
    fn logp(&mut self,q:&[f64],g:&mut[f64])->Result<f64,EvalError>{
        self.calls.fetch_add(1,Ordering::Relaxed);
        let value=if self.kind.starts_with("banana_"){banana_value(q,g,self.kind=="banana_latent")}else if self.kind=="analytic_rotated_gaussian" {
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
fn one<S:Settings>(settings:S,target:Target,c:&Value,warmup:usize,draws:usize,observe:bool,compact:bool)->anyhow::Result<Value>{
    let latent=target.kind=="banana_latent";observer::reset(observe);observer::set_latent_banana(latent);let calls=target.calls.clone();let mut rng=ChaCha8Rng::seed_from_u64(c["seed"].as_u64().unwrap());let math=CpuMath::new(target);let start:Vec<f64>=serde_json::from_value(c["start"].clone())?;
    let clock=Instant::now();let mut chain=settings.new_chain(0,math,&mut rng);chain.set_position(&start)?;
    let mut hash=Sha256::new();let mut ordinary=Acc::default();let mut conditional=Acc::default();let mut retained_divergences=0usize;let mut total_steps=0u64;let mut positions=Vec::new();let mut progress=Vec::new();let mut warmup_calls=0;
    for i in 0..warmup+draws{let (q,p)=chain.draw()?;for x in q.iter(){hash.update(x.to_le_bytes());}total_steps+=p.num_steps as u64;if i>=warmup{ordinary.push(&observable(&banana_physical(&q,latent)));retained_divergences+=p.diverging as usize;}if compact{if observe{let recorded=observer::drain();assert_eq!(recorded.len(),1);if i>=warmup{conditional.push(&recorded[0]);}}}else{positions.push(q.to_vec());progress.push(json!({"draw":p.draw,"chain":p.chain,"diverging":p.diverging,"tuning":p.tuning,"step_size":p.step_size,"num_steps":p.num_steps}));}if i+1==warmup{warmup_calls=calls.load(Ordering::Relaxed);}}
    let seconds=clock.elapsed().as_secs_f64();let recycled=observer::drain();if observe&&!compact{assert_eq!(recycled.len(),warmup+draws);for v in &recycled[warmup..]{conditional.push(v);}}
    Ok(json!({"draw_sha256":format!("{:x}",hash.finalize()),"ordinary_summary":ordinary.finish(),"conditional_summary":conditional.finish(),"retained_divergences":retained_divergences,"total_steps":total_steps,"all_draws":positions,"all_progress":progress,"recycled":recycled,"warmup":warmup,"draws":draws,"target_calls":calls.load(Ordering::Relaxed),"warmup_calls":warmup_calls,"seconds":seconds}))
}
fn main()->anyhow::Result<()>{
    let args:Vec<_>=std::env::args().collect();let spec:Value=serde_json::from_slice(&fs::read(&args[1])?)?;let kind=spec["target"].as_str().unwrap();assert!(["analytic_rotated_gaussian","noncentered","funnel","banana_direct","banana_latent"].contains(&kind));let dim=if kind.starts_with("banana_"){24}else if kind=="analytic_rotated_gaussian"{2}else{10};let warmup=spec["warmup"].as_u64().unwrap() as usize;assert!(warmup>0);let draws=spec["draws"].as_u64().unwrap() as usize;let observe=spec["observe"].as_bool().unwrap_or(false);let compact=spec["compact"].as_bool().unwrap_or(false);let mut rows=Vec::new();
    for c in spec["chains"].as_array().unwrap(){let target=Target{kind:kind.into(),dim,calls:Arc::new(AtomicU64::new(0))};let row=if spec["adaptation"].as_str()==Some("low_rank"){
        let mut s=LowRankNutsSettings::default();s.num_tune=warmup as u64;s.num_draws=draws as u64;s.maxdepth=10;s.adapt_options.step_size_settings.jitter=None;s.adapt_options.step_size_settings.target_accept=spec["target_accept"].as_f64().unwrap_or(0.8);one(s,target,c,warmup,draws,observe,compact)?
    }else{let mut s=DiagNutsSettings::default();s.num_tune=warmup as u64;s.num_draws=draws as u64;s.maxdepth=10;s.adapt_options.step_size_settings.jitter=None;s.adapt_options.step_size_settings.target_accept=spec["target_accept"].as_f64().unwrap_or(0.8);one(s,target,c,warmup,draws,observe,compact)?};rows.push(row);}
    fs::write(&args[2],serde_json::to_vec(&json!({"chains":rows,"target":kind,"adaptation":spec["adaptation"],"scope":"Native source qualification, not Python-wheel binary identity or performance comparison"}))?)?;Ok(())
}
#[cfg(test)] mod tests{
    use super::*;
    #[test] fn finite_difference_targets(){for kind in ["analytic_rotated_gaussian","noncentered","funnel"]{let dim=if kind=="analytic_rotated_gaussian"{2}else{10};let mut t=Target{kind:kind.into(),dim,calls:Arc::new(AtomicU64::new(0))};let q=vec![0.3;dim];let mut g=vec![0.;dim];t.logp(&q,&mut g).unwrap();for i in 0..dim{let mut a=q.clone();let mut b=q.clone();a[i]+=1e-6;b[i]-=1e-6;let mut scratch=vec![0.;dim];let fd=(t.logp(&a,&mut scratch).unwrap()-t.logp(&b,&mut scratch).unwrap())/2e-6;assert!((fd-g[i]).abs()<1e-6);}}}
    #[cfg(feature="observe")] #[test] fn merge_probabilities(){let a=[1.,2.];let b=[5.,8.];assert_eq!(observer::merge(&a,&b,f64::NEG_INFINITY),a);assert_eq!(observer::merge(&a,&b,10.),b);assert_eq!(observer::merge(&a,&b,0.5_f64.ln()),vec![3.,5.]);assert!(observer::merge(&[],&[],f64::NAN).is_empty());}
}

use sha2::{Digest,Sha256};
#[derive(Default)] struct Acc {count:usize,sum:Vec<f64>,partial:Vec<f64>,partial_count:usize,blocks:Vec<Vec<f64>>,sizes:Vec<usize>}
impl Acc {
 fn push(&mut self,v:&[f64]) {assert!(!v.is_empty()&&v.iter().all(|x|x.is_finite()));if self.count==0{self.sum=vec![0.;v.len()];self.partial=vec![0.;v.len()];}assert_eq!(self.sum.len(),v.len());for (i,x) in v.iter().enumerate(){self.sum[i]+=x;self.partial[i]+=x;}self.count+=1;self.partial_count+=1;if self.partial_count==50{self.flush();}}
 fn flush(&mut self){if self.partial_count>0{self.blocks.push(self.partial.iter().map(|x|x/self.partial_count as f64).collect());self.sizes.push(self.partial_count);self.partial.fill(0.);self.partial_count=0;}}
 fn finish(mut self)->Value{self.flush();let mean:Vec<f64>=self.sum.iter().map(|x|x/self.count as f64).collect();json!({"count":self.count,"mean":mean,"block_means":self.blocks,"block_sizes":self.sizes})}
}
fn observable(q:&[f64])->Vec<f64>{q.iter().copied().chain(q.iter().map(|x|x*x)).chain(q.iter().map(|x|if *x<0.{1.}else{0.})).chain(q.iter().map(|x|if *x< -2.{1.}else{0.})).collect()}
#[cfg(test)] mod compact_tests {
 use super::*;
 #[test] fn partial_block(){let mut a=Acc::default();for i in 0..53{a.push(&[i as f64]);}let v=a.finish();assert_eq!(v["count"],53);assert_eq!(v["mean"],json!([26.]));assert_eq!(v["block_sizes"],json!([50,3]));assert_eq!(v["block_means"],json!([[24.5],[51.]]));}
 #[test] #[should_panic] fn nonfinite_rejected(){Acc::default().push(&[f64::NAN]);}
 #[test] fn feature_order(){assert_eq!(observable(&[-3.,2.]),vec![-3.,2.,9.,4.,1.,0.,1.,0.]);}
}

include!("../../banana_core.rs");
