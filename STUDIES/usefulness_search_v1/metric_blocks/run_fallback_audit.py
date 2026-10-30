import json,shutil,sys
from pathlib import Path
root=Path(__file__).resolve().parent;out=root/'monitor';out.mkdir(exist_ok=False)
sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source')
from resource_monitor import execute
r=execute([sys.executable,str(root/'audit_fallback.py')],str(root),180,out,2*1024**3,
    64*1024**2,out/'worker.log',output_scan_interval=2)
(root/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n')
shutil.copytree(root,'/home/ubuntu/lanes/metric-blocks-recovery-20261030/evidence/fallbackaudit01')
print(json.dumps(r))

