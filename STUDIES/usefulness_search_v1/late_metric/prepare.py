from pathlib import Path
import subprocess,hashlib,json
root=Path('/dev/shm/late-metric-20261029')
study=root/'STUDIES/metric_autoselect_confirmation_v1'
p=study/'src/bin/pdb.rs';s=p.read_text()
old='const SELECT_WINDOW: usize = 2;'
assert s.count(old)==1
s=s.replace(old,'fn select_window() -> usize { std::env::var("STUDY_SELECT_WINDOW").unwrap_or_else(|_| "2".into()).parse().expect("selection window") }')
s=s.replace('SELECT_WINDOW','select_window()');p.write_text(s)
with (root/'build.log').open('xb') as f:
 r=subprocess.run(['timeout','300','/home/ubuntu/.cargo/bin/cargo','build','--release','--locked','--offline','--bin','pdb','-j','4'],cwd=study,stdout=f,stderr=subprocess.STDOUT)
binary=study/'target/release/pdb'
record=dict(build_exit=r.returncode,source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_archive_sha256=hashlib.sha256(Path('/dev/shm/late-metric-source.tar').read_bytes()).hexdigest())
if binary.exists():record['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
(root/'BUILD.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
raise SystemExit(r.returncode)
