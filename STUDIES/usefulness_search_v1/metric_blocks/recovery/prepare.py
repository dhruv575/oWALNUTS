import hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work/audit');old=Path('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work/reconsider');source=root/'source';source.mkdir(exist_ok=False)
assert shutil.disk_usage('/').free>=1024**3 and shutil.disk_usage('/home/ubuntu/lanes/metric-blocks-recovery-20261030/work').free>=4*1024**3
build=json.loads((old/'BUILD.json').read_text())
for p,h in build['hashes'].items():
 mapped=old/Path(p).relative_to('/dev/shm/reconsider-20261029');assert hashlib.sha256(mapped.read_bytes()).hexdigest()==h,p
for name in ['src','tests','integrations','STUDIES']:
 shutil.copytree(old/name,source/name,ignore=shutil.ignore_patterns('target','__pycache__','.git'))
for name in ['Cargo.toml','Cargo.lock']:shutil.copy2(old/name,source/name)
p=source/'src/walnutpie.rs';original=p.read_bytes();(root/'walnutpie-original.rs').write_bytes(original);s=original.decode()
needle='''    let Some(sigma) = cholesky(&precision, n_dim)
        .and_then(|factor| inverse_from_cholesky(&factor, n_dim))'''
assert s.count(needle)==1
log='''    eprintln!("METRIC_AUDIT window={} transition={} dim={} r2={:?} cxx={:?} b={:?} precision={:?}", window_index, transition, n_dim, r2, cxx, b, precision);
'''
s=s.replace(needle,log+needle);p.write_text(s)
inputs={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in source.rglob('*') if x.is_file()};(root/'SOURCE-INPUTS.json').write_text(json.dumps(inputs,indent=2)+'\n')
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
folder=root/'build';folder.mkdir();study=source/'STUDIES/metric_autoselect_confirmation_v1';r=execute(['/home/ubuntu/.cargo/bin/cargo','build','--release','--offline','--locked','--bin','pdb','-j','4'],str(study),300,folder,4*1024**3,64*1024**2,folder/'worker.log',output_scan_interval=2)
binary=study/'target/release/pdb';r['binary_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest() if binary.exists() else None;r['inputs_unchanged']=all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in inputs.items());(root/'BUILD.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));assert r['exit_code']==0 and r['group_drained'] and r['inputs_unchanged']
