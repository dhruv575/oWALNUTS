import shutil
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';snap=local/'recycling_source03';shutil.copytree(local/'recycling_source02',snap)
p=snap/'src/recycling.rs';s=p.read_text()
s=s.replace('static LOWER:', 'static COMPACT:AtomicBool=AtomicBool::new(false);\nstatic ACC:Mutex<Option<Accumulator>>=Mutex::new(None);\nstatic LOWER:')
s=s.replace('ENABLED.store(enabled,Ordering::Relaxed);','ENABLED.store(enabled,Ordering::Relaxed); COMPACT.store(false,Ordering::Relaxed); *ACC.lock().unwrap()=None;')
needle='q.iter().copied().chain(q.iter().map(|x|x*x)).chain(q.iter().map(|x|if *x<0. {1.}else{0.})).chain(q.iter().map(|x|if *x< -2. {1.}else{0.})).collect()'
assert s.count(needle)==1;s=s.replace(needle,'observables(q)')
s=s.replace('RECORDS.lock().unwrap().push(v);','if COMPACT.load(Ordering::Relaxed) { ACC.lock().unwrap().as_mut().unwrap().push(&v); } else { RECORDS.lock().unwrap().push(v); }')
s+='''
pub fn observables(q:&[f64])->Vec<f64> { OBSERVABLES }
#[derive(Clone,Debug)]
pub struct Accumulator { pub count:usize,pub sums:Vec<f64>,pub blocks:Vec<Vec<f64>>,pub sizes:Vec<usize>,pending:Vec<f64>,pending_count:usize,block_size:usize }
impl Accumulator {
    pub fn new(block_size:usize)->Self {assert!(block_size>0); Self {count:0,sums:vec![],blocks:vec![],sizes:vec![],pending:vec![],pending_count:0,block_size} }
    pub fn push(&mut self,v:&[f64]) {
        assert!(!v.is_empty() && v.iter().all(|x|x.is_finite()));
        if self.count==0 {self.sums=vec![0.;v.len()];self.pending=vec![0.;v.len()];}
        assert_eq!(v.len(),self.sums.len());
        for i in 0..v.len(){self.sums[i]+=v[i];self.pending[i]+=v[i];}
        self.count+=1;self.pending_count+=1;
        if self.pending_count==self.block_size {self.flush();}
    }
    fn flush(&mut self){if self.pending_count>0 {self.blocks.push(self.pending.iter().map(|x|x/self.pending_count as f64).collect());self.sizes.push(self.pending_count);self.pending.fill(0.);self.pending_count=0;}}
    pub fn finish(mut self)->Self {assert!(self.count>0);self.flush();self}
    pub fn mean(&self)->Vec<f64>{assert!(self.count>0);self.sums.iter().map(|x|x/self.count as f64).collect()}
}
pub fn set_compact(value:bool) {COMPACT.store(value,Ordering::Relaxed);*ACC.lock().unwrap()=if value {Some(Accumulator::new(50))}else{None};}
pub fn drain_compact()->Accumulator {ACC.lock().unwrap().take().unwrap().finish()}
'''.replace('OBSERVABLES',needle)
p.write_text(s)
package=study/'compact_recycling_runner';(package/'src').mkdir(parents=True,exist_ok=False)
s=(study/'recycling_runner/src/main.rs').read_text();s='use sha2::{Digest,Sha256};\n'+s
s=s.replace('owalnuts::recycling::reset(input["observe"].as_bool().unwrap_or(false));','''let observe=input["observe"].as_bool().unwrap_or(false);
        let compact=input["compact"].as_bool().unwrap_or(false);
        owalnuts::recycling::reset(observe);
        owalnuts::recycling::set_compact(compact && observe);''')
needle='rows.push(json!({"draws":draws,"recycled":owalnuts::recycling::drain(),'
assert s.count(needle)==1
s=s.replace(needle,'''let mut hash=Sha256::new();for draw in &draws {for x in draw {hash.update(x.to_bits().to_le_bytes());}}
        let digest=format!("{:x}",hash.finalize());
        let summary=if compact {
            let acc=if observe {owalnuts::recycling::drain_compact()}else{
                let mut a=owalnuts::recycling::Accumulator::new(50);
                for draw in &draws {a.push(&owalnuts::recycling::observables(draw));}a.finish()
            };
            json!({"count":acc.count,"mean":acc.mean(),"block_means":acc.blocks,"block_sizes":acc.sizes})
        }else{Value::Null};
        rows.push(json!({"draw_sha256":digest,"summary":summary,"draws":if compact {Vec::<Vec<f64>>::new()}else{draws},"recycled":owalnuts::recycling::drain(),''')
s+='''
#[cfg(test)] mod compact_tests {
    use owalnuts::recycling::Accumulator;
    #[test] fn partial_blocks_and_means(){let mut a=Accumulator::new(2);a.push(&[1.,2.]);a.push(&[3.,4.]);a.push(&[8.,9.]);let a=a.finish();assert_eq!(a.count,3);assert_eq!(a.mean(),vec![4.,5.]);assert_eq!(a.blocks,vec![vec![2.,3.],vec![8.,9.]]);assert_eq!(a.sizes,vec![2,1]);}
    #[test] #[should_panic] fn empty_rejected(){Accumulator::new(2).finish();}
    #[test] #[should_panic] fn nonfinite_rejected(){Accumulator::new(2).push(&[f64::NAN]);}
}
''';(package/'src/main.rs').write_text(s)
(package/'Cargo.toml').write_text((study/'recycling_runner/Cargo.toml').read_text().replace('recycling-research-runner','compact-recycling-runner').replace('recycling_source02','recycling_source03').replace('serde_json = "1"','serde_json = "1"\nsha2 = "=0.10.9"'))
b=(study/'build_recycling_corrected.py').read_text().replace('recycling_build03','compact_recycling_build01').replace('recycling01','compact-recycling01').replace('recycling_runner','compact_recycling_runner').replace('recycling-research-runner','compact-recycling-runner')
b=b.replace("['cargo','generate-lockfile','--offline']","['cargo','generate-lockfile']").replace("),60,cache,1024**3", "),120,cache,2*1024**3")
needle="cmd=['cargo','build'"
b=b.replace(needle,"fetch=execute(['cargo','fetch','--locked'],str(study/'compact_recycling_runner'),120,cache,2*1024**3,1024**3,root/'fetch.log',output_scan_interval=2)\nassert fetch['exit_code']==0 and fetch['group_drained']\n"+needle)
(study/'build_compact_recycling.py').write_text(b)
