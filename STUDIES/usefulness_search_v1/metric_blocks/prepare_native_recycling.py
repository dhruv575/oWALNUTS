import hashlib,json,shutil,difflib
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';original=local/'native_source01/nuts-rs-0.18.3';snapshot=local/'native_recycling_source01';shutil.copytree(original,snapshot)
manifest={str(p.relative_to(original)):hashlib.sha256(p.read_bytes()).hexdigest() for p in original.rglob('*') if p.is_file()};(snapshot/'ORIGINAL-SOURCE.json').write_text(json.dumps(manifest,indent=2)+'\n')
p=snapshot/'Cargo.toml';p.write_text(p.read_text().replace('name = "nuts-rs"','name = "nuts-rs-recycling-research"',1))
observer='''use std::sync::{Mutex,atomic::{AtomicBool,Ordering}};
use crate::{Math,dynamics::{State,Point}};
static ENABLED:AtomicBool=AtomicBool::new(false);
static RECORDS:Mutex<Vec<Vec<f64>>>=Mutex::new(Vec::new());
pub fn reset(value:bool){ENABLED.store(value,Ordering::Relaxed);RECORDS.lock().unwrap().clear();}
pub fn drain()->Vec<Vec<f64>>{std::mem::take(&mut *RECORDS.lock().unwrap())}
pub fn features<M:Math,P:Point<M>>(math:&mut M,state:&State<M,P>)->Vec<f64>{
    if !ENABLED.load(Ordering::Relaxed){return vec![];}
    let mut q=vec![0.;math.dim()];state.write_position(math,&mut q);
    q.iter().copied().chain(q.iter().map(|x|x*x)).chain(q.iter().map(|x|if *x<0.{1.}else{0.})).chain(q.iter().map(|x|if *x< -2.{1.}else{0.})).collect()
}
pub fn merge(old:&[f64],new:&[f64],log_p:f64)->Vec<f64>{
    assert_eq!(old.len(),new.len());if old.is_empty(){return vec![];}assert!(!log_p.is_nan());let p=log_p.min(0.).exp();
    old.iter().zip(new).map(|(a,b)|(1.-p)*a+p*b).collect()
}
pub fn record(v:&[f64]){if ENABLED.load(Ordering::Relaxed){assert!(!v.is_empty()&&v.iter().all(|x|x.is_finite()));RECORDS.lock().unwrap().push(v.to_vec());}}
''';(snapshot/'src/research_recycling.rs').write_text(observer)
p=snapshot/'src/lib.rs';p.write_text(p.read_text()+'\npub mod research_recycling;\n')
p=snapshot/'src/nuts.rs';before=p.read_text();s=before
needle='struct NutsTree<M: Math, H: Hamiltonian<M>, C: Collector<M, H::Point>> {';assert s.count(needle)==1;s=s.replace(needle,needle+'\n    recycled: Vec<f64>,')
s=s.replace('fn new(state: State<M, H::Point>) -> NutsTree<M, H, C> {','fn new(state: State<M, H::Point>, math: &mut M) -> NutsTree<M, H, C> {\n        let recycled=crate::research_recycling::features(math,&state);')
s=s.replace('right: state.clone(),','recycled,\n            right: state.clone(),',1)
needle='let log_size = -end.point().energy_error();';assert s.count(needle)==1;s=s.replace(needle,needle+'\n        let recycled=crate::research_recycling::features(math,&end);')
s=s.replace('right: end.clone(),','recycled,\n            right: end.clone(),',1)
needle='        if (other.log_size >= self_log_size)';assert s.count(needle)==1;s=s.replace(needle,'        self.recycled=crate::research_recycling::merge(&self.recycled,&other.recycled,other.log_size-self_log_size);\n'+needle)
s=s.replace('NutsTree::new(init.clone())','NutsTree::new(init.clone(), math)')
needle='collector.register_draw(math, &tree.draw, &info);';assert s.count(needle)==4;s=s.replace(needle,'crate::research_recycling::record(&tree.recycled);\n                '+needle)
p.write_text(s);(study/'NATIVE-RECYCLING-KERNEL.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='nuts-rs/src/nuts.rs',tofile='research/src/nuts.rs',n=0)))
for name,package,path,feature in [('native_recycling_runner','native-recycling-runner','../local_recovery/native_recycling_source01','nuts-rs-recycling-research'),('native_pristine_runner','native-pristine-runner','../local_recovery/native_source01/nuts-rs-0.18.3','nuts-rs')]:
    folder=study/name;(folder/'src').mkdir(parents=True,exist_ok=False)
    (folder/'src/main.rs').write_text((study/'native_recycling_main.rs').read_text())
    (folder/'Cargo.toml').write_text(f'''[package]
name = "{package}"
version = "0.1.0"
edition = "2024"
publish = false
[features]
observe = []
[dependencies]
nuts-rs = {{package="{feature}",path="{path}",default-features=false}}
serde_json = "1"
anyhow = "1"
thiserror = "2"
[workspace]
''')
