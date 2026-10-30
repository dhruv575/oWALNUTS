use std::{fs,time::Instant};
use rand::{SeedableRng,rngs::ChaCha8Rng};
use rand_distr::{Distribution,StandardNormal};
use serde_json::{Value,json};
include!("../../native_compact_support.rs");
include!("../../banana_core.rs");
fn main()->Result<(),Box<dyn std::error::Error>>{
 let args:Vec<_>=std::env::args().collect();let spec:Value=serde_json::from_slice(&fs::read(&args[1])?)?;let draws=spec["draws"].as_u64().unwrap() as usize;let compact=spec["compact"].as_bool().unwrap_or(true);let mut chains=vec![];
 for c in spec["chains"].as_array().unwrap(){let clock=Instant::now();let mut rng=ChaCha8Rng::seed_from_u64(c["seed"].as_u64().unwrap());let mut acc=Acc::default();let mut hash=Sha256::new();let mut positions=vec![];for _ in 0..draws{let z:Vec<f64>=(0..24).map(|_|StandardNormal.sample(&mut rng)).collect();let x=banana_physical(&z,true);for q in &x{hash.update(q.to_le_bytes());}acc.push(&observable(&x));if !compact{positions.push(x);}}chains.push(json!({"seconds":clock.elapsed().as_secs_f64(),"summary":acc.finish(),"draw_sha256":format!("{:x}",hash.finalize()),"draws":positions,"target_calls":0,"retained_divergences":0}));}
 fs::write(&args[2],serde_json::to_vec(&json!({"chains":chains,"scope":"Independent exact transformed-normal draws, no tuning or warmup needed"}))?)?;Ok(())
}
