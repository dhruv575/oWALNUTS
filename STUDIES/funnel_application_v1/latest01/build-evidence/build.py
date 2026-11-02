import os,sys,json
from pathlib import Path
sys.path.insert(0,'/home/ubuntu/lanes/funnel-application-20261101')
from resource_monitor import execute
p=Path(__file__).resolve().parent
os.environ.update(CARGO_HOME=str(p/'cargo'),CARGO_TARGET_DIR=str(p/'target'),TMPDIR=str(p),PYO3_PYTHON='/home/ubuntu/venv/bin/python',CARGO_BUILD_JOBS='4',RUSTUP_HOME='/home/ubuntu/.rustup')
r=execute(['/home/ubuntu/.cargo/bin/cargo','build','--release','--locked','--manifest-path',str(p/'integrations/python/Cargo.toml')],p,900,p,8*1024**3,3*1024**3,p/'build-online.log',output_scan_interval=10.)
(p/'BUILD-STATUS.json').write_text(json.dumps(r,indent=2))
