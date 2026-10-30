import hashlib,json,re,shutil,difflib
from pathlib import Path
p=Path(__file__).resolve().parent;repo=p.parents[2];l=p/'local_recovery';out=l/'allocation_attribution_source01';out.mkdir(exist_ok=False);shutil.copytree(repo/'src',out/'src')
(out/'Cargo.toml').write_text((l/'cold_wal_source01/Cargo.toml').read_text().replace('owalnuts-recycling-research','owalnuts-allocation-attribution'))
(out/'ORIGINAL-SOURCE.json').write_text(json.dumps({str(f.relative_to(repo)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (repo/'src').rglob('*') if f.is_file()},indent=2)+'\n')
module='''use std::cell::Cell;
thread_local! {static CURRENT:Cell<usize>=const{Cell::new(0)};}
pub fn stage()->usize{CURRENT.try_with(|v|v.get()).unwrap_or(0)}
pub struct Scope{previous:usize}
impl Scope{pub fn enter(stage:usize)->Self{Self{previous:CURRENT.with(|v|v.replace(stage))}}}
impl Drop for Scope{fn drop(&mut self){let _=CURRENT.try_with(|v|v.set(self.previous));}}
'''
(out/'src/allocation_attribution.rs').write_text(module);lib=out/'src/lib.rs';lib.write_text(lib.read_text()+'\npub mod allocation_attribution;\n')
names=['other','pooled_state','generate_reverse_schedule','record_histogram','merge_histogram','build_span_inner','build_span_counted_inner','macro_leaf_in_workspace','integrate','spans_make_u_turn_observed','transition_w_inner','transition_w_untraced_inner'];f=out/'src/kernel.rs';original=f.read_text();text=original
for i,name in enumerate(names[1:],1):
    matches=list(re.finditer(r'(?m)^fn '+name+r'(?:<|\()',text));assert len(matches)==1,name;pos=text.index('{',matches[0].start())+1;text=text[:pos]+f'\n    let _allocation_scope=crate::allocation_attribution::Scope::enter({i});'+text[pos:]
f.write_text(text);(p/'ALLOCATION-ATTRIBUTION-KERNEL.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='src/kernel.rs',tofile='allocation_attribution_source01/src/kernel.rs',n=0)))
driver=p/'allocation_attribution_runner';driver.mkdir(exist_ok=False);(driver/'src').mkdir();manifest=(p/'allocation_probe_runner/Cargo.toml').read_text().replace('allocation-probe-runner','allocation-attribution-runner').replace('owalnuts = { path = "../../../.." }','owalnuts = {package="owalnuts-allocation-attribution",path="../local_recovery/allocation_attribution_source01"}');assert 'owalnuts-allocation-attribution' in manifest;(driver/'Cargo.toml').write_text(manifest)
probe=(p/'allocation_probe.rs').read_text();probe=probe.replace('pub struct Probe;','pub struct Probe;\nstatic STAGE_EVENTS:[AtomicU64;12]=[const{AtomicU64::new(0)};12];static STAGE_BYTES:[AtomicU64;12]=[const{AtomicU64::new(0)};12];')
probe=probe.replace('fn requested(size:usize){','fn requested(size:usize){let stage=owalnuts::allocation_attribution::stage();STAGE_EVENTS[stage].fetch_add(1,Ordering::Relaxed);STAGE_BYTES[stage].fetch_add(size as u64,Ordering::Relaxed);')
probe=probe.replace('for a in &BINS{a.store(0,Ordering::Relaxed);}','for a in &BINS{a.store(0,Ordering::Relaxed);}for a in STAGE_EVENTS.iter().chain(STAGE_BYTES.iter()){a.store(0,Ordering::Relaxed);}')
probe=probe.replace('serde_json::json!({"alloc":','serde_json::json!({"stage_events":STAGE_EVENTS.iter().map(|a|a.load(Ordering::Relaxed)).collect::<Vec<_>>(),"stage_bytes":STAGE_BYTES.iter().map(|a|a.load(Ordering::Relaxed)).collect::<Vec<_>>(),"alloc":')
(p/'allocation_attribution_probe.rs').write_text(probe);(driver/'src/main.rs').write_text((p/'allocation_probe_runner/src/main.rs').read_text().replace('include!("../../allocation_probe.rs")','include!("../../allocation_attribution_probe.rs")'))
(p/'ALLOCATION-ATTRIBUTION-LABELS.json').write_text(json.dumps(names,indent=2)+'\n');build=(p/'build_allocation_probe.py').read_text().replace('allocation_probe_build01','allocation_attribution_build01').replace('allocation_probe_runner','allocation_attribution_runner');(p/'build_allocation_attribution.py').write_text(build)
