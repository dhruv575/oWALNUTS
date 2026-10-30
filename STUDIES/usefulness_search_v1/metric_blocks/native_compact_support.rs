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
