import json,sys
from pathlib import Path
base=Path(__file__).resolve().parent;sys.path.insert(0,'/home/ubuntu/lanes/gp-full-cost-20261030')
from resource_monitor import execute
out=base/'scoring-supervision01';out.mkdir(exist_ok=False)
s=execute([sys.executable,str(base/'score_predictive.py')],str(base),300,base/'scoring01',4*1024**3,32*1024**2,out/'worker.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s))
