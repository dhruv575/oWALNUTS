import hashlib,json,os,sys,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/work_profile_build01';root.mkdir(exist_ok=False)
cache=Path('/home/dhruv/.cache/owalnuts/work-profile01');cache.mkdir(exist_ok=False);assert shutil.disk_usage(cache).free>2*1024**3
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache);sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
cmd=['cargo','build','--release','--offline','--locked','-j','1'];r=execute(cmd,str(study/'work_profile_runner'),300,cache,4*1024**3,1024**3,root/'build.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');assert r['exit_code']==0 and r['group_drained']
binary=cache/'release/work-profile-research-runner';(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),indent=2)+'\n')
