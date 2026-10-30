import shutil,difflib
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';old=local/'recycling_source01';new=local/'recycling_source02';shutil.copytree(old,new)
p=new/'src/recycling.rs';source=p.read_text()
source=source.replace('static ENABLED:', 'static LOWER:Mutex<Vec<f64>>=Mutex::new(Vec::new());\nstatic ENABLED:')
source=source.replace('RECORDS.lock().unwrap().clear();','RECORDS.lock().unwrap().clear(); LOWER.lock().unwrap().clear();')
needle='q.iter().copied().chain';assert source.count(needle)==1
source=source.replace(needle,'''let lower=LOWER.lock().unwrap();
    let restored=if lower.is_empty(){q.to_vec()}else{
        let n=q.len();assert_eq!(lower.len(),n*n);let mut x=vec![0.;n];
        for i in (0..n).rev(){let sum:f64=(i+1..n).map(|j|lower[j*n+i]*x[j]).sum();x[i]=(q[i]-sum)/lower[i*n+i];}x
    };
    let q=&restored;
    q.iter().copied().chain''')
source+='\npub fn set_dense_lower(lower:&[f64]) { if ENABLED.load(Ordering::Relaxed) { *LOWER.lock().unwrap()=lower.to_vec(); } }\n'
p.write_text(source)
p=new/'src/walnutpie.rs';before=p.read_text();source=before
needle='''    let transformed = multiply_lower_transpose(&mass.chol_lower, initial_position, mass.dimension);
    let identity = DiagonalMass::identity''';assert source.count(needle)==1
source=source.replace(needle,'''    crate::recycling::set_dense_lower(&mass.chol_lower);
'''+needle)
p.write_text(source)
(study/'RECYCLING-COORDINATE.patch').write_text(''.join(difflib.unified_diff(before.splitlines(True),source.splitlines(True),fromfile='src/walnutpie.rs',tofile='research/src/walnutpie.rs',n=0)))
p=study/'recycling_runner/Cargo.toml';p.write_text(p.read_text().replace('recycling_source01','recycling_source02'))
p=study/'recycling_runner/src/main.rs';source=p.read_text();source+='''
#[cfg(test)]
mod coordinate_tests {
    #[test]
    fn exact_dense_restore_before_nonlinear_features() {
        use owalnuts::recycling::{reset,set_dense_lower,features};
        reset(true);set_dense_lower(&[2.,0.,1.,3.]);
        // z=L^T*x for x=(1,-2), so z=(0,-6).
        assert_eq!(features(&[0.,-6.]),vec![1.,-2.,1.,4.,0.,1.,0.,0.]);
        reset(false);assert!(features(&[0.,-6.]).is_empty());
    }
}
''';p.write_text(source)
p=study/'build_recycling.py';(study/'build_recycling_corrected.py').write_text(p.read_text().replace('recycling_build02','recycling_build03'))
p=study/'test_recycling.py';(study/'test_recycling_corrected.py').write_text(p.read_text().replace('recycling_build02','recycling_build03').replace('recycling_test01','recycling_test02').replace('recycling_source01','recycling_source02'))
