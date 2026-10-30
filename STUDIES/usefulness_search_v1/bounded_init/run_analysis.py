import json,sys
from pathlib import Path
root=Path('/dev/shm/bounded-init-20261030');assert (root/'run01/FINAL.json').exists();sys.path.insert(0,'/home/ubuntu/lanes/pharma-ode-logforecast-20261029/source');from resource_monitor import execute
out=root/'analysis-supervision';out.mkdir(exist_ok=False);r=execute([sys.executable,str(root/'analyze.py')],str(root),300,out,2*1024**3,16*1024**2,out/'analysis.log',output_scan_interval=2);(out/'SUPERVISION.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
