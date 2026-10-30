import json,shutil,sys
from pathlib import Path
study=Path(__file__).resolve().parent;local=study/'local_recovery';root=local/'counter01';root.mkdir(exist_ok=False)
assert shutil.disk_usage(root).free>=1024**3
sys.path.insert(0,str(local/'inputs'))
from resource_monitor import execute
r=execute([sys.executable,str(study/'test_counted_native.py'),str(root)],str(root),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
