import json,sys
from pathlib import Path
study=Path(__file__).resolve().parent;root=study/'local_recovery/compat01';root.mkdir(exist_ok=False)
sys.path.insert(0,str(study/'local_recovery/inputs'))
from resource_monitor import execute
r=execute([sys.executable,str(study/'local_compat_worker.py'),str(root)],str(study),180,root,2*1024**3,64*1024**2,root/'worker.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
