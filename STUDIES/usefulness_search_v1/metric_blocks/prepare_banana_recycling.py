import hashlib,json,shutil
from pathlib import Path
p=Path(__file__).resolve().parent;l=p/'local_recovery'
mapping='''static LATENT_BANANA:AtomicBool=AtomicBool::new(false);
pub fn set_latent_banana(value:bool){LATENT_BANANA.store(value,Ordering::Relaxed);}
pub fn physical(q:&[f64])->Vec<f64>{let mut x=q.to_vec();if LATENT_BANANA.load(Ordering::Relaxed){assert_eq!(q.len(),24);for j in (0..24).step_by(2){x[j+1]+=5.*(q[j]*q[j]-1.);}}x}
'''
for old,new,file in [('recycling_source03','banana_wal_source01','src/recycling.rs'),('native_recycling_source01','banana_native_source01','src/research_recycling.rs')]:
    shutil.copytree(l/old,l/new);f=l/new/file;text=f.read_text();text+='\n'+mapping
    if old.startswith('recycling'):
        text=text.replace('pub fn observables(q:&[f64])->Vec<f64> {','pub fn observables(q:&[f64])->Vec<f64> {let mapped=physical(q);let q=&mapped;')
    else:text=text.replace('q.iter().copied().chain','let mapped=physical(&q);let q=&mapped;\n    q.iter().copied().chain')
    f.write_text(text);(l/new/'PARENT-SOURCE.json').write_text(json.dumps({str(f.relative_to(l/old)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (l/old).rglob('*') if f.is_file()},indent=2)+'\n')
for old,new in [('compact_original_runner','banana_wal_original_runner'),('compact_recycling_runner','banana_wal_recycling_runner'),('native_compact_pristine_runner','banana_native_pristine_runner'),('native_compact_recycling_runner','banana_native_recycling_runner')]:
    dest=p/new;dest.mkdir(exist_ok=False);(dest/'src').mkdir();manifest=(p/old/'Cargo.toml').read_text().replace(old.replace('_','-'),new.replace('_','-')).replace('recycling_source03','banana_wal_source01').replace('native_recycling_source01','banana_native_source01');(dest/'Cargo.toml').write_text(manifest)
    text=(p/old/'src/main.rs').read_text();text+='\ninclude!("../../banana_core.rs");\n'
    if old.startswith('compact'):
        namespace='measurement' if 'original' in old else 'owalnuts'
        text=text.replace('const DIMENSION:usize=10;','const DIMENSION:usize=10;\nstruct Banana{latent:bool}\nimpl Target for Banana{fn dimension(&self)->usize{24} fn log_density_gradient(&self,q:&[f64],g:&mut[f64])->Result<f64,TargetError>{let lp=banana_value(q,g,self.latent);if lp.is_finite()&&g.iter().all(|x|x.is_finite()){Ok(lp)}else{Err(TargetError::recoverable("nonfinite banana"))}}}')
        reset=namespace+'::recycling::reset(observe);';assert reset in text;text=text.replace(reset,reset+namespace+'::recycling::set_latent_banana(input["target"].as_str()==Some("banana_latent"));')
        text=text.replace('let out=if input["target"]','let out=if input["target"].as_str()==Some("banana_direct"){run(Banana{latent:false},&input)?}else if input["target"].as_str()==Some("banana_latent"){run(Banana{latent:true},&input)?}else if input["target"]')
    else:
        text=text.replace('pub fn drain()->Vec<Vec<f64>>{vec![]}','pub fn drain()->Vec<Vec<f64>>{vec![]}pub fn set_latent_banana(_value:bool){}')
        text=text.replace('let value=if self.kind==','let value=if self.kind.starts_with("banana_"){banana_value(q,g,self.kind=="banana_latent")}else if self.kind==')
        text=text.replace('observer::reset(observe);','let latent=target.kind=="banana_latent";observer::reset(observe);observer::set_latent_banana(latent);')
        text=text.replace('ordinary.push(&observable(&q))','ordinary.push(&observable(&banana_physical(&q,latent)))')
        text=text.replace('["analytic_rotated_gaussian","noncentered","funnel"].contains','["analytic_rotated_gaussian","noncentered","funnel","banana_direct","banana_latent"].contains')
        text=text.replace('let dim=if kind=="analytic_rotated_gaussian"{2}else{10};let warmup','let dim=if kind.starts_with("banana_"){24}else if kind=="analytic_rotated_gaussian"{2}else{10};let warmup')
    (dest/'src/main.rs').write_text(text)
build=(p/'build_native_compact.py').read_text().replace('native_compact_build01','banana_recycling_build01').replace("[('native_compact_pristine_runner',[]),('native_compact_recycling_runner',['--features','observe'])]","[('banana_wal_original_runner',[]),('banana_wal_recycling_runner',[]),('banana_native_pristine_runner',[]),('banana_native_recycling_runner',['--features','observe'])]")
assert 'banana_wal_original_runner' in build
(p/'build_banana_recycling.py').write_text(build)
