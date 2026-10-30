import json,shutil,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
assert shutil.disk_usage(base).free>1024**3
s=execute([sys.executable,str(base/'aws_preflight.py')],str(base),300,base,4*1024**3,128*1024**2,base/'worker.log',output_scan_interval=2);(base/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s))
