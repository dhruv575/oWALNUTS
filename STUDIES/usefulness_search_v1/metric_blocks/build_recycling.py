import hashlib,json,os,sys,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/recycling_build02';root.mkdir(exist_ok=False)
cache=Path('/home/dhruv/.cache/owalnuts/recycling01');cache.mkdir(exist_ok=True);assert shutil.disk_usage(cache).free>2*1024**3
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache);sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
lock=execute(['cargo','generate-lockfile','--offline'],str(study/'recycling_runner'),60,cache,1024**3,1024**3,root/'lock.log',output_scan_interval=2)
assert lock['exit_code']==0 and lock['group_drained']
cmd=['cargo','build','--release','--offline','--locked','-j','1'];r=execute(cmd,str(study/'recycling_runner'),300,cache,4*1024**3,1024**3,root/'build.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
test=execute(['cargo','test','--release','--offline','--locked','-j','1'],str(study/'recycling_runner'),180,cache,4*1024**3,1024**3,root/'test.log',output_scan_interval=2)
(root/'TEST-SUPERVISION.json').write_text(json.dumps(test,indent=2)+'\n');assert test['exit_code']==0 and test['group_drained']
binary=cache/'release/recycling-research-runner';(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),indent=2)+'\n')
