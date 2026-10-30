import hashlib,json,os,sys,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;project=study/'fixed_metric_runner';attempt=int(sys.argv[1]) if len(sys.argv)>1 else 1
assert attempt in [1,2]
root=study/'local_recovery'/f'fixed_metric_build{attempt:02d}';root.mkdir(exist_ok=False)
cache=Path(f'/home/dhruv/.cache/owalnuts/fixed-metric-runner{attempt:02d}');cache.mkdir(exist_ok=False)
assert shutil.disk_usage(cache).free>2*1024**3
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache)
sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
cmd=['/home/dhruv/.cargo/bin/cargo','build','--release','-j','1']+(['--offline'] if attempt==1 else [])
r=execute(cmd,str(project),300,cache,4*1024**3,1024**3,root/'worker.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
sources=[project/'Cargo.toml',project/'src/main.rs']
if (project/'Cargo.lock').exists():sources.append(project/'Cargo.lock')
out=dict(passed=r['exit_code']==0 and r['group_drained'],command=cmd,inputs={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
if out['passed']:
    binary=cache/'release/fixed-metric-research-runner';out.update(binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
(root/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
