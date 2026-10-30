import json,os,sys,hashlib,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;repo=study.parents[2];root=study/'local_recovery/dense_metric_preflight01';root.mkdir(exist_ok=False)
cache=Path('/home/dhruv/.cache/owalnuts/dense-metric-preflight01');cache.mkdir(exist_ok=False)
assert shutil.disk_usage(cache).free>2*1024**3 and shutil.disk_usage(root).free>1024**3
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache)
sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
sources=[repo/'Cargo.toml',repo/'Cargo.lock',repo/'tests/public_facade.rs',repo/'src/walnutpie.rs',repo/'src/sampler.rs']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
cmd=['/home/dhruv/.cargo/bin/cargo','test','--locked','--offline','--features','research','--test','public_facade','dense_','-j','1']
r=execute(cmd,str(repo),300,cache,4*1024**3,1024**3,root/'worker.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
out=dict(passed=r['exit_code']==0 and r['group_drained'],command=cmd,inputs=hashes,unchanged=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items()),cache=str(cache),scope='Existing compiled dense-metric tests, not new metric-transfer or posterior validation.')
(root/'SUMMARY.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out));assert out['passed'] and out['unchanged']
