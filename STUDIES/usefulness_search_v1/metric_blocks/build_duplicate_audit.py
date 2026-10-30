import hashlib,json,os,sys,shutil
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/duplicate_audit_build01';root.mkdir(exist_ok=False)
cache=Path('/home/dhruv/.cache/owalnuts/duplicate-audit01');cache.mkdir(exist_ok=False);assert shutil.disk_usage(cache).free>2*1024**3
os.environ['PATH']='/home/dhruv/.cargo/bin:'+os.environ['PATH'];os.environ['CARGO_TARGET_DIR']=str(cache);sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
rows=[]
for action in ['test','build']:
    cmd=['cargo',action,'--release','--offline','--locked','-j','1'];r=execute(cmd,str(study/'duplicate_eval_runner'),300,cache,4*1024**3,1024**3,root/(action+'.log'),output_scan_interval=2)
    (root/(action+'-SUPERVISION.json')).write_text(json.dumps(r,indent=2)+'\n');rows.append(r);assert r['exit_code']==0 and r['group_drained']
binary=cache/'release/duplicate-eval-research-runner'
(root/'SUMMARY.json').write_text(json.dumps(dict(passed=True,binary=str(binary),binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()),indent=2)+'\n')
