import json
import sys
from pathlib import Path
from resource_monitor import execute
base=Path(__file__).resolve().parent
out=base/'cheap_supervision01';out.mkdir(exist_ok=False)
s=execute([sys.executable,str(base/'cheap_controls.py')],str(base),120,base/'cheap_controls01',
          1024**3,16*1024**2,out/'worker.log',output_scan_interval=2)
(out/'SUPERVISION.json').write_text(json.dumps(s,indent=2)+'\n');print(json.dumps(s),flush=True)
