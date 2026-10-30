mod allocation_probe {
 use std::alloc::{GlobalAlloc,Layout,System};
 use std::sync::atomic::{AtomicBool,AtomicU64,Ordering};
 pub struct Probe;
static STAGE_EVENTS:[AtomicU64;12]=[const{AtomicU64::new(0)};12];static STAGE_BYTES:[AtomicU64;12]=[const{AtomicU64::new(0)};12];
 static ENABLED:AtomicBool=AtomicBool::new(false);
 static ALLOCS:AtomicU64=AtomicU64::new(0);static ZEROED:AtomicU64=AtomicU64::new(0);static REALLOCS:AtomicU64=AtomicU64::new(0);static BYTES:AtomicU64=AtomicU64::new(0);static FREES:AtomicU64=AtomicU64::new(0);static FREED:AtomicU64=AtomicU64::new(0);
 static BINS:[AtomicU64;5]=[const{AtomicU64::new(0)};5];
 fn requested(size:usize){let stage=owalnuts::allocation_attribution::stage();STAGE_EVENTS[stage].fetch_add(1,Ordering::Relaxed);STAGE_BYTES[stage].fetch_add(size as u64,Ordering::Relaxed);BYTES.fetch_add(size as u64,Ordering::Relaxed);let bin=if size<=32{0}else if size<=128{1}else if size<=512{2}else if size<=2048{3}else{4};BINS[bin].fetch_add(1,Ordering::Relaxed);}
 unsafe impl GlobalAlloc for Probe {
  unsafe fn alloc(&self,l:Layout)->*mut u8{if ENABLED.load(Ordering::Relaxed){ALLOCS.fetch_add(1,Ordering::Relaxed);requested(l.size());}unsafe{System.alloc(l)}}
  unsafe fn alloc_zeroed(&self,l:Layout)->*mut u8{if ENABLED.load(Ordering::Relaxed){ZEROED.fetch_add(1,Ordering::Relaxed);requested(l.size());}unsafe{System.alloc_zeroed(l)}}
  unsafe fn realloc(&self,p:*mut u8,l:Layout,size:usize)->*mut u8{if ENABLED.load(Ordering::Relaxed){REALLOCS.fetch_add(1,Ordering::Relaxed);requested(size);}unsafe{System.realloc(p,l,size)}}
  unsafe fn dealloc(&self,p:*mut u8,l:Layout){if ENABLED.load(Ordering::Relaxed){FREES.fetch_add(1,Ordering::Relaxed);FREED.fetch_add(l.size() as u64,Ordering::Relaxed);}unsafe{System.dealloc(p,l)}}
 }
 pub fn start(enabled:bool){ENABLED.store(false,Ordering::Relaxed);for a in [&ALLOCS,&ZEROED,&REALLOCS,&BYTES,&FREES,&FREED]{a.store(0,Ordering::Relaxed);}for a in &BINS{a.store(0,Ordering::Relaxed);}for a in STAGE_EVENTS.iter().chain(STAGE_BYTES.iter()){a.store(0,Ordering::Relaxed);}ENABLED.store(enabled,Ordering::Relaxed);}
 pub fn finish()->serde_json::Value{ENABLED.store(false,Ordering::Relaxed);serde_json::json!({"stage_events":STAGE_EVENTS.iter().map(|a|a.load(Ordering::Relaxed)).collect::<Vec<_>>(),"stage_bytes":STAGE_BYTES.iter().map(|a|a.load(Ordering::Relaxed)).collect::<Vec<_>>(),"alloc":ALLOCS.load(Ordering::Relaxed),"alloc_zeroed":ZEROED.load(Ordering::Relaxed),"realloc":REALLOCS.load(Ordering::Relaxed),"requested_bytes":BYTES.load(Ordering::Relaxed),"dealloc":FREES.load(Ordering::Relaxed),"freed_bytes":FREED.load(Ordering::Relaxed),"request_size_bins":[BINS[0].load(Ordering::Relaxed),BINS[1].load(Ordering::Relaxed),BINS[2].load(Ordering::Relaxed),BINS[3].load(Ordering::Relaxed),BINS[4].load(Ordering::Relaxed)]})}
}
#[global_allocator] static ALLOCATION_PROBE:allocation_probe::Probe=allocation_probe::Probe;
