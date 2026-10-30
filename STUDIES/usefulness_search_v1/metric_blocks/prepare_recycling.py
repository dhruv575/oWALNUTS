import difflib,hashlib,json,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;repo=study.parents[2];local=study/'local_recovery';snapshot=local/'recycling_source01';snapshot.mkdir(exist_ok=False)
shutil.copytree(repo/'src',snapshot/'src')
manifest={str(p.relative_to(repo)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (repo/'src').rglob('*') if p.is_file()}
(snapshot/'ORIGINAL-SOURCE.json').write_text(json.dumps(manifest,indent=2)+'\n')
(snapshot/'Cargo.toml').write_text('''[package]
name = "owalnuts-recycling-research"
version = "0.3.0"
edition = "2024"
publish = false
[lib]
name = "owalnuts"
[features]
research = []
candidate-levels10 = []
[dependencies]
rand = { version = "0.9", features = ["small_rng"] }
rand_distr = "0.5"
rayon = "1.10"
''')
p=snapshot/'src/lib.rs';p.write_text(p.read_text()+'\npub mod recycling;\n')
observer='''use std::sync::{Mutex,atomic::{AtomicBool,Ordering}};
static ENABLED:AtomicBool=AtomicBool::new(false);
static RECORDS:Mutex<Vec<Vec<f64>>>=Mutex::new(Vec::new());
pub fn reset(enabled:bool) { ENABLED.store(enabled,Ordering::Relaxed); RECORDS.lock().unwrap().clear(); }
pub fn drain()->Vec<Vec<f64>> { std::mem::take(&mut *RECORDS.lock().unwrap()) }
pub fn features(q:&[f64])->Vec<f64> {
    if !ENABLED.load(Ordering::Relaxed) {return Vec::new();}
    q.iter().copied().chain(q.iter().map(|x|x*x)).chain(q.iter().map(|x|if *x<0. {1.}else{0.})).chain(q.iter().map(|x|if *x< -2. {1.}else{0.})).collect()
}
pub fn merge(old:&[f64],new:&[f64],log_p:f64)->Vec<f64> {
    assert_eq!(old.len(),new.len());
    if old.is_empty(){return Vec::new();}
    assert!(!log_p.is_nan()); let p=log_p.min(0.).exp();
    assert!((0. ..=1.).contains(&p));
    old.iter().zip(new).map(|(a,b)|(1.-p)*a+p*b).collect()
}
pub fn record(v:Vec<f64>) { if ENABLED.load(Ordering::Relaxed) { assert!(!v.is_empty() && v.iter().all(|x|x.is_finite())); RECORDS.lock().unwrap().push(v); } }
'''
(snapshot/'src/recycling.rs').write_text(observer)
p=snapshot/'src/kernel.rs';old=p.read_text();source=old
source=source.replace('pub struct Span {','pub struct Span {\n    pub recycled: Vec<f64>,',1)
needle='let endpoint = Endpoint { state, log_joint };';assert source.count(needle)==1
source=source.replace(needle,'let recycled = crate::recycling::features(&state.theta);\n        '+needle)
source=source.replace('backward: endpoint.clone(),','recycled,\n            backward: endpoint.clone(),',1)
needle='backward: earlier.backward,';assert source.count(needle)==1
source=source.replace(needle,'recycled: Vec::new(),\n            '+needle)
for name in ['combine_barker_observed','combine_metropolis_observed']:
    start=source.index('fn '+name);end=source.index('\nfn ',start+3);part=source[start:end]
    needle='let draw = rng.uniform_01()?;';assert part.count(needle)==1
    part=part.replace(needle,'let recycled=crate::recycling::merge(&old.recycled,&new.recycled,update_log_probability);\n    '+needle)
    needle='Span::from_subspans(earlier, later, selected, total),';assert part.count(needle)==1
    part=part.replace(needle,'{ let mut span=Span::from_subspans(earlier, later, selected, total); span.recycled=recycled; span },')
    source=source[:start]+part+source[end:]
needle='fn take_selected(span: Span) -> SelectedState {';assert source.count(needle)==1
source=source.replace(needle,needle+'\n    crate::recycling::record(span.recycled.clone());')
p.write_text(source)
(study/'RECYCLING-KERNEL.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),source.splitlines(True),fromfile='src/kernel.rs',tofile='research/src/kernel.rs',n=0)))
package=study/'recycling_runner';(package/'src').mkdir(parents=True,exist_ok=False)
source=(study/'funnel_cross_runner/src/main.rs').read_text();source=source.replace('use owalnuts_bridgestan::{ReplicatedStanTarget, default_preload};','')
needle='let before=target.calls.load(Ordering::Relaxed);';source=source.replace(needle,'owalnuts::recycling::reset(input["observe"].as_bool().unwrap_or(false));\n        '+needle)
source=source.replace('"draws":draws,','"draws":draws,"recycled":owalnuts::recycling::drain(),')
start=source.index('else {\n        let data=fs::read_to_string');end=source.index('\n    };',start)
source=source[:start]+'else { return Err("unknown analytic target".into());'+source[end:]
(package/'src/main.rs').write_text(source)
(package/'Cargo.toml').write_text('''[package]
name = "recycling-research-runner"
version = "0.1.0"
edition = "2024"
publish = false
[dependencies]
owalnuts = { package = "owalnuts-recycling-research", path = "../local_recovery/recycling_source01" }
serde_json = "1"
[workspace]
''')
build=(study/'build_funnel_cross.py').read_text().replace('funnel_cross_build01','recycling_build01').replace('funnel-cross01','recycling01').replace('funnel_cross_runner','recycling_runner').replace('funnel-cross-runner','recycling-research-runner')
needle="cmd=['cargo','build'"
build=build.replace(needle,"lock=execute(['cargo','generate-lockfile','--offline'],str(study/'recycling_runner'),60,cache,1024**3,1024**3,root/'lock.log',output_scan_interval=2)\nassert lock['exit_code']==0 and lock['group_drained']\n"+needle)
(study/'build_recycling.py').write_text(build)
