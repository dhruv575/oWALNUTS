import json
import os
import sys
from pathlib import Path
from resource_monitor import execute
root=Path(__file__).resolve().parent
os.environ['XDG_CACHE_HOME']=str(root/'driver-cache')
s=execute([sys.executable,str(root/'campaign.py')],str(root),1200,root,16*1024**3,128*1024**2,root/'campaign.log',output_scan_interval=2)
(root/'CAMPAIGN-SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s),flush=True)
