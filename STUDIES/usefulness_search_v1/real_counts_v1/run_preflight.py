import json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030');from resource_monitor import execute
assert __import__('shutil').disk_usage(base).free>1024**3
r=execute([sys.executable,str(base/'preflight.py')],str(base),300,base,3*1024**3,128*1024**2,base/'worker.log',output_scan_interval=2);(base/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
