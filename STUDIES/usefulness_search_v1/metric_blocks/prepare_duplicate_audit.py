import hashlib,json
from pathlib import Path
study=Path(__file__).resolve().parent;parent=study/'fixed_metric_runner';dest=study/'duplicate_eval_runner';dest.mkdir(exist_ok=False);(dest/'src').mkdir()
source=(parent/'src/main.rs').read_text();fragment=(study/'duplicate_audit_fragment.rs').read_text()
def replace(old,new):
    global source
    assert source.count(old)==1,old;source=source.replace(old,new)
replace('struct Counted<T> { inner: T, calls: AtomicU64 }',fragment+'\nstruct Counted<T> { inner: T, calls: AtomicU64, enabled: bool, audit: std::sync::Mutex<Audit> }')
replace('self.inner.log_density_gradient(q,g)', '''let result=self.inner.log_density_gradient(q,g);
        if self.enabled {
            let mut audit=self.audit.lock().unwrap();
            match &result { Ok(lp)=>audit.observe(q,*lp,g), Err(_)=>audit.errors+=1 }
        }
        result''')
replace('calls: AtomicU64::new(0) };', 'calls: AtomicU64::new(0), enabled: input["audit"].as_bool().unwrap_or(false), audit: std::sync::Mutex::new(Audit::default()) };')
replace('let before=target.calls.load(Ordering::Relaxed);', '*target.audit.lock().unwrap()=Audit::default();\n        let before=target.calls.load(Ordering::Relaxed);')
replace('"revision":result.algorithm_revision()', '"revision":result.algorithm_revision(),"duplicate_audit":target.audit.lock().unwrap().summary()')
(dest/'src/main.rs').write_text(source)
for name in ['Cargo.toml','Cargo.lock']:(dest/name).write_text((parent/name).read_text().replace('fixed-metric-research-runner','duplicate-eval-research-runner'))
paths=[parent/'src/main.rs',study/'duplicate_audit_fragment.rs',dest/'src/main.rs',dest/'Cargo.toml',dest/'Cargo.lock']
(study/'local_recovery/DUPLICATE-AUDIT-PROVENANCE.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},indent=2)+'\n')
