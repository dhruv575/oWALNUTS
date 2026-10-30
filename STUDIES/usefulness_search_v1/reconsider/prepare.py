import hashlib,json,subprocess
from pathlib import Path
root=Path('/dev/shm/reconsider-20261029');study=root/'STUDIES/metric_autoselect_confirmation_v1';p=study/'src/bin/pdb.rs'
s=p.read_text();old='''DenseAutoSelectConfig::hessian_fit(
                        SELECT_WINDOW,
                        THRESHOLD,
                        MIN_LINEARITY,
                    )?'''
assert s.count(old)==1
s=s.replace(old,'auto_config(arm)?').replace('"auto" => (','"auto" | "reconsider" => (')
s=s.replace('const SELECT_WINDOW: usize = 2;','''fn auto_config(arm: &str) -> Result<DenseAutoSelectConfig, Box<dyn Error>> {
    let window = env::var("STUDY_SELECT_WINDOW").unwrap_or_else(|_| "2".into()).parse()?;
    let config = DenseAutoSelectConfig::hessian_fit(window, THRESHOLD, MIN_LINEARITY)?;
    Ok(if arm == "reconsider" { config.with_reconsideration(3)? } else { config })
}''');p.write_text(s)
with (root/'build.log').open('xb') as f:
 r=subprocess.run(['timeout','300','/home/ubuntu/.cargo/bin/cargo','build','--release','--offline','--locked','--bin','pdb','-j','4'],cwd=study,stdout=f,stderr=subprocess.STDOUT)
paths=[p,root/'src/walnutpie.rs',root/'tests/metric_autoselect_hessian.rs',Path(__file__)]
if r.returncode==0:paths.append(study/'target/release/pdb')
(root/'BUILD.json').write_text(json.dumps(dict(exit_code=r.returncode,hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),indent=2)+'\n')
raise SystemExit(r.returncode)
