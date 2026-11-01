import json
import os
import sys
from pathlib import Path
from resource_monitor import execute
root=Path(__file__).resolve().parent
os.environ['XDG_CACHE_HOME']=str(root/'preflight-cache')
s=execute([sys.executable,str(root/'prepare.py')],str(root),300,root,2*1024**3,16*1024**2,root/'preflight.log',output_scan_interval=2)
(root/'PREFLIGHT-SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s),flush=True)
