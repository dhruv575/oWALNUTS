import json
import os
import sys
from pathlib import Path
from resource_monitor import execute
base=Path(__file__).resolve().parent
out=base/'terrain_supervision01';out.mkdir(exist_ok=False)
os.environ['XDG_CACHE_HOME']=str(out/'cache')
s=execute([sys.executable,str(base/'terrain_control.py')],str(base),300,base/'terrain_control01',
          2*1024**3,64*1024**2,out/'worker.log',output_scan_interval=2)
(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n')
print(json.dumps(s),flush=True)
