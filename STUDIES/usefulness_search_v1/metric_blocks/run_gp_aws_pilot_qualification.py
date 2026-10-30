import json,sys
from pathlib import Path
base=Path('/home/ubuntu/lanes/gp-full-cost-20261030');sys.path.insert(0,str(base));from resource_monitor import execute
root=Path('/home/ubuntu/lanes/gp-aws-pilot-qualification-20261030');root.mkdir(exist_ok=False)
result=execute([sys.executable,'/home/ubuntu/qualify_gp_aws_pilots.py',str(base),str(root/'evidence')],str(base),180,root,2*1024**3,128*1024**2,root/'worker.log',output_scan_interval=2);(root/'SUPERVISION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
